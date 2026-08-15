import os
import threading
import concurrent.futures
import time
import customtkinter as ctk
from tkinter import filedialog, messagebox
from core.config import MODELS, CHUNK_SIZE, MAX_OUTPUT_TOKENS, DEFAULT_SCAN_CHAR_LIMIT, DEFAULT_PROMPT, USD_TO_VND
from core.text_helpers import build_default_output_path, read_file_content_safely, write_text_atomically, get_checkpoint_path, get_translation_cache_path, get_failed_chunks_path, format_time
from core.chunker import split_text
from core.glossary import parse_glossary, build_prompt_with_glossary, normalize_scanned_glossary, build_scan_segments
from core.checkpoint import build_checkpoint_metadata, read_checkpoint_data, reset_checkpoint, checkpoint_matches, load_current_failed_chunks
from core.history import save_translation_history_entry, get_request_metrics_snapshot, reset_request_metrics
from core.translator import TranslationEngine, is_gemini_v3_or_above
from core.drive_sync import upload_file_to_drive
from ui.dialogs.fallback_dialog import FallbackDialog

class TranslateTab(ctk.CTkFrame):
	def __init__(self, parent, main_app):
		super().__init__(parent)
		self.main_app = main_app
		self.engine = TranslationEngine(log_callback=self.add_log)
		self.fallback_order_str = "|".join(MODELS)

		self._build_ui()

	def add_log(self, message: str):
		self.main_app.post_to_ui(self._add_log_ui, message)

	def _add_log_ui(self, message: str):
		timestamp = time.strftime("[%H:%M:%S] ")
		self.txt_log.configure(state="normal")
		self.txt_log.insert("end", timestamp + message + "\n")
		self.txt_log.see("end")
		self.txt_log.configure(state="disabled")

	def _build_ui(self):
		# Split layout into left controls (scrollable) and right logs/stats
		self.grid_columnconfigure(0, weight=4)
		self.grid_columnconfigure(1, weight=5)
		self.grid_rowconfigure(0, weight=1)

		# Left Panel (Settings)
		left_frame = ctk.CTkScrollableFrame(self, label_text="⚙️ CẤU HÌNH DỊCH TRUYỆN")
		left_frame.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

		# 1. API Key Section
		sec_key = ctk.CTkFrame(left_frame)
		sec_key.pack(fill="x", padx=10, pady=5)
		ctk.CTkLabel(sec_key, text="🔑 Gemini API Key:", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=10, pady=(5, 2))

		row_key = ctk.CTkFrame(sec_key, fg_color="transparent")
		row_key.pack(fill="x", padx=10, pady=(0, 5))

		self.combo_key_profile = ctk.CTkOptionMenu(row_key, values=["Mặc định"], width=130, command=self._on_key_profile_change)
		self.combo_key_profile.pack(side="left", padx=(0, 5))

		self.entry_api_key = ctk.CTkEntry(row_key, show="*", placeholder_text="Nhập API Key tại đây...")
		self.entry_api_key.pack(side="left", fill="x", expand=True, padx=5)

		self.btn_show_key = ctk.CTkButton(row_key, text="👁️", width=35, command=self._toggle_key_visibility)
		self.btn_show_key.pack(side="left", padx=2)

		self.btn_add_key = ctk.CTkButton(row_key, text="+", width=30, command=self._add_key_profile)
		self.btn_add_key.pack(side="left", padx=2)

		# 2. File Selection Section
		sec_file = ctk.CTkFrame(left_frame)
		sec_file.pack(fill="x", padx=10, pady=5)
		ctk.CTkLabel(sec_file, text="📁 File Truyện Đầu Vào & Đầu Ra:", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=10, pady=(5, 2))

		# Input
		row_in = ctk.CTkFrame(sec_file, fg_color="transparent")
		row_in.pack(fill="x", padx=10, pady=2)
		ctk.CTkLabel(row_in, text="Input:", width=50).pack(side="left")
		self.entry_input = ctk.CTkEntry(row_in, placeholder_text="Chọn file truyện .txt...")
		self.entry_input.pack(side="left", fill="x", expand=True, padx=5)
		ctk.CTkButton(row_in, text="📂 Chọn", width=70, command=self._browse_input).pack(side="left")

		# Output
		row_out = ctk.CTkFrame(sec_file, fg_color="transparent")
		row_out.pack(fill="x", padx=10, pady=(2, 5))
		ctk.CTkLabel(row_out, text="Output:", width=50).pack(side="left")
		self.entry_output = ctk.CTkEntry(row_out, placeholder_text="Tự động tạo file đầu ra...")
		self.entry_output.pack(side="left", fill="x", expand=True, padx=5)
		ctk.CTkButton(row_out, text="📂 Lưu", width=70, command=self._browse_output).pack(side="left")

		# 3. Model & Hyperparameters Section
		sec_param = ctk.CTkFrame(left_frame)
		sec_param.pack(fill="x", padx=10, pady=5)
		ctk.CTkLabel(sec_param, text="🤖 Model & Tham số Dịch:", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=10, pady=(5, 2))

		grid_p = ctk.CTkFrame(sec_param, fg_color="transparent")
		grid_p.pack(fill="x", padx=10, pady=5)

		# Model
		ctk.CTkLabel(grid_p, text="Model Dịch:").grid(row=0, column=0, sticky="w", pady=3)
		self.combo_model = ctk.CTkOptionMenu(grid_p, values=MODELS, width=200, command=self._on_model_select)
		self.combo_model.grid(row=0, column=1, sticky="w", padx=5, pady=3)

		self.btn_fallback = ctk.CTkButton(grid_p, text="⚡ Fallback", width=80, fg_color="#6272a4", command=self._open_fallback_dialog)
		self.btn_fallback.grid(row=0, column=2, sticky="w", padx=5, pady=3)

		# Thinking level
		ctk.CTkLabel(grid_p, text="Thinking Level:").grid(row=1, column=0, sticky="w", pady=3)
		self.combo_thinking = ctk.CTkOptionMenu(grid_p, values=["minimal", "low", "medium", "high"], width=130)
		self.combo_thinking.set("medium")
		self.combo_thinking.grid(row=1, column=1, sticky="w", padx=5, pady=3)

		# Threads & Chunk Size
		ctk.CTkLabel(grid_p, text="Số luồng (1-20):").grid(row=2, column=0, sticky="w", pady=3)
		self.entry_threads = ctk.CTkEntry(grid_p, width=80)
		self.entry_threads.insert(0, "3")
		self.entry_threads.grid(row=2, column=1, sticky="w", padx=5, pady=3)

		ctk.CTkLabel(grid_p, text="Chunk Size:").grid(row=3, column=0, sticky="w", pady=3)
		self.entry_chunk_size = ctk.CTkEntry(grid_p, width=100)
		self.entry_chunk_size.insert(0, str(CHUNK_SIZE))
		self.entry_chunk_size.grid(row=3, column=1, sticky="w", padx=5, pady=3)

		# Temperature & Max tokens
		ctk.CTkLabel(grid_p, text="Nhiệt độ (0-1):").grid(row=4, column=0, sticky="w", pady=3)
		self.entry_temp = ctk.CTkEntry(grid_p, width=80)
		self.entry_temp.insert(0, "0.5")
		self.entry_temp.grid(row=4, column=1, sticky="w", padx=5, pady=3)

		# Split Mode
		ctk.CTkLabel(grid_p, text="Chế độ tách:").grid(row=5, column=0, sticky="w", pady=3)
		self.combo_split_mode = ctk.CTkOptionMenu(grid_p, values=["keyword", "equals"], width=130)
		self.combo_split_mode.grid(row=5, column=1, sticky="w", padx=5, pady=3)

		# 4. Prompt & Glossary Section
		sec_prompt = ctk.CTkFrame(left_frame)
		sec_prompt.pack(fill="x", padx=10, pady=5)

		row_pr_head = ctk.CTkFrame(sec_prompt, fg_color="transparent")
		row_pr_head.pack(fill="x", padx=10, pady=(5, 2))
		ctk.CTkLabel(row_pr_head, text="📝 Prompt Dịch giả:", font=("Segoe UI", 12, "bold")).pack(side="left")
		self.combo_prompt_profile = ctk.CTkOptionMenu(row_pr_head, values=["Mặc định"], width=130, command=self._on_prompt_profile_change)
		self.combo_prompt_profile.pack(side="right")

		self.txt_prompt = ctk.CTkTextbox(sec_prompt, height=90)
		self.txt_prompt.pack(fill="x", padx=10, pady=5)
		self.txt_prompt.insert("1.0", DEFAULT_PROMPT)

		# Glossary
		ctk.CTkLabel(sec_prompt, text="📖 Glossary (Thuật ngữ: nguồn => đích):", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=(5, 2))
		self.txt_glossary = ctk.CTkTextbox(sec_prompt, height=80)
		self.txt_glossary.pack(fill="x", padx=10, pady=5)

		row_scan = ctk.CTkFrame(sec_prompt, fg_color="transparent")
		row_scan.pack(fill="x", padx=10, pady=(0, 5))
		self.entry_scan_limit = ctk.CTkEntry(row_scan, width=80)
		self.entry_scan_limit.insert(0, str(DEFAULT_SCAN_CHAR_LIMIT))
		self.entry_scan_limit.pack(side="left", padx=5)
		ctk.CTkLabel(row_scan, text="Ký tự quét").pack(side="left")
		ctk.CTkButton(row_scan, text="🔍 Scan Truyện", fg_color="#6272a4", width=110, command=self._scan_story).pack(side="right")

		# 5. Drive Backup Option
		sec_drive = ctk.CTkFrame(left_frame)
		sec_drive.pack(fill="x", padx=10, pady=5)
		self.chk_drive = ctk.CTkCheckBox(sec_drive, text="☁️ Tự động Upload Google Drive sau khi dịch xong")
		self.chk_drive.pack(anchor="w", padx=10, pady=5)

		# Right Panel (Status & Controls)
		right_frame = ctk.CTkFrame(self)
		right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
		right_frame.grid_rowconfigure(2, weight=1)
		right_frame.grid_columnconfigure(0, weight=1)

		# Action Buttons Bar
		frame_btns = ctk.CTkFrame(right_frame)
		frame_btns.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

		self.btn_start = ctk.CTkButton(
			frame_btns,
			text="🚀 BẮT ĐẦU DỊCH",
			font=("Segoe UI", 14, "bold"),
			fg_color="#28a745",
			hover_color="#218838",
			height=42,
			command=self.start_translation
		)
		self.btn_start.pack(side="left", fill="x", expand=True, padx=5)

		self.btn_pause = ctk.CTkButton(
			frame_btns,
			text="⏸️ TẠM DỪNG",
			font=("Segoe UI", 12, "bold"),
			fg_color="#ff9500",
			hover_color="#e08300",
			height=42,
			state="disabled",
			command=self.toggle_pause
		)
		self.btn_pause.pack(side="left", padx=5)

		self.btn_stop = ctk.CTkButton(
			frame_btns,
			text="🛑 DỪNG HẲN",
			font=("Segoe UI", 12, "bold"),
			fg_color="#dc3545",
			hover_color="#c82333",
			height=42,
			state="disabled",
			command=self.stop_translation
		)
		self.btn_stop.pack(side="left", padx=5)

		# Metrics & Cards Grid
		frame_cards = ctk.CTkFrame(right_frame)
		frame_cards.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

		self.lbl_progress_status = ctk.CTkLabel(frame_cards, text="Tiến độ: 0/0 chunks (0%)", font=("Segoe UI", 13, "bold"))
		self.lbl_progress_status.pack(anchor="w", padx=10, pady=(5, 2))

		self.progress_bar = ctk.CTkProgressBar(frame_cards)
		self.progress_bar.set(0)
		self.progress_bar.pack(fill="x", padx=10, pady=5)

		grid_metrics = ctk.CTkFrame(frame_cards, fg_color="transparent")
		grid_metrics.pack(fill="x", padx=10, pady=5)
		grid_metrics.grid_columnconfigure((0, 1, 2), weight=1)

		self.card_time = self._create_metric_card(grid_metrics, "⏱️ Thời gian", "0s", 0, 0)
		self.card_tokens = self._create_metric_card(grid_metrics, "🪙 Tokens In/Out", "0 / 0", 0, 1)
		self.card_cost = self._create_metric_card(grid_metrics, "💰 Chi phí (USD / VNĐ)", "$0.00 (0 đ)", 0, 2)

		# Log Terminal
		ctk.CTkLabel(right_frame, text="📜 Nhật Ký Tiến Trình (Log):", font=("Segoe UI", 12, "bold")).grid(row=2, column=0, sticky="nw", padx=10, pady=(10, 2))
		self.txt_log = ctk.CTkTextbox(right_frame, font=("Consolas", 10), state="disabled")
		self.txt_log.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))

	def _create_metric_card(self, parent, title, value, row, col):
		card = ctk.CTkFrame(parent)
		card.grid(row=row, column=col, sticky="ew", padx=5, pady=5)
		ctk.CTkLabel(card, text=title, font=("Segoe UI", 10), text_color="#6272a4").pack(anchor="w", padx=8, pady=(4, 0))
		lbl_val = ctk.CTkLabel(card, text=value, font=("Segoe UI", 12, "bold"))
		lbl_val.pack(anchor="w", padx=8, pady=(0, 4))
		return lbl_val

	def _toggle_key_visibility(self):
		if self.entry_api_key.cget("show") == "*":
			self.entry_api_key.configure(show="")
			self.btn_show_key.configure(text="🙈")
		else:
			self.entry_api_key.configure(show="*")
			self.btn_show_key.configure(text="👁️")

	def _on_key_profile_change(self, choice):
		pass

	def _add_key_profile(self):
		pass

	def _on_prompt_profile_change(self, choice):
		pass

	def _on_model_select(self, selected_model):
		if is_gemini_v3_or_above(selected_model):
			self.combo_thinking.configure(state="normal")
		else:
			self.combo_thinking.configure(state="disabled")

	def _open_fallback_dialog(self):
		def on_save(order_str):
			self.fallback_order_str = order_str
			self.add_log(f"⚙️ Đã cập nhật chuỗi Fallback Model: {order_str}")
		FallbackDialog(self, self.fallback_order_str, on_save)

	def _browse_input(self):
		path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
		if path:
			self.entry_input.delete(0, "end")
			self.entry_input.insert(0, path)
			if not self.entry_output.get().strip():
				def_out = build_default_output_path(path, self.combo_model.get())
				self.entry_output.delete(0, "end")
				self.entry_output.insert(0, def_out)

	def _browse_output(self):
		path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt")])
		if path:
			self.entry_output.delete(0, "end")
			self.entry_output.insert(0, path)

	def toggle_pause(self):
		if self.engine.is_paused:
			self.engine.resume()
			self.btn_pause.configure(text="⏸️ TẠM DỪNG", fg_color="#ff9500")
			self.add_log("▶️ Đã tiếp tục dịch...")
		else:
			self.engine.pause()
			self.btn_pause.configure(text="▶️ TIẾP TỤC", fg_color="#28a745")
			self.add_log("⏸️ Đã tạm dừng dịch...")

	def stop_translation(self):
		if messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn dừng hẳn tiến trình dịch?"):
			self.engine.stop()
			self.add_log("🛑 Đang dừng hẳn tiến trình dịch...")
			self.btn_start.configure(state="normal")
			self.btn_pause.configure(state="disabled")
			self.btn_stop.configure(state="disabled")

	def _scan_story(self):
		in_file = self.entry_input.get().strip()
		api_key = self.entry_api_key.get().strip()
		if not in_file or not os.path.exists(in_file):
			messagebox.showerror("Lỗi", "Vui lòng chọn file đầu vào hợp lệ.")
			return
		if not api_key:
			messagebox.showerror("Lỗi", "Vui lòng nhập API Key.")
			return

		limit = int(self.entry_scan_limit.get() or "10000")
		model_id = self.combo_model.get()
		temp = float(self.entry_temp.get() or "0.5")

		self.add_log(f"🔍 Đang quét thuật ngữ (tối đa {limit:,} ký tự)...")

		def run():
			full_text = read_file_content_safely(in_file)[:limit]
			scan_prompt = (
				"Bạn là chuyên gia biên tập truyện dịch từ Trung sang Việt.\n"
				"Hãy trích xuất danh sách thuật ngữ quan trọng từ đoạn sau để đưa vào từ điển (Glossary).\n"
				"ĐỊNH DẠNG BẮT BUỘC: mỗi dòng một mục theo mẫu: Nguồn => Đích\n\n"
			)
			res, _, _, err = self.engine.translate_with_gemini(
				model_id=model_id,
				prompt=scan_prompt,
				chunk=full_text,
				temperature=temp,
				max_output_tokens=4000,
				api_key=api_key
			)
			if res:
				norm = normalize_scanned_glossary(res)
				self.main_app.post_to_ui(self._on_scan_finish, norm)
			else:
				self.main_app.post_to_ui(lambda: messagebox.showerror("Lỗi", f"Quét thất bại: {err}"))

		threading.Thread(target=run, daemon=True).start()

	def _on_scan_finish(self, scanned_text):
		if scanned_text:
			curr = self.txt_glossary.get("1.0", "end-1c").strip()
			new_glossary = (curr + "\n" + scanned_text).strip() if curr else scanned_text
			self.txt_glossary.delete("1.0", "end")
			self.txt_glossary.insert("1.0", new_glossary)
			self.add_log(f"✅ Quét hoàn tất! Đã thêm thuật ngữ vào Glossary.")
			messagebox.showinfo("Thành công", "Đã trích xuất thuật ngữ vào Glossary!")

	def start_translation(self):
		api_key = self.entry_api_key.get().strip()
		in_file = self.entry_input.get().strip()
		out_file = self.entry_output.get().strip()

		if not api_key or not in_file or not os.path.exists(in_file):
			messagebox.showerror("Lỗi", "Vui lòng kiểm tra lại API Key và file đầu vào.")
			return

		if not out_file:
			out_file = build_default_output_path(in_file, self.combo_model.get())
			self.entry_output.delete(0, "end")
			self.entry_output.insert(0, out_file)

		threads = int(self.entry_threads.get() or "3")
		chunk_size = int(self.entry_chunk_size.get() or "70000")
		max_tokens = int(self.combo_model.cget("text") and MAX_OUTPUT_TOKENS)
		temp = float(self.entry_temp.get() or "0.5")
		split_mode = self.combo_split_mode.get()
		model_id = self.combo_model.get()
		thinking_level = self.combo_thinking.get()
		prompt_base = self.txt_prompt.get("1.0", "end-1c").strip()
		glossary_raw = self.txt_glossary.get("1.0", "end-1c").strip()

		glossary_entries = parse_glossary(glossary_raw)
		full_prompt = build_prompt_with_glossary(prompt_base, glossary_entries)

		self.btn_start.configure(state="disabled")
		self.btn_pause.configure(state="normal", text="⏸️ TẠM DỪNG", fg_color="#ff9500")
		self.btn_stop.configure(state="normal")

		def worker():
			self.add_log(f"🚀 Khởi tạo bản dịch: {os.path.basename(in_file)}")
			text_content = read_file_content_safely(in_file)
			chunks = split_text(text_content, size=chunk_size, split_mode=split_mode)
			total_chunks = len(chunks)

			self.engine.reset_stats(total_chunks)
			reset_request_metrics()

			cp_file = get_checkpoint_path(in_file)
			cache_file = get_translation_cache_path(in_file)
			failed_file = get_failed_chunks_path(in_file)

			expected_metadata = build_checkpoint_metadata(text_content, chunk_size, split_mode, total_chunks)
			cp_metadata, cp_data = read_checkpoint_data(cp_file)

			translated_map = {}
			if cp_data and checkpoint_matches(cp_metadata, expected_metadata):
				ans = self.main_app.ask_yes_no("Checkpoint Resume", f"Tìm thấy bản dịch dở dang ({len(cp_data)}/{total_chunks} chunks). Bạn muốn dịch tiếp không?")
				if ans:
					translated_map = dict(cp_data)
					self.engine.stats["chunks_done"] = len(translated_map)
				else:
					reset_checkpoint(cp_file, expected_metadata)
			else:
				reset_checkpoint(cp_file, expected_metadata)

			fallback_order = [m.strip() for m in self.fallback_order_str.split("|") if m.strip()]
			if model_id not in fallback_order:
				fallback_order.insert(0, model_id)

			pending_indices = [i for i in range(total_chunks) if str(i) not in translated_map]
			self.add_log(f"📊 Tổng số: {total_chunks} chunks ({len(pending_indices)} cần dịch, {threads} luồng)")

			# Periodic Stats Update
			stop_stats_flag = threading.Event()
			def stats_loop():
				while not stop_stats_flag.is_set():
					self.main_app.post_to_ui(self._update_stats_ui)
					time.sleep(1)

			threading.Thread(target=stats_loop, daemon=True).start()

			with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
				futures = {}
				for idx in pending_indices:
					if self.engine.is_stopped:
						break
					chunk_text = chunks[idx]
					fut = executor.submit(
						self.engine.translate_chunk,
						model_id=model_id,
						prompt=full_prompt,
						chunk=chunk_text,
						index=idx,
						cp_file=cp_file,
						temperature=temp,
						max_output_tokens=max_tokens,
						model_fallback_order=fallback_order,
						retries=3,
						failed_file=failed_file,
						api_key=api_key,
						thinking_level=thinking_level
					)
					futures[fut] = idx

				for fut in concurrent.futures.as_completed(futures):
					idx, res = fut.result()
					if res:
						translated_map[str(idx)] = res

			stop_stats_flag.set()
			self.main_app.post_to_ui(self._update_stats_ui)

			# Finish assembly
			if len(translated_map) == total_chunks:
				full_output = "\n\n".join([translated_map[str(i)] for i in range(total_chunks)])
				write_text_atomically(out_file, full_output)
				write_text_atomically(cache_file, full_output)
				if os.path.exists(cp_file):
					try:
						os.remove(cp_file)
					except Exception:
						pass

				entry = {
					"start_at": time.strftime("%Y-%m-%d %H:%M:%S"),
					"input_file": in_file,
					"output_file": out_file,
					"model": model_id,
					"total_chunks": total_chunks,
					"total_tokens": self.engine.stats["total_input_tokens"] + self.engine.stats["total_output_tokens"],
					"total_cost_usd": self.engine.stats["total_cost_usd"],
					"request_counts_by_minute": get_request_metrics_snapshot()
				}
				save_translation_history_entry(entry)

				self.add_log(f"🎉 HOÀN THÀNH TOÀN BỘ BẢN DỊCH! File xuất: {out_file}")
				self.main_app.post_to_ui(lambda: messagebox.showinfo("Thành công", f"Đã dịch xong {total_chunks} chunks!\nLưu tại: {out_file}"))
			else:
				self.add_log(f"⚠️ Dịch chưa hoàn tất ({len(translated_map)}/{total_chunks} chunks). Tiến trình đã được lưu checkpoint.")

			self.main_app.post_to_ui(self._reset_action_buttons)

		threading.Thread(target=worker, daemon=True).start()

	def _update_stats_ui(self):
		st = self.engine.stats
		done = st["chunks_done"]
		total = st["total_chunks"] or 1
		pct = done / total
		self.progress_bar.set(pct)
		self.lbl_progress_status.configure(text=f"Tiến độ: {done}/{total} chunks ({int(pct * 100)}%)")

		elapsed = time.time() - st["start_time"] if st["start_time"] else 0
		self.card_time.configure(text=format_time(elapsed))

		in_tok = st["total_input_tokens"]
		out_tok = st["total_output_tokens"]
		self.card_tokens.configure(text=f"{in_tok:,} / {out_tok:,}")

		cost_usd = st["total_cost_usd"]
		cost_vnd = int(cost_usd * USD_TO_VND)
		self.card_cost.configure(text=f"${cost_usd:.4f} ({cost_vnd:,} đ)")

	def _reset_action_buttons(self):
		self.btn_start.configure(state="normal")
		self.btn_pause.configure(state="disabled", text="⏸️ TẠM DỪNG")
		self.btn_stop.configure(state="disabled")
