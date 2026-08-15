import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from core.history import normalize_request_counts, summarize_request_counts

class RequestDetailDialog(ctk.CTkToplevel):
	def __init__(self, parent, history_entry: dict):
		super().__init__(parent)
		self.title("📊 Chi tiết Tải Request theo Phút")
		self.geometry("640x500")
		self.grab_set()

		self.entry = history_entry
		self._build_ui()

	def _build_ui(self):
		counts = normalize_request_counts(self.entry)
		total_req, peak_rpm, model_totals = summarize_request_counts(counts)

		frame_summary = ctk.CTkFrame(self)
		frame_summary.pack(fill="x", padx=15, pady=10)

		lbl_title = ctk.CTkLabel(
			frame_summary,
			text=f"Bản dịch: {self.entry.get('output_file', 'Unsaved')} | Model: {self.entry.get('model', 'N/A')}",
			font=("Segoe UI", 12, "bold")
		)
		lbl_title.pack(anchor="w", padx=10, pady=(10, 5))

		stats_str = f"Tổng Request API: {total_req:,}  |  Đỉnh điểm RPM (Request/Phút): {peak_rpm:,}"
		lbl_stats = ctk.CTkLabel(frame_summary, text=stats_str, text_color="#bd93f9")
		lbl_stats.pack(anchor="w", padx=10, pady=(0, 10))

		# Table Frame
		frame_table = ctk.CTkFrame(self)
		frame_table.pack(fill="both", expand=True, padx=15, pady=5)

		columns = ("minute", "model", "count")
		self.tree = ttk.Treeview(frame_table, columns=columns, show="headings", height=15)
		self.tree.heading("minute", text="Phút (YYYY-MM-DD HH:MM)")
		self.tree.heading("model", text="Model")
		self.tree.heading("count", text="Số Request Gửi")

		self.tree.column("minute", width=220, anchor="center")
		self.tree.column("model", width=220, anchor="w")
		self.tree.column("count", width=120, anchor="center")

		sb = ctk.CTkScrollbar(frame_table, command=self.tree.yview)
		self.tree.configure(yscrollcommand=sb.set)

		self.tree.pack(side="left", fill="both", expand=True, padx=5, pady=5)
		sb.pack(side="right", fill="y", pady=5)

		for item in counts:
			self.tree.insert("", "end", values=(item["minute"], item["model"], f"{item['count']:,}"))
