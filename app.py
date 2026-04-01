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
    def __init__(self, parent, missing_seqs, monitor_name, stp_callback):
        super().__init__(parent)
        self.title("🚨 Sync Alert!")
        self.geometry("450x350")
        self.grab_set() 
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        label_title = ctk.CTkLabel(self, text="⚠️ พบข้อมูลตกหล่น!", font=("Arial", 18, "bold"), text_color="yellow")
        label_title.grid(row=0, column=0, pady=(20, 5), sticky="ew")

        missing_list = sorted(list(missing_seqs))
        msg = f"Monitor Task: {monitor_name}\n"
        msg += f"จำนวน {len(missing_list)} รายการที่ฝั่ง STG ไม่มี:\n\n"
        
        display_list = missing_list[:20]
        msg += ", ".join(map(str, display_list))
        if len(missing_list) > 20:
            msg += f"\n... (และอีก {len(missing_list)-20} รายการ)"

        text_box = ctk.CTkTextbox(self, width=400, height=150, state="disabled")
        text_box.grid(row=1, column=0, pady=10)
        text_box.configure(state="normal")
        text_box.insert("1.0", msg)
        text_box.configure(state="disabled")

        label_question = ctk.CTkLabel(self, text="ต้องการรัน Stored Procedure ตอนนี้เลยไหม?", font=("Arial", 12))
        label_question.grid(row=2, column=0, pady=(5, 15))

        frame_btns = ctk.CTkFrame(self, fg_color="transparent")
        frame_btns.grid(row=3, column=0, pady=10)
        
        btn_stp = ctk.CTkButton(frame_btns, text="ใช่, รัน STP", fg_color="#d9534f", hover_color="#c9302c", 
                               command=lambda: [stp_callback(), self.destroy()])
        btn_stp.pack(side="left", padx=10)

        btn_cancel = ctk.CTkButton(frame_btns, text="ยังก่อน", fg_color="gray", command=self.destroy)
        btn_cancel.pack(side="left", padx=10)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Dynamic DB Sync Monitor")
        self.geometry("800x750")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # -- Sidebar --
        self.sidebar_frame = ctk.CTkFrame(self, width=150, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Tools Menu", font=("Arial", 16, "bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.btn_monitor_nav = ctk.CTkButton(self.sidebar_frame, text="Monitor Status", command=self.show_monitor)
        self.btn_monitor_nav.grid(row=1, column=0, padx=20, pady=10)
        
        self.btn_config_nav = ctk.CTkButton(self.sidebar_frame, text="Configuration", command=self.show_config)
        self.btn_config_nav.grid(row=2, column=0, padx=20, pady=10)

        self.tabview_main = ctk.CTkTabview(self)
        self.tabview_main.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        self.monitor_tab = self.tabview_main.add("Monitor")
        self.config_tab = self.tabview_main.add("Configuration")
        self.tabview_main._segmented_button.grid_forget()

        # สร้างตัวแปรเก็บค่า
        self.entries = {}
        self.textboxes = {}

        self.setup_config_tab()
        self.setup_monitor_tab()
        
        self.load_config()
        self.show_monitor() 

    def setup_config_tab(self):
        # สร้าง Scrollable Frame สำหรับหน้า Config เพราะข้อมูลเริ่มเยอะ
        scroll_frame = ctk.CTkScrollableFrame(self.config_tab, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True)

        title_lbl = ctk.CTkLabel(scroll_frame, text="ตั้งค่า Database & Query", font=("Arial", 16, "bold"))
        title_lbl.grid(row=0, column=0, columnspan=2, pady=10)

        # --- Helper Functions สร้าง UI ---
        row_idx = 1
        def add_section_title(text):
            nonlocal row_idx
            lbl = ctk.CTkLabel(scroll_frame, text=text, font=("Arial", 14, "bold"), text_color="#5bc0de")
            lbl.grid(row=row_idx, column=0, columnspan=2, pady=(15, 5), sticky="w")
            row_idx += 1

        def add_entry(key, label_text, default_val="", is_pwd=False):
            nonlocal row_idx
            ctk.CTkLabel(scroll_frame, text=label_text, width=120, anchor="w").grid(row=row_idx, column=0, padx=10, pady=5, sticky="w")
            entry = ctk.CTkEntry(scroll_frame, width=250)
            if is_pwd: entry.configure(show="*")
            entry.insert(0, default_val)
            entry.grid(row=row_idx, column=1, padx=10, pady=5, sticky="w")
            self.entries[key] = entry
            row_idx += 1

        def add_textbox(key, label_text, default_val="", height=60):
            nonlocal row_idx
            ctk.CTkLabel(scroll_frame, text=label_text, width=120, anchor="nw").grid(row=row_idx, column=0, padx=10, pady=5, sticky="nw")
            textbox = ctk.CTkTextbox(scroll_frame, width=400, height=height)
            textbox.insert("1.0", default_val)
            textbox.grid(row=row_idx, column=1, padx=10, pady=5, sticky="w")
            self.textboxes[key] = textbox
            row_idx += 1

        def add_test_btn(text, command):
            nonlocal row_idx
            btn = ctk.CTkButton(scroll_frame, text=text, width=120, command=command, fg_color="#5cb85c", hover_color="#4cae4c")
            btn.grid(row=row_idx, column=1, padx=10, pady=5, sticky="w")
            row_idx += 1

        # --- CENTRAL DB ---
        add_section_title("[ CENTRAL DB ]")
        add_entry('central_server', "IP/Server Name:", "10.3.129.1")
        add_entry('central_db', "Database Name:", "TPCentralDB")
        add_entry('central_user', "UID:")
        add_entry('central_pwd', "Password:", is_pwd=True)
        default_cq = "SELECT TOP 100 ISequenceNumber\nFROM dbo.sysTPDotnetLog\nWHERE szTableName='Item'\nORDER BY ITimeStamp DESC"
        add_textbox('central_query', "Central Query\n(ดึง 1 คอลัมน์เพื่อเทียบ):", default_cq)
        add_test_btn("Test Central DB", lambda: self.test_connection('central'))

        # --- STG DB ---
        add_section_title("[ STG DB ]")
        add_entry('stg_server', "Server Name:", "ADAPOSSTG")
        add_entry('stg_db', "Database Name:", "ADAPOSSTG")
        add_entry('stg_user', "UID:")
        add_entry('stg_pwd', "Password:", is_pwd=True)
        default_sq = "SELECT TOP 100 ISequenceNumber\nFROM dbo.sysTPDotnetLog\nWHERE szTableName='Item'\nORDER BY ITimeStamp DESC"
        add_textbox('stg_query', "STG Query\n(ดึง 1 คอลัมน์เพื่อเทียบ):", default_sq)
        add_test_btn("Test STG DB", lambda: self.test_connection('stg'))

        # --- EXTRA ---
        add_section_title("[ EXTRA ACTION ]")
        add_entry('monitor_name', "Task Name:", "Item Table Monitor")
        add_entry('stp_name', "Fix STP Name:", "EXEC dbo.stp_FixItemSync")

        btn_save = ctk.CTkButton(scroll_frame, text="💾 บันทึกการตั้งค่า", command=self.save_config, width=200)
        btn_save.grid(row=row_idx, column=0, columnspan=2, pady=30)

    def setup_monitor_tab(self):
        self.status_label = ctk.CTkLabel(self.monitor_tab, text="เตรียมพร้อมตรวจสอบ", 
                                      font=("Arial", 22, "bold"), text_color="gray", pady=20)
        self.status_label.pack()

        self.monitor_text = ctk.CTkTextbox(self.monitor_tab, width=550, height=300, state="disabled", font=("Courier", 12))
        self.monitor_text.pack(pady=20, fill="both", expand=True)

        btn_frame = ctk.CTkFrame(self.monitor_tab, fg_color="transparent")
        btn_frame.pack(pady=10)

        self.btn_check = ctk.CTkButton(btn_frame, text="🔍 เริ่มตรวจสอบ (Compare)", command=self.check_sync_action)
        self.btn_check.pack(side="left", padx=15)
        
        self.btn_run_stp = ctk.CTkButton(btn_frame, text="🛠️ บังคับรัน STP", 
                                         fg_color="#f0ad4e", hover_color="#ec971f", text_color="black",
                                         command=self.execute_stp_action)
        self.btn_run_stp.pack(side="left", padx=15)

    # -- Logic --
    def show_monitor(self): self.tabview_main.set("Monitor")
    def show_config(self): self.tabview_main.set("Configuration")

    def get_conn_str(self, prefix):
        return f"DRIVER={{SQL Server}};SERVER={self.entries[prefix+'_server'].get()};DATABASE={self.entries[prefix+'_db'].get()};UID={self.entries[prefix+'_user'].get()};PWD={self.entries[prefix+'_pwd'].get()}"

    def save_config(self):
        config_data = {key: entry.get() for key, entry in self.entries.items()}
        # เพิ่มข้อมูลจาก Textbox
        for key, tb in self.textboxes.items():
            config_data[key] = tb.get("1.0", "end-1c")

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
                elif key in self.textboxes:
                    self.textboxes[key].delete("1.0", "end")
                    self.textboxes[key].insert("1.0", val)
        except: pass

    def test_connection(self, db_prefix):
        conn_str = self.get_conn_str(db_prefix)
        db_name = self.entries[db_prefix+'_db'].get()
        try:
            conn = pyodbc.connect(conn_str, timeout=5)
            conn.close()
            messagebox.showinfo("Success", f"เชื่อมต่อ {db_name} สำเร็จ! 🟢")
        except Exception as e:
            messagebox.showerror("Failed", f"เชื่อมต่อ {db_name} ล้มเหลว 🔴\n\nDetail:\n{e}")

    def get_data_from_query(self, conn_str, query):
        """รับ string SQL มา execute แล้วคืนค่าเป็น Set ของคอลัมน์แรก"""
        result_set = set()
        try:
            conn = pyodbc.connect(conn_str, timeout=15)
            cursor = conn.cursor()
            cursor.execute(query)
            
            # ดึงเฉพาะข้อมูลคอลัมน์แรก (index 0) มาใส่ Set
            for row in cursor.fetchall(): 
                result_set.add(row[0]) 
                
            conn.close()
        except Exception as ex:
             return None, str(ex)
        return result_set, None

    def check_sync_action(self):
        self.btn_check.configure(state="disabled", text="กำลังตรวจสอบ...")
        self.update_log_display(f"--- เริ่มต้นการตรวจสอบ {self.entries['monitor_name'].get()} ---\n")
        threading.Thread(target=self.check_sync_thread).start()

    def check_sync_thread(self):
        c_query = self.textboxes['central_query'].get("1.0", "end-1c")
        s_query = self.textboxes['stg_query'].get("1.0", "end-1c")

        self.update_log_display(">>> Querying Central DB...\n")
        central_data, c_err = self.get_data_from_query(self.get_conn_str('central'), c_query)
        
        self.update_log_display(">>> Querying STG DB...\n")
        stg_data, s_err = self.get_data_from_query(self.get_conn_str('stg'), s_query)
        
        self.after(0, self.check_sync_finished, central_data, c_err, stg_data, s_err)

    def check_sync_finished(self, central_data, c_err, stg_data, s_err):
        self.btn_check.configure(state="normal", text="🔍 เริ่มตรวจสอบ (Compare)")
        
        if c_err or s_err:
            self.status_label.configure(text="🔴 พบข้อผิดพลาด", text_color="red")
            if c_err: self.update_log_display(f"[Central Error] {c_err}\n")
            if s_err: self.update_log_display(f"[STG Error] {s_err}\n")
            return

        # Central ตั้ง ลบด้วย STG หาตัวที่หายไป
        missing_data = central_data - stg_data
        monitor_name = self.entries['monitor_name'].get()
        
        self.update_log_display(f"- Central Result Row(s): {len(central_data)}\n")
        self.update_log_display(f"- STG Result Row(s): {len(stg_data)}\n")

        if missing_data:
            self.status_label.configure(text=f"🔴 พบข้อมูลตกหล่น!", text_color="#d9534f")
            self.update_log_display(f"!!! ตรวจพบความแตกต่าง {len(missing_data)} รายการ\n")
            SyncAlertPopup(self, missing_data, monitor_name, self.execute_stp_action)
        else:
            self.status_label.configure(text=f"🟢 ข้อมูลตรงกัน", text_color="green")
            self.update_log_display(">>> เยี่ยม! ไม่พบข้อมูลตกหล่นจาก Query ที่กำหนด\n")

    def execute_stp_action(self):
        stp_cmd = self.entries['stp_name'].get()
        if not stp_cmd.strip():
            messagebox.showwarning("Warning", "ยังไม่ได้กำหนดคำสั่งรัน STP ในหน้า Config")
            return

        user_choice = messagebox.askyesno("Confirm Execute", f"ยืนยันการรันคำสั่ง:\n{stp_cmd}\nที่ฐานข้อมูล STG หรือไม่?")
        if not user_choice: return

        self.btn_run_stp.configure(state="disabled")
        self.update_log_display(f"\n>>> Executing Command: {stp_cmd}\n")
        threading.Thread(target=self.execute_stp_thread, args=(stp_cmd,)).start()

    def execute_stp_thread(self, stp_cmd):
        stg_conn_str = self.get_conn_str('stg')
        err = None
        try:
            conn = pyodbc.connect(stg_conn_str, timeout=60, autocommit=True)
            cursor = conn.cursor()
            cursor.execute(stp_cmd)
            conn.close()
        except Exception as e:
            err = str(e)

        self.after(0, self.execute_stp_finished, stp_cmd, err)

    def execute_stp_finished(self, stp_cmd, err):
        self.btn_run_stp.configure(state="normal")
        if err:
            self.update_log_display(f"[Execute Error] {err}\n")
            messagebox.showerror("Error", f"Execution Failed:\n{err}")
        else:
            self.update_log_display(f">>> Command Executed Successfully.\n")
            messagebox.showinfo("Success", "รันคำสั่งสำเร็จ! กรุณากดตรวจสอบอีกครั้ง")

    def update_log_display(self, text):
        self.monitor_text.configure(state="normal")
        self.monitor_text.insert("end", text)
        self.monitor_text.configure(state="disabled")
        self.monitor_text.see("end")

if __name__ == "__main__":
    app = App()
    app.mainloop()
