import customtkinter as ctk
from tkinter import messagebox
from core.config import MODELS

class FallbackDialog(ctk.CTkToplevel):
	def __init__(self, parent, current_order_str: str, on_save_callback):
		super().__init__(parent)
		self.title("⚡ Cấu hình Thứ tự Model Dự phòng (Fallback)")
		self.geometry("520x480")
		self.resizable(False, False)
		self.on_save_callback = on_save_callback
		self.grab_set()

		# Parse initial list
		raw_items = [m.strip() for m in current_order_str.split("|") if m.strip()]
		valid_items = [m for m in raw_items if m in MODELS]
		for m in MODELS:
			if m not in valid_items:
				valid_items.append(m)
		self.model_items = valid_items

		self._build_ui()

	def _build_ui(self):
		lbl_desc = ctk.CTkLabel(
			self,
			text="Khi model chính gặp lỗi quota (429), app sẽ tự động thử các model theo thứ tự bên dưới:",
			wraplength=480,
			justify="left"
		)
		lbl_desc.pack(padx=20, pady=(15, 10))

		frame_list = ctk.CTkFrame(self)
		frame_list.pack(fill="both", expand=True, padx=20, pady=5)

		# Listbox container
		import tkinter as tk
		self.listbox = tk.Listbox(
			frame_list,
			bg="#181825",
			fg="#f8f8f2",
			selectbackground="#bd93f9",
			selectforeground="#000000",
			font=("Segoe UI", 11),
			bd=0,
			highlightthickness=0,
		)
		self.listbox.pack(side="left", fill="both", expand=True, padx=10, pady=10)

		scrollbar = ctk.CTkScrollbar(frame_list, command=self.listbox.yview)
		scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=10)
		self.listbox.config(yscrollcommand=scrollbar.set)

		for item in self.model_items:
			self.listbox.insert(tk.END, item)

		# Buttons
		frame_btns = ctk.CTkFrame(self)
		frame_btns.pack(fill="x", padx=20, pady=15)

		btn_up = ctk.CTkButton(frame_btns, text="⬆️ Lên", width=80, command=self.move_up)
		btn_up.pack(side="left", padx=5)

		btn_down = ctk.CTkButton(frame_btns, text="⬇️ Xuống", width=80, command=self.move_down)
		btn_down.pack(side="left", padx=5)

		btn_reset = ctk.CTkButton(frame_btns, text="🔄 Mặc định", width=90, fg_color="#6272a4", command=self.reset_default)
		btn_reset.pack(side="left", padx=5)

		btn_save = ctk.CTkButton(frame_btns, text="💾 Lưu", width=90, fg_color="#28a745", hover_color="#218838", command=self.save)
		btn_save.pack(side="right", padx=5)

	def move_up(self):
		sel = self.listbox.curselection()
		if not sel or sel[0] == 0:
			return
		idx = sel[0]
		val = self.listbox.get(idx)
		self.listbox.delete(idx)
		self.listbox.insert(idx - 1, val)
		self.listbox.selection_set(idx - 1)

	def move_down(self):
		sel = self.listbox.curselection()
		if not sel or sel[0] == self.listbox.size() - 1:
			return
		idx = sel[0]
		val = self.listbox.get(idx)
		self.listbox.delete(idx)
		self.listbox.insert(idx + 1, val)
		self.listbox.selection_set(idx + 1)

	def reset_default(self):
		self.listbox.delete(0, ctk.END)
		for item in MODELS:
			self.listbox.insert(ctk.END, item)

	def save(self):
		items = list(self.listbox.get(0, ctk.END))
		order_str = "|".join(items)
		if self.on_save_callback:
			self.on_save_callback(order_str)
		self.destroy()
