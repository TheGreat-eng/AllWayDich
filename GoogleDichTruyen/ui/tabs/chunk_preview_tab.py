import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
from core.text_helpers import read_file_content_safely, get_translation_cache_path, write_text_atomically
from core.chunker import split_text
from ui.dialogs.regenerate_dialog import RegenerateDialog

class ChunkPreviewTab(ctk.CTkFrame):
	def __init__(self, parent, main_app):
		super().__init__(parent)
		self.main_app = main_app
		self.current_file = ""
		self.chunks = []
		self.translated_chunks = []

		self._build_ui()

	def _build_ui(self):
		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)

		# Top Control Bar
		frame_top = ctk.CTkFrame(self)
		frame_top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

		ctk.CTkButton(frame_top, text="📂 Chọn File Truyện / Cache Chunk", command=self._load_file).pack(side="left", padx=10, pady=10)

		self.lbl_file_info = ctk.CTkLabel(frame_top, text="Chưa tải file", font=("Segoe UI", 11, "bold"), text_color="#6272a4")
		self.lbl_file_info.pack(side="left", padx=10)

		ctk.CTkLabel(frame_top, text="Chọn Chunk:").pack(side="left", padx=(20, 5))
		self.combo_chunks = ctk.CTkOptionMenu(frame_top, values=["Chưa có dữ liệu"], command=self._on_chunk_select, width=160)
		self.combo_chunks.pack(side="left", padx=5)

		self.btn_regen = ctk.CTkButton(
			frame_top,
			text="🔄 Dịch Lại Chunk Này",
			fg_color="#0066cc",
			hover_color="#0052a3",
			command=self._open_regenerate_dialog
		)
		self.btn_regen.pack(side="right", padx=10)

		self.btn_save_edits = ctk.CTkButton(
			frame_top,
			text="💾 Lưu Sửa Đổi",
			fg_color="#28a745",
			hover_color="#218838",
			command=self._save_edits
		)
		self.btn_save_edits.pack(side="right", padx=5)

		# Split View Panes
		frame_panes = ctk.CTkFrame(self)
		frame_panes.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
		frame_panes.grid_columnconfigure(0, weight=1)
		frame_panes.grid_columnconfigure(1, weight=1)
		frame_panes.grid_rowconfigure(1, weight=1)

		ctk.CTkLabel(frame_panes, text="📄 Văn Bản Gốc Chunk (Tiếng Trung / Nguyên Bản):", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=5)
		ctk.CTkLabel(frame_panes, text="📝 Kết Quả Dịch Chunk (Tiếng Việt):", font=("Segoe UI", 12, "bold")).grid(row=0, column=1, sticky="w", padx=10, pady=5)

		self.txt_original = ctk.CTkTextbox(frame_panes, font=("Consolas", 11))
		self.txt_original.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=(0, 10))

		self.txt_translated = ctk.CTkTextbox(frame_panes, font=("Segoe UI", 11))
		self.txt_translated.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=(0, 10))

	def _load_file(self):
		path = filedialog.askopenfilename(filetypes=[("Text & JSON", "*.txt;*.json"), ("All files", "*.*")])
		if not path:
			return

		self.current_file = path
		content = read_file_content_safely(path)
		if not content:
			messagebox.showerror("Lỗi", "Không thể đọc nội dung file.")
			return

		# Check if cache file exists
		cache_path = get_translation_cache_path(path)
		if os.path.exists(cache_path):
			trans_content = read_file_content_safely(cache_path)
			self.translated_chunks = trans_content.split("\n\n")
		else:
			self.translated_chunks = []

		self.chunks = split_text(content, size=70000)
		self.lbl_file_info.configure(text=f"File: {os.path.basename(path)} ({len(self.chunks)} chunks)")

		chunk_options = [f"Chunk #{i+1}" for i in range(len(self.chunks))]
		self.combo_chunks.configure(values=chunk_options)
		if chunk_options:
			self.combo_chunks.set(chunk_options[0])
			self._on_chunk_select(chunk_options[0])

	def _on_chunk_select(self, choice):
		if not choice or choice == "Chưa có dữ liệu" or not self.chunks:
			return
		try:
			idx = int(choice.replace("Chunk #", "")) - 1
		except ValueError:
			return

		if 0 <= idx < len(self.chunks):
			self.txt_original.delete("1.0", "end")
			self.txt_original.insert("1.0", self.chunks[idx])

			self.txt_translated.delete("1.0", "end")
			if idx < len(self.translated_chunks):
				self.txt_translated.insert("1.0", self.translated_chunks[idx])

	def _open_regenerate_dialog(self):
		choice = self.combo_chunks.get()
		if not choice or choice == "Chưa có dữ liệu" or not self.chunks:
			messagebox.showwarning("Cảnh báo", "Vui lòng tải file và chọn chunk để dịch lại.")
			return
		idx = int(choice.replace("Chunk #", "")) - 1
		orig = self.chunks[idx]
		curr_trans = self.translated_chunks[idx] if idx < len(self.translated_chunks) else ""

		# Retrieve main app settings
		def_model = self.main_app.translate_tab.combo_model.get()
		def_prompt = self.main_app.translate_tab.txt_prompt.get("1.0", "end-1c")
		api_key = self.main_app.translate_tab.entry_api_key.get().strip()

		def on_success(c_idx, new_text):
			while len(self.translated_chunks) <= c_idx:
				self.translated_chunks.append("")
			self.translated_chunks[c_idx] = new_text
			self.txt_translated.delete("1.0", "end")
			self.txt_translated.insert("1.0", new_text)

		RegenerateDialog(self, idx, orig, curr_trans, def_model, def_prompt, api_key, on_success)

	def _save_edits(self):
		choice = self.combo_chunks.get()
		if not choice or choice == "Chưa có dữ liệu":
			return
		idx = int(choice.replace("Chunk #", "")) - 1
		new_text = self.txt_translated.get("1.0", "end-1c")

		while len(self.translated_chunks) <= idx:
			self.translated_chunks.append("")
		self.translated_chunks[idx] = new_text

		if self.current_file:
			cache_path = get_translation_cache_path(self.current_file)
			full_trans = "\n\n".join(self.translated_chunks)
			write_text_atomically(cache_path, full_trans)
			messagebox.showinfo("Thành công", f"Đã lưu chỉnh sửa Chunk #{idx+1} vào cache!")
