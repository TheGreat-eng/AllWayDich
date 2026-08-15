import difflib
import customtkinter as ctk
from tkinter import filedialog, messagebox
from core.text_helpers import read_file_content_safely

class DiffTab(ctk.CTkFrame):
	def __init__(self, parent, main_app):
		super().__init__(parent)
		self.main_app = main_app
		self._build_ui()

	def _build_ui(self):
		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)

		# Controls Bar
		frame_top = ctk.CTkFrame(self)
		frame_top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

		ctk.CTkLabel(frame_top, text="🔍 So Sánh Đối Chiếu Văn Bản Gốc & Bản Dịch", font=("Segoe UI", 13, "bold")).pack(side="left", padx=10)

		ctk.CTkButton(frame_top, text="📂 Chọn File Gốc", width=120, command=self._browse_orig).pack(side="left", padx=5)
		self.lbl_orig = ctk.CTkLabel(frame_top, text="Chưa chọn", text_color="#6272a4")
		self.lbl_orig.pack(side="left", padx=5)

		ctk.CTkButton(frame_top, text="📂 Chọn File Dịch", width=120, command=self._browse_trans).pack(side="left", padx=(15, 5))
		self.lbl_trans = ctk.CTkLabel(frame_top, text="Chưa chọn", text_color="#6272a4")
		self.lbl_trans.pack(side="left", padx=5)

		ctk.CTkButton(frame_top, text="⚡ So Sánh", fg_color="#0066cc", width=100, command=self.run_diff).pack(side="right", padx=10)

		# Split View Panes
		frame_panes = ctk.CTkFrame(self)
		frame_panes.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
		frame_panes.grid_columnconfigure(0, weight=1)
		frame_panes.grid_columnconfigure(1, weight=1)
		frame_panes.grid_rowconfigure(1, weight=1)

		ctk.CTkLabel(frame_panes, text="📄 Văn Bản Gốc:", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=5)
		ctk.CTkLabel(frame_panes, text="📝 Văn Bản Dịch:", font=("Segoe UI", 12, "bold")).grid(row=0, column=1, sticky="w", padx=10, pady=5)

		self.txt_orig = ctk.CTkTextbox(frame_panes, font=("Consolas", 11))
		self.txt_orig.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=(0, 10))

		self.txt_trans = ctk.CTkTextbox(frame_panes, font=("Segoe UI", 11))
		self.txt_trans.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=(0, 10))

	def _browse_orig(self):
		path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
		if path:
			self.lbl_orig.configure(text=path)
			content = read_file_content_safely(path)
			self.txt_orig.delete("1.0", "end")
			self.txt_orig.insert("1.0", content)

	def _browse_trans(self):
		path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
		if path:
			self.lbl_trans.configure(text=path)
			content = read_file_content_safely(path)
			self.txt_trans.delete("1.0", "end")
			self.txt_trans.insert("1.0", content)

	def run_diff(self):
		t1 = self.txt_orig.get("1.0", "end-1c")
		t2 = self.txt_trans.get("1.0", "end-1c")
		if not t1 or not t2:
			messagebox.showwarning("Cảnh báo", "Vui lòng chọn hoặc nhập đủ 2 nội dung văn bản để so sánh.")
			return

		lines1 = t1.splitlines()
		lines2 = t2.splitlines()

		matcher = difflib.SequenceMatcher(None, lines1, lines2)
		ratio = matcher.ratio()
		messagebox.showinfo("Kết quả So sánh", f"Độ tương đồng cấu trúc đoạn: {ratio * 100:.1f}%\nTổng số dòng Gốc: {len(lines1)}\nTổng số dòng Dịch: {len(lines2)}")
