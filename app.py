import customtkinter as ctk
import pyodbc
import json
import os
import threading
from tkinter import messagebox

# ตั้งค่าธีม
ctk.set_appearance_mode("Dark")  
ctk.set_default_color_theme("blue") 

CONFIG_FILE = "db_config.json"

class SyncAlertPopup(ctk.CTkToplevel):
    def __init__(self, parent, missing_seqs, table_name, stp_callback):
        super().__init__(parent)
        self.title("🚨 Sync Alert!")
        self.geometry("400x320")
        
        # ทำให้ popup เด้งทับหน้าต่างหลักและห้ามกดหน้าต่างหลัก
        self.grab_set() 
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        label_title = ctk.CTkLabel(self, text="⚠️ พบข้อมูลตกหล่น!", font=("Arial", 18, "bold"), text_color="yellow")
        label_title.grid(row=0, column=0, pady=(20, 5), sticky="ew")

        # แสดงรายการ Sequence
        missing_list = sorted(list(missing_seqs))
        msg = f"ตาราง: {table_name}\n"
        msg += f"จำนวน {len(missing_list)} รายการที่ฝั่ง STG หายไป:\n\n"
        
        # แสดงแค่ 10 ตัวแรกถ้ามีเยอะเกินไป
        display_list = missing_list[:10]
        msg += ", ".join(map(str, display_list))
        if len(missing_list) > 10:
            msg += f" ... (และอีก {len(missing_list)-10} รายการ)"

        text_box = ctk.CTkTextbox(self, width=350, height=120, state="disabled")
        text_box.grid(row=1, column=0, pady=10)
        text_box.configure(state="normal")
        text_box.insert("1.0", msg)
        text_box.configure(state="disabled")

        label_question = ctk.CTkLabel(self, text="ต้องการรัน STP ตอนนี้เลยไหม?", font=("Arial", 12))
        label_question.grid(row=2, column=0, pady=(5, 15))

        # ปุ่มกด
        frame_btns = ctk.CTkFrame(self, fg_color="transparent")
        frame_btns.grid(row=3, column=0, pady=10)
        
        btn_stp = ctk.CTkButton(frame_btns, text="ใช่, รัน STP", fg_color="#d9534f", hover_color="#c9302c", 
                               command=lambda: [stp_callback(), self.destroy()])
        btn_stp.pack(side="left", padx=10)

        btn_cancel = ctk.CTkButton(frame_btns, text="ยังก่อน", ctk_color="gray", command=self.destroy)
        btn_cancel.pack(side="left", padx=10)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("TPDB Sync Monitor Tools")
        self.geometry("600x650")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # -- Sidebar --
        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Tools Menu", font=("Arial", 16, "bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.btn_monitor_nav = ctk.CTkButton(self.sidebar_frame, text="Monitor Status", command=self.show_monitor)
        self.btn_monitor_nav.grid(row=1, column=0, padx=20, pady=10)
        
        self.btn_config_nav = ctk.CTkButton(self.sidebar_frame, text="DB Config", command=self.show_config)
        self.btn_config_nav.grid(row=2, column=0, padx=20, pady=10)

        self.tabview_main = ctk.CTkTabview(self)
        self.tabview_main.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        # สร้าง Tab
        self.monitor_tab = self.tabview_main.add("Monitor")
        self.config_tab = self.tabview_main.add("DB Configuration")
        
        # ซ่อน Tab selector
        self.tabview_main._segmented_button.grid_forget()

        self.setup_config_tab()
        self.setup_monitor_tab()
        
        self.load_config()
        self.show_monitor() # เริ่มต้นที่หน้า Monitor

    def setup_config_tab(self):
        label = ctk.CTkLabel(self.config_tab, text="กรอกข้อมูลเชื่อมต่อ Database", font=("Arial", 16, "bold"))
        label.pack(pady=10)

        self.entries = {}
        
        # ฟังก์ชันช่วยสร้าง Entry box
        def create_entry(parent, label_text, default_val=""):
            frame = ctk.CTkFrame(parent, fg_color="transparent")
            frame.pack(fill="x", padx=20, pady=5)
            ctk.CTkLabel(frame, text=label_text, width=120, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(frame, width=250)
            entry.insert(0, default_val)
            entry.pack(side="left")
            return entry

        create_entry(self.config_tab, "[ CENTRAL DB ]", "").configure(font=("Arial", 12, "bold"), text_color="cyan", state="disabled")
        self.entries['central_server'] = create_entry(self.config_tab, "IP/Server Name:", "10.3.129.1")
        self.entries['central_db'] = create_entry(self.config_tab, "Database Name:", "TPCentralDB")
        self.entries['central_user'] = create_entry(self.config_tab, "UID:")
        self.entries['central_pwd'] = create_entry(self.config_tab, "Password:")
        self.entries['central_pwd'].configure(show="*")

        ctk.CTkLabel(self.config_tab, text="").pack(pady=5) # Spacing

        create_entry(self.config_tab, "[ STG DB ]", "").configure(font=("Arial", 12, "bold"), text_color="cyan", state="disabled")
        self.entries['stg_server'] = create_entry(self.config_tab, "Server Name:", "ADAPOSSTG")
        self.entries['stg_db'] = create_entry(self.config_tab, "Database Name:", "ADAPOSSTG")
        self.entries['stg_user'] = create_entry(self.config_tab, "UID:")
        self.entries['stg_pwd'] = create_entry(self.config_tab, "Password:")
        self.entries['stg_pwd'].configure(show="*")

        ctk.CTkLabel(self.config_tab, text="").pack(pady=5) # Spacing
        
        # ตั้งค่าเพิ่มเติม
        create_entry(self.config_tab, "[ EXTRA ]", "").configure(font=("Arial", 12, "bold"), text_color="cyan", state="disabled")
        self.entries['table_name'] = create_entry(self.config_tab, "Table to monitor:", "Item")
        self.entries['stp_name'] = create_entry(self.config_tab, "Fix STP Name:", "dbo.stp_FixItemSync")

        btn_save = ctk.CTkButton(self.config_tab, text="บันทึกการตั้งค่า", command=self.save_config)
        btn_save.pack(pady=30)

    def setup_monitor_tab(self):
        self.status_label = ctk.CTkLabel(self.monitor_tab, text="🟢 ข้อมูลตรงกันปกติ", 
                                      font=("Arial", 22, "bold"), text_color="green", pady=20)
        self.status_label.pack()

        # ส่วนแสดงรายละเอียด log (ถ้าต้องการในอนาคต)
        self.monitor_text = ctk.CTkTextbox(self.monitor_tab, width=500, height=250, state="disabled", font=("Courier", 11))
        self.monitor_text.pack(pady=20)

        # แผงปุ่ม
        btn_frame = ctk.CTkFrame(self.monitor_tab, fg_color="transparent")
        btn_frame.pack(pady=10)

        self.btn_check = ctk.CTkButton(btn_frame, text="🔍 เช็กสถานะเดี๋ยวนี้", command=self.check_sync_action)
        self.btn_check.pack(side="left", padx=15)
        
        self.btn_run_stp = ctk.CTkButton(btn_frame, text="🛠️ รัน STP ทันที", 
                                         fg_color="#f0ad4e", hover_color="#ec971f", text_color="black",
                                         command=self.execute_stp_action)
        self.btn_run_stp.pack(side="left", padx=15)

    # -- Logic --
    def show_monitor(self): self.tabview_main.set("Monitor")
    def show_config(self): self.tabview_main.set("DB Configuration")

    def save_config(self):
        config_data = {key: entry.get() for key, entry in self.entries.items()}
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_data, f, indent=4)
            messagebox.showinfo("Success", "บันทึกการตั้งค่าเรียบร้อยแล้ว")
        except Exception as e:
            messagebox.showerror("Error", f"ไม่สามารถบันทึกไฟล์ได้: {e}")

    def load_config(self):
        if not os.path.exists(CONFIG_FILE): return
        try:
            with open(CONFIG_FILE, 'r') as f:
                config_data = json.load(f)
            for key, val in config_data.items():
                if key in self.entries:
                    self.entries[key].delete(0, "end")
                    self.entries[key].insert(0, val)
        except: pass

    def get_conn_str(self, prefix):
        return f"DRIVER={{SQL Server}};SERVER={self.entries[prefix+'_server'].get()};DATABASE={self.entries[prefix+'_db'].get()};UID={self.entries[prefix+'_user'].get()};PWD={self.entries[prefix+'_pwd'].get()}"

    def get_sequences(self, conn_str):
        sequences = set()
        try:
            conn = pyodbc.connect(conn_str, timeout=10)
            cursor = conn.cursor()
            table_name = self.entries['table_name'].get()
            query = f"SELECT TOP 100 ISequenceNumber FROM sysTPDotnetLog WHERE szTableName='{table_name}' ORDER BY ITimeStamp DESC"
            cursor.execute(query)
            for row in cursor.fetchall(): sequences.add(row.ISequenceNumber)
            conn.close()
        except pyodbc.Error as ex:
             return None, str(ex)
        return sequences, None

    def check_sync_action(self):
        """เรียกเช็ก sync โดยใช้ thread เพื่อไม่ให้ UI ค้าง"""
        self.btn_check.configure(state="disabled", text="กำลังตรวจสอบ...")
        self.update_log_display(">>> กำลังตรวจสอบ Database...\n")
        threading.Thread(target=self.check_sync_thread).start()

    def check_sync_thread(self):
        central_seqs, c_err = self.get_sequences(self.get_conn_str('central'))
        stg_seqs, s_err = self.get_sequences(self.get_conn_str('stg'))
        
        # ปรับปรุง UI กลับมา (ต้องทำผ่าน after ของ tkinter)
        self.after(0, self.check_sync_finished, central_seqs, c_err, stg_seqs, s_err)

    def check_sync_finished(self, central_seqs, c_err, stg_seqs, s_err):
        self.btn_check.configure(state="normal", text="🔍 เช็กสถานะเดี๋ยวนี้")
        
        if c_err or s_err:
            self.status_label.configure(text="🔴 เชื่อมต่อ DB ผิดพลาด", text_color="red")
            self.update_log_display(f"ERROR (Central): {c_err}\nERROR (STG): {s_err}\n")
            return

        # เทียบข้อมูล
        missing_seqs = central_seqs - stg_seqs
        table_monitored = self.entries['table_name'].get()
        
        self.update_log_display(f"- Central Seq Count: {len(central_seqs)}\n")
        self.update_log_display(f"- STG Seq Count: {len(stg_seqs)}\n")

        if missing_seqs:
            self.status_label.configure(text=f"🔴 {table_monitored} ข้อมูลตกหล่น!", text_color="#d9534f")
            # โชว์ pop-up
            SyncAlertPopup(self, missing_seqs, table_monitored, self.execute_stp_action)
        else:
            self.status_label.configure(text=f"🟢 {table_monitored} ซิงค์ปกติ", text_color="green")
            self.update_log_display(">>> OK, Data Sync perfectly.\n")

    def execute_stp_action(self):
        stp_name = self.entries['stp_name'].get()
        user_choice = messagebox.askyesno("Confirm Execute", f"คุณต้องการรัน Stored Procedure '{stp_name}' ตอนนี้หรือไม่?")
        if not user_choice: return

        self.btn_run_stp.configure(state="disabled", text="กำลังรัน STP...")
        self.update_log_display(f">>> กำลัง Execute Stored Procedure: {stp_name}...\n")
        threading.Thread(target=self.execute_stp_thread, args=(stp_name,)).start()

    def execute_stp_thread(self, stp_name):
        stg_conn_str = self.get_conn_str('stg')
        err = None
        try:
            # รัน STP ในฝั่ง STG
            conn = pyodbc.connect(stg_conn_str, timeout=30, autocommit=True)
            cursor = conn.cursor()
            cursor.execute(f"EXEC {stp_name}")
            conn.close()
        except Exception as e:
            err = str(e)

        self.after(0, self.execute_stp_finished, stp_name, err)

    def execute_stp_finished(self, stp_name, err):
        self.btn_run_stp.configure(state="normal", text="🛠️ รัน STP ทันที")
        if err:
            self.update_log_display(f"ERROR running STP: {err}\n")
            messagebox.showerror("Error", f"การ Execute STP '{stp_name}' ล้มเหลว:\n{err}")
        else:
            self.update_log_display(f">>> STP Execute Successfully.\n")
            messagebox.showinfo("Success", f"Execute Stored Procedure '{stp_name}' สำเร็จ\nกรุณากด 'เช็กสถานะ' เพื่อตรวจสอบอีกครั้ง")

    def update_log_display(self, text):
        self.monitor_text.configure(state="normal")
        self.monitor_text.insert("end", text)
        self.monitor_text.configure(state="disabled")
        self.monitor_text.see("end")

if __name__ == "__main__":
    app = App()
    app.mainloop()
