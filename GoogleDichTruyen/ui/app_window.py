import queue
import threading
import customtkinter as ctk
from tkinter import messagebox
from core.history import load_settings, save_settings
from ui.theme import COLORS
from ui.tabs.translate_tab import TranslateTab
from ui.tabs.chunk_preview_tab import ChunkPreviewTab
from ui.tabs.history_tab import HistoryTab
from ui.tabs.cost_tab import CostTab
from ui.tabs.quick_translate_tab import QuickTranslateTab
from ui.tabs.diff_tab import DiffTab

class GoogleDichTruyenApp(ctk.CTk):
	def __init__(self):
		super().__init__()
		self.title("GoogleDichTruyen v2.0 - Dịch Truyện Chuẩn AI Gemini (CustomTkinter UI)")
		self.geometry("1280x820")
		self.minsize(1080, 700)

		self.ui_event_queue = queue.Queue()
		self.settings = load_settings()

		self._build_ui()
		self._apply_initial_settings()

		self.protocol("WM_DELETE_WINDOW", self.on_closing)
		self.after(50, self.process_ui_events)

	def _build_ui(self):
		# Header Bar
		header_frame = ctk.CTkFrame(self, fg_color=(" #e1e1e6", "#181825"), corner_radius=0)
		header_frame.pack(fill="x", side="top")

		lbl_logo = ctk.CTkLabel(
			header_frame,
			text="📚 GoogleDichTruyen",
			font=("Segoe UI", 20, "bold"),
			text_color=("#0066cc", "#bd93f9")
		)
		lbl_logo.pack(side="left", padx=20, pady=12)

		lbl_subtitle = ctk.CTkLabel(
			header_frame,
			text="Ứng dụng Dịch Truyện Chuyên Nghiệp bằng Google Gemini AI",
			font=("Segoe UI", 11),
			text_color="#6272a4"
		)
		lbl_subtitle.pack(side="left", padx=5, pady=12)

		# Theme Switcher
		self.switch_theme = ctk.CTkSwitch(
			header_frame,
			text="🌙 Dark Mode",
			command=self.toggle_theme
		)
		self.switch_theme.pack(side="right", padx=20, pady=12)
		if self.settings.get("theme", "dark") == "dark":
			self.switch_theme.select()
			ctk.set_appearance_mode("Dark")
		else:
			self.switch_theme.deselect()
			ctk.set_appearance_mode("Light")

		# Main Tabview
		self.tabview = ctk.CTkTabview(self, corner_radius=8)
		self.tabview.pack(fill="both", expand=True, padx=15, pady=(5, 15))

		# Add Tabs
		t_trans = self.tabview.add("🚀 Dịch Truyện")
		t_preview = self.tabview.add("🔍 Xem Chunk")
		t_history = self.tabview.add("🗂️ Lịch Sử Dịch")
		t_cost = self.tabview.add("💰 Thống Kê Chi Phí")
		t_quick = self.tabview.add("⚡ Dịch Nhanh")
		t_diff = self.tabview.add("🔍 So Sánh Diff")

		# Instantiate Tab Controllers
		self.translate_tab = TranslateTab(t_trans, self)
		self.translate_tab.pack(fill="both", expand=True)

		self.chunk_preview_tab = ChunkPreviewTab(t_preview, self)
		self.chunk_preview_tab.pack(fill="both", expand=True)

		self.history_tab = HistoryTab(t_history, self)
		self.history_tab.pack(fill="both", expand=True)

		self.cost_tab = CostTab(t_cost, self)
		self.cost_tab.pack(fill="both", expand=True)

		self.quick_translate_tab = QuickTranslateTab(t_quick, self)
		self.quick_translate_tab.pack(fill="both", expand=True)

		self.diff_tab = DiffTab(t_diff, self)
		self.diff_tab.pack(fill="both", expand=True)

	def _apply_initial_settings(self):
		s = self.settings
		tt = self.translate_tab

		# API Keys
		keys_dict = s.get("api_keys", {})
		if keys_dict:
			tt.combo_key_profile.configure(values=list(keys_dict.keys()))
			curr_k = s.get("current_key_name", "Mặc định")
			if curr_k in keys_dict:
				tt.combo_key_profile.set(curr_k)
				tt.entry_api_key.insert(0, keys_dict[curr_k])

		# Files & Params
		if s.get("input_file"):
			tt.entry_input.insert(0, s["input_file"])
		if s.get("output_file"):
			tt.entry_output.insert(0, s["output_file"])
		if s.get("model") in tt.combo_model.cget("values"):
			tt.combo_model.set(s["model"])
		if s.get("thinking_level"):
			tt.combo_thinking.set(s["thinking_level"])

		tt.entry_threads.delete(0, "end")
		tt.entry_threads.insert(0, str(s.get("threads", "3")))

		tt.entry_chunk_size.delete(0, "end")
		tt.entry_chunk_size.insert(0, str(s.get("chunk_size", "70000")))

		tt.entry_temp.delete(0, "end")
		tt.entry_temp.insert(0, str(s.get("temperature", "0.5")))

		if s.get("chunk_split_mode"):
			tt.combo_split_mode.set(s["chunk_split_mode"])

		# Prompts
		if s.get("prompt"):
			tt.txt_prompt.delete("1.0", "end")
			tt.txt_prompt.insert("1.0", s["prompt"])
		if s.get("glossary"):
			tt.txt_glossary.delete("1.0", "end")
			tt.txt_glossary.insert("1.0", s["glossary"])

		if s.get("model_fallback_order"):
			tt.fallback_order_str = s["model_fallback_order"]

		if s.get("drive_upload_enabled"):
			tt.chk_drive.select()

	def toggle_theme(self):
		if self.switch_theme.get() == 1:
			ctk.set_appearance_mode("Dark")
			self.switch_theme.configure(text="🌙 Dark Mode")
		else:
			ctk.set_appearance_mode("Light")
			self.switch_theme.configure(text="☀️ Light Mode")

	def post_to_ui(self, callback, *args, **kwargs):
		self.ui_event_queue.put((callback, args, kwargs))

	def process_ui_events(self):
		processed = 0
		while processed < 200:
			try:
				callback, args, kwargs = self.ui_event_queue.get_nowait()
			except queue.Empty:
				break
			try:
				callback(*args, **kwargs)
			except Exception as exc:
				print(f"UI event failed: {exc}")
			processed += 1
		if self.winfo_exists():
			self.after(50, self.process_ui_events)

	def ask_yes_no(self, title: str, message: str) -> bool:
		if threading.current_thread() is threading.main_thread():
			return messagebox.askyesno(title, message)

		done = threading.Event()
		ans = {"val": False}

		def ask():
			try:
				ans["val"] = messagebox.askyesno(title, message)
			finally:
				done.set()

		self.post_to_ui(ask)
		done.wait()
		return ans["val"]

	def on_closing(self):
		# Save current UI settings before exit
		tt = self.translate_tab
		self.settings["input_file"] = tt.entry_input.get().strip()
		self.settings["output_file"] = tt.entry_output.get().strip()
		self.settings["model"] = tt.combo_model.get()
		self.settings["thinking_level"] = tt.combo_thinking.get()
		self.settings["threads"] = tt.entry_threads.get().strip()
		self.settings["chunk_size"] = tt.entry_chunk_size.get().strip()
		self.settings["temperature"] = tt.entry_temp.get().strip()
		self.settings["chunk_split_mode"] = tt.combo_split_mode.get()
		self.settings["prompt"] = tt.txt_prompt.get("1.0", "end-1c").strip()
		self.settings["glossary"] = tt.txt_glossary.get("1.0", "end-1c").strip()
		self.settings["model_fallback_order"] = tt.fallback_order_str
		self.settings["theme"] = "dark" if self.switch_theme.get() == 1 else "light"
		self.settings["drive_upload_enabled"] = bool(tt.chk_drive.get())

		curr_key = tt.entry_api_key.get().strip()
		if curr_key:
			keys_dict = self.settings.get("api_keys", {})
			keys_dict["Mặc định"] = curr_key
			self.settings["api_keys"] = keys_dict

		save_settings(self.settings)

		# Stop active background translation if running
		tt.engine.stop()
		self.destroy()
