import concurrent.futures
import json
import os
import random
import re
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
from tkinter import filedialog, messagebox, scrolledtext, ttk


# ================= CẤU HÌNH LOCAL API =================
LOCAL_MODELS = [
	"gemma-4-e2b",
	"gemma-4-e4b-uncensored-hauhaucs-aggressive",
	"gemma-3-12b-it",
	"gemma-2-9b-it",
	"qwen3.5-4b",
]

DEFAULT_ENDPOINT = "http://localhost:1234/v1/chat/completions"
CHUNK_SIZE = 3000
MAX_OUTPUT_TOKENS = 2048
DEFAULT_SCAN_CHAR_LIMIT = 10000

DEFAULT_PROMPT = (
	"Bạn là một biên tập viên truyện dịch chuyên nghiệp, thành thạo tiếng Trung và tiếng Việt.\n"
	"Nhiệm vụ của bạn là viết lại đoạn văn sau thành tiếng Việt thuần, tự nhiên, mượt mà, "
	"loại bỏ cảm giác máy dịch, sao cho đọc giống truyện Việt.\n"
	"Không dịch sát từng chữ, ưu tiên ý nghĩa, ngữ cảnh và cảm xúc.\n"
	"Cho phép gộp hoặc tách câu, điều chỉnh trật tự câu cho phù hợp tiếng Việt.\n"
	"Giữ nguyên nội dung, nhân vật, xưng hô, bối cảnh và ý nghĩa gốc.\n"
	"Không thêm nội dung mới, không lược bỏ nội dung.\n"
	"Không giải thích, không bình luận.\n"
	"Giữ cách xuống dòng và bố cục đoạn văn hợp lý như truyện.\n"
)

DEFAULT_GLOSSARY = ""


# ================= BIẾN ĐIỀU KHIỂN =================
is_paused = False
is_stopped = False
pause_event = threading.Event()
pause_event.set()


# ================= THỐNG KÊ =================
stats = {
	"start_time": 0,
	"chunks_done": 0,
	"total_chunks": 0,
	"total_input_chars": 0,
	"total_output_chars": 0,
	"total_input_tokens": 0,
	"total_output_tokens": 0,
}


current_theme = "dark"
THEMES = {
	"dark": {
		"bg": "#0f172a",
		"panel": "#111827",
		"border": "#1f2937",
		"text": "#e5e7eb",
		"text_muted": "#9ca3af",
		"accent": "#f59e0b",
		"accent_alt": "#38bdf8",
		"input_bg": "#0b1220",
		"warn": "#f87171",
		"ok": "#34d399",
		"gradient_start": "#0f172a",
		"gradient_end": "#1f2937",
	},
	"light": {
		"bg": "#f8fafc",
		"panel": "#ffffff",
		"border": "#e2e8f0",
		"text": "#1e293b",
		"text_muted": "#64748b",
		"accent": "#f59e0b",
		"accent_alt": "#0ea5e9",
		"input_bg": "#f1f5f9",
		"warn": "#ef4444",
		"ok": "#10b981",
		"gradient_start": "#f8fafc",
		"gradient_end": "#e2e8f0",
	},
}
PALETTE = THEMES["dark"]


SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_settings_local.json")
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translation_history_local.json")


def load_settings():
	default_settings = {
		"endpoint": DEFAULT_ENDPOINT,
		"input_file": "",
		"output_file": "",
		"model": LOCAL_MODELS[0],
		"threads": "3",
		"chunk_size": str(CHUNK_SIZE),
		"max_output_tokens": str(MAX_OUTPUT_TOKENS),
		"scan_char_limit": str(DEFAULT_SCAN_CHAR_LIMIT),
		"temperature": "0.7",
		"prompt": DEFAULT_PROMPT,
		"glossary": DEFAULT_GLOSSARY,
		"theme": "dark",
	}

	try:
		if os.path.exists(SETTINGS_FILE):
			with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
				saved = json.load(f)
				default_settings.update(saved)
	except Exception as exc:
		print(f"Không thể tải cài đặt: {exc}")

	return default_settings


def save_settings():
	settings = {
		"endpoint": endpoint_var.get().strip(),
		"input_file": input_path.get(),
		"output_file": output_path.get(),
		"model": model_var.get(),
		"threads": thread_var.get(),
		"chunk_size": chunk_size_var.get(),
		"max_output_tokens": max_output_tokens_var.get(),
		"scan_char_limit": scan_char_limit_var.get(),
		"temperature": temp_var.get(),
		"glossary": glossary_text.get("1.0", tk.END).strip(),
		"prompt": prompt_text.get("1.0", tk.END).strip(),
		"theme": current_theme,
	}

	try:
		with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
			json.dump(settings, f, ensure_ascii=False, indent=2)
		add_log("💾 Đã lưu cài đặt local app.")
	except Exception as exc:
		add_log(f"⚠️ Lỗi lưu cài đặt: {exc}")


def apply_settings(settings):
	global current_theme

	endpoint_var.set(settings.get("endpoint", DEFAULT_ENDPOINT))
	input_path.set(settings.get("input_file", ""))
	output_path.set(settings.get("output_file", ""))
	model_var.set(settings.get("model", LOCAL_MODELS[0]))
	thread_var.set(settings.get("threads", "3"))
	chunk_size_var.set(settings.get("chunk_size", str(CHUNK_SIZE)))
	max_output_tokens_var.set(settings.get("max_output_tokens", str(MAX_OUTPUT_TOKENS)))
	scan_char_limit_var.set(settings.get("scan_char_limit", str(DEFAULT_SCAN_CHAR_LIMIT)))
	temp_var.set(settings.get("temperature", "0.7"))

	glossary_text.delete("1.0", tk.END)
	glossary_text.insert(tk.END, settings.get("glossary", DEFAULT_GLOSSARY))

	prompt_text.delete("1.0", tk.END)
	prompt_text.insert(tk.END, settings.get("prompt", DEFAULT_PROMPT))

	current_theme = settings.get("theme", "dark")


def on_closing():
	save_settings()
	root.destroy()


def get_checkpoint_path(input_file):
	base_name = os.path.splitext(input_file)[0]
	return f"{base_name}.resume_local.json"


def build_default_output_path(input_file):
	input_dir = os.path.dirname(input_file)
	input_name = os.path.splitext(os.path.basename(input_file))[0]
	random_suffix = random.randint(1000, 9999)
	return os.path.join(input_dir, f"DichLocal_{input_name}_{random_suffix}.txt")


def add_log(message):
	timestamp = time.strftime("%H:%M:%S")
	log_message = f"[{timestamp}] {message}\n"

	def _append():
		if "log_box" in globals() and log_box.winfo_exists():
			log_box.config(state="normal")
			log_box.insert(tk.END, log_message)
			log_box.see(tk.END)
			log_box.config(state="disabled")

	if threading.current_thread() is threading.main_thread():
		_append()
	else:
		try:
			if "root" in globals() and root.winfo_exists():
				root.after(0, _append)
		except Exception:
			pass

	print(log_message.strip())


def format_time(seconds):
	if seconds < 0:
		return "--:--"
	hours = int(seconds // 3600)
	minutes = int((seconds % 3600) // 60)
	secs = int(seconds % 60)
	if hours > 0:
		return f"{hours:02d}:{minutes:02d}:{secs:02d}"
	return f"{minutes:02d}:{secs:02d}"


def parse_glossary(raw_text):
	entries = []
	if not raw_text:
		return entries

	for line in raw_text.splitlines():
		clean = line.strip()
		if not clean or clean.startswith("#"):
			continue

		separator = None
		for candidate in ["=>", "->", ":"]:
			if candidate in clean:
				separator = candidate
				break

		if not separator:
			continue

		source, target = clean.split(separator, 1)
		source = source.strip()
		target = target.strip()
		if source and target:
			entries.append((source, target))

	return entries


def build_prompt_with_glossary(base_prompt, glossary_entries):
	if not glossary_entries:
		return base_prompt

	glossary_lines = "\n".join([f"- {src} => {dst}" for src, dst in glossary_entries])
	glossary_instruction = (
		"\nQUY TẮC THUẬT NGỮ BẮT BUỘC (ƯU TIÊN CAO):\n"
		"- Khi gặp thuật ngữ ở cột trái, phải dùng đúng thuật ngữ cột phải.\n"
		"- Giữ nhất quán tuyệt đối toàn bộ chương và các chương tiếp theo.\n"
		"- Không tự ý đổi biến thể khác nếu glossary đã quy định.\n"
		f"{glossary_lines}\n"
	)
	return f"{base_prompt}\n{glossary_instruction}"


def save_checkpoint(cp_file, index, text):
	try:
		if os.path.exists(cp_file):
			with open(cp_file, "r", encoding="utf-8") as f:
				data = json.load(f)
		else:
			data = {}

		data[str(index)] = text

		with open(cp_file, "w", encoding="utf-8") as f:
			json.dump(data, f, ensure_ascii=False, indent=2)
	except Exception as exc:
		print(f"Lỗi lưu checkpoint: {exc}")


def load_translation_history():
	try:
		if os.path.exists(HISTORY_FILE):
			with open(HISTORY_FILE, "r", encoding="utf-8") as f:
				data = json.load(f)
				if isinstance(data, list):
					return data
	except Exception as exc:
		print(f"Không thể tải lịch sử dịch: {exc}")
	return []


def save_translation_history_entry(entry, max_entries=200):
	try:
		history = load_translation_history()
		history.append(entry)
		history = history[-max_entries:]
		with open(HISTORY_FILE, "w", encoding="utf-8") as f:
			json.dump(history, f, ensure_ascii=False, indent=2)
	except Exception as exc:
		print(f"Không thể lưu lịch sử dịch: {exc}")


def refresh_history_display():
	if "history_table" not in globals():
		return

	for row_id in history_table.get_children():
		history_table.delete(row_id)

	history = load_translation_history()
	if not history:
		history_hint_var.set("Chưa có lịch sử dịch.")
		return

	history_hint_var.set("Hiển thị 20 lần dịch gần nhất.")
	recent = history[-20:]
	for idx, item in enumerate(reversed(recent), 1):
		start_at = item.get("start_at", "--")
		status = item.get("status", "--")
		model = item.get("model", "--")
		in_file = os.path.basename(item.get("input_file", ""))
		out_file = os.path.basename(item.get("output_file", ""))
		duration = format_time(item.get("duration_seconds", 0))
		chunks_done = item.get("chunks_done", 0)
		total_chunks = item.get("total_chunks", 0)
		input_chars = item.get("total_input_chars", 0)
		output_chars = item.get("total_output_chars", 0)
		input_tokens = item.get("total_input_tokens", 0)
		output_tokens = item.get("total_output_tokens", 0)
		threads = item.get("threads", "--")
		temperature = item.get("temperature", "--")
		error = item.get("error", "")
		tokens_text = f"in {input_tokens:,} | out {output_tokens:,}"
		meta_text = f"{threads} luồng | temp {temperature}"
		error_text = (error[:80] + "...") if len(error) > 80 else error
		row_tag = "even" if idx % 2 == 0 else "odd"
		status_tag = f"status_{status.lower()}"

		history_table.insert(
			"",
			tk.END,
			values=(
				start_at,
				status.upper(),
				model,
				f"{chunks_done}/{total_chunks}",
				f"{input_chars:,} → {output_chars:,}",
				tokens_text,
				duration,
				meta_text,
				f"{in_file} → {out_file}",
				error_text,
			),
			tags=(row_tag, status_tag),
		)


def clear_translation_history():
	if not messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa toàn bộ lịch sử dịch?"):
		return

	try:
		with open(HISTORY_FILE, "w", encoding="utf-8") as f:
			json.dump([], f, ensure_ascii=False, indent=2)
		refresh_history_display()
		add_log("🧹 Đã xóa toàn bộ lịch sử dịch.")
	except Exception as exc:
		messagebox.showerror("Lỗi", f"Không thể xóa lịch sử dịch: {exc}")


def update_stats_display():
	if stats["total_chunks"] == 0:
		return

	elapsed = time.time() - stats["start_time"]
	done = stats["chunks_done"]
	total = stats["total_chunks"]
	remaining = total - done

	if done > 0:
		avg_time_per_chunk = elapsed / done
		eta = avg_time_per_chunk * remaining
		speed = done / (elapsed / 60) if elapsed > 0 else 0
	else:
		eta = -1
		speed = 0

	stats_time_var.set(f"⏱️ Đã chạy: {format_time(elapsed)}")
	stats_eta_var.set(f"⏳ Còn lại: {format_time(eta)}")
	stats_speed_var.set(f"🚀 Tốc độ: {speed:.1f} đoạn/phút")
	stats_chars_var.set(f"📝 Ký tự: {stats['total_input_chars']:,} → {stats['total_output_chars']:,}")
	stats_input_tokens_var.set(f"🔢 Input Token: {stats['total_input_tokens']:,}")
	stats_output_tokens_var.set(f"🔢 Output Token: {stats['total_output_tokens']:,}")


def toggle_theme():
	global current_theme, PALETTE

	current_theme = "light" if current_theme == "dark" else "dark"
	PALETTE = THEMES[current_theme]

	apply_theme()
	draw_gradient()

	theme_icon = "🌙" if current_theme == "dark" else "☀️"
	btn_theme.config(text=f"{theme_icon} {'Tối' if current_theme == 'dark' else 'Sáng'}")
	add_log(f"🎨 Đã chuyển sang chế độ {'tối' if current_theme == 'dark' else 'sáng'}")


def apply_theme():
	root.configure(bg=PALETTE["bg"])
	canvas_bg.configure(bg=PALETTE["bg"])
	main_container.configure(bg=PALETTE["bg"])
	main_frame.configure(bg=PALETTE["bg"])
	header.configure(bg=PALETTE["bg"])
	header_top.configure(bg=PALETTE["bg"])
	header_title_frame.configure(bg=PALETTE["bg"])
	badge_row.configure(bg=PALETTE["bg"])

	style.configure("Card.TFrame", background=PALETTE["panel"])
	style.configure("TLabel", background=PALETTE["panel"], foreground=PALETTE["text"])
	style.configure("Header.TLabel", background=PALETTE["bg"], foreground=PALETTE["text"])
	style.configure("SubHeader.TLabel", background=PALETTE["bg"], foreground=PALETTE["text_muted"])
	style.configure("Accent.Horizontal.TProgressbar", troughcolor=PALETTE["panel"], background=PALETTE["accent"])
	style.configure("Accent.Horizontal.TScale", background=PALETTE["panel"], troughcolor=PALETTE["bg"])

	if "history_table" in globals():
		history_table.tag_configure("odd", background=PALETTE["input_bg"])
		history_table.tag_configure("even", background=PALETTE["panel"])

	for widget in main_container.winfo_children():
		update_widget_colors(widget)


def update_widget_colors(widget):
	try:
		widget_type = widget.winfo_class()

		if widget_type in ["Frame", "Labelframe"]:
			try:
				widget.configure(bg=PALETTE["bg"])
			except Exception:
				pass
		elif widget_type == "Label":
			try:
				widget.configure(bg=PALETTE["panel"], fg=PALETTE["text"])
			except Exception:
				pass
		elif widget_type in ["Entry", "Text"]:
			try:
				widget.configure(
					bg=PALETTE["input_bg"],
					fg=PALETTE["text"],
					insertbackground=PALETTE["accent"],
					highlightbackground=PALETTE["border"],
				)
			except Exception:
				pass

		for child in widget.winfo_children():
			update_widget_colors(child)
	except Exception:
		pass


def split_text(text, size=CHUNK_SIZE):
	chunks = []
	current_chunk = ""
	pattern = re.compile(r"^\s*(Chương\s+\w+|Thứ\s+\w+\s+chương|Hồi\s+\w+|Quyển\s+\w+)", re.IGNORECASE)

	lines = text.splitlines(True)
	blocks = []
	current_block = ""

	for line in lines:
		if pattern.match(line):
			if current_block.strip():
				blocks.append(current_block)
			current_block = line
		else:
			current_block += line

	if current_block.strip():
		blocks.append(current_block)

	for block in blocks:
		if len(current_chunk) + len(block) > size:
			if current_chunk.strip():
				chunks.append(current_chunk)
				current_chunk = ""

			if len(block) > size:
				temp_str = ""
				paragraphs = block.split("\n\n")
				for p in paragraphs:
					p_text = p + "\n\n" if p != paragraphs[-1] else p
					if len(temp_str) + len(p_text) > size:
						if temp_str.strip():
							chunks.append(temp_str)

						if len(p_text) > size:
							temp_str2 = ""
							sentences = re.split(r"(?<=[.!?]) +|\n", p_text)
							for s in sentences:
								s_text = s + " "
								if len(temp_str2) + len(s_text) > size:
									if temp_str2.strip():
										chunks.append(temp_str2)
									temp_str2 = s_text
								else:
									temp_str2 += s_text
							temp_str = temp_str2
						else:
							temp_str = p_text
					else:
						temp_str += p_text

				if temp_str.strip():
					current_chunk = temp_str
			else:
				current_chunk = block
		else:
			current_chunk += block

	if current_chunk.strip():
		chunks.append(current_chunk)

	return chunks


def _extract_local_response(data):
	choices = data.get("choices", [])
	if not choices:
		return ""
	message = choices[0].get("message", {})
	return str(message.get("content", "")).strip()


def _extract_usage_tokens(data):
	usage = data.get("usage", {}) or {}
	input_tokens = int(usage.get("prompt_tokens", 0) or 0)
	output_tokens = int(usage.get("completion_tokens", 0) or 0)
	return input_tokens, output_tokens


def call_local_chat_completion(endpoint, model_id, prompt, chunk, temperature, max_output_tokens, timeout=180):
	user_content = "NỘI DUNG CẦN DỊCH:\n" + chunk
	body = {
		"model": model_id,
		"messages": [
			{"role": "system", "content": prompt},
			{"role": "user", "content": user_content},
		],
		"temperature": temperature,
		"max_tokens": max_output_tokens,
		"stream": False,
	}
	body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
	request = urllib.request.Request(
		endpoint,
		data=body_bytes,
		headers={"Content-Type": "application/json"},
		method="POST",
	)

	try:
		with urllib.request.urlopen(request, timeout=timeout) as response:
			raw = response.read().decode("utf-8", errors="replace")
			payload = json.loads(raw)
			text = _extract_local_response(payload)
			in_tokens, out_tokens = _extract_usage_tokens(payload)
			if not text:
				raise RuntimeError("Model local không trả content hợp lệ.")
			return text, in_tokens, out_tokens
	except urllib.error.HTTPError as exc:
		try:
			error_body = exc.read().decode("utf-8", errors="replace")
		except Exception:
			error_body = str(exc)
		raise RuntimeError(f"HTTP {exc.code}: {error_body[:300]}") from exc
	except urllib.error.URLError as exc:
		raise RuntimeError(f"Không kết nối được LM Studio endpoint: {exc}") from exc


def translate_chunk(endpoint, model_id, prompt, chunk, index, cp_file, temperature, max_output_tokens, retries=3):
	global is_stopped

	pause_event.wait()
	if is_stopped:
		return index, None

	last_error = None
	for attempt in range(retries):
		if is_stopped:
			return index, None

		pause_event.wait()

		try:
			add_log(f"⏳ Đang dịch đoạn {index + 1}... (lần thử {attempt + 1}/{retries})")
			translated_text, input_tokens, output_tokens = call_local_chat_completion(
				endpoint,
				model_id,
				prompt,
				chunk,
				temperature,
				max_output_tokens,
			)

			save_checkpoint(cp_file, index, translated_text)

			stats["chunks_done"] += 1
			stats["total_input_chars"] += len(chunk)
			stats["total_output_chars"] += len(translated_text)
			stats["total_input_tokens"] += input_tokens
			stats["total_output_tokens"] += output_tokens

			add_log(f"✅ Hoàn thành đoạn {index + 1}")
			return index, translated_text

		except Exception as exc:
			last_error = exc
			add_log(f"⚠️ Đoạn {index + 1} gặp lỗi (lần {attempt + 1}): {str(exc)[:140]}")
			time.sleep(2 + attempt * 2)

	add_log(f"❌ Đoạn {index + 1} thất bại hoàn toàn sau {retries} lần thử")
	stats["chunks_done"] += 1
	return index, f"[ĐOẠN {index + 1} BỊ LỖI SAU {retries} LẦN THỬ: {last_error}]"


def toggle_pause():
	global is_paused

	if is_paused:
		is_paused = False
		pause_event.set()
		btn_pause.config(text="⏸️ TẠM DỪNG", bg="#FFC107")
		add_log("▶️ Đã tiếp tục dịch...")
	else:
		is_paused = True
		pause_event.clear()
		btn_pause.config(text="▶️ TIẾP TỤC", bg="#4CAF50")
		add_log("⏸️ Đã tạm dừng. Nhấn 'Tiếp tục' để dịch tiếp.")


def stop_translation():
	global is_stopped, is_paused

	if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn DỪNG dịch?\n(Tiến trình đã lưu, có thể dịch tiếp sau)"):
		is_stopped = True
		is_paused = False
		pause_event.set()
		add_log("🛑 Đang dừng quá trình dịch...")


def validate_inputs():
	endpoint = endpoint_var.get().strip()
	if not endpoint:
		messagebox.showerror("Lỗi", "Vui lòng nhập endpoint local API.")
		return False

	if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
		messagebox.showerror("Lỗi", "Endpoint phải bắt đầu bằng http:// hoặc https://")
		return False

	if not input_path.get() or not os.path.isfile(input_path.get()):
		messagebox.showerror("Lỗi", "Vui lòng chọn file truyện đầu vào hợp lệ.")
		return False

	try:
		thread_count = int(thread_var.get())
		if thread_count <= 0 or thread_count > 20:
			raise ValueError
	except Exception:
		messagebox.showerror("Lỗi", "Số luồng phải là số nguyên từ 1 đến 20.")
		return False

	try:
		chunk_size = int(chunk_size_var.get())
		if chunk_size < 500 or chunk_size > 50000:
			raise ValueError
	except Exception:
		messagebox.showerror("Lỗi", "Chunk size phải là số nguyên từ 500 đến 50000.")
		return False

	try:
		max_output_tokens = int(max_output_tokens_var.get())
		if max_output_tokens < 128 or max_output_tokens > 65536:
			raise ValueError
	except Exception:
		messagebox.showerror("Lỗi", "Max output tokens phải là số nguyên từ 128 đến 65536.")
		return False

	try:
		temp = float(temp_var.get())
		if temp < 0 or temp > 2:
			raise ValueError
	except Exception:
		messagebox.showerror("Lỗi", "Nhiệt độ phải nằm trong khoảng 0 đến 2.")
		return False

	return True


def get_scan_char_limit():
	try:
		scan_char_limit = int(scan_char_limit_var.get())
		if scan_char_limit < 500 or scan_char_limit > 200000:
			raise ValueError
		return scan_char_limit
	except Exception:
		messagebox.showerror("Lỗi", "Giới hạn ký tự quét phải là số nguyên từ 500 đến 200000.")
		return None


def normalize_scanned_glossary(raw_text):
	if not raw_text:
		return ""

	cleaned_lines = []
	seen = set()
	for line in raw_text.splitlines():
		clean = line.strip().lstrip("-•* ").strip()
		if not clean:
			continue

		separator = None
		for candidate in ["=>", "->", "→", ":", "="]:
			if candidate in clean:
				separator = candidate
				break

		if not separator:
			continue

		source, target = clean.split(separator, 1)
		source = source.strip(" \t\"'“”‘’[](){}")
		target = target.strip(" \t\"'“”‘’[](){}")
		if not source or not target:
			continue

		normalized = f"{source} => {target}"
		key = normalized.lower()
		if key in seen:
			continue
		seen.add(key)
		cleaned_lines.append(normalized)

	return "\n".join(cleaned_lines)


def build_scan_segments(text, segment_size=12000, max_segments=10):
	if not text:
		return []

	segments = []
	paragraphs = text.split("\n\n")
	bucket = ""

	for para in paragraphs:
		part = para if para == paragraphs[-1] else para + "\n\n"
		if len(bucket) + len(part) > segment_size and bucket.strip():
			segments.append(bucket)
			bucket = part
		else:
			bucket += part

	if bucket.strip():
		segments.append(bucket)

	if len(segments) <= max_segments:
		return segments

	selected = []
	selected_positions = set()
	for i in range(max_segments):
		pos = int(round(i * (len(segments) - 1) / (max_segments - 1))) if max_segments > 1 else 0
		if pos not in selected_positions:
			selected_positions.add(pos)
			selected.append(segments[pos])

	return selected


def scan_story():
	if not validate_inputs():
		return

	scan_char_limit = get_scan_char_limit()
	if scan_char_limit is None:
		return

	endpoint = endpoint_var.get().strip()
	in_file = input_path.get()
	model_id = model_var.get()
	temperature = float(temp_var.get())

	def run_scan():
		try:
			add_log(f"🔍 Đang quét thuật ngữ (tối đa {scan_char_limit:,} ký tự)...")
			with open(in_file, "r", encoding="utf-8") as f:
				full_text = f.read()

			limited_text = full_text[:scan_char_limit]
			scan_segments = build_scan_segments(limited_text, segment_size=12000, max_segments=10)
			add_log(f"🧩 Quét {len(scan_segments)} đoạn mẫu để tìm thuật ngữ.")

			scan_prompt = (
				"Bạn là chuyên gia biên tập truyện dịch từ Trung sang Việt.\n"
				"Hãy trích xuất danh sách thuật ngữ quan trọng từ đoạn sau.\n"
				"Định dạng bắt buộc mỗi dòng: Nguồn => Đích.\n"
				"Không giải thích, không đánh số, không tiêu đề.\n"
				"Nếu không có thì trả: Không có"
			)

			merged_terms = []
			seen_terms = set()

			for seg_idx, segment in enumerate(scan_segments, 1):
				add_log(f"🔎 Quét đoạn mẫu {seg_idx}/{len(scan_segments)}...")
				raw_result, _, _ = call_local_chat_completion(
					endpoint,
					model_id,
					scan_prompt,
					segment,
					temperature,
					1536,
				)
				if not raw_result or "không có" in raw_result.lower():
					continue

				normalized = normalize_scanned_glossary(raw_result)
				if not normalized:
					continue

				for term_line in normalized.splitlines():
					term_key = term_line.strip().lower()
					if not term_key or term_key in seen_terms:
						continue
					seen_terms.add(term_key)
					merged_terms.append(term_line.strip())

				time.sleep(0.2)

			extracted_terms = "\n".join(merged_terms)
			if extracted_terms:
				add_log(f"✅ Quét xong thuật ngữ! Tìm thấy {len(merged_terms)} mục.")

				def ask_user():
					if messagebox.askyesno("Kết quả quét thuật ngữ", f"Đã tìm thấy các thuật ngữ:\n\n{extracted_terms}\n\nBạn có muốn thêm vào Glossary không?"):
						current_glossary = glossary_text.get("1.0", tk.END).strip()
						new_glossary = f"{current_glossary}\n{extracted_terms}".strip() if current_glossary else extracted_terms
						glossary_text.delete("1.0", tk.END)
						glossary_text.insert(tk.END, new_glossary)
						add_log("📝 Đã thêm thuật ngữ vào Glossary.")

				root.after(0, ask_user)
			else:
				add_log("ℹ️ Không tìm thấy thuật ngữ đặc biệt nào.")
				root.after(0, lambda: messagebox.showinfo("Kết quả", "Không tìm thấy thuật ngữ đặc biệt nào từ các đoạn đầu truyện."))

		except Exception as exc:
			add_log(f"🛑 Lỗi khi quét thuật ngữ: {exc}")
			root.after(0, lambda: messagebox.showerror("Lỗi", f"Có lỗi xảy ra: {exc}"))

	threading.Thread(target=run_scan, daemon=True).start()


def start_translation():
	global is_stopped, is_paused

	if not validate_inputs():
		return

	is_stopped = False
	is_paused = False
	pause_event.set()

	output_path.set(build_default_output_path(input_path.get()))
	add_log(f"📄 File output mặc định: {output_path.get()}")

	save_settings()

	task_thread = threading.Thread(target=process_translation_logic, daemon=True)
	task_thread.start()

	stats_thread = threading.Thread(target=stats_update_loop, daemon=True)
	stats_thread.start()

	add_log("🚀 Đã kích hoạt luồng dịch thuật ngầm (Local Gemma)...")


def stats_update_loop():
	while not is_stopped and btn_start["state"] == "disabled":
		update_stats_display()
		time.sleep(1)


def process_translation_logic():
	global is_stopped

	btn_start.config(state="disabled")
	btn_pause.config(state="normal")
	btn_stop.config(state="normal")

	stats["start_time"] = time.time()
	stats["chunks_done"] = 0
	stats["total_input_chars"] = 0
	stats["total_output_chars"] = 0
	stats["total_input_tokens"] = 0
	stats["total_output_tokens"] = 0

	history_status = "error"
	history_error = ""
	in_file = input_path.get()
	out_file = output_path.get()
	model = model_var.get()
	threads = thread_var.get()
	temperature = temp_var.get()

	try:
		endpoint = endpoint_var.get().strip()
		cp_file = get_checkpoint_path(in_file)
		threads_int = int(thread_var.get())
		chunk_size = int(chunk_size_var.get())
		max_output_tokens = int(max_output_tokens_var.get())
		temperature_float = float(temp_var.get())

		prompt = prompt_text.get("1.0", tk.END).strip()
		glossary_raw = glossary_text.get("1.0", tk.END).strip()
		glossary_entries = parse_glossary(glossary_raw)
		prompt = build_prompt_with_glossary(prompt, glossary_entries)
		if glossary_entries:
			add_log(f"📚 Áp dụng glossary: {len(glossary_entries)} mục thuật ngữ.")

		with open(in_file, "r", encoding="utf-8") as f:
			chunks = split_text(f.read(), size=chunk_size)

		total = len(chunks)
		stats["total_chunks"] = total
		results = [None] * total

		if os.path.exists(cp_file):
			with open(cp_file, "r", encoding="utf-8") as f:
				saved_data = json.load(f)

			if messagebox.askyesno("Khôi phục", f"Tìm thấy bản dịch dở dang ({len(saved_data)}/{total} đoạn). Dịch tiếp chứ?"):
				for idx_str, text in saved_data.items():
					idx = int(idx_str)
					if 0 <= idx < total:
						results[idx] = text
				stats["chunks_done"] = len([r for r in results if r is not None])
				add_log(f"🔄 Đã khôi phục {stats['chunks_done']} đoạn từ file checkpoint.")
		else:
			with open(cp_file, "w", encoding="utf-8") as f:
				json.dump({}, f)

		pending_indices = [i for i in range(total) if results[i] is None]
		progress_bar["maximum"] = total
		progress_bar["value"] = total - len(pending_indices)

		add_log(f"📦 Bắt đầu dịch {len(pending_indices)} đoạn còn lại bằng {model}...")
		add_log(f"⚙️ Chunk size: {chunk_size} | Max output tokens: {max_output_tokens}")
		add_log(f"🌡️ Temperature: {temperature_float}")

		with concurrent.futures.ThreadPoolExecutor(max_workers=threads_int) as executor:
			futures = {
				executor.submit(
					translate_chunk,
					endpoint,
					model,
					prompt,
					chunks[i],
					i,
					cp_file,
					temperature_float,
					max_output_tokens,
				): i
				for i in pending_indices
			}

			for future in concurrent.futures.as_completed(futures):
				if is_stopped:
					executor.shutdown(wait=False, cancel_futures=True)
					break

				idx, translated = future.result()
				if translated is not None:
					results[idx] = translated
					current_val = progress_bar["value"] + 1
					progress_bar["value"] = current_val
					status_var.set(f"Tiến độ: {int(current_val)}/{total}")
					root.update_idletasks()

		if is_stopped:
			add_log("🛑 Đã dừng dịch. Tiến trình đã được lưu vào checkpoint.")
			messagebox.showinfo("Đã dừng", "Quá trình dịch đã dừng.\nTiến trình được lưu, bạn có thể tiếp tục sau.")
			history_status = "stopped"
			return

		with open(out_file, "w", encoding="utf-8") as f:
			f.write("\n\n".join([r for r in results if r is not None]))

		if os.path.exists(cp_file):
			os.remove(cp_file)

		total_time = time.time() - stats["start_time"]
		add_log(f"🎊 HOÀN TẤT! Tổng thời gian: {format_time(total_time)}")
		add_log(f"📊 Đã dịch {stats['total_input_chars']:,} → {stats['total_output_chars']:,} ký tự")
		add_log(f"🔢 Input Token: {stats['total_input_tokens']:,}")
		add_log(f"🔢 Output Token: {stats['total_output_tokens']:,}")
		history_status = "completed"

		messagebox.showinfo(
			"Hoàn tất",
			f"Truyện đã được dịch xong!\nThời gian: {format_time(total_time)}\nLưu tại: {out_file}",
		)

	except Exception as exc:
		history_error = str(exc)
		add_log(f"🛑 LỖI HỆ THỐNG: {history_error}")
		messagebox.showerror("Lỗi", f"Quá trình dịch bị gián đoạn: {history_error}")

	finally:
		end_time = time.time()
		duration_seconds = max(0, int(end_time - stats["start_time"])) if stats["start_time"] else 0
		history_entry = {
			"engine": "Local Gemma (LM Studio)",
			"status": history_status,
			"start_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stats["start_time"] if stats["start_time"] else end_time)),
			"end_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_time)),
			"duration_seconds": duration_seconds,
			"input_file": in_file,
			"output_file": out_file,
			"model": model,
			"threads": threads,
			"temperature": temperature,
			"chunks_done": stats["chunks_done"],
			"total_chunks": stats["total_chunks"],
			"total_input_chars": stats["total_input_chars"],
			"total_output_chars": stats["total_output_chars"],
			"total_input_tokens": stats["total_input_tokens"],
			"total_output_tokens": stats["total_output_tokens"],
			"error": history_error,
		}
		save_translation_history_entry(history_entry)
		refresh_history_display()

		btn_start.config(state="normal")
		btn_pause.config(state="disabled", text="⏸️ TẠM DỪNG", bg="#FFC107")
		btn_stop.config(state="disabled")
		status_var.set("Sẵn sàng")
		is_stopped = True


root = tk.Tk()
root.title("📖 App Dịch Truyện Local – LM Studio Gemma")
root.geometry("1080x920")
root.minsize(820, 620)
root.configure(bg=PALETTE["bg"])

style = ttk.Style()
style.theme_use("clam")
style.configure("Card.TFrame", background=PALETTE["panel"], borderwidth=0, relief="flat")
style.configure("TLabel", background=PALETTE["panel"], foreground=PALETTE["text"], font=("Segoe UI", 10))
style.configure("Header.TLabel", background=PALETTE["bg"], foreground=PALETTE["text"], font=("Segoe UI", 22, "bold"))
style.configure("SubHeader.TLabel", background=PALETTE["bg"], foreground=PALETTE["text_muted"], font=("Segoe UI", 11))
style.configure("Accent.Horizontal.TProgressbar", troughcolor=PALETTE["panel"], background=PALETTE["accent"])
style.configure("Accent.Horizontal.TScale", background=PALETTE["panel"], troughcolor=PALETTE["bg"])

canvas_bg = tk.Canvas(root, highlightthickness=0, bd=0, bg=PALETTE["bg"])
scrollbar = tk.Scrollbar(root, orient="vertical", command=canvas_bg.yview, bg=PALETTE["border"], troughcolor=PALETTE["bg"])
canvas_bg.configure(yscrollcommand=scrollbar.set)
scrollbar.pack(side="right", fill="y")
canvas_bg.pack(side="left", fill="both", expand=True)


def _hex_to_rgb(hex_color):
	hex_color = hex_color.lstrip("#")
	return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
	return "#%02x%02x%02x" % rgb


def draw_gradient(event=None):
	canvas_bg.delete("gradient")
	w = max(canvas_bg.winfo_width(), 1)
	h = max(canvas_bg.winfo_height(), 1)
	steps = 80
	r1, g1, b1 = _hex_to_rgb(PALETTE["gradient_start"])
	r2, g2, b2 = _hex_to_rgb(PALETTE["gradient_end"])
	for i in range(steps):
		r = int(r1 + (r2 - r1) * i / steps)
		g = int(g1 + (g2 - g1) * i / steps)
		b = int(b1 + (b2 - b1) * i / steps)
		y0 = int(h * i / steps)
		y1 = int(h * (i + 1) / steps)
		canvas_bg.create_rectangle(0, y0, w, y1, outline="", fill=_rgb_to_hex((r, g, b)), tags="gradient")


canvas_bg.bind("<Configure>", draw_gradient)
draw_gradient()

main_container = tk.Frame(canvas_bg, bg=PALETTE["bg"])
canvas_window = canvas_bg.create_window((0, 0), window=main_container, anchor="nw")


def on_frame_configure(event=None):
	canvas_bg.configure(scrollregion=canvas_bg.bbox("all"))


def on_canvas_configure(event):
	canvas_bg.itemconfig(canvas_window, width=event.width)


main_container.bind("<Configure>", on_frame_configure)
canvas_bg.bind("<Configure>", on_canvas_configure)


def on_mousewheel(event):
	canvas_bg.yview_scroll(int(-1 * (event.delta / 120)), "units")


canvas_bg.bind_all("<MouseWheel>", on_mousewheel)

main_frame = tk.Frame(main_container, bg=PALETTE["bg"])
main_frame.pack(fill="both", expand=True, padx=20, pady=10)
for col in range(2):
	main_frame.columnconfigure(col, weight=1)

header = tk.Frame(main_frame, bg=PALETTE["bg"])
header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))

header_top = tk.Frame(header, bg=PALETTE["bg"])
header_top.pack(fill="x")
header_title_frame = tk.Frame(header_top, bg=PALETTE["bg"])
header_title_frame.pack(side="left", fill="both", expand=True)

ttk.Label(header_title_frame, text="App Dịch Truyện – Local Gemma", style="Header.TLabel").pack(anchor="w")
ttk.Label(header_title_frame, text="Dùng LM Studio local API, không cần cloud key.", style="SubHeader.TLabel").pack(anchor="w", pady=(4, 6))

btn_theme = tk.Button(
	header_top,
	text="🌙 Tối",
	font=("Segoe UI", 10, "bold"),
	bg=PALETTE["accent_alt"],
	fg="#0b0f19",
	bd=0,
	padx=15,
	pady=8,
	command=toggle_theme,
	cursor="hand2",
)
btn_theme.pack(side="right", padx=(10, 0))

badge_row = tk.Frame(header, bg=PALETTE["bg"])
badge_row.pack(anchor="w", pady=(4, 0))
for text, color in [("LM Studio Local API", PALETTE["accent"]), ("Gemma Models", PALETTE["accent_alt"]), ("Resume Checkpoint", PALETTE["ok"])]:
	tk_label = tk.Label(badge_row, text=text, bg=color, fg="#0b0f19", font=("Segoe UI", 9, "bold"), padx=10, pady=4, bd=0)
	tk_label.pack(side="left", padx=(0, 8))


def build_card(parent, title, col, row, colspan=1):
	card = ttk.Frame(parent, style="Card.TFrame")
	card.grid(row=row, column=col, columnspan=colspan, sticky="nsew", padx=6, pady=6, ipadx=8, ipady=8)
	card.columnconfigure(0, weight=1)
	ttk.Label(card, text=title, style="TLabel", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
	return card


tabs = ttk.Notebook(main_frame)
tabs.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 6))
main_frame.rowconfigure(1, weight=1)

translate_tab = tk.Frame(tabs, bg=PALETTE["bg"])
preview_tab = tk.Frame(tabs, bg=PALETTE["bg"])
history_tab = tk.Frame(tabs, bg=PALETTE["bg"])
tabs.add(translate_tab, text="🚀 Dịch truyện")
tabs.add(preview_tab, text="🔍 Xem Chunk")
tabs.add(history_tab, text="🗂️ Lịch sử dịch")

for col in range(2):
	translate_tab.columnconfigure(col, weight=1)

preview_tab.columnconfigure(0, weight=1)
preview_tab.columnconfigure(1, weight=3)
preview_tab.rowconfigure(1, weight=1)

history_tab.columnconfigure(0, weight=1)
history_tab.rowconfigure(0, weight=1)

input_path = tk.StringVar()
output_path = tk.StringVar()
endpoint_var = tk.StringVar(value=DEFAULT_ENDPOINT)
model_var = tk.StringVar(value=LOCAL_MODELS[0])
thread_var = tk.StringVar(value="3")
chunk_size_var = tk.StringVar(value=str(CHUNK_SIZE))
max_output_tokens_var = tk.StringVar(value=str(MAX_OUTPUT_TOKENS))
scan_char_limit_var = tk.StringVar(value=str(DEFAULT_SCAN_CHAR_LIMIT))
temp_var = tk.StringVar(value="0.7")

entry_opts = {
	"bg": PALETTE["input_bg"],
	"fg": PALETTE["text"],
	"insertbackground": PALETTE["accent"],
	"relief": "flat",
	"highlightthickness": 1,
	"highlightbackground": PALETTE["border"],
}

card_api = build_card(translate_tab, "🔌 Local API endpoint", 0, 1, colspan=2)
tk.Label(card_api, text="Endpoint mặc định LM Studio: http://localhost:1234/v1/chat/completions", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=(0, 6))
tk.Entry(card_api, textvariable=endpoint_var, **entry_opts).grid(row=2, column=0, sticky="ew")

card_files = build_card(translate_tab, "📂 Chọn file nguồn / đích", 0, 2)
tk.Label(card_files, text="File truyện đầu vào (.txt)", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w")
frame_input = tk.Frame(card_files, bg=PALETTE["panel"])
frame_input.grid(row=2, column=0, sticky="ew", pady=(2, 8))
frame_input.columnconfigure(0, weight=1)
tk.Entry(frame_input, textvariable=input_path, **entry_opts).grid(row=0, column=0, sticky="ew")
tk.Button(frame_input, text="Chọn file", bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=10, pady=6, command=lambda: input_path.set(filedialog.askopenfilename(filetypes=[("Text files", "*.txt")]))).grid(row=0, column=1, padx=(8, 0))
tk.Label(card_files, text="Output tự động: DichLocal_tên_file_ngẫu_nhiên.txt", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9)).grid(row=3, column=0, sticky="w", pady=(6, 0))

card_config = build_card(translate_tab, "⚙️ Cấu hình dịch", 1, 2)
tk.Label(card_config, text="Model", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w")
model_cb = ttk.Combobox(card_config, values=LOCAL_MODELS, textvariable=model_var, state="readonly")
model_cb.grid(row=2, column=0, sticky="ew", pady=(2, 8))

perf_frame = tk.Frame(card_config, bg=PALETTE["panel"])
perf_frame.grid(row=3, column=0, sticky="ew", pady=(2, 8))
for col in range(3):
	perf_frame.columnconfigure(col, weight=1)

tk.Label(perf_frame, text="Số luồng", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
tk.Entry(perf_frame, textvariable=thread_var, width=8, **entry_opts).grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(2, 0))
tk.Label(perf_frame, text="Chunk size", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w")
tk.Entry(perf_frame, textvariable=chunk_size_var, width=10, **entry_opts).grid(row=1, column=1, sticky="ew", padx=3, pady=(2, 0))
tk.Label(perf_frame, text="Max output tokens", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w")
tk.Entry(perf_frame, textvariable=max_output_tokens_var, width=12, **entry_opts).grid(row=1, column=2, sticky="ew", padx=(6, 0), pady=(2, 0))

tk.Label(card_config, text="Nhiệt độ (0-2)", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=4, column=0, sticky="w")
temp_scale = ttk.Scale(card_config, from_=0.0, to=2.0, variable=temp_var, orient="horizontal", length=200, style="Accent.Horizontal.TScale")
temp_scale.grid(row=5, column=0, sticky="ew")
tk.Label(card_config, textvariable=temp_var, bg=PALETTE["panel"], fg=PALETTE["accent"], font=("Segoe UI", 10, "bold")).grid(row=5, column=1, padx=(8, 0))


def update_temp_label(event=None):
	temp_var.set(f"{float(temp_var.get()):.2f}")


temp_scale.bind("<Motion>", update_temp_label)
temp_scale.bind("<ButtonRelease-1>", update_temp_label)

card_prompt = build_card(translate_tab, "📝 Prompt dịch giả", 0, 3, colspan=2)
glossary_header_frame = tk.Frame(card_prompt, bg=PALETTE["panel"])
glossary_header_frame.grid(row=1, column=0, sticky="ew", pady=(0, 4))
glossary_header_frame.columnconfigure(0, weight=1)
tk.Label(glossary_header_frame, text="Glossary/Từ điển thuật ngữ (mỗi dòng: nguồn => đích)", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).pack(side="left")

scan_limit_frame = tk.Frame(glossary_header_frame, bg=PALETTE["panel"])
scan_limit_frame.pack(side="right")
tk.Label(scan_limit_frame, text="Giới hạn ký tự quét:", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 4))
tk.Entry(scan_limit_frame, textvariable=scan_char_limit_var, width=8, **entry_opts).pack(side="left", padx=(0, 8))
tk.Button(scan_limit_frame, text="🔍 Quét thuật ngữ", font=("Segoe UI", 8, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=8, pady=2, command=scan_story).pack(side="right")

glossary_text = tk.Text(card_prompt, height=4, bg=PALETTE["input_bg"], fg=PALETTE["text"], insertbackground=PALETTE["accent"], wrap="word", relief="flat", highlightthickness=1, highlightbackground=PALETTE["border"])
glossary_text.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
glossary_text.insert(tk.END, DEFAULT_GLOSSARY)

tk.Label(card_prompt, text="Prompt dịch giả", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=3, column=0, sticky="w", pady=(0, 4))
prompt_text = tk.Text(card_prompt, height=5, bg=PALETTE["input_bg"], fg=PALETTE["text"], insertbackground=PALETTE["accent"], wrap="word", relief="flat", highlightthickness=1, highlightbackground=PALETTE["border"])
prompt_text.grid(row=4, column=0, sticky="nsew", pady=(0, 6))
prompt_text.insert(tk.END, DEFAULT_PROMPT)
card_prompt.rowconfigure(2, weight=1)
card_prompt.rowconfigure(4, weight=1)

card_stats = build_card(translate_tab, "📊 Thống kê", 0, 4)
stats_time_var = tk.StringVar(value="⏱️ Đã chạy: --:--")
stats_eta_var = tk.StringVar(value="⏳ Còn lại: --:--")
stats_speed_var = tk.StringVar(value="🚀 Tốc độ: -- đoạn/phút")
stats_chars_var = tk.StringVar(value="📝 Ký tự: -- → --")
stats_input_tokens_var = tk.StringVar(value="🔢 Input Token: --")
stats_output_tokens_var = tk.StringVar(value="🔢 Output Token: --")

for i, var in enumerate([stats_time_var, stats_eta_var, stats_speed_var, stats_chars_var, stats_input_tokens_var, stats_output_tokens_var]):
	ttk.Label(card_stats, textvariable=var, style="TLabel", font=("Consolas", 10)).grid(row=1 + i // 2, column=i % 2, sticky="w", padx=8, pady=4)

card_progress = build_card(translate_tab, "🚀 Điều khiển & tiến độ", 1, 4)
progress_bar = ttk.Progressbar(card_progress, style="Accent.Horizontal.TProgressbar", length=400, mode="determinate")
progress_bar.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(2, 8))
status_var = tk.StringVar(value="Sẵn sàng")
tk.Label(card_progress, textvariable=status_var, bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 10, "italic")).grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 8))

btn_pause = tk.Button(card_progress, text="⏸️ TẠM DỪNG", font=("Segoe UI", 10, "bold"), bg="#fbbf24", fg="#0b0f19", bd=0, padx=10, pady=10, command=toggle_pause, state="disabled")
btn_pause.grid(row=3, column=0, sticky="ew", padx=(0, 6))
btn_stop = tk.Button(card_progress, text="🛑 DỪNG HẲN", font=("Segoe UI", 10, "bold"), bg=PALETTE["warn"], fg="#0b0f19", bd=0, padx=10, pady=10, command=stop_translation, state="disabled")
btn_stop.grid(row=3, column=1, sticky="ew", padx=6)
btn_start = tk.Button(card_progress, text="🚀 BẮT ĐẦU DỊCH", font=("Segoe UI", 11, "bold"), bg=PALETTE["accent"], fg="#0b0f19", bd=0, padx=10, pady=12, command=start_translation)
btn_start.grid(row=3, column=2, sticky="ew", padx=(6, 0))

tk.Button(card_progress, text="💾 LƯU CÀI ĐẶT", font=("Segoe UI", 10, "bold"), bg=PALETTE["ok"], fg="#0b0f19", bd=0, padx=10, pady=8, command=save_settings).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0), padx=(0, 6))
tk.Button(card_progress, text="🔄 RESET PROMPT", font=("Segoe UI", 10, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=10, pady=8, command=lambda: (prompt_text.delete("1.0", tk.END), prompt_text.insert(tk.END, DEFAULT_PROMPT))).grid(row=4, column=2, sticky="ew", pady=(8, 0), padx=(6, 0))
for c in range(3):
	card_progress.columnconfigure(c, weight=1)

card_log = build_card(translate_tab, "📋 Nhật ký hoạt động", 0, 5, colspan=2)
log_box = scrolledtext.ScrolledText(card_log, height=8, state="disabled", bg=PALETTE["input_bg"], fg=PALETTE["text"], insertbackground=PALETTE["accent"], relief="flat", highlightthickness=1, highlightbackground=PALETTE["border"])
log_box.grid(row=1, column=0, sticky="nsew")
card_log.rowconfigure(1, weight=1)

preview_toolbar = tk.Frame(preview_tab, bg=PALETTE["panel"])
preview_toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6), padx=6)
preview_info_var = tk.StringVar(value="Tổng số chunk: 0")
previewed_chunks = []


def load_and_preview_chunks():
	global previewed_chunks
	try:
		input_file = input_path.get()
	except NameError:
		messagebox.showerror("Lỗi", "Giao diện chưa sẵn sàng!")
		return

	if not input_file or not os.path.exists(input_file):
		messagebox.showerror("Lỗi", "Vui lòng chọn file nguồn hợp lệ ở tab 'Dịch truyện' trước!")
		return

	try:
		size_limit = int(chunk_size_var.get())
	except ValueError:
		size_limit = CHUNK_SIZE

	try:
		with open(input_file, "r", encoding="utf-8") as f:
			text = f.read()
		previewed_chunks = split_text(text, size_limit)

		chunk_listbox.delete(0, tk.END)
		for i, chunk in enumerate(previewed_chunks):
			lines = chunk.strip().split("\n")
			first_line = lines[0][:35] + "..." if lines and len(lines[0]) > 35 else (lines[0] if lines else "")
			chunk_listbox.insert(tk.END, f"Chunk {i + 1} ({len(chunk)} ký tự) - {first_line}")

		preview_info_var.set(f"Tổng số chunk: {len(previewed_chunks)}")
		chunk_content_text.config(state="normal")
		chunk_content_text.delete("1.0", tk.END)
		chunk_content_text.config(state="disabled")
	except Exception as exc:
		messagebox.showerror("Lỗi", f"Không thể chia chunk: {exc}")


tk.Button(preview_toolbar, text="🔄 Tải & Chia Chunk", font=("Segoe UI", 9, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=10, pady=5, command=load_and_preview_chunks).pack(side="left", padx=5, pady=5)
tk.Label(preview_toolbar, textvariable=preview_info_var, bg=PALETTE["panel"], fg=PALETTE["text"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=10)

chunk_list_frame = tk.Frame(preview_tab, bg=PALETTE["panel"])
chunk_list_frame.grid(row=1, column=0, sticky="nsew", padx=(6, 3), pady=6)
chunk_listbox = tk.Listbox(chunk_list_frame, bg=PALETTE["input_bg"], fg=PALETTE["text"], selectbackground=PALETTE["accent_alt"], selectforeground="#0b0f19", font=("Segoe UI", 9), activestyle="none", highlightthickness=0, bd=0)
chunk_listbox.pack(side="left", fill="both", expand=True, padx=5, pady=5)
chunk_list_scroll = ttk.Scrollbar(chunk_list_frame, orient="vertical", command=chunk_listbox.yview)
chunk_list_scroll.pack(side="right", fill="y")
chunk_listbox.configure(yscrollcommand=chunk_list_scroll.set)

chunk_content_frame = tk.Frame(preview_tab, bg=PALETTE["panel"])
chunk_content_frame.grid(row=1, column=1, sticky="nsew", padx=(3, 6), pady=6)
chunk_content_text = scrolledtext.ScrolledText(chunk_content_frame, bg=PALETTE["input_bg"], fg=PALETTE["text"], wrap="word", font=("Consolas", 10), relief="flat", highlightthickness=1, highlightbackground=PALETTE["border"])
chunk_content_text.pack(fill="both", expand=True, padx=5, pady=5)
chunk_content_text.config(state="disabled")


def on_chunk_select(event):
	selection = chunk_listbox.curselection()
	if selection:
		index = selection[0]
		if 0 <= index < len(previewed_chunks):
			chunk_content_text.config(state="normal")
			chunk_content_text.delete("1.0", tk.END)
			chunk_content_text.insert(tk.END, previewed_chunks[index])
			chunk_content_text.config(state="disabled")


chunk_listbox.bind("<<ListboxSelect>>", on_chunk_select)

card_history = build_card(history_tab, "🗂️ Lịch sử dịch", 0, 0, colspan=1)
history_toolbar = tk.Frame(card_history, bg=PALETTE["panel"])
history_toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 6))
history_toolbar.columnconfigure(0, weight=1)
history_hint_var = tk.StringVar(value="Hiển thị 20 lần dịch gần nhất.")
tk.Label(history_toolbar, textvariable=history_hint_var, bg=PALETTE["panel"], fg=PALETTE["text"], font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
tk.Button(history_toolbar, text="🔄 Làm mới", font=("Segoe UI", 9, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=10, pady=5, command=refresh_history_display).grid(row=0, column=1, padx=(8, 6))
tk.Button(history_toolbar, text="🗑️ Xóa lịch sử", font=("Segoe UI", 9, "bold"), bg=PALETTE["warn"], fg="#0b0f19", bd=0, padx=10, pady=5, command=clear_translation_history).grid(row=0, column=2)

history_table_frame = tk.Frame(card_history, bg=PALETTE["panel"])
history_table_frame.grid(row=2, column=0, sticky="nsew")
history_table_frame.columnconfigure(0, weight=1)
history_table_frame.rowconfigure(0, weight=1)

history_columns = ("start_at", "status", "model", "progress", "chars", "tokens", "duration", "meta", "files", "error")
history_table = ttk.Treeview(history_table_frame, columns=history_columns, show="headings")
history_table.grid(row=0, column=0, sticky="nsew")
history_scroll_y = ttk.Scrollbar(history_table_frame, orient="vertical", command=history_table.yview)
history_scroll_y.grid(row=0, column=1, sticky="ns")
history_scroll_x = ttk.Scrollbar(history_table_frame, orient="horizontal", command=history_table.xview)
history_scroll_x.grid(row=1, column=0, sticky="ew")
history_table.configure(yscrollcommand=history_scroll_y.set, xscrollcommand=history_scroll_x.set)

history_table.heading("start_at", text="Bắt đầu")
history_table.heading("status", text="Trạng thái")
history_table.heading("model", text="Model")
history_table.heading("progress", text="Tiến độ")
history_table.heading("chars", text="Ký tự")
history_table.heading("tokens", text="Token")
history_table.heading("duration", text="Thời gian")
history_table.heading("meta", text="Thiết lập")
history_table.heading("files", text="File")
history_table.heading("error", text="Lỗi")

history_table.column("start_at", width=145, anchor="w")
history_table.column("status", width=95, anchor="center")
history_table.column("model", width=180, anchor="w")
history_table.column("progress", width=90, anchor="center")
history_table.column("chars", width=160, anchor="e")
history_table.column("tokens", width=190, anchor="e")
history_table.column("duration", width=90, anchor="center")
history_table.column("meta", width=130, anchor="center")
history_table.column("files", width=330, anchor="w")
history_table.column("error", width=220, anchor="w")

for i in range(6):
	translate_tab.rowconfigure(i, weight=1 if i in [3, 5] else 0)

saved_settings = load_settings()
apply_settings(saved_settings)

if saved_settings.get("theme"):
	current_theme = saved_settings["theme"]
	PALETTE = THEMES[current_theme]
	theme_icon = "🌙" if current_theme == "dark" else "☀️"
	btn_theme.config(text=f"{theme_icon} {'Tối' if current_theme == 'dark' else 'Sáng'}")
	apply_theme()

root.protocol("WM_DELETE_WINDOW", on_closing)
add_log("📂 Đã tải cài đặt local app từ lần sử dụng trước.")
add_log("🔌 Hãy đảm bảo LM Studio đang bật server tại endpoint đã cấu hình.")
refresh_history_display()

root.mainloop()
