import threading
import customtkinter as ctk
from tkinter import messagebox
from core.config import MODELS
from core.translator import is_gemini_v3_or_above

class RegenerateDialog(ctk.CTkToplevel):
	def __init__(self, parent, chunk_index: int, original_text: str, current_translated: str, default_model: str, default_prompt: str, api_key: str, on_success_callback):
		super().__init__(parent)
		self.title(f"🔄 Dịch lại Chunk #{chunk_index + 1}")
		self.geometry("900x680")
		self.grab_set()

		self.chunk_index = chunk_index
		self.original_text = original_text
		self.current_translated = current_translated
		self.api_key = api_key
		self.on_success_callback = on_success_callback

		self._build_ui(default_model, default_prompt)

	def _build_ui(self, default_model, default_prompt):
		# Header Controls
		frame_top = ctk.CTkFrame(self)
		frame_top.pack(fill="x", padx=15, pady=10)

		ctk.CTkLabel(frame_top, text="Model:").pack(side="left", padx=(10, 5))
		self.combo_model = ctk.CTkOptionMenu(frame_top, values=MODELS, width=220, command=self._on_model_change)
		self.combo_model.set(default_model if default_model in MODELS else MODELS[0])
		self.combo_model.pack(side="left", padx=5)

		ctk.CTkLabel(frame_top, text="Thinking:").pack(side="left", padx=(15, 5))
		self.combo_thinking = ctk.CTkOptionMenu(frame_top, values=["minimal", "low", "medium", "high"], width=110)
		self.combo_thinking.set("medium")
		self.combo_thinking.pack(side="left", padx=5)

		ctk.CTkLabel(frame_top, text="Temp:").pack(side="left", padx=(15, 5))
		self.entry_temp = ctk.CTkEntry(frame_top, width=60)
		self.entry_temp.insert(0, "0.5")
		self.entry_temp.pack(side="left", padx=5)

		self._on_model_change(self.combo_model.get())

		# Prompt Section
		frame_prompt = ctk.CTkFrame(self)
		frame_prompt.pack(fill="x", padx=15, pady=5)
		ctk.CTkLabel(frame_prompt, text="Prompt Dịch giả:").pack(anchor="w", padx=10, pady=(5, 2))
		self.txt_prompt = ctk.CTkTextbox(frame_prompt, height=70)
		self.txt_prompt.pack(fill="x", padx=10, pady=(0, 10))
		self.txt_prompt.insert("1.0", default_prompt)

		# Text Panes (Side-by-Side Split)
		frame_texts = ctk.CTkFrame(self)
		frame_texts.pack(fill="both", expand=True, padx=15, pady=5)
		frame_texts.grid_columnconfigure(0, weight=1)
		frame_texts.grid_columnconfigure(1, weight=1)
		frame_texts.grid_rowconfigure(1, weight=1)

		ctk.CTkLabel(frame_texts, text="📄 Gốc (Tiếng Trung / Nguyên bản):", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=5)
		ctk.CTkLabel(frame_texts, text="📝 Bản Dịch (Hiện tại / Kết quả):", font=("Segoe UI", 12, "bold")).grid(row=0, column=1, sticky="w", padx=10, pady=5)

		self.txt_original = ctk.CTkTextbox(frame_texts, font=("Consolas", 11))
		self.txt_original.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=(0, 10))
		self.txt_original.insert("1.0", self.original_text)

		self.txt_translated = ctk.CTkTextbox(frame_texts, font=("Segoe UI", 11))
		self.txt_translated.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=(0, 10))
		self.txt_translated.insert("1.0", self.current_translated)

		# Action Bar
		frame_action = ctk.CTkFrame(self)
		frame_action.pack(fill="x", padx=15, pady=10)

		self.lbl_status = ctk.CTkLabel(frame_action, text="Sẵn sàng", text_color="#6272a4")
		self.lbl_status.pack(side="left", padx=10)

		self.btn_run = ctk.CTkButton(
			frame_action,
			text="🚀 Dịch lại Chunk này",
			fg_color="#0066cc",
			hover_color="#0052a3",
			font=("Segoe UI", 12, "bold"),
			command=self.run_retranslation
		)
		self.btn_run.pack(side="right", padx=10)

	def _on_model_change(self, selected_model):
		if is_gemini_v3_or_above(selected_model):
			self.combo_thinking.configure(state="normal")
		else:
			self.combo_thinking.configure(state="disabled")

	def run_retranslation(self):
		model_id = self.combo_model.get()
		prompt = self.txt_prompt.get("1.0", "end-1c").strip()
		temp = float(self.entry_temp.get() or "0.5")
		thinking = self.combo_thinking.get()

		self.btn_run.configure(state="disabled")
		self.lbl_status.configure(text="⏳ Đang gọi Gemini API để dịch lại...", text_color="#ffb86c")

		def worker():
			from core.translator import TranslationEngine
			engine = TranslationEngine()
			res_text, in_tok, out_tok, err = engine.translate_with_gemini(
				model_id=model_id,
				prompt=prompt,
				chunk=self.original_text,
				temperature=temp,
				max_output_tokens=70000,
				thinking_level=thinking,
				api_key=self.api_key
			)
			self.after(0, lambda: self._on_finish(res_text, err))

		threading.Thread(target=worker, daemon=True).start()

	def _on_finish(self, result_text, error):
		self.btn_run.configure(state="normal")
		if error or not result_text:
			self.lbl_status.configure(text=f"❌ Thất bại: {error or 'Rỗng'}", text_color="#ff5555")
			messagebox.showerror("Lỗi", f"Dịch lại thất bại: {error}")
		else:
			self.lbl_status.configure(text="✅ Hoàn thành!", text_color="#50fa7b")
			self.txt_translated.delete("1.0", "end")
			self.txt_translated.insert("1.0", result_text)
			if self.on_success_callback:
				self.on_success_callback(self.chunk_index, result_text)
