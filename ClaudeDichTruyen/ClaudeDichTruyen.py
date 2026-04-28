import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import os
import concurrent.futures
import time
import json
import threading
import random
import base64
import hashlib
import datetime
import re
import shutil
import subprocess
import urllib.request
import urllib.error

# ================= CẤU HÌNH CLAUDE =================
CLAUDE_PROXY_URL = "https://1gw.gwai.cloud/v1/messages"
CLAUDE_API_VERSION = "2023-06-01"
CHUNK_SIZE = 3000
MAX_TOKENS = 8192
USD_TO_VND = 25400

# Claude API IDs / aliases hiện tại theo docs Anthropic
MODELS = [
	"claude-opus-4-7",
	"claude-sonnet-4-6",
	"claude-haiku-4-5",
]

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

MODEL_PRICING = {
	"claude-opus-4-7": {"input_per_1m": 5.00, "output_per_1m": 25.00},
	"claude-sonnet-4-6": {"input_per_1m": 3.00, "output_per_1m": 15.00},
	"claude-haiku-4-5": {"input_per_1m": 1.00, "output_per_1m": 5.00},
}

# ================= BIẾN ĐIỀU KHIỂN =================
is_paused = False
is_stopped = True
pause_event = threading.Event()
pause_event.set()

stats = {
	"start_time": 0,
	"chunks_done": 0,
	"total_chunks": 0,
	"total_input_chars": 0,
	"total_output_chars": 0,
	"total_input_tokens": 0,
	"total_output_tokens": 0,
	"total_input_cost_usd": 0.0,
	"total_output_cost_usd": 0.0,
	"total_cost_usd": 0.0,
}

THEMES = {
	"dark": {
		"bg": "#0f172a",
		"panel": "#111827",
		"border": "#1f2937",
		"text": "#e5e7eb",
		"text_muted": "#9ca3af",
		"accent": "#f97316",
		"accent_alt": "#fb923c",
		"input_bg": "#0b1220",
		"warn": "#f87171",
		"ok": "#34d399",
		"gradient_start": "#1a120e",
		"gradient_end": "#3f1d0f",
	},
	"light": {
		"bg": "#f8fafc",
		"panel": "#ffffff",
		"border": "#e2e8f0",
		"text": "#1e293b",
		"text_muted": "#64748b",
		"accent": "#f97316",
		"accent_alt": "#0ea5e9",
		"input_bg": "#f1f5f9",
		"warn": "#ef4444",
		"ok": "#10b981",
		"gradient_start": "#f8fafc",
		"gradient_end": "#e2e8f0",
	},
}

current_theme = "dark"
PALETTE = THEMES[current_theme]

# ================= MÃ HÓA API KEY =================
def get_machine_key():
	unique_string = os.environ.get("COMPUTERNAME", "PC") + os.environ.get("USERNAME", "User") + "DichTruyenSecretKey2026"
	return hashlib.sha256(unique_string.encode()).digest()


def xor_encrypt_decrypt(data, key):
	if not data:
		return ""
	data_bytes = data.encode("utf-8")
	key_repeated = (key * ((len(data_bytes) // len(key)) + 1))[: len(data_bytes)]
	result = bytes([a ^ b for a, b in zip(data_bytes, key_repeated)])
	return base64.b64encode(result).decode("utf-8")


def xor_decrypt(encrypted_data, key):
	if not encrypted_data:
		return ""
	try:
		data_bytes = base64.b64decode(encrypted_data.encode("utf-8"))
		key_repeated = (key * ((len(data_bytes) // len(key)) + 1))[: len(data_bytes)]
		result = bytes([a ^ b for a, b in zip(data_bytes, key_repeated)])
		return result.decode("utf-8")
	except Exception:
		return ""


def encrypt_api_key(api_key):
	return xor_encrypt_decrypt(api_key, get_machine_key())


def decrypt_api_key(encrypted_key):
	return xor_decrypt(encrypted_key, get_machine_key())

# ================= LƯU TRỮ =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "app_settings.json")
HISTORY_FILE = os.path.join(BASE_DIR, "translation_history.json")


def get_default_settings():
	return {
		"api_key_encrypted": "",
		"input_file": "",
		"output_file": "",
		"model": MODELS[0],
		"threads": "3",
		"chunk_size": str(CHUNK_SIZE),
		"max_output_tokens": str(MAX_TOKENS),
		"temperature": "0.5",
		"prompt": DEFAULT_PROMPT,
		"theme": "dark",
	}


def load_settings():
	settings = get_default_settings()
	try:
		if os.path.exists(SETTINGS_FILE):
			with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
				saved = json.load(f)
			settings.update(saved)
			if saved.get("api_key_encrypted"):
				settings["api_key"] = decrypt_api_key(saved["api_key_encrypted"])
			else:
				settings["api_key"] = ""
		else:
			settings["api_key"] = ""
	except Exception as e:
		print(f"Không thể tải cài đặt: {e}")
		settings["api_key"] = ""
	return settings


def save_settings():
	api_key = api_key_entry.get().strip()
	settings = {
		"api_key_encrypted": encrypt_api_key(api_key),
		"input_file": input_path.get(),
		"output_file": output_path.get(),
		"model": model_var.get(),
		"threads": thread_var.get(),
		"chunk_size": chunk_size_var.get(),
		"max_output_tokens": max_output_tokens_var.get(),
		"temperature": temp_var.get(),
		"prompt": prompt_text.get("1.0", tk.END).strip(),
		"theme": current_theme,
	}
	try:
		with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
			json.dump(settings, f, ensure_ascii=False, indent=2)
		add_log("Đã lưu cài đặt.")
	except Exception as e:
		messagebox.showerror("Lỗi", f"Không thể lưu cài đặt: {e}")


def apply_settings(settings):
	global current_theme, PALETTE
	api_key_entry.insert(0, settings.get("api_key", ""))
	input_path.set(settings.get("input_file", ""))
	output_path.set(settings.get("output_file", ""))
	model_var.set(settings.get("model", MODELS[0]))
	thread_var.set(settings.get("threads", "3"))
	chunk_size_var.set(settings.get("chunk_size", str(CHUNK_SIZE)))
	max_output_tokens_var.set(settings.get("max_output_tokens", str(MAX_TOKENS)))
	temp_var.set(settings.get("temperature", "0.5"))
	prompt_text.delete("1.0", tk.END)
	prompt_text.insert(tk.END, settings.get("prompt", DEFAULT_PROMPT))
	current_theme = settings.get("theme", "dark")
	PALETTE = THEMES[current_theme]


def on_closing():
	save_settings()
	root.destroy()

# ================= HỖ TRỢ =================
def get_checkpoint_path(input_file):
	base_name = os.path.splitext(input_file)[0]
	return f"{base_name}.resume.json"


def build_default_output_path(input_file):
	input_dir = os.path.dirname(input_file)
	input_name = os.path.splitext(os.path.basename(input_file))[0]
	random_suffix = random.randint(1000, 9999)
	return os.path.join(input_dir, f"Dich_{input_name}_{random_suffix}.txt")


def add_log(message):
	timestamp = time.strftime("%H:%M:%S")
	log_message = f"[{timestamp}] {message}\n"
	if "log_box" in globals():
		log_box.config(state="normal")
		log_box.insert(tk.END, log_message)
		log_box.see(tk.END)
		log_box.config(state="disabled")
	print(log_message.strip())


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
	except Exception as e:
		print(f"Lỗi khi lưu checkpoint: {e}")


def format_time(seconds):
	if seconds < 0:
		return "--:--"
	hours = int(seconds // 3600)
	minutes = int((seconds % 3600) // 60)
	secs = int(seconds % 60)
	if hours > 0:
		return f"{hours:02d}:{minutes:02d}:{secs:02d}"
	return f"{minutes:02d}:{secs:02d}"


def load_translation_history():
	try:
		if os.path.exists(HISTORY_FILE):
			with open(HISTORY_FILE, "r", encoding="utf-8") as f:
				data = json.load(f)
			if isinstance(data, list):
				return data
	except Exception as e:
		print(f"Không thể tải lịch sử dịch: {e}")
	return []


def save_translation_history_entry(entry, max_entries=200):
	try:
		history = load_translation_history()
		history.append(entry)
		history = history[-max_entries:]
		with open(HISTORY_FILE, "w", encoding="utf-8") as f:
			json.dump(history, f, ensure_ascii=False, indent=2)
	except Exception as e:
		print(f"Không thể lưu lịch sử dịch: {e}")


def refresh_history_display():
	if "history_table" not in globals():
		return
	history = load_translation_history()
	for row_id in history_table.get_children():
		history_table.delete(row_id)
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
		total_cost = float(item.get("total_cost_usd", 0.0) or 0.0)
		threads = item.get("threads", "--")
		temperature = item.get("temperature", "--")
		error = item.get("error", "")
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
				f"in {input_tokens:,} | out {output_tokens:,}",
				f"${total_cost:.4f}",
				duration,
				f"{threads} luồng | temp {temperature}",
				f"{in_file} → {out_file}",
				(error[:80] + "...") if len(error) > 80 else error,
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
		add_log("Đã xóa lịch sử dịch.")
	except Exception as e:
		messagebox.showerror("Lỗi", f"Không thể xóa lịch sử dịch: {e}")


def get_model_prices_usd_per_1m(model_id):
	pricing = MODEL_PRICING.get(model_id, {"input_per_1m": 0.0, "output_per_1m": 0.0})
	return pricing.get("input_per_1m", 0.0), pricing.get("output_per_1m", 0.0)


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
		speed = done / (elapsed / 60)
	else:
		eta = -1
		speed = 0
	stats_time_var.set(f"⏱️ Đã chạy: {format_time(elapsed)}")
	stats_eta_var.set(f"⏳ Còn lại: {format_time(eta)}")
	stats_speed_var.set(f"🚀 Tốc độ: {speed:.1f} đoạn/phút")
	stats_chars_var.set(f"📝 Ký tự: {stats['total_input_chars']:,} → {stats['total_output_chars']:,}")
	stats_input_tokens_var.set(f"🔢 Input Token: {stats['total_input_tokens']:,}")
	stats_output_tokens_var.set(f"🔢 Output Token: {stats['total_output_tokens']:,}")
	stats_input_cost_var.set(f"💵 Input Cost: ${stats['total_input_cost_usd']:.4f}")
	stats_output_cost_var.set(f"💵 Output Cost: ${stats['total_output_cost_usd']:.4f}")
	stats_total_cost_var.set(f"💰 Total Cost: ${stats['total_cost_usd']:.4f}")

# ================= THEME =================
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
				current_bg = widget.cget("bg")
				if current_bg not in [PALETTE["accent"], PALETTE["accent_alt"], "#f59e0b", "#38bdf8", "#0ea5e9"]:
					widget.configure(bg=PALETTE["panel"], fg=PALETTE["text"])
			except Exception:
				pass
		elif widget_type in ["Entry", "Text"]:
			try:
				widget.configure(bg=PALETTE["input_bg"], fg=PALETTE["text"], insertbackground=PALETTE["accent"], highlightbackground=PALETTE["border"])
			except Exception:
				pass
		for child in widget.winfo_children():
			update_widget_colors(child)
	except Exception:
		pass


def apply_theme():
	root.configure(bg=PALETTE["bg"])
	canvas_bg.configure(bg=PALETTE["bg"])
	scrollbar.configure(bg=PALETTE["border"], troughcolor=PALETTE["bg"], activebackground=PALETTE["accent"])
	style.configure("Card.TFrame", background=PALETTE["panel"])
	style.configure("TLabel", background=PALETTE["panel"], foreground=PALETTE["text"])
	style.configure("Header.TLabel", background=PALETTE["bg"], foreground=PALETTE["text"], font=("Segoe UI", 22, "bold"))
	style.configure("SubHeader.TLabel", background=PALETTE["bg"], foreground=PALETTE["text_muted"], font=("Segoe UI", 11))
	style.configure("Accent.Horizontal.TProgressbar", troughcolor=PALETTE["panel"], background=PALETTE["accent"])
	style.configure("History.Treeview", background=PALETTE["input_bg"], fieldbackground=PALETTE["input_bg"], foreground="#000000", bordercolor=PALETTE["border"], rowheight=28)
	style.map("History.Treeview", background=[("selected", PALETTE["accent_alt"])], foreground=[("selected", "#000000")])
	style.configure("History.Treeview.Heading", background=PALETTE["panel"], foreground="#000000", relief="flat", font=("Segoe UI", 9, "bold"))
	style.map("History.Treeview.Heading", background=[("active", PALETTE["accent"])], foreground=[("active", "#000000")])
	if "history_table" in globals():
		history_table.tag_configure("odd", background=PALETTE["input_bg"])
		history_table.tag_configure("even", background=PALETTE["panel"])
		history_table.tag_configure("status_completed", foreground="#000000")
		history_table.tag_configure("status_stopped", foreground="#000000")
		history_table.tag_configure("status_error", foreground="#000000")
	if "cost_tree_table" in globals():
		cost_tree_table.tag_configure("month_row", background=PALETTE["panel"], foreground=PALETTE["accent"], font=("Segoe UI", 10, "bold"))
		cost_tree_table.tag_configure("week_row", background=PALETTE["input_bg"], foreground=PALETTE["text"])
	if "history_hint_label" in globals():
		history_hint_label.configure(bg=PALETTE["panel"], fg="#000000")
	for widget in main_container.winfo_children():
		update_widget_colors(widget)


def toggle_theme():
	global current_theme, PALETTE
	current_theme = "light" if current_theme == "dark" else "dark"
	PALETTE = THEMES[current_theme]
	apply_theme()
	draw_gradient()
	btn_theme.config(text=("🌙 Tối" if current_theme == "dark" else "☀️ Sáng"))
	add_log(f"Đã chuyển sang chế độ {'tối' if current_theme == 'dark' else 'sáng'}.")

# ================= TRANSLATION CORE =================
def split_text(text, size=CHUNK_SIZE):
	chunks = []
	current = ""
	chapter_pattern = re.compile(r'^\s*(\d+\s*\||Chương\s+\d+|Quyển\s+\d+|Đệ\s+\d+\s+Chương)', re.IGNORECASE)
	for line in text.splitlines(True):
		is_chapter_heading = chapter_pattern.match(line)
		if (is_chapter_heading and len(current) > 500) or (len(current) + len(line) > size):
			if current.strip():
				chunks.append(current)
			current = line
		else:
			current += line
	if current.strip():
		chunks.append(current)
	return chunks


def http_post_json(url, headers, payload):
	data_json = json.dumps(payload, ensure_ascii=False)
	curl_exe = shutil.which("curl")
	if curl_exe:
		command = [
			curl_exe,
			"--url",
			url,
			"--silent",
			"--show-error",
			"--location",
			"--request",
			"POST",
		]
		for key, value in headers.items():
			command.extend(["--header", f"{key}: {value}"])
		command.extend(["--data-raw", data_json])
		completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=120)
		if completed.returncode != 0:
			raise urllib.error.HTTPError(url, completed.returncode, completed.stderr.strip() or "curl failed", hdrs=None, fp=None)
		return json.loads(completed.stdout)
	data = data_json.encode("utf-8")
	req = urllib.request.Request(url, data=data, headers=headers, method="POST")
	with urllib.request.urlopen(req, timeout=120) as response:
		body = response.read().decode("utf-8")
		return json.loads(body)


def call_claude_proxy(api_key, model_id, prompt, chunk, temperature, max_output_tokens):
	payload = {
		"model": model_id,
		"max_tokens": max_output_tokens,
		"temperature": temperature,
		"system": prompt,
		"messages": [
			{"role": "user", "content": chunk}
		],
	}
	headers = {
		"x-api-key": api_key,
		"anthropic-version": CLAUDE_API_VERSION,
		"content-type": "application/json",
	}
	result = http_post_json(CLAUDE_PROXY_URL, headers, payload)
	content = result.get("content", [])
	text_parts = [part.get("text", "") for part in content if isinstance(part, dict)]
	usage = result.get("usage", {})
	return "\n".join([p for p in text_parts if p]).strip(), int(usage.get("input_tokens", 0) or 0), int(usage.get("output_tokens", 0) or 0)


def request_translation(api_key, model_id, prompt, chunk, temperature, max_output_tokens):
	return call_claude_proxy(api_key, model_id, prompt, chunk, temperature, max_output_tokens)


def translate_chunk(api_key, model_id, prompt, chunk, index, cp_file, temperature, max_output_tokens, retries=3):
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
			add_log(f"Đang dịch đoạn {index + 1}... ({attempt + 1}/{retries})")
			translated_text, input_tokens, output_tokens = request_translation(api_key, model_id, prompt, chunk, temperature, max_output_tokens)
			if not translated_text:
				raise ValueError("Proxy/Claude trả về nội dung rỗng")
			input_price, output_price = get_model_prices_usd_per_1m(model_id)
			input_cost = (input_tokens / 1_000_000) * input_price
			output_cost = (output_tokens / 1_000_000) * output_price
			save_checkpoint(cp_file, index, translated_text)
			stats["chunks_done"] += 1
			stats["total_input_chars"] += len(chunk)
			stats["total_output_chars"] += len(translated_text)
			stats["total_input_tokens"] += input_tokens
			stats["total_output_tokens"] += output_tokens
			stats["total_input_cost_usd"] += input_cost
			stats["total_output_cost_usd"] += output_cost
			stats["total_cost_usd"] = stats["total_input_cost_usd"] + stats["total_output_cost_usd"]
			add_log(f"Hoàn thành đoạn {index + 1}")
			return index, translated_text
		except urllib.error.HTTPError as e:
			err_body = ""
			try:
				err_body = e.read().decode("utf-8")
			except Exception:
				err_body = str(e)
			last_error = f"HTTP {e.code}: {err_body[:300]}"
			add_log(f"Đoạn {index + 1} lỗi HTTP: {last_error}")
			time.sleep(2 + attempt * 2)
		except Exception as e:
			last_error = str(e)
			add_log(f"Đoạn {index + 1} lỗi: {last_error[:200]}")
			time.sleep(2 + attempt * 2)
	stats["chunks_done"] += 1
	return index, f"[ĐOẠN {index + 1} BỊ LỖI SAU {retries} LẦN: {last_error}]"

# ================= ĐIỀU KHIỂN =================
def toggle_pause():
	global is_paused
	if is_paused:
		is_paused = False
		pause_event.set()
		btn_pause.config(text="⏸️ TẠM DỪNG", bg="#fbbf24")
		add_log("Đã tiếp tục dịch.")
	else:
		is_paused = True
		pause_event.clear()
		btn_pause.config(text="▶️ TIẾP TỤC", bg="#4CAF50")
		add_log("Đã tạm dừng.")


def stop_translation():
	global is_stopped, is_paused
	if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn DỪNG dịch?\n(Tiến trình đã lưu, có thể dịch tiếp sau)"):
		is_stopped = True
		is_paused = False
		pause_event.set()
		add_log("Đang dừng quá trình dịch...")


def start_translation():
	global is_stopped, is_paused
	is_stopped = False
	is_paused = False
	pause_event.set()
	api_key = api_key_entry.get().strip()
	if not api_key.startswith("sk-"):
		messagebox.showerror("Lỗi", "Vui lòng nhập Claude API Key đúng dạng sk-...")
		return
	if not input_path.get():
		messagebox.showerror("Lỗi", "Vui lòng chọn file truyện đầu vào.")
		return
	try:
		chunk_size = int(chunk_size_var.get())
		if chunk_size < 500 or chunk_size > 50000:
			raise ValueError
	except Exception:
		messagebox.showerror("Lỗi", "Chunk size phải là số nguyên từ 500 đến 50000.")
		return
	try:
		max_output_tokens = int(max_output_tokens_var.get())
		if max_output_tokens < 256 or max_output_tokens > 65536:
			raise ValueError
	except Exception:
		messagebox.showerror("Lỗi", "Max output tokens phải là số nguyên từ 256 đến 65536.")
		return
	output_path.set(build_default_output_path(input_path.get()))
	add_log(f"File output mặc định: {output_path.get()}")
	save_settings()
	task_thread = threading.Thread(target=process_translation_logic)
	task_thread.daemon = True
	task_thread.start()
	stats_thread = threading.Thread(target=stats_update_loop)
	stats_thread.daemon = True
	stats_thread.start()
	add_log("Đã kích hoạt luồng dịch ngầm...")


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
	stats["total_input_cost_usd"] = 0.0
	stats["total_output_cost_usd"] = 0.0
	stats["total_cost_usd"] = 0.0
	history_status = "error"
	history_error = ""
	in_file = input_path.get()
	out_file = output_path.get()
	model = model_var.get()
	threads = thread_var.get()
	try:
		cp_file = get_checkpoint_path(in_file)
		threads = int(thread_var.get())
		chunk_size = int(chunk_size_var.get())
		max_output_tokens = int(max_output_tokens_var.get())
		temperature = float(temp_var.get())
		prompt = prompt_text.get("1.0", tk.END).strip()
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
					results[int(idx_str)] = text
				stats["chunks_done"] = len(saved_data)
				add_log(f"Đã khôi phục {len(saved_data)} đoạn từ checkpoint.")
		else:
			with open(cp_file, "w", encoding="utf-8") as f:
				json.dump({}, f)
		progress_bar["maximum"] = total
		pending_indices = [i for i in range(total) if results[i] is None]
		progress_bar["value"] = total - len(pending_indices)
		add_log(f"Bắt đầu dịch {len(pending_indices)} đoạn còn lại bằng {model}...")
		add_log(f"Chunk size: {chunk_size} | Max output tokens: {max_output_tokens} | Temperature: {temperature}")
		with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
			futures = {
				executor.submit(translate_chunk, api_key_entry.get().strip(), model, prompt, chunks[i], i, cp_file, temperature, max_output_tokens): i
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
					status_var.set(f"Tiến độ: {current_val}/{total}")
					root.update_idletasks()
		if is_stopped:
			add_log("Đã dừng dịch. Tiến trình được lưu ở checkpoint.")
			messagebox.showinfo("Đã dừng", "Quá trình dịch đã dừng. Tiến trình được lưu, bạn có thể tiếp tục sau.")
			history_status = "stopped"
			return
		with open(out_file, "w", encoding="utf-8") as f:
			f.write("\n\n".join([r for r in results if r is not None]))
		if os.path.exists(cp_file):
			os.remove(cp_file)
		total_time = time.time() - stats["start_time"]
		add_log(f"HOÀN TẤT! Tổng thời gian: {format_time(total_time)}")
		add_log(f"Đã dịch {stats['total_input_chars']:,} → {stats['total_output_chars']:,} ký tự")
		add_log(f"Input Token: {stats['total_input_tokens']:,}")
		add_log(f"Output Token: {stats['total_output_tokens']:,}")
		add_log(f"Input Cost: ${stats['total_input_cost_usd']:.4f}")
		add_log(f"Output Cost: ${stats['total_output_cost_usd']:.4f}")
		add_log(f"Total Cost: ${stats['total_cost_usd']:.4f}")
		history_status = "completed"
		messagebox.showinfo("Hoàn tất", f"Truyện đã được dịch xong!\nThời gian: {format_time(total_time)}\nTổng tiền: ${stats['total_cost_usd']:.4f}\nLưu tại: {out_file}")
	except Exception as e:
		history_error = str(e)
		add_log(f"LỖI HỆ THỐNG: {history_error}")
		messagebox.showerror("Lỗi", f"Quá trình dịch bị gián đoạn: {history_error}")
	finally:
		end_time = time.time()
		duration_seconds = max(0, int(end_time - stats["start_time"])) if stats["start_time"] else 0
		history_entry = {
			"engine": "Claude Proxy",
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
			"total_input_cost_usd": round(stats["total_input_cost_usd"], 6),
			"total_output_cost_usd": round(stats["total_output_cost_usd"], 6),
			"total_cost_usd": round(stats["total_cost_usd"], 6),
			"error": history_error,
		}
		save_translation_history_entry(history_entry)
		refresh_history_display()
		btn_start.config(state="normal")
		btn_pause.config(state="disabled", text="⏸️ TẠM DỪNG", bg="#fbbf24")
		btn_stop.config(state="disabled")
		status_var.set("Sẵn sàng")
		is_stopped = True

# ================= GUI =================
root = tk.Tk()
root.title("📖 App Dịch Truyện – Claude Proxy")
root.geometry("1100x950")
root.minsize(800, 600)
root.configure(bg=PALETTE["bg"])

style = ttk.Style()
style.theme_use("clam")
style.configure("Card.TFrame", background=PALETTE["panel"], borderwidth=0, relief="flat")
style.configure("TLabel", background=PALETTE["panel"], foreground=PALETTE["text"], font=("Segoe UI", 10))
style.configure("Header.TLabel", background=PALETTE["bg"], foreground=PALETTE["text"], font=("Segoe UI", 22, "bold"))
style.configure("SubHeader.TLabel", background=PALETTE["bg"], foreground=PALETTE["text_muted"], font=("Segoe UI", 11))
style.configure("Accent.Horizontal.TProgressbar", troughcolor=PALETTE["panel"], background=PALETTE["accent"], bordercolor=PALETTE["panel"], lightcolor=PALETTE["accent"], darkcolor=PALETTE["accent"])
style.configure("History.Treeview", background=PALETTE["input_bg"], fieldbackground=PALETTE["input_bg"], foreground="#000000", bordercolor=PALETTE["border"], rowheight=28)
style.map("History.Treeview", background=[("selected", PALETTE["accent_alt"])], foreground=[("selected", "#000000")])
style.configure("History.Treeview.Heading", background=PALETTE["panel"], foreground="#000000", relief="flat", font=("Segoe UI", 9, "bold"))
style.map("History.Treeview.Heading", background=[("active", PALETTE["accent"])], foreground=[("active", "#000000")])

canvas_bg = tk.Canvas(root, highlightthickness=0, bd=0, bg=PALETTE["bg"])
scrollbar = tk.Scrollbar(root, orient="vertical", command=canvas_bg.yview, bg=PALETTE["border"], troughcolor=PALETTE["bg"])
canvas_bg.configure(yscrollcommand=scrollbar.set)
scrollbar.pack(side="right", fill="y")
canvas_bg.pack(side="left", fill="both", expand=True)

main_container = tk.Frame(canvas_bg, bg=PALETTE["bg"])
canvas_window = canvas_bg.create_window((0, 0), window=main_container, anchor="nw")


def on_frame_configure(event=None):
	canvas_bg.configure(scrollregion=canvas_bg.bbox("all"))


def on_canvas_configure(event):
	canvas_bg.itemconfig(canvas_window, width=event.width)


canvas_bg.bind("<Configure>", draw_gradient)
canvas_bg.bind("<Configure>", on_canvas_configure)
main_container.bind("<Configure>", on_frame_configure)
draw_gradient()


def on_mousewheel(event):
	canvas_bg.yview_scroll(int(-1 * (event.delta / 120)), "units")


canvas_bg.bind_all("<MouseWheel>", on_mousewheel)

main_frame = tk.Frame(main_container, bg=PALETTE["bg"])
main_frame.pack(fill="both", expand=True, padx=20, pady=10)
main_frame.columnconfigure(0, weight=1)
main_frame.columnconfigure(1, weight=1)

header = tk.Frame(main_frame, bg=PALETTE["bg"])
header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
header_top = tk.Frame(header, bg=PALETTE["bg"])
header_top.pack(fill="x")
header_title_frame = tk.Frame(header_top, bg=PALETTE["bg"])
header_title_frame.pack(side="left", fill="both", expand=True)

ttk.Label(header_title_frame, text="App Dịch Truyện – Claude Proxy", style="Header.TLabel").pack(anchor="w")
ttk.Label(header_title_frame, text="Dịch truyện bằng Claude qua proxy bên thứ ba, có resume, history và thống kê chi phí.", style="SubHeader.TLabel").pack(anchor="w", pady=(4, 6))

btn_theme = tk.Button(header_top, text="🌙 Tối", font=("Segoe UI", 10, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=15, pady=8, command=toggle_theme, cursor="hand2")
btn_theme.pack(side="right", padx=(10, 0))

badge_row = tk.Frame(header, bg=PALETTE["bg"])
badge_row.pack(anchor="w", pady=(4, 0))
for text, color in [("Claude API Proxy", PALETTE["accent"]), ("Latest models: Opus 4.7 / Sonnet 4.6 / Haiku 4.5", PALETTE["accent_alt"])]:
	tk.Label(badge_row, text=text, background=color, foreground="#0b0f19", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 8), ipadx=10, ipady=4)


def build_card(parent, title, col, row, colspan=1, rowspan=1):
	card = ttk.Frame(parent, style="Card.TFrame")
	card.grid(row=row, column=col, columnspan=colspan, rowspan=rowspan, sticky="nsew", padx=6, pady=6, ipadx=8, ipady=8)
	card.columnconfigure(0, weight=1)
	tk.Label(card, text=title, background=PALETTE["panel"], foreground=PALETTE["text"], font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
	return card


tabs = ttk.Notebook(main_frame)
tabs.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 6))
main_frame.rowconfigure(1, weight=1)

translate_tab = tk.Frame(tabs, bg=PALETTE["bg"])
preview_tab = tk.Frame(tabs, bg=PALETTE["bg"])
history_tab = tk.Frame(tabs, bg=PALETTE["bg"])
stats_tab = tk.Frame(tabs, bg=PALETTE["bg"])
tabs.add(translate_tab, text="🚀 Dịch truyện")
tabs.add(preview_tab, text="👀 Xem Chunk")
tabs.add(history_tab, text="🗂️ Lịch sử dịch")
tabs.add(stats_tab, text="💰 Thống kê chi phí")
for col in range(2):
	translate_tab.columnconfigure(col, weight=1)
history_tab.columnconfigure(0, weight=1)
history_tab.rowconfigure(1, weight=1)
preview_tab.columnconfigure(0, weight=1)
preview_tab.columnconfigure(1, weight=3)
preview_tab.rowconfigure(1, weight=1)
stats_tab.columnconfigure(0, weight=1)
stats_tab.rowconfigure(1, weight=1)

input_path = tk.StringVar()
output_path = tk.StringVar()
model_var = tk.StringVar(value=MODELS[0])
thread_var = tk.StringVar(value="3")
chunk_size_var = tk.StringVar(value=str(CHUNK_SIZE))
max_output_tokens_var = tk.StringVar(value=str(MAX_TOKENS))
temp_var = tk.StringVar(value="0.5")
entry_opts = {"bg": PALETTE["input_bg"], "fg": PALETTE["text"], "insertbackground": PALETTE["accent"], "relief": "flat", "highlightthickness": 1, "highlightbackground": PALETTE["border"]}

card_api = build_card(translate_tab, "🔐 Claude API Key", 0, 1, colspan=2)
tk.Label(card_api, text="Dùng key dạng sk-... của Anthropic. App sẽ gọi proxy gwai.cloud thay vì endpoint gốc.", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=(0, 6))
api_key_frame = tk.Frame(card_api, bg=PALETTE["panel"])
api_key_frame.grid(row=2, column=0, sticky="ew")
api_key_frame.columnconfigure(0, weight=1)
api_key_entry = tk.Entry(api_key_frame, show="*", width=60, **entry_opts)
api_key_entry.grid(row=0, column=0, sticky="ew")


def toggle_api_key_visibility():
	if api_key_entry.cget("show") == "*":
		api_key_entry.config(show="")
		btn_toggle_api.config(text="🙈 Ẩn")
	else:
		api_key_entry.config(show="*")
		btn_toggle_api.config(text="👁️ Hiện")


btn_toggle_api = tk.Button(api_key_frame, text="👁️ Hiện", font=("Segoe UI", 9, "bold"), pady=2, command=toggle_api_key_visibility)
btn_toggle_api.grid(row=0, column=1, padx=(6, 0))

tk.Label(card_api, text="Model mới nhất hiện tại theo docs: claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5.", bg=PALETTE["panel"], fg=PALETTE["accent_alt"], font=("Segoe UI", 9, "bold")).grid(row=3, column=0, sticky="w", pady=(4, 0))

card_files = build_card(translate_tab, "📂 Chọn file nguồn / đích", 0, 2)
tk.Label(card_files, text="File truyện đầu vào (.txt)", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w")
frame_input = tk.Frame(card_files, bg=PALETTE["panel"])
frame_input.grid(row=2, column=0, sticky="ew", pady=(2, 8))
frame_input.columnconfigure(0, weight=1)
tk.Entry(frame_input, textvariable=input_path, **entry_opts).grid(row=0, column=0, sticky="ew")
tk.Button(frame_input, text="Chọn file", bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=10, pady=6, command=lambda: input_path.set(filedialog.askopenfilename(filetypes=[("Text files", "*.txt")]))).grid(row=0, column=1, padx=(8, 0))
tk.Label(card_files, text="Output sẽ tự động lưu cạnh file input theo mẫu: Dich_tên_file_số_ngẫu_nhiên.txt", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9)).grid(row=3, column=0, sticky="w", pady=(6, 0))

card_config = build_card(translate_tab, "⚙️ Cấu hình dịch", 1, 2)
tk.Label(card_config, text="Model", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w")
model_cb = ttk.Combobox(card_config, values=MODELS, textvariable=model_var, state="readonly")
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
tk.Label(card_config, text="Nhiệt độ (0-1)", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=4, column=0, sticky="w")
temp_scale = ttk.Scale(card_config, from_=0.0, to=1.0, variable=temp_var, orient="horizontal", length=200)
temp_scale.grid(row=5, column=0, sticky="ew")
temp_label = tk.Label(card_config, textvariable=temp_var, bg=PALETTE["panel"], fg=PALETTE["accent"], font=("Segoe UI", 10, "bold"))
temp_label.grid(row=5, column=1, padx=(8, 0))


def update_temp_label(event=None):
	try:
		temp_var.set(f"{float(temp_var.get()):.2f}")
	except Exception:
		pass


temp_scale.bind("<Motion>", update_temp_label)
temp_scale.bind("<ButtonRelease-1>", update_temp_label)

card_prompt = build_card(translate_tab, "📝 Prompt dịch giả", 0, 3, colspan=2)
prompt_text = tk.Text(card_prompt, height=5, bg=PALETTE["input_bg"], fg=PALETTE["text"], insertbackground=PALETTE["accent"], wrap="word", relief="flat", highlightthickness=1, highlightbackground=PALETTE["border"])
prompt_text.grid(row=1, column=0, sticky="nsew", pady=(4, 6))
prompt_text.insert(tk.END, DEFAULT_PROMPT)
card_prompt.rowconfigure(1, weight=1)

card_stats = build_card(translate_tab, "📊 Thống kê", 0, 4)
stats_time_var = tk.StringVar(value="⏱️ Đã chạy: --:--")
stats_eta_var = tk.StringVar(value="⏳ Còn lại: --:--")
stats_speed_var = tk.StringVar(value="🚀 Tốc độ: -- đoạn/phút")
stats_chars_var = tk.StringVar(value="📝 Ký tự: -- → --")
stats_input_tokens_var = tk.StringVar(value="🔢 Input Token: --")
stats_output_tokens_var = tk.StringVar(value="🔢 Output Token: --")
stats_input_cost_var = tk.StringVar(value="💵 Input Cost: $0.0000")
stats_output_cost_var = tk.StringVar(value="💵 Output Cost: $0.0000")
stats_total_cost_var = tk.StringVar(value="💰 Total Cost: $0.0000")
for i, var in enumerate([stats_time_var, stats_eta_var, stats_speed_var, stats_chars_var, stats_input_tokens_var, stats_output_tokens_var, stats_input_cost_var, stats_output_cost_var, stats_total_cost_var]):
	tk.Label(card_stats, textvariable=var, background=PALETTE["panel"], foreground=PALETTE["text"], font=("Consolas", 10)).grid(row=1 + i // 2, column=i % 2, sticky="w", padx=8, pady=4)

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
btn_save_settings = tk.Button(card_progress, text="💾 LƯU CÀI ĐẶT", font=("Segoe UI", 10, "bold"), bg=PALETTE["ok"], fg="#0b0f19", bd=0, padx=10, pady=8, command=save_settings)
btn_save_settings.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0), padx=(0, 6))
btn_reset_prompt = tk.Button(card_progress, text="🔄 RESET PROMPT", font=("Segoe UI", 10, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=10, pady=8, command=lambda: (prompt_text.delete("1.0", tk.END), prompt_text.insert(tk.END, DEFAULT_PROMPT)))
btn_reset_prompt.grid(row=4, column=2, sticky="ew", pady=(8, 0), padx=(6, 0))
for c in range(3):
	card_progress.columnconfigure(c, weight=1)

card_log = build_card(translate_tab, "📋 Nhật ký hoạt động", 0, 5, colspan=2)
log_box = scrolledtext.ScrolledText(card_log, height=8, state="disabled", bg=PALETTE["input_bg"], fg=PALETTE["text"], insertbackground=PALETTE["accent"], relief="flat", highlightthickness=1, highlightbackground=PALETTE["border"])
log_box.grid(row=1, column=0, sticky="nsew")
card_log.rowconfigure(1, weight=1)

card_history = build_card(history_tab, "🗂️ Lịch sử dịch", 0, 0, colspan=1)
history_toolbar = tk.Frame(card_history, bg=PALETTE["panel"])
history_toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 6))
history_toolbar.columnconfigure(0, weight=1)
history_hint_var = tk.StringVar(value="Hiển thị 20 lần dịch gần nhất.")
history_hint_label = tk.Label(history_toolbar, textvariable=history_hint_var, bg=PALETTE["panel"], fg="#000000", font=("Segoe UI", 9))
history_hint_label.grid(row=0, column=0, sticky="w")
tk.Button(history_toolbar, text="🔄 Làm mới", font=("Segoe UI", 9, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=10, pady=5, command=refresh_history_display).grid(row=0, column=1, padx=(8, 6))
tk.Button(history_toolbar, text="🗑️ Xóa lịch sử", font=("Segoe UI", 9, "bold"), bg=PALETTE["warn"], fg="#0b0f19", bd=0, padx=10, pady=5, command=clear_translation_history).grid(row=0, column=2)

history_table_frame = tk.Frame(card_history, bg=PALETTE["panel"])
history_table_frame.grid(row=2, column=0, sticky="nsew")
history_table_frame.columnconfigure(0, weight=1)
history_table_frame.rowconfigure(0, weight=1)

history_columns = ("start_at", "status", "model", "progress", "chars", "tokens", "cost", "duration", "meta", "files", "error")
history_table = ttk.Treeview(history_table_frame, columns=history_columns, show="headings", style="History.Treeview")
history_table.grid(row=0, column=0, sticky="nsew")
history_scroll_y = ttk.Scrollbar(history_table_frame, orient="vertical", command=history_table.yview)
history_scroll_y.grid(row=0, column=1, sticky="ns")
history_scroll_x = ttk.Scrollbar(history_table_frame, orient="horizontal", command=history_table.xview)
history_scroll_x.grid(row=1, column=0, sticky="ew")
history_table.configure(yscrollcommand=history_scroll_y.set, xscrollcommand=history_scroll_x.set)
for col_name, title in [("start_at", "Bắt đầu"), ("status", "Trạng thái"), ("model", "Model"), ("progress", "Tiến độ"), ("chars", "Ký tự"), ("tokens", "Token"), ("cost", "Tổng tiền"), ("duration", "Thời gian"), ("meta", "Thiết lập"), ("files", "File"), ("error", "Lỗi")]:
	history_table.heading(col_name, text=title)
for col_name, width, anchor in [("start_at", 145, "w"), ("status", 95, "center"), ("model", 220, "w"), ("progress", 90, "center"), ("chars", 160, "e"), ("tokens", 190, "e"), ("cost", 100, "e"), ("duration", 90, "center"), ("meta", 130, "center"), ("files", 340, "w"), ("error", 220, "w")]:
	history_table.column(col_name, width=width, anchor=anchor)
history_table.tag_configure("odd", background=PALETTE["input_bg"])
history_table.tag_configure("even", background=PALETTE["panel"])
history_table.tag_configure("status_completed", foreground="#000000")
history_table.tag_configure("status_stopped", foreground="#000000")
history_table.tag_configure("status_error", foreground="#000000")
card_history.rowconfigure(2, weight=1)

preview_toolbar = tk.Frame(preview_tab, bg=PALETTE["panel"])
preview_toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6), padx=6)
preview_info_var = tk.StringVar(value="Tổng số chunk: 0")
previewed_chunks = []


def load_and_preview_chunks():
	global previewed_chunks
	try:
		input_file = input_path.get()
		if not input_file or not os.path.exists(input_file):
			messagebox.showwarning("Cảnh báo", "Vui lòng chọn file đầu vào hợp lệ.")
			return
		try:
			size_limit = int(chunk_size_var.get())
		except ValueError:
			messagebox.showwarning("Cảnh báo", "Chunk size không hợp lệ.")
			return
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
	except Exception as e:
		messagebox.showerror("Lỗi", f"Không thể chia chunk: {str(e)}")


tk.Button(preview_toolbar, text="🔄 Tải & Chia Chunk", font=("Segoe UI", 9, "bold"), bg=PALETTE["accent_alt"], bd=0, padx=10, pady=5, command=load_and_preview_chunks).pack(side="left", padx=5, pady=5)
tk.Label(preview_toolbar, textvariable=preview_info_var, bg=PALETTE["panel"], fg=PALETTE["text"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=10)
chunk_list_frame = tk.Frame(preview_tab, bg=PALETTE["panel"])
chunk_list_frame.grid(row=1, column=0, sticky="nsew", padx=(6, 3), pady=6)
chunk_list_frame.rowconfigure(0, weight=1)
chunk_list_frame.columnconfigure(0, weight=1)
chunk_list_scroll = tk.Scrollbar(chunk_list_frame)
chunk_listbox = tk.Listbox(chunk_list_frame, bg=PALETTE["input_bg"], fg=PALETTE["text"], selectbackground=PALETTE["accent_alt"], selectforeground="#000000", bd=0, highlightthickness=0, font=("Consolas", 10))
chunk_listbox.pack(side="left", fill="both", expand=True)
chunk_list_scroll.pack(side="right", fill="y")
chunk_listbox.configure(yscrollcommand=chunk_list_scroll.set)
chunk_list_scroll.configure(command=chunk_listbox.yview)
chunk_content_frame = tk.Frame(preview_tab, bg=PALETTE["panel"])
chunk_content_frame.grid(row=1, column=1, sticky="nsew", padx=(3, 6), pady=6)
chunk_content_frame.rowconfigure(0, weight=1)
chunk_content_frame.columnconfigure(0, weight=1)
chunk_content_text = scrolledtext.ScrolledText(chunk_content_frame, state="disabled", bg=PALETTE["input_bg"], fg=PALETTE["text"], bd=0, highlightthickness=0, font=("Consolas", 11), wrap="word")
chunk_content_text.pack(fill="both", expand=True)


def on_chunk_select(event):
	selection = chunk_listbox.curselection()
	if selection:
		index = selection[0]
		chunk_content_text.config(state="normal")
		chunk_content_text.delete("1.0", tk.END)
		chunk_content_text.insert(tk.END, previewed_chunks[index])
		chunk_content_text.config(state="disabled")


chunk_listbox.bind("<<ListboxSelect>>", on_chunk_select)

stats_toolbar = tk.Frame(stats_tab, bg=PALETTE["panel"])
stats_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
total_cost_label_var = tk.StringVar(value="Tổng chi phí: $0.0000 (0 đ)")
tk.Label(stats_toolbar, textvariable=total_cost_label_var, bg=PALETTE["panel"], fg=PALETTE["text"], font=("Segoe UI", 12, "bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")


def refresh_cost_stats():
	if "cost_tree_table" not in globals():
		return
	for row_id in cost_tree_table.get_children():
		cost_tree_table.delete(row_id)
	history = load_translation_history()
	if not history:
		return
	stats_tree = {}
	overall_cost = 0.0
	overall_cost_vnd = 0.0
	for entry in history:
		start_at = entry.get("start_at", "")
		if not start_at or start_at == "--":
			continue
		try:
			dt = datetime.datetime.strptime(start_at, "%Y-%m-%d %H:%M:%S")
		except ValueError:
			continue
		iso_year, iso_week, _ = dt.isocalendar()
		monday = dt - datetime.timedelta(days=dt.weekday())
		sunday = monday + datetime.timedelta(days=6)
		month_key = f"🗓️ Tháng {dt.month}/{dt.year}"
		week_key = f"   📅 Tuần {iso_week} ({monday.strftime('%d/%m')} - {sunday.strftime('%d/%m')})"
		cost_usd = float(entry.get("total_cost_usd", 0.0) or 0.0)
		cost_vnd = float(entry.get("total_cost_vnd", cost_usd * USD_TO_VND) or 0.0)
		tokens_in = entry.get("total_input_tokens", 0)
		tokens_out = entry.get("total_output_tokens", 0)
		tokens = tokens_in + tokens_out
		chars = entry.get("total_input_chars", 0)
		if month_key not in stats_tree:
			stats_tree[month_key] = {"cost": 0.0, "cost_vnd": 0.0, "tokens": 0, "chars": 0, "sort_val": dt.strftime("%Y-%m"), "weeks": {}}
		month_data = stats_tree[month_key]
		month_data["cost"] += cost_usd
		month_data["cost_vnd"] += cost_vnd
		month_data["tokens"] += tokens
		month_data["chars"] += chars
		if week_key not in month_data["weeks"]:
			month_data["weeks"][week_key] = {"cost": 0.0, "cost_vnd": 0.0, "tokens": 0, "chars": 0, "sort_val": f"{iso_year}-{iso_week:02d}"}
		week_data = month_data["weeks"][week_key]
		week_data["cost"] += cost_usd
		week_data["cost_vnd"] += cost_vnd
		week_data["tokens"] += tokens
		week_data["chars"] += chars
		overall_cost += cost_usd
		overall_cost_vnd += cost_vnd
	total_cost_label_var.set(f"Tổng chi phí từ trước đến nay: ${overall_cost:.4f} ({int(overall_cost_vnd):,} đ)")
	for month_key in sorted(stats_tree.keys(), key=lambda k: stats_tree[k]["sort_val"], reverse=True):
		data = stats_tree[month_key]
		m_node = cost_tree_table.insert("", tk.END, text=month_key, values=(f"${data['cost']:.4f}", f"{int(data['cost_vnd']):,} đ", f"{data['tokens']:,}", f"{data['chars']:,}"), tags=("month_row",), open=True)
		weeks = data["weeks"]
		for week_key in sorted(weeks.keys(), key=lambda k: weeks[k]["sort_val"], reverse=True):
			w_data = weeks[week_key]
			cost_tree_table.insert(m_node, tk.END, text=week_key, values=(f"${w_data['cost']:.4f}", f"{int(w_data['cost_vnd']):,} đ", f"{w_data['tokens']:,}", f"{w_data['chars']:,}"), tags=("week_row",))


tk.Button(stats_toolbar, text="🔄 Làm mới thống kê", font=("Segoe UI", 9, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=10, pady=8, command=refresh_cost_stats).grid(row=0, column=2, padx=10)
stats_panels_frame = tk.Frame(stats_tab, bg=PALETTE["bg"])
stats_panels_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
stats_panels_frame.columnconfigure(0, weight=1)
stats_panels_frame.rowconfigure(0, weight=1)
card_tree = build_card(stats_panels_frame, "📊 Chi phí theo Tháng và Tuần", 0, 0)
card_tree.rowconfigure(1, weight=1)
tv_frame = tk.Frame(card_tree, bg=PALETTE["panel"])
tv_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 5))
tv_frame.columnconfigure(0, weight=1)
tv_frame.rowconfigure(0, weight=1)
cost_columns = ("total_cost", "total_cost_vnd", "total_tokens", "total_chars")
cost_tree_table = ttk.Treeview(tv_frame, columns=cost_columns, style="History.Treeview")
cost_tree_table.grid(row=0, column=0, sticky="nsew")
tv_scroll_y = ttk.Scrollbar(tv_frame, orient="vertical", command=cost_tree_table.yview)
tv_scroll_y.grid(row=0, column=1, sticky="ns")
cost_tree_table.configure(yscrollcommand=tv_scroll_y.set)
cost_tree_table.heading("#0", text="Thời gian")
cost_tree_table.heading("total_cost", text="Chi phí (USD)")
cost_tree_table.heading("total_cost_vnd", text="Chi phí (VNĐ)")
cost_tree_table.heading("total_tokens", text="Số Token")
cost_tree_table.heading("total_chars", text="Số Ký tự")
cost_tree_table.column("#0", width=300, anchor="w")
cost_tree_table.column("total_cost", width=120, anchor="e")
cost_tree_table.column("total_cost_vnd", width=150, anchor="e")
cost_tree_table.column("total_tokens", width=120, anchor="e")
cost_tree_table.column("total_chars", width=120, anchor="e")
cost_tree_table.tag_configure("month_row", background=PALETTE["panel"], foreground=PALETTE["accent"], font=("Segoe UI", 10, "bold"))
cost_tree_table.tag_configure("week_row", background=PALETTE["input_bg"], foreground=PALETTE["text"])

for i in range(6):
	translate_tab.rowconfigure(i, weight=1 if i in [3, 5] else 0)

saved_settings = load_settings()
apply_settings(saved_settings)
if saved_settings.get("theme"):
	current_theme = saved_settings["theme"]
	PALETTE = THEMES[current_theme]
	btn_theme.config(text=("🌙 Tối" if current_theme == "dark" else "☀️ Sáng"))
	apply_theme()

root.protocol("WM_DELETE_WINDOW", on_closing)
add_log("Đã tải cài đặt từ lần sử dụng trước.")
add_log("API Key được mã hóa khi lưu, chỉ hoạt động trên máy này.")
refresh_history_display()
refresh_cost_stats()

if __name__ == "__main__":
	root.mainloop()
