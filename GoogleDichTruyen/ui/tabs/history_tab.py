import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from core.history import load_translation_history, clear_translation_history
from ui.dialogs.request_detail_dialog import RequestDetailDialog

class HistoryTab(ctk.CTkFrame):
	def __init__(self, parent, main_app):
		super().__init__(parent)
		self.main_app = main_app
		self.history_entries = []

		self._build_ui()
		self.refresh_history()

	def _build_ui(self):
		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)

		# Header bar
		frame_head = ctk.CTkFrame(self)
		frame_head.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

		ctk.CTkLabel(frame_head, text="📜 Lịch Sử Các Lần Dịch Truyện", font=("Segoe UI", 14, "bold")).pack(side="left", padx=10, pady=10)

		ctk.CTkButton(frame_head, text="🔄 Làm Mới", width=90, command=self.refresh_history).pack(side="right", padx=5)
		ctk.CTkButton(frame_head, text="🗑️ Xóa Lịch Sử", width=100, fg_color="#dc3545", hover_color="#c82333", command=self._clear_history).pack(side="right", padx=5)

		# Treeview container
		frame_tree = ctk.CTkFrame(self)
		frame_tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

		columns = ("time", "output", "model", "chunks", "tokens", "cost", "details")
		self.tree = ttk.Treeview(frame_tree, columns=columns, show="headings", height=15)

		self.tree.heading("time", text="Thời Gian")
		self.tree.heading("output", text="File Bản Dịch")
		self.tree.heading("model", text="Model")
		self.tree.heading("chunks", text="Chunks")
		self.tree.heading("tokens", text="Tổng Tokens")
		self.tree.heading("cost", text="Chi Phí (USD)")
		self.tree.heading("details", text="Request Log")

		self.tree.column("time", width=140, anchor="center")
		self.tree.column("output", width=260, anchor="w")
		self.tree.column("model", width=160, anchor="w")
		self.tree.column("chunks", width=70, anchor="center")
		self.tree.column("tokens", width=100, anchor="e")
		self.tree.column("cost", width=90, anchor="e")
		self.tree.column("details", width=100, anchor="center")

		sb = ctk.CTkScrollbar(frame_tree, command=self.tree.yview)
		self.tree.configure(yscrollcommand=sb.set)

		self.tree.pack(side="left", fill="both", expand=True, padx=5, pady=5)
		sb.pack(side="right", fill="y", pady=5)

		self.tree.bind("<Double-1>", self._on_row_double_click)

	def refresh_history(self):
		for row in self.tree.get_children():
			self.tree.delete(row)

		self.history_entries = load_translation_history()
		for i, entry in enumerate(self.history_entries):
			time_str = entry.get("start_at", "N/A")
			out_str = entry.get("output_file", "N/A")
			model_str = entry.get("model", "N/A")
			chunks_str = str(entry.get("total_chunks", 0))
			tokens_str = f"{entry.get('total_tokens', 0):,}"
			cost_str = f"${entry.get('total_cost_usd', 0.0):.4f}"
			details_str = "🔍 Xem Chi Tiết"

			self.tree.insert("", "end", iid=str(i), values=(time_str, out_str, model_str, chunks_str, tokens_str, cost_str, details_str))

	def _clear_history(self):
		if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa toàn bộ lịch sử dịch?"):
			clear_translation_history()
			self.refresh_history()

	def _on_row_double_click(self, event):
		item_id = self.tree.focus()
		if not item_id:
			return
		try:
			idx = int(item_id)
			if 0 <= idx < len(self.history_entries):
				RequestDetailDialog(self, self.history_entries[idx])
		except ValueError:
			pass
