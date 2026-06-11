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
import requests

# ================= CẤU HÌNH XAH API =================
API_BASE_URL = "https://api.xah.io/v1/chat/completions"
API_KEY = "sk-d550a12461017a360f1c942f4271eae296bd6f10aca64c15d70847e46e6caf3c"

# Model từ Xah API
MODELS = ["phuocanh421994/Qwen3.7-Plus (Đại hạ giá)"]

CHUNK_SIZE = 3000  # Độ dài mỗi đoạn văn 3000
MAX_TOKENS = 8192  # Độ dài tối đa câu trả lời
USD_TO_VND = 25400

DEFAULT_PROMPT = (
	"Bạn là một biên tập viên truyện dịch chuyên nghiệp, thành thạo tiếng Trung và tiếng Việt.\n"
	"Nhiệm vụ của bạn là viết lại đoạn văn sau thành tiếng Việt thuần, tự nhiên, mượt mà, "
	"loại bỏ cảm giác máy dịch, sao cho đọc giống truyện Việt.\n"
	"Không dịch sát từng chữ, ưu tiên ý nghĩa, ngữ cảnh và cảm xúc.\n"
	"Cho phép gộp hoặc tách câu, điều chỉnh trật tự câu cho phù hợp tiếng Việt.\n"
	"Giữ nguyên nội dung, nhân vật, xưng hô, bối cảnh và ý nghĩa gốc.\n"
	"Không thêm nội dung mới, không lược bỏ nội dung.\n"
	"Không giải thích, không bình luận.\n"
	"Giữ cách xuống dòng và bố cục đoạn văn hợp lý như truyện.\n\n"
)

# ================= BIẾN ĐIỀU KHIỂN TẠM DỪNG =================
is_paused = False
is_stopped = False
pause_event = threading.Event()
pause_event.set()  # Mặc định không tạm dừng

# ================= THỐNG KÊ =================
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

# Giá token (USD / 1M token). Xah API chưa công bố rõ ràng nên để 0 tạm thời
MODEL_PRICING = {
	"phuocanh421994/Qwen3.7-Plus (Đại hạ giá)": {"input_per_1m": 0.0, "output_per_1m": 0.0},
}

def get_model_prices_usd_per_1m(model_id):
	pricing = MODEL_PRICING.get(model_id, {"input_per_1m": 0.0, "output_per_1m": 0.0})
	return pricing.get("input_per_1m", 0.0), pricing.get("output_per_1m", 0.0)

# ================= CHẾ ĐỘ SÁNG/TỐI =================
current_theme = "dark"  # Mặc định chế độ tối

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
		"gradient_end": "#1f2937"
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
		"gradient_end": "#e2e8f0"
	}
}

PALETTE = THEMES["dark"]

# ================= MÃ HÓA API KEY =================
def get_machine_key():
	"""Tạo key mã hóa dựa trên thông tin máy tính (unique cho mỗi máy/user)"""
	unique_string = os.environ.get('COMPUTERNAME', 'PC') + os.environ.get('USERNAME', 'User') + "DichTruyenSecretKey2025"
	return hashlib.sha256(unique_string.encode()).digest()

def xor_encrypt_decrypt(data: str, key: bytes) -> str:
	"""Mã hóa/giải mã bằng XOR (symmetric)"""
	if not data:
		return ""
	data_bytes = data.encode('utf-8')
	key_repeated = (key * ((len(data_bytes) // len(key)) + 1))[:len(data_bytes)]
	result = bytes([a ^ b for a, b in zip(data_bytes, key_repeated)])
	return base64.b64encode(result).decode('utf-8')

def xor_decrypt(encrypted_data: str, key: bytes) -> str:
	"""Giải mã XOR"""
	if not encrypted_data:
		return ""
	try:
		data_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
		key_repeated = (key * ((len(data_bytes) // len(key)) + 1))[:len(data_bytes)]
		result = bytes([a ^ b for a, b in zip(data_bytes, key_repeated)])
		return result.decode('utf-8')
	except Exception:
		return ""

def encrypt_api_key(api_key: str) -> str:
	"""Mã hóa API Key trước khi lưu"""
	return xor_encrypt_decrypt(api_key, get_machine_key())

def decrypt_api_key(encrypted_key: str) -> str:
	"""Giải mã API Key khi tải"""
	return xor_decrypt(encrypted_key, get_machine_key())

# ================= CẤU HÌNH LƯU TRỮ CÀI ĐẶT =================
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_settings_xah.json")
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translation_history_xah.json")

def load_settings():
	"""Tải cài đặt từ file JSON"""
	default_settings = {
		"api_key_encrypted": "",
		"input_file": "",
		"output_file": "",
		"model": MODELS[0],
		"threads": "3",
		"chunk_size": str(CHUNK_SIZE),
		"max_output_tokens": str(MAX_TOKENS),
		"temperature": "0.5",
		"prompt": DEFAULT_PROMPT,
		"theme": "dark"
	}

	try:
		if os.path.exists(SETTINGS_FILE):
			with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
				saved_settings = json.load(f)
				default_settings.update(saved_settings)

				# Giải mã API Key
				if saved_settings.get("api_key_encrypted"):
					default_settings["api_key"] = decrypt_api_key(saved_settings["api_key_encrypted"])
				else:
					default_settings["api_key"] = API_KEY
	except Exception as e:
		print(f"Không thể tải cài đặt: {e}")

	return default_settings

def save_settings():
	"""Lưu cài đặt hiện tại vào file JSON (API Key được mã hóa)"""
	api_key = api_key_entry.get().strip() or API_KEY

	settings = {
		"api_key_encrypted": encrypt_api_key(api_key),  # Mã hóa API Key
		"input_file": input_path.get(),
		"output_file": output_path.get(),
		"model": model_var.get(),
		"threads": thread_var.get(),
		"chunk_size": chunk_size_var.get(),
		"max_output_tokens": max_output_tokens_var.get(),
		"temperature": temp_var.get(),
		"prompt": prompt_text.get("1.0", tk.END).strip(),
		"theme": current_theme
	}

	try:
		with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
			json.dump(settings, f, ensure_ascii=False, indent=2)
		add_log("💾 Đã lưu cài đặt thành công! (API Key đã được mã hóa)")
	except Exception as e:
		print(f"Không thể lưu cài đặt: {e}")

def apply_settings(settings):
	"""Áp dụng cài đặt đã lưu vào giao diện"""
	global current_theme

	api_key_entry.insert(0, settings.get("api_key", API_KEY))
	input_path.set(settings.get("input_file", ""))
	output_path.set(settings.get("output_file", ""))
	model_var.set(settings.get("model", MODELS[0]))
	thread_var.set(settings.get("threads", "3"))
	chunk_size_var.set(settings.get("chunk_size", str(CHUNK_SIZE)))
	max_output_tokens_var.set(settings.get("max_output_tokens", str(MAX_TOKENS)))
	temp_var.set(settings.get("temperature", "0.5"))

	# Xóa prompt mặc định và thay bằng prompt đã lưu
	prompt_text.delete("1.0", tk.END)
	prompt_text.insert(tk.END, settings.get("prompt", DEFAULT_PROMPT))

	# Áp dụng theme
	current_theme = settings.get("theme", "dark")

def on_closing():
	"""Xử lý khi đóng ứng dụng - tự động lưu cài đặt"""
	save_settings()
	root.destroy()

# ================= HÀM HỖ TRỢ =================
def get_checkpoint_path(input_file):
	"""Tạo đường dẫn file checkpoint từ file đầu vào"""
	base_name = os.path.splitext(input_file)[0]
	return f"{base_name}.resume_xah.json"

def build_default_output_path(input_file):
	input_dir = os.path.dirname(input_file)
	input_name = os.path.splitext(os.path.basename(input_file))[0]
	random_suffix = random.randint(1000, 9999)
	return os.path.join(input_dir, f"Dich_Xah_{input_name}_{random_suffix}.txt")

def add_log(message):
	"""Thêm log vào ô log (nếu có) hoặc in ra console"""
	timestamp = time.strftime("%H:%M:%S")
	log_message = f"[{timestamp}] {message}\n"

	# Nếu có log_box thì hiển thị lên GUI
	if 'log_box' in globals():
		log_box.config(state='normal')
		log_box.insert(tk.END, log_message)
		log_box.see(tk.END)
		log_box.config(state='disabled')

	# In ra console để debug
	print(log_message.strip())

def save_checkpoint(cp_file, index, text):
	"""Lưu tiến trình dịch vào file checkpoint"""
	try:
		# Đọc dữ liệu cũ
		if os.path.exists(cp_file):
			with open(cp_file, "r", encoding="utf-8") as f:
				data = json.load(f)
		else:
			data = {}

		# Cập nhật đoạn mới
		data[str(index)] = text

		# Ghi lại file
		with open(cp_file, "w", encoding="utf-8") as f:
			json.dump(data, f, ensure_ascii=False, indent=2)
	except Exception as e:
		print(f"Lỗi khi lưu checkpoint: {e}")

def format_time(seconds):
	"""Chuyển đổi giây thành định dạng mm:ss hoặc hh:mm:ss"""
	if seconds < 0:
		return "--:--"
	hours = int(seconds // 3600)
	minutes = int((seconds % 3600) // 60)
	secs = int(seconds % 60)
	if hours > 0:
		return f"{hours:02d}:{minutes:02d}:{secs:02d}"
	return f"{minutes:02d}:{secs:02d}"

def load_translation_history():
	"""Tải lịch sử dịch từ file JSON"""
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
	"""Lưu thêm 1 bản ghi lịch sử dịch"""
	try:
		history = load_translation_history()
		history.append(entry)
		history = history[-max_entries:]
		with open(HISTORY_FILE, "w", encoding="utf-8") as f:
			json.dump(history, f, ensure_ascii=False, indent=2)
	except Exception as e:
		print(f"Không thể lưu lịch sử dịch: {e}")

def refresh_history_display():
	"""Làm mới khung hiển thị lịch sử dịch"""
	if 'history_table' not in globals():
		return

	history = load_translation_history()
	for row_id in history_table.get_children():
		history_table.delete(row_id)

	if not history:
		history_hint_var.set("Chưa có lịch sử dịch.")
	else:
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
			input_cost = float(item.get("total_input_cost_usd", 0.0) or 0.0)
			output_cost = float(item.get("total_output_cost_usd", 0.0) or 0.0)
			total_cost = float(item.get("total_cost_usd", 0.0) or 0.0)
			threads = item.get("threads", "--")
			temperature = item.get("temperature", "--")
			error = item.get("error", "")

			tokens_text = f"in {input_tokens:,} | out {output_tokens:,}"
			cost_text = f"${total_cost:.4f}"
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
					cost_text,
					duration,
					meta_text,
					f"{in_file} → {out_file}",
					error_text,
				),
				tags=(row_tag, status_tag),
			)

def clear_translation_history():
	"""Xóa toàn bộ lịch sử dịch"""
	if not messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa toàn bộ lịch sử dịch?"):
		return

	try:
		with open(HISTORY_FILE, "w", encoding="utf-8") as f:
			json.dump([], f, ensure_ascii=False, indent=2)
		refresh_history_display()
		try:
			refresh_cost_stats()
		except NameError:
			pass
		add_log("🧹 Đã xóa toàn bộ lịch sử dịch.")
	except Exception as e:
		messagebox.showerror("Lỗi", f"Không thể xóa lịch sử dịch: {e}")

def update_stats_display():
	"""Cập nhật hiển thị thống kê"""
	if stats["total_chunks"] == 0:
		return

	elapsed = time.time() - stats["start_time"]
	done = stats["chunks_done"]
	total = stats["total_chunks"]
	remaining = total - done

	# Tính tốc độ và thời gian còn lại
	if done > 0:
		avg_time_per_chunk = elapsed / done
		eta = avg_time_per_chunk * remaining
		speed = done / (elapsed / 60)  # chunks per minute
	else:
		eta = -1
		speed = 0

	# Cập nhật labels
	stats_time_var.set(f"⏱️ Đã chạy: {format_time(elapsed)}")
	stats_eta_var.set(f"⏳ Còn lại: {format_time(eta)}")
	stats_speed_var.set(f"🚀 Tốc độ: {speed:.1f} đoạn/phút")
	stats_chars_var.set(f"📝 Ký tự: {stats['total_input_chars']:,} → {stats['total_output_chars']:,}")
	stats_input_tokens_var.set(f"🔢 Input Token: {stats['total_input_tokens']:,}")
	stats_output_tokens_var.set(f"🔢 Output Token: {stats['total_output_tokens']:,}")
	stats_input_cost_var.set(f"💵 Input Cost: ${stats['total_input_cost_usd']:.4f}")
	stats_output_cost_var.set(f"💵 Output Cost: ${stats['total_output_cost_usd']:.4f}")
	stats_total_cost_var.set(f"💰 Total Cost: ${stats['total_cost_usd']:.4f}")

# ================= CHUYỂN ĐỔI THEME =================
def toggle_theme():
	"""Chuyển đổi giữa chế độ sáng và tối"""
	global current_theme, PALETTE

	current_theme = "light" if current_theme == "dark" else "dark"
	PALETTE = THEMES[current_theme]

	apply_theme()
	draw_gradient()

	# Cập nhật text nút
	theme_icon = "🌙" if current_theme == "dark" else "☀️"
	btn_theme.config(text=f"{theme_icon} {'Tối' if current_theme == 'dark' else 'Sáng'}")

	add_log(f"🎨 Đã chuyển sang chế độ {'tối' if current_theme == 'dark' else 'sáng'}")

def apply_theme():
	"""Áp dụng theme hiện tại cho toàn bộ giao diện"""
	# Cập nhật root và canvas
	root.configure(bg=PALETTE["bg"])
	canvas_bg.configure(bg=PALETTE["bg"])

	# Cập nhật scrollbar
	scrollbar.configure(bg=PALETTE["border"], troughcolor=PALETTE["bg"], activebackground=PALETTE["accent"])

	# Cập nhật style
	style.configure("Card.TFrame", background=PALETTE["panel"])
	style.configure("TLabel", background=PALETTE["panel"], foreground=PALETTE["text"])
	style.configure("Header.TLabel", background=PALETTE["bg"], foreground=PALETTE["text"])
	style.configure("SubHeader.TLabel", background=PALETTE["bg"], foreground=PALETTE["text_muted"])
	style.configure("Section.TLabel", background=PALETTE["panel"], foreground=PALETTE["text_muted"])
	style.configure("Accent.Horizontal.TProgressbar", troughcolor=PALETTE["panel"], background=PALETTE["accent"])
	style.configure("Accent.Horizontal.TScale", background=PALETTE["panel"], troughcolor=PALETTE["bg"])
	style.configure(
		"History.Treeview",
		background=PALETTE["input_bg"],
		fieldbackground=PALETTE["input_bg"],
		foreground="#000000",
		bordercolor=PALETTE["border"],
		rowheight=28,
	)
	style.map("History.Treeview", background=[("selected", PALETTE["accent_alt"])], foreground=[("selected", "#000000")])
	style.configure(
		"History.Treeview.Heading",
		background=PALETTE["panel"],
		foreground="#000000",
		relief="flat",
		font=("Segoe UI", 9, "bold"),
	)
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

	# Cập nhật frames
	main_container.configure(bg=PALETTE["bg"])
	main_frame.configure(bg=PALETTE["bg"])
	header.configure(bg=PALETTE["bg"])
	badge_row.configure(bg=PALETTE["bg"])

	# Cập nhật tất cả các widgets
	for widget in main_container.winfo_children():
		update_widget_colors(widget)

def update_widget_colors(widget):
	"""Cập nhật màu sắc cho widget và các widget con"""
	try:
		widget_type = widget.winfo_class()

		if widget_type in ["Frame", "Labelframe"]:
			try:
				widget.configure(bg=PALETTE["bg"])
			except Exception:
				pass
		elif widget_type == "Label":
			try:
				# Kiểm tra xem có phải là badge không
				current_bg = widget.cget("bg")
				if current_bg not in [PALETTE["accent"], PALETTE["accent_alt"], "#f59e0b", "#38bdf8", "#0ea5e9"]:
					widget.configure(bg=PALETTE["panel"], fg=PALETTE["text"])
			except Exception:
				pass
		elif widget_type in ["Entry", "Text"]:
			try:
				widget.configure(bg=PALETTE["input_bg"], fg=PALETTE["text"],
							   insertbackground=PALETTE["accent"],
							   highlightbackground=PALETTE["border"])
			except Exception:
				pass
		elif widget_type == "Button":
			# Giữ nguyên màu của các button đặc biệt
			pass

		# Đệ quy cho các widget con
		for child in widget.winfo_children():
			update_widget_colors(child)
	except Exception:
		pass

# ================= CHIA CHUNK =================
def split_text(text, size=CHUNK_SIZE):
	chunks = []
	current = ""
	# Biểu thức chính quy nhận diện tiêu đề chương (ví dụ: "215|", "Chương 215", "Quyển 1", "Đệ 1 Chương")
	chapter_pattern = re.compile(r'^\s*(\d+\s*\||Chương\s+\d+|Quyển\s+\d+|Đệ\s+\d+\s+Chương)', re.IGNORECASE)

	for line in text.splitlines(True):
		is_chapter_heading = chapter_pattern.match(line)

		# Cắt chunk mới nếu gặp tiêu đề chương (giúp giữ trọn vẹn chương) và chunk hiện tại đủ dài (> 500 ký tự)
		# Hoặc cắt nếu chiều dài vượt quá chunk_size
		if (is_chapter_heading and len(current) > 500) or (len(current) + len(line) > size):
			if current.strip():
				chunks.append(current)
			current = line
		else:
			current += line

	if current.strip():
		chunks.append(current)
	return chunks

# ================= DỊCH 1 CHUNK =================
def translate_chunk(api_key, model_id, prompt, chunk, index, cp_file, temperature, max_output_tokens, retries=3):
	global is_stopped

	# Chờ nếu đang tạm dừng
	pause_event.wait()

	# Kiểm tra nếu đã dừng hẳn
	if is_stopped:
		return index, None

	payload = {
		"model": model_id,
		"messages": [
			{
				"role": "user",
				"content": prompt + "\n\nNỘI DUNG CẦN DỊCH:\n" + chunk
			}
		],
		"temperature": temperature,
		"max_tokens": max_output_tokens
	}

	headers = {
		"Authorization": f"Bearer {api_key}",
		"Content-Type": "application/json"
	}

	last_error = None
	for attempt in range(retries):
		# Kiểm tra lại trạng thái dừng
		if is_stopped:
			return index, None

		# Chờ nếu đang tạm dừng
		pause_event.wait()

		try:
			add_log(f"⏳ Đang dịch đoạn {index + 1}... (lần thử {attempt + 1}/{retries})")

			response = requests.post(API_BASE_URL, headers=headers, json=payload, timeout=120)
			if response.status_code >= 400:
				try:
					err_data = response.json()
					err_msg = err_data.get("error", {}).get("message") or err_data.get("message") or response.text
				except Exception:
					err_msg = response.text
				raise RuntimeError(f"HTTP {response.status_code}: {err_msg}")

			data = response.json()
			choices = data.get("choices", [])
			if not choices:
				raise RuntimeError("Không có dữ liệu trả về từ API.")

			translated_text = choices[0].get("message", {}).get("content", "")
			if not translated_text:
				raise RuntimeError("API trả về nội dung rỗng.")

			usage = data.get("usage", {})
			input_tokens = int(usage.get("prompt_tokens", 0) or 0)
			output_tokens = int(usage.get("completion_tokens", 0) or 0)
			input_price_per_1m, output_price_per_1m = get_model_prices_usd_per_1m(model_id)
			input_cost = (input_tokens / 1_000_000) * input_price_per_1m
			output_cost = (output_tokens / 1_000_000) * output_price_per_1m

			# Lưu checkpoint sau khi dịch thành công
			save_checkpoint(cp_file, index, translated_text.strip())

			# Cập nhật thống kê
			stats["chunks_done"] += 1
			stats["total_input_chars"] += len(chunk)
			stats["total_output_chars"] += len(translated_text)
			stats["total_input_tokens"] += input_tokens
			stats["total_output_tokens"] += output_tokens
			stats["total_input_cost_usd"] += input_cost
			stats["total_output_cost_usd"] += output_cost
			stats["total_cost_usd"] = stats["total_input_cost_usd"] + stats["total_output_cost_usd"]

			add_log(f"✅ Hoàn thành đoạn {index + 1}")
			return index, translated_text.strip()

		except Exception as e:
			last_error = e
			add_log(f"⚠️ Đoạn {index + 1} gặp lỗi (lần {attempt + 1}): {str(e)[:100]}")
			time.sleep(2 + attempt * 2)  # Chờ một lát rồi thử lại

	add_log(f"❌ Đoạn {index + 1} thất bại hoàn toàn sau {retries} lần thử")
	stats["chunks_done"] += 1
	return index, f"[ĐOẠN {index} BỊ LỖI SAU {retries} LẦN THỬ: {last_error}]"

# ================= ĐIỀU KHIỂN TẠM DỪNG =================
def toggle_pause():
	"""Chuyển đổi trạng thái tạm dừng/tiếp tục"""
	global is_paused

	if is_paused:
		# Tiếp tục
		is_paused = False
		pause_event.set()
		btn_pause.config(text="⏸️ TẠM DỪNG", bg="#FFC107")
		add_log("▶️ Đã tiếp tục dịch...")
	else:
		# Tạm dừng
		is_paused = True
		pause_event.clear()
		btn_pause.config(text="▶️ TIẾP TỤC", bg="#4CAF50")
		add_log("⏸️ Đã tạm dừng. Nhấn 'Tiếp tục' để dịch tiếp.")

def stop_translation():
	"""Dừng hoàn toàn quá trình dịch"""
	global is_stopped, is_paused

	if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn DỪNG dịch?\n(Tiến trình đã lưu, có thể dịch tiếp sau)"):
		is_stopped = True
		is_paused = False
		pause_event.set()  # Mở khóa để thread có thể kết thúc
		add_log("🛑 Đang dừng quá trình dịch...")

# ================= 1. PHƯƠNG THỨC KÍCH HOẠT (START) =================
def start_translation():
	"""Hàm này chỉ chạy trên Luồng Chính để tránh treo giao diện"""
	global is_stopped, is_paused

	# Reset trạng thái
	is_stopped = False
	is_paused = False
	pause_event.set()

	# Kiểm tra file đầu vào
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
	add_log(f"📄 File output mặc định: {output_path.get()}")

	# Lưu cài đặt trước khi bắt đầu dịch
	save_settings()

	# Khởi tạo một luồng riêng (Background Thread) để chạy logic dịch
	task_thread = threading.Thread(target=process_translation_logic)
	task_thread.daemon = True
	task_thread.start()

	# Khởi tạo thread cập nhật thống kê
	stats_thread = threading.Thread(target=stats_update_loop)
	stats_thread.daemon = True
	stats_thread.start()

	add_log("🚀 Đã kích hoạt luồng dịch thuật ngầm...")

def stats_update_loop():
	"""Vòng lặp cập nhật thống kê mỗi giây"""
	while not is_stopped and btn_start["state"] == "disabled":
		update_stats_display()
		time.sleep(1)

# ================= 2. PHƯƠNG THỨC LOGIC CHÍNH (LOGIC) =================
def process_translation_logic():
	"""Toàn bộ logic xử lý nặng nằm ở đây, chạy ngầm hoàn toàn"""
	global is_stopped

	btn_start.config(state="disabled")
	btn_pause.config(state="normal")
	btn_stop.config(state="normal")

	# Reset thống kê
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
	temperature = temp_var.get()

	try:
		in_file = input_path.get()
		out_file = output_path.get()
		model = model_var.get()
		cp_file = get_checkpoint_path(in_file)
		threads = int(thread_var.get())
		chunk_size = int(chunk_size_var.get())
		max_output_tokens = int(max_output_tokens_var.get())
		temperature = float(temp_var.get())
		prompt = prompt_text.get("1.0", tk.END).strip()
		api_key = api_key_entry.get().strip() or API_KEY

		# Đọc nội dung file
		with open(in_file, "r", encoding="utf-8") as f:
			chunks = split_text(f.read(), size=chunk_size)

		total = len(chunks)
		stats["total_chunks"] = total
		results = [None] * total

		# KIỂM TRA TIẾN TRÌNH CŨ (RESUME)
		if os.path.exists(cp_file):
			with open(cp_file, "r", encoding="utf-8") as f:
				saved_data = json.load(f)

			if messagebox.askyesno("Khôi phục", f"Tìm thấy bản dịch dở dang ({len(saved_data)}/{total} đoạn). Dịch tiếp chứ?"):
				for idx_str, text in saved_data.items():
					results[int(idx_str)] = text
				stats["chunks_done"] = len(saved_data)
				add_log(f"🔄 Đã khôi phục {len(saved_data)} đoạn từ file checkpoint.")
		else:
			with open(cp_file, "w", encoding="utf-8") as f:
				json.dump({}, f)

		progress_bar["maximum"] = total

		# Lọc ra những đoạn chưa được dịch
		pending_indices = [i for i in range(total) if results[i] is None]
		progress_bar["value"] = total - len(pending_indices)

		add_log(f"📦 Bắt đầu dịch {len(pending_indices)} đoạn còn lại bằng {model}...")
		add_log(f"⚙️ Chunk size: {chunk_size} | Max output tokens: {max_output_tokens}")
		add_log(f"🌡️ Temperature: {temperature}")

		# Chạy đa luồng để dịch
		with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
			futures = {
				executor.submit(translate_chunk, api_key, model, prompt, chunks[i], i, cp_file, temperature, max_output_tokens): i
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

		# Kiểm tra nếu bị dừng giữa chừng
		if is_stopped:
			add_log("🛑 Đã dừng dịch. Tiến trình đã được lưu vào checkpoint.")
			messagebox.showinfo("Đã dừng", "Quá trình dịch đã dừng.\nTiến trình được lưu, bạn có thể tiếp tục sau.")
			history_status = "stopped"
			return

		# LƯU FILE CUỐI CÙNG
		with open(out_file, "w", encoding="utf-8") as f:
			f.write("\n\n".join([r for r in results if r is not None]))

		# Dọn dẹp checkpoint
		if os.path.exists(cp_file):
			os.remove(cp_file)

		# Thống kê cuối cùng
		total_time = time.time() - stats["start_time"]
		add_log(f"🎊 HOÀN TẤT! Tổng thời gian: {format_time(total_time)}")
		add_log(f"📊 Đã dịch {stats['total_input_chars']:,} → {stats['total_output_chars']:,} ký tự")
		add_log(f"🔢 Input Token: {stats['total_input_tokens']:,}")
		add_log(f"🔢 Output Token: {stats['total_output_tokens']:,}")
		add_log(f"💵 Input Cost: ${stats['total_input_cost_usd']:.4f}")
		add_log(f"💵 Output Cost: ${stats['total_output_cost_usd']:.4f}")
		add_log(f"💰 Total Cost: ${stats['total_cost_usd']:.4f}")
		history_status = "completed"
		messagebox.showinfo("Hoàn tất", f"Truyện đã được dịch xong!\nThời gian: {format_time(total_time)}\nTổng tiền: ${stats['total_cost_usd']:.4f}\nLưu tại: {out_file}")

	except Exception as e:
		error_msg = str(e)
		history_error = error_msg
		add_log(f"🛑 LỖI HỆ THỐNG: {error_msg}")
		messagebox.showerror("Lỗi", f"Quá trình dịch bị gián đoạn: {error_msg}")

	finally:
		end_time = time.time()
		duration_seconds = max(0, int(end_time - stats["start_time"])) if stats["start_time"] else 0
		history_entry = {
			"engine": "Xah API",
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
		try:
			refresh_cost_stats()
		except NameError:
			pass

		btn_start.config(state="normal")
		btn_pause.config(state="disabled", text="⏸️ TẠM DỪNG", bg="#FFC107")
		btn_stop.config(state="disabled")
		status_var.set("Sẵn sàng")
		is_stopped = True  # Dừng thread thống kê

# ================= GUI (Giao diện) =================
root = tk.Tk()
root.title("📖 App Dịch Truyện – Xah AI (Qwen3.7-Plus)")
root.geometry("1100x950")
root.minsize(800, 600)

root.configure(bg=PALETTE["bg"])

style = ttk.Style()
style.theme_use("clam")
style.configure("Card.TFrame", background=PALETTE["panel"], borderwidth=0, relief="flat")
style.configure("TLabel", background=PALETTE["panel"], foreground=PALETTE["text"], font=("Segoe UI", 10))
style.configure("Header.TLabel", background=PALETTE["bg"], foreground=PALETTE["text"], font=("Segoe UI", 22, "bold"))
style.configure("SubHeader.TLabel", background=PALETTE["bg"], foreground=PALETTE["text_muted"], font=("Segoe UI", 11))
style.configure("Section.TLabel", background=PALETTE["panel"], foreground=PALETTE["text_muted"], font=("Segoe UI", 9, "bold"))
style.configure("Accent.TButton", background=PALETTE["accent"], foreground="#0b0f19", font=("Segoe UI", 10, "bold"), padding=6)
style.map("Accent.TButton", background=[("active", "#fbbf24")])
style.configure("Ghost.TButton", background=PALETTE["panel"], foreground=PALETTE["text"], font=("Segoe UI", 10, "bold"), padding=6)
style.map("Ghost.TButton", background=[("active", "#1f2937")])
style.configure("Accent.Horizontal.TProgressbar", troughcolor=PALETTE["panel"], background=PALETTE["accent"], bordercolor=PALETTE["panel"], lightcolor=PALETTE["accent"], darkcolor=PALETTE["accent"])
style.configure("Accent.Horizontal.TScale", background=PALETTE["panel"], troughcolor=PALETTE["bg"])
style.configure(
	"History.Treeview",
	background=PALETTE["input_bg"],
	fieldbackground=PALETTE["input_bg"],
	foreground="#000000",
	bordercolor=PALETTE["border"],
	rowheight=28,
)
style.map("History.Treeview", background=[("selected", PALETTE["accent_alt"])], foreground=[("selected", "#000000")])
style.configure(
	"History.Treeview.Heading",
	background=PALETTE["panel"],
	foreground="#000000",
	relief="flat",
	font=("Segoe UI", 9, "bold"),
)
style.map("History.Treeview.Heading", background=[("active", PALETTE["accent"])], foreground=[("active", "#000000")])

# ================= TẠO CANVAS VÀ SCROLLBAR =================
canvas_bg = tk.Canvas(root, highlightthickness=0, bd=0, bg=PALETTE["bg"])
scrollbar = tk.Scrollbar(root, orient="vertical", command=canvas_bg.yview, bg=PALETTE["border"], troughcolor=PALETTE["bg"])
canvas_bg.configure(yscrollcommand=scrollbar.set)

scrollbar.pack(side="right", fill="y")
canvas_bg.pack(side="left", fill="both", expand=True)

def _hex_to_rgb(hex_color):
	hex_color = hex_color.lstrip("#")
	return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

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

# Frame chính chứa nội dung
main_container = tk.Frame(canvas_bg, bg=PALETTE["bg"])
canvas_window = canvas_bg.create_window((0, 0), window=main_container, anchor="nw")

def on_frame_configure(event=None):
	"""Cập nhật vùng cuộn của canvas"""
	canvas_bg.configure(scrollregion=canvas_bg.bbox("all"))

def on_canvas_configure(event):
	"""Cập nhật chiều rộng của frame khi canvas thay đổi kích thước"""
	canvas_width = event.width
	canvas_bg.itemconfig(canvas_window, width=canvas_width)

main_container.bind("<Configure>", on_frame_configure)
canvas_bg.bind("<Configure>", on_canvas_configure)

# Hỗ trợ cuộn bằng chuột
def on_mousewheel(event):
	canvas_bg.yview_scroll(int(-1*(event.delta/120)), "units")

canvas_bg.bind_all("<MouseWheel>", on_mousewheel)

main_frame = tk.Frame(main_container, bg=PALETTE["bg"])
main_frame.pack(fill="both", expand=True, padx=20, pady=10)

for col in range(2):
	main_frame.columnconfigure(col, weight=1)

header = tk.Frame(main_frame, bg=PALETTE["bg"])
header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))

# Thêm nút chuyển theme vào header
header_top = tk.Frame(header, bg=PALETTE["bg"])
header_top.pack(fill="x")

header_title_frame = tk.Frame(header_top, bg=PALETTE["bg"])
header_title_frame.pack(side="left", fill="both", expand=True)

ttk.Label(header_title_frame, text="App Dịch Truyện – Xah AI", style="Header.TLabel").pack(anchor="w")
ttk.Label(header_title_frame, text="Model: Qwen3.7-Plus (Đại hạ giá)", style="SubHeader.TLabel").pack(anchor="w", pady=(0, 10))

header_btn_frame = tk.Frame(header_top, bg=PALETTE["bg"])
header_btn_frame.pack(side="right", fill="x")

btn_theme = tk.Button(header_btn_frame, text="🌙 Tối", command=toggle_theme, bg="#374151", fg=PALETTE["text"], font=("Segoe UI", 9, "bold"), cursor="hand2")
btn_theme.pack(side="right", padx=5)

badge_row = tk.Frame(header, bg=PALETTE["bg"])
badge_row.pack(fill="x", pady=(0, 10))

# Section: Cài đặt API
section1 = ttk.Frame(main_frame, style="Card.TFrame")
section1.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)

ttk.Label(section1, text="⚙️ API & File", style="Section.TLabel").pack(anchor="w", padx=10, pady=(10, 5))

# Hàng API Key
api_frame = tk.Frame(section1, bg=PALETTE["panel"])
api_frame.pack(fill="x", padx=10, pady=5)

ttk.Label(api_frame, text="API Key:", background=PALETTE["panel"], foreground=PALETTE["text"]).pack(side="left", padx=(0, 10))
api_key_entry = tk.Entry(api_frame, font=("Segoe UI", 10), bg=PALETTE["input_bg"], fg=PALETTE["text"], insertbackground=PALETTE["accent"])
api_key_entry.pack(side="left", fill="x", expand=True)

# Hàng Input File
input_frame = tk.Frame(section1, bg=PALETTE["panel"])
input_frame.pack(fill="x", padx=10, pady=5)

ttk.Label(input_frame, text="File đầu vào:", background=PALETTE["panel"], foreground=PALETTE["text"]).pack(side="left", padx=(0, 10))
input_path = tk.StringVar()
input_entry = tk.Entry(input_frame, textvariable=input_path, font=("Segoe UI", 10), bg=PALETTE["input_bg"], fg=PALETTE["text"], insertbackground=PALETTE["accent"])
input_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

def select_input_file():
	file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
	if file_path:
		input_path.set(file_path)

tk.Button(input_frame, text="📂 Chọn file", command=select_input_file, bg="#374151", fg=PALETTE["text"], cursor="hand2").pack(side="left")

# Hàng Output File
output_frame = tk.Frame(section1, bg=PALETTE["panel"])
output_frame.pack(fill="x", padx=10, pady=5)

ttk.Label(output_frame, text="File đầu ra:", background=PALETTE["panel"], foreground=PALETTE["text"]).pack(side="left", padx=(0, 10))
output_path = tk.StringVar()
output_entry = tk.Entry(output_frame, textvariable=output_path, font=("Segoe UI", 10), bg=PALETTE["input_bg"], fg=PALETTE["text"], insertbackground=PALETTE["accent"])
output_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

def select_output_file():
	file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
	if file_path:
		output_path.set(file_path)

tk.Button(output_frame, text="📁 Chọn nơi lưu", command=select_output_file, bg="#374151", fg=PALETTE["text"], cursor="hand2").pack(side="left")

# Section: Cài đặt mô hình
section2 = ttk.Frame(main_frame, style="Card.TFrame")
section2.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)

ttk.Label(section2, text="🤖 Model & Tham số", style="Section.TLabel").pack(anchor="w", padx=10, pady=(10, 5))

settings_row1 = tk.Frame(section2, bg=PALETTE["panel"])
settings_row1.pack(fill="x", padx=10, pady=5)

# Model
ttk.Label(settings_row1, text="Model:", background=PALETTE["panel"], foreground=PALETTE["text"]).pack(side="left", padx=(0, 10))
model_var = tk.StringVar(value=MODELS[0])
model_combo = ttk.Combobox(settings_row1, textvariable=model_var, values=MODELS, state="readonly", font=("Segoe UI", 10), width=40)
model_combo.pack(side="left", padx=(0, 20))

# Threads
ttk.Label(settings_row1, text="Threads:", background=PALETTE["panel"], foreground=PALETTE["text"]).pack(side="left", padx=(0, 5))
thread_var = tk.StringVar(value="3")
thread_spin = ttk.Spinbox(settings_row1, from_=1, to=16, textvariable=thread_var, font=("Segoe UI", 10), width=5)
thread_spin.pack(side="left")

settings_row2 = tk.Frame(section2, bg=PALETTE["panel"])
settings_row2.pack(fill="x", padx=10, pady=5)

# Chunk Size
ttk.Label(settings_row2, text="Chunk Size:", background=PALETTE["panel"], foreground=PALETTE["text"]).pack(side="left", padx=(0, 5))
chunk_size_var = tk.StringVar(value=str(CHUNK_SIZE))
chunk_size_spin = ttk.Spinbox(settings_row2, from_=500, to=50000, textvariable=chunk_size_var, font=("Segoe UI", 10), width=8)
chunk_size_spin.pack(side="left", padx=(0, 20))

# Max Output Tokens
ttk.Label(settings_row2, text="Max Output Tokens:", background=PALETTE["panel"], foreground=PALETTE["text"]).pack(side="left", padx=(0, 5))
max_output_tokens_var = tk.StringVar(value=str(MAX_TOKENS))
max_output_tokens_spin = ttk.Spinbox(settings_row2, from_=256, to=65536, textvariable=max_output_tokens_var, font=("Segoe UI", 10), width=8)
max_output_tokens_spin.pack(side="left", padx=(0, 20))

# Temperature
ttk.Label(settings_row2, text="Temperature:", background=PALETTE["panel"], foreground=PALETTE["text"]).pack(side="left", padx=(0, 5))
temp_var = tk.StringVar(value="0.5")
temp_scale = ttk.Scale(settings_row2, from_=0.0, to=2.0, orient="horizontal", variable=temp_var)
temp_scale.pack(side="left", fill="x", expand=True)

# Section: Prompt
section3 = ttk.Frame(main_frame, style="Card.TFrame")
section3.grid(row=3, column=0, columnspan=2, sticky="ew", pady=5)

ttk.Label(section3, text="✍️ Prompt Dịch", style="Section.TLabel").pack(anchor="w", padx=10, pady=(10, 5))

prompt_frame = tk.Frame(section3, bg=PALETTE["panel"])
prompt_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

prompt_text = scrolledtext.ScrolledText(prompt_frame, height=8, font=("Segoe UI", 9), bg=PALETTE["input_bg"], fg=PALETTE["text"], insertbackground=PALETTE["accent"], wrap=tk.WORD)
prompt_text.pack(fill="both", expand=True)

# Section: Kiểm soát
section4 = ttk.Frame(main_frame, style="Card.TFrame")
section4.grid(row=4, column=0, columnspan=2, sticky="ew", pady=5)

ttk.Label(section4, text="🎮 Kiểm soát", style="Section.TLabel").pack(anchor="w", padx=10, pady=(10, 5))

ctrl_frame = tk.Frame(section4, bg=PALETTE["panel"])
ctrl_frame.pack(fill="x", padx=10, pady=(0, 10))

btn_start = tk.Button(ctrl_frame, text="▶️ BẮT ĐẦU DỊCH", command=start_translation, bg="#10b981", fg="white", font=("Segoe UI", 11, "bold"), cursor="hand2", padx=20, pady=8)
btn_start.pack(side="left", padx=5)

btn_pause = tk.Button(ctrl_frame, text="⏸️ TẠM DỪNG", command=toggle_pause, state="disabled", bg="#FFC107", fg="#0b0f19", font=("Segoe UI", 11, "bold"), cursor="hand2", padx=20, pady=8)
btn_pause.pack(side="left", padx=5)

btn_stop = tk.Button(ctrl_frame, text="🛑 DỪNG", command=stop_translation, state="disabled", bg="#ef4444", fg="white", font=("Segoe UI", 11, "bold"), cursor="hand2", padx=20, pady=8)
btn_stop.pack(side="left", padx=5)

btn_save = tk.Button(ctrl_frame, text="💾 LƯU CÀI ĐẶT", command=save_settings, bg="#6366f1", fg="white", font=("Segoe UI", 11, "bold"), cursor="hand2", padx=20, pady=8)
btn_save.pack(side="left", padx=5)

# Status
status_var = tk.StringVar(value="Sẵn sàng")
status_label = ttk.Label(section4, textvariable=status_var, background=PALETTE["panel"], foreground=PALETTE["accent"], font=("Segoe UI", 10, "bold"))
status_label.pack(anchor="w", padx=10, pady=(0, 10))

# Section: Thống kê
section5 = ttk.Frame(main_frame, style="Card.TFrame")
section5.grid(row=5, column=0, columnspan=2, sticky="ew", pady=5)

ttk.Label(section5, text="📊 Thống kê", style="Section.TLabel").pack(anchor="w", padx=10, pady=(10, 5))

stats_frame = tk.Frame(section5, bg=PALETTE["panel"])
stats_frame.pack(fill="x", padx=10, pady=(0, 10))

stats_time_var = tk.StringVar(value="⏱️ Đã chạy: --:--")
ttk.Label(stats_frame, textvariable=stats_time_var, background=PALETTE["panel"], foreground=PALETTE["text"]).pack(anchor="w")

stats_eta_var = tk.StringVar(value="⏳ Còn lại: --:--")
ttk.Label(stats_frame, textvariable=stats_eta_var, background=PALETTE["panel"], foreground=PALETTE["text"]).pack(anchor="w")

stats_speed_var = tk.StringVar(value="🚀 Tốc độ: 0 đoạn/phút")
ttk.Label(stats_frame, textvariable=stats_speed_var, background=PALETTE["panel"], foreground=PALETTE["text"]).pack(anchor="w")

stats_chars_var = tk.StringVar(value="📝 Ký tự: 0 → 0")
ttk.Label(stats_frame, textvariable=stats_chars_var, background=PALETTE["panel"], foreground=PALETTE["text"]).pack(anchor="w")

stats_input_tokens_var = tk.StringVar(value="🔢 Input Token: 0")
ttk.Label(stats_frame, textvariable=stats_input_tokens_var, background=PALETTE["panel"], foreground=PALETTE["text"]).pack(anchor="w")

stats_output_tokens_var = tk.StringVar(value="🔢 Output Token: 0")
ttk.Label(stats_frame, textvariable=stats_output_tokens_var, background=PALETTE["panel"], foreground=PALETTE["text"]).pack(anchor="w")

stats_input_cost_var = tk.StringVar(value="💵 Input Cost: $0.0000")
ttk.Label(stats_frame, textvariable=stats_input_cost_var, background=PALETTE["panel"], foreground=PALETTE["text"]).pack(anchor="w")

stats_output_cost_var = tk.StringVar(value="💵 Output Cost: $0.0000")
ttk.Label(stats_frame, textvariable=stats_output_cost_var, background=PALETTE["panel"], foreground=PALETTE["text"]).pack(anchor="w")

stats_total_cost_var = tk.StringVar(value="💰 Total Cost: $0.0000")
ttk.Label(stats_frame, textvariable=stats_total_cost_var, background=PALETTE["panel"], foreground=PALETTE["accent"], font=("Segoe UI", 10, "bold")).pack(anchor="w")

# Progress Bar
progress_bar = ttk.Progressbar(section5, style="Accent.Horizontal.TProgressbar", length=400, mode='determinate')
progress_bar.pack(fill="x", padx=10, pady=(0, 10))

# Section: Nhật ký
section6 = ttk.Frame(main_frame, style="Card.TFrame")
section6.grid(row=6, column=0, columnspan=2, sticky="ew", pady=5)

ttk.Label(section6, text="📝 Nhật ký", style="Section.TLabel").pack(anchor="w", padx=10, pady=(10, 5))

log_box = scrolledtext.ScrolledText(section6, height=10, font=("Segoe UI", 9), bg=PALETTE["input_bg"], fg=PALETTE["text"], state="disabled")
log_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

# Section: Lịch sử dịch
section7 = ttk.Frame(main_frame, style="Card.TFrame")
section7.grid(row=7, column=0, columnspan=2, sticky="ew", pady=5)

ttk.Label(section7, text="📚 Lịch sử dịch", style="Section.TLabel").pack(anchor="w", padx=10, pady=(10, 5))

history_hint_var = tk.StringVar(value="Chưa có lịch sử dịch.")
history_hint_label = tk.Label(section7, textvariable=history_hint_var, bg=PALETTE["panel"], fg="#000000", font=("Segoe UI", 9))
history_hint_label.pack(anchor="w", padx=10, pady=(0, 5))

# Treeview cho lịch sử
history_frame = tk.Frame(section7, bg=PALETTE["panel"])
history_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

history_table = ttk.Treeview(
	history_frame,
	style="History.Treeview",
	columns=("start_at", "status", "model", "chunks", "chars", "tokens", "cost", "time", "meta", "files", "error"),
	height=8,
	show="headings",
)

history_table.heading("start_at", text="Thời gian")
history_table.heading("status", text="Trạng thái")
history_table.heading("model", text="Model")
history_table.heading("chunks", text="Đoạn")
history_table.heading("chars", text="Ký tự")
history_table.heading("tokens", text="Token")
history_table.heading("cost", text="Chi phí")
history_table.heading("time", text="Thời lượng")
history_table.heading("meta", text="Meta")
history_table.heading("files", text="File")
history_table.heading("error", text="Lỗi")

history_table.column("start_at", width=140)
history_table.column("status", width=100)
history_table.column("model", width=120)
history_table.column("chunks", width=100)
history_table.column("chars", width=120)
history_table.column("tokens", width=120)
history_table.column("cost", width=100)
history_table.column("time", width=100)
history_table.column("meta", width=120)
history_table.column("files", width=180)
history_table.column("error", width=200)

history_scrollbar = ttk.Scrollbar(history_frame, orient="horizontal", command=history_table.xview)
history_table.configure(xscrollcommand=history_scrollbar.set)
history_table.pack(fill="both", expand=True)
history_scrollbar.pack(fill="x")

# Nút xóa lịch sử
btn_clear_history = tk.Button(section7, text="🗑️ Xóa lịch sử", command=clear_translation_history, bg="#ef4444", fg="white", font=("Segoe UI", 9, "bold"), cursor="hand2")
btn_clear_history.pack(anchor="w", padx=10, pady=(0, 10))

# ================= KHỞI TẠO =================
settings = load_settings()
apply_settings(settings)
refresh_history_display()

# Xử lý đóng cửa sổ
root.protocol("WM_DELETE_WINDOW", on_closing)

# Chạy ứng dụng
root.mainloop()
