import threading
import customtkinter as ctk
from tkinter import messagebox
from core.config import MODELS, DEFAULT_PROMPT
from core.translator import TranslationEngine, is_gemini_v3_or_above

class QuickTranslateTab(ctk.CTkFrame):
	def __init__(self, parent, main_app):
		super().__init__(parent)
		self.main_app = main_app
		self.engine = TranslationEngine()

		self._build_ui()

	def _build_ui(self):
		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)

		# Top Control Bar
		frame_top = ctk.CTkFrame(self)
		frame_top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

		ctk.CTkLabel(frame_top, text="⚡ Dịch Nhanh Đoạn Văn / Clipboard", font=("Segoe UI", 13, "bold")).pack(side="left", padx=10)

		ctk.CTkButton(frame_top, text="📋 Dán từ Clipboard", width=120, command=self._paste_clipboard).pack(side="left", padx=5)

		ctk.CTkLabel(frame_top, text="Model:").pack(side="left", padx=(15, 5))
		self.combo_model = ctk.CTkOptionMenu(frame_top, values=MODELS, width=200, command=self._on_model_change)
		self.combo_model.pack(side="left", padx=5)

		ctk.CTkLabel(frame_top, text="Thinking:").pack(side="left", padx=(10, 5))
		self.combo_thinking = ctk.CTkOptionMenu(frame_top, values=["minimal", "low", "medium", "high"], width=100)
		self.combo_thinking.set("medium")
		self.combo_thinking.pack(side="left", padx=5)

		self.btn_translate = ctk.CTkButton(
			frame_top,
			text="🚀 Dịch Ngay",
			font=("Segoe UI", 12, "bold"),
			fg_color="#28a745",
			hover_color="#218838",
			command=self.run_quick_translation
		)
		self.btn_translate.pack(side="right", padx=10)

		# Split Input/Output Panes
		frame_panes = ctk.CTkFrame(self)
		frame_panes.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
		frame_panes.grid_columnconfigure(0, weight=1)
		frame_panes.grid_columnconfigure(1, weight=1)
		frame_panes.grid_rowconfigure(1, weight=1)

		row_head0 = ctk.CTkFrame(frame_panes, fg_color="transparent")
		row_head0.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
		ctk.CTkLabel(row_head0, text="📄 Văn bản gốc:", font=("Segoe UI", 12, "bold")).pack(side="left")

		row_head1 = ctk.CTkFrame(frame_panes, fg_color="transparent")
		row_head1.grid(row=0, column=1, sticky="ew", padx=10, pady=5)
		ctk.CTkLabel(row_head1, text="📝 Kết quả dịch:", font=("Segoe UI", 12, "bold")).pack(side="left")
		ctk.CTkButton(row_head1, text="📋 Sao chép", width=90, command=self._copy_output).pack(side="right")

		self.txt_input = ctk.CTkTextbox(frame_panes, font=("Consolas", 11))
		self.txt_input.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=(0, 10))

		self.txt_output = ctk.CTkTextbox(frame_panes, font=("Segoe UI", 11))
		self.txt_output.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=(0, 10))

	def _on_model_change(self, model_id):
		if is_gemini_v3_or_above(model_id):
			self.combo_thinking.configure(state="normal")
		else:
			self.combo_thinking.configure(state="disabled")

	def _paste_clipboard(self):
		try:
			text = self.clipboard_get()
			self.txt_input.delete("1.0", "end")
			self.txt_input.insert("1.0", text)
		except Exception as e:
			messagebox.showerror("Lỗi", f"Không thể lấy dữ liệu từ Clipboard: {e}")

	def _copy_output(self):
		text = self.txt_output.get("1.0", "end-1c")
		if text.strip():
			self.clipboard_clear()
			self.clipboard_append(text)
			messagebox.showinfo("Thông báo", "Đã sao chép kết quả dịch vào Clipboard!")

	def run_quick_translation(self):
		text = self.txt_input.get("1.0", "end-1c").strip()
		if not text:
			messagebox.showwarning("Cảnh báo", "Vui lòng nhập hoặc dán văn bản cần dịch.")
			return

		api_key = self.main_app.translate_tab.entry_api_key.get().strip()
		if not api_key:
			messagebox.showerror("Lỗi", "Vui lòng nhập Gemini API Key ở tab Dịch truyện.")
			return

		model_id = self.combo_model.get()
		thinking = self.combo_thinking.get()
		prompt = DEFAULT_PROMPT

		self.btn_translate.configure(state="disabled")
		self.txt_output.delete("1.0", "end")
		self.txt_output.insert("1.0", "⏳ Đang dịch...")

		def worker():
			res, in_tok, out_tok, err = self.engine.translate_with_gemini(
				model_id=model_id,
				prompt=prompt,
				chunk=text,
				temperature=0.5,
				max_output_tokens=70000,
				thinking_level=thinking,
				api_key=api_key
			)
			self.after(0, lambda: self._on_finish(res, err))

		threading.Thread(target=worker, daemon=True).start()

	def _on_finish(self, result_text, error):
		self.btn_translate.configure(state="normal")
		self.txt_output.delete("1.0", "end")
		if error or not result_text:
			self.txt_output.insert("1.0", f"❌ Dịch thất bại: {error}")
		else:
			self.txt_output.insert("1.0", result_text)
