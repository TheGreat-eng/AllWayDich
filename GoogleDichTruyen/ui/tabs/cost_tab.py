import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from core.config import USD_TO_VND
from core.history import load_translation_history

class CostTab(ctk.CTkFrame):
	def __init__(self, parent, main_app):
		super().__init__(parent)
		self.main_app = main_app
		self._build_ui()
		self.refresh_stats()

	def _build_ui(self):
		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(2, weight=1)

		# Top Bar Controls
		frame_top = ctk.CTkFrame(self)
		frame_top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

		ctk.CTkLabel(frame_top, text="💰 Thống Kê Chi Phí Dịch AI", font=("Segoe UI", 14, "bold")).pack(side="left", padx=10, pady=10)

		self.combo_filter = ctk.CTkOptionMenu(frame_top, values=["Tất cả thời gian", "Tháng này", "Tuần này"], command=lambda _: self.refresh_stats())
		self.combo_filter.pack(side="right", padx=10)
		ctk.CTkLabel(frame_filter := frame_top, text="Thời gian:").pack(side="right", padx=5)

		# Total Summary Card
		frame_summary = ctk.CTkFrame(self)
		frame_summary.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

		self.lbl_total_usd = ctk.CTkLabel(frame_summary, text="Tổng Chi Phí: $0.0000", font=("Segoe UI", 16, "bold"), text_color="#bd93f9")
		self.lbl_total_usd.pack(anchor="w", padx=15, pady=(10, 2))

		self.lbl_total_vnd = ctk.CTkLabel(frame_summary, text="Tương đương: 0 VNĐ (Tỷ giá 27,000 đ/$)", font=("Segoe UI", 12), text_color="#6272a4")
		self.lbl_total_vnd.pack(anchor="w", padx=15, pady=(0, 10))

		# Model Breakdown Table
		frame_table = ctk.CTkFrame(self)
		frame_table.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))

		columns = ("model", "count", "tokens", "cost_usd", "cost_vnd")
		self.tree = ttk.Treeview(frame_table, columns=columns, show="headings", height=12)

		self.tree.heading("model", text="Model Gemini")
		self.tree.heading("count", text="Số Bản Dịch")
		self.tree.heading("tokens", text="Tổng Tokens")
		self.tree.heading("cost_usd", text="Chi Phí (USD)")
		self.tree.heading("cost_vnd", text="Chi Phí (VNĐ)")

		self.tree.column("model", width=220, anchor="w")
		self.tree.column("count", width=100, anchor="center")
		self.tree.column("tokens", width=140, anchor="e")
		self.tree.column("cost_usd", width=120, anchor="e")
		self.tree.column("cost_vnd", width=140, anchor="e")

		sb = ctk.CTkScrollbar(frame_table, command=self.tree.yview)
		self.tree.configure(yscrollcommand=sb.set)

		self.tree.pack(side="left", fill="both", expand=True, padx=5, pady=5)
		sb.pack(side="right", fill="y", pady=5)

	def refresh_stats(self):
		for row in self.tree.get_children():
			self.tree.delete(row)

		history = load_translation_history()
		filter_mode = self.combo_filter.get()

		now = datetime.now()
		filtered = []
		for entry in history:
			start_str = entry.get("start_at", "")
			try:
				dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
			except ValueError:
				dt = now

			if filter_mode == "Tháng này" and (dt.month != now.month or dt.year != now.year):
				continue
			if filter_mode == "Tuần này" and dt < (now - timedelta(days=7)):
				continue
			filtered.append(entry)

		total_usd = sum(e.get("total_cost_usd", 0.0) for e in filtered)
		total_vnd = int(total_usd * USD_TO_VND)

		self.lbl_total_usd.configure(text=f"Tổng Chi Phí: ${total_usd:.4f}")
		self.lbl_total_vnd.configure(text=f"Tương đương: {total_vnd:,} VNĐ (Tỷ giá {USD_TO_VND:,} đ/$)")

		model_stats = {}
		for entry in filtered:
			m = entry.get("model", "Unknown")
			if m not in model_stats:
				model_stats[m] = {"count": 0, "tokens": 0, "cost_usd": 0.0}
			model_stats[m]["count"] += 1
			model_stats[m]["tokens"] += entry.get("total_tokens", 0)
			model_stats[m]["cost_usd"] += entry.get("total_cost_usd", 0.0)

		for m, data in sorted(model_stats.items(), key=lambda x: x[1]["cost_usd"], reverse=True):
			c_usd = data["cost_usd"]
			c_vnd = int(c_usd * USD_TO_VND)
			self.tree.insert("", "end", values=(m, f"{data['count']:,}", f"{data['tokens']:,}", f"${c_usd:.4f}", f"{c_vnd:,} đ"))
