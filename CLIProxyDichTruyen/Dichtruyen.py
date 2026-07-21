import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext, simpledialog
import os
import concurrent.futures
import time
import datetime
import json
import threading
import random
import base64
import hashlib
import re
import mimetypes
import webbrowser
import urllib.request
import urllib.parse
import urllib.error

try:
	from google.oauth2.credentials import Credentials
	from googleapiclient.discovery import build
	from googleapiclient.errors import HttpError
	from googleapiclient.http import MediaFileUpload
	from google_auth_oauthlib.flow import InstalledAppFlow
	from google.auth.transport.requests import Request
except ImportError:
	Credentials = None
	build = None
	HttpError = None
	MediaFileUpload = None
	InstalledAppFlow = None
	Request = None

# ================= CẤU HÌNH DEFAULT MODELS & PARAMS =================
DEFAULT_MODELS = [
	"thanhnhan9023/glm-5.2",
	"mainnewnol/deepseek-v4-flash",
	"deepseek-v4-flash-free",
	"vuduythanh2023/qwen3.7-max",
	"vutienanh291/MiniMax-M3",
	"vpsnodelab/deepseek-v4-pro",
	"thanhnhan9023/claude-opus-4.8",
	"lohieuky1/grok-4.5",
	"vuduythanh2023/gemini-3.5-flash",
	"gemini-3.1-pro-high"
]
MODELS = DEFAULT_MODELS

CHUNK_SIZE = 3500
MAX_OUTPUT_TOKENS = 4096
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
	"Giữ cách xuống dòng và bố cục đoạn văn hợp lý như truyện.\n\n"
)

DEFAULT_GLOSSARY = ""

# ================= BIẾN ĐIỀU KHIỂN TẠM DỪNG =================
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
	"total_input_cost_usd": 0.0,
	"total_output_cost_usd": 0.0,
	"total_cost_usd": 0.0,
}

MODEL_PRICING = {
	"deepseek-v3": {"input_per_1m": 0.14, "output_per_1m": 0.28},
	"deepseek-r1": {"input_per_1m": 0.55, "output_per_1m": 2.19},
	"deepseek-v4-pro": {"input_per_1m": 0.14, "output_per_1m": 0.28},
	"deepseek-v4-flash": {"input_per_1m": 0.0, "output_per_1m": 0.0},
	"deepseek-v4-flash-free": {"input_per_1m": 0.0, "output_per_1m": 0.0},
	"qwen2.5-72b-instruct": {"input_per_1m": 0.40, "output_per_1m": 0.40},
	"qwen3.7-max": {"input_per_1m": 0.40, "output_per_1m": 0.40},
	"glm-5.2": {"input_per_1m": 0.10, "output_per_1m": 0.20},
	"default": {"input_per_1m": 0.15, "output_per_1m": 0.30}
}
USD_TO_VND = 27000
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
DRIVE_TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "drive_token.json")

# ================= QUOTA & ERROR HANDLING =================
def is_quota_exceeded_error(error_str: str) -> bool:
	error_lower = str(error_str).lower()
	return "429" in error_lower or "resource_exhausted" in error_lower or "quota" in error_lower or "rate limit" in error_lower

def get_model_prices_usd_per_1m(model_id, input_tokens):
	model_id_lower = str(model_id).lower()
	for key, price in MODEL_PRICING.items():
		if key != "default" and key in model_id_lower:
			return price.get("input_per_1m", 0.0), price.get("output_per_1m", 0.0)
	default_price = MODEL_PRICING.get("default", {"input_per_1m": 0.15, "output_per_1m": 0.30})
	return default_price.get("input_per_1m", 0.15), default_price.get("output_per_1m", 0.30)

# ================= CHẾ ĐỘ SÁNG/TỐI =================
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

# ================= MÃ HÓA API KEY =================
def get_machine_key():
	unique_string = (
		os.environ.get("COMPUTERNAME", "PC")
		+ os.environ.get("USERNAME", "User")
		+ "GoogleDichTruyenSecretKey2026"
	)
	return hashlib.sha256(unique_string.encode()).digest()

def xor_encrypt(data: str, key: bytes) -> str:
	if not data: return ""
	data_bytes = data.encode("utf-8")
	key_repeated = (key * ((len(data_bytes) // len(key)) + 1))[: len(data_bytes)]
	result = bytes([a ^ b for a, b in zip(data_bytes, key_repeated)])
	return base64.b64encode(result).decode("utf-8")

def xor_decrypt(encrypted_data: str, key: bytes) -> str:
	if not encrypted_data: return ""
	try:
		data_bytes = base64.b64decode(encrypted_data.encode("utf-8"))
		key_repeated = (key * ((len(data_bytes) // len(key)) + 1))[: len(data_bytes)]
		result = bytes([a ^ b for a, b in zip(data_bytes, key_repeated)])
		return result.decode("utf-8")
	except Exception:
		return ""

def encrypt_api_key(api_key: str) -> str:
	return xor_encrypt(api_key, get_machine_key())

def decrypt_api_key(encrypted_key: str) -> str:
	return xor_decrypt(encrypted_key, get_machine_key())

# ================= CẤU HÌNH LƯU TRỮ CÀI ĐẶT =================
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_settings.json")
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translation_history.json")

api_keys_dict = {}
prompts_dict = {}
last_selected_key = "Mặc định"
last_selected_prompt = "Mặc định"

def load_settings():
	default_settings = {
		"vps_ip": "https://api.xah.io",
		"api_key_encrypted": "",
		"input_file": "",
		"output_file": "",
		"model": MODELS[0],
		"quick_model": MODELS[0],
		"thinking_level": "medium",
		"model_fallback_order": "|".join(MODELS),
		"threads": "3",
		"chunk_size": str(CHUNK_SIZE),
		"chunk_split_mode": "keyword",
		"max_output_tokens": str(MAX_OUTPUT_TOKENS),
		"scan_char_limit": str(DEFAULT_SCAN_CHAR_LIMIT),
		"temperature": "0.5",
		"prompt": DEFAULT_PROMPT,
		"glossary": DEFAULT_GLOSSARY,
		"theme": "dark",
		"drive_upload_enabled": False,
		"drive_credentials_path": "",
		"drive_folder_id": "",
		"api_keys": {},
		"current_key_name": "Mặc định",
		"prompts": {},
		"current_prompt_name": "Mặc định"
	}
	try:
		if os.path.exists(SETTINGS_FILE):
			with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
				saved_settings = json.load(f)
				default_settings.update(saved_settings)
				old_api_key = ""
				if saved_settings.get("api_key_encrypted"):
					old_api_key = decrypt_api_key(saved_settings["api_key_encrypted"])
				api_keys = saved_settings.get("api_keys", {})
				decrypted_api_keys = {}
				for k_name, k_val in api_keys.items():
					if isinstance(k_val, dict):
						decrypted_api_keys[k_name] = {
							"url": k_val.get("url", ""),
							"key": decrypt_api_key(k_val.get("key", ""))
						}
					else:
						decrypted_api_keys[k_name] = {
							"url": default_settings.get("vps_ip", "https://api.xah.io"),
							"key": decrypt_api_key(str(k_val))
						}
				if "Mặc định" not in decrypted_api_keys:
					decrypted_api_keys["Mặc định"] = {
						"url": default_settings.get("vps_ip", "https://api.xah.io"),
						"key": old_api_key
					}
				default_settings["api_keys"] = decrypted_api_keys
				prompts = saved_settings.get("prompts", {})
				old_prompt = saved_settings.get("prompt", DEFAULT_PROMPT)
				if old_prompt and "Mặc định" not in prompts:
					prompts["Mặc định"] = old_prompt
				if "Mặc định" not in prompts:
					prompts["Mặc định"] = DEFAULT_PROMPT
				default_settings["prompts"] = prompts
	except Exception as e:
		print(f"Không thể tải cài đặt: {e}")
	return default_settings

def save_settings():
	curr_key = current_key_name_var.get()
	if curr_key:
		api_keys_dict[curr_key] = {
			"url": vps_ip_entry.get().strip(),
			"key": api_key_entry.get().strip()
		}
	curr_prompt = current_prompt_name_var.get()
	if curr_prompt:
		prompts_dict[curr_prompt] = prompt_text.get("1.0", tk.END).strip()
	encrypted_api_keys = {}
	for k_name, k_val in api_keys_dict.items():
		if isinstance(k_val, dict):
			encrypted_api_keys[k_name] = {
				"url": k_val.get("url", ""),
				"key": encrypt_api_key(k_val.get("key", ""))
			}
		else:
			encrypted_api_keys[k_name] = {
				"url": vps_ip_entry.get().strip(),
				"key": encrypt_api_key(str(k_val))
			}
	active_url = vps_ip_entry.get().strip()
	active_key = api_key_entry.get().strip()
	active_prompt = prompt_text.get("1.0", tk.END).strip()
	settings = {
		"vps_ip": active_url,
		"api_key_encrypted": encrypt_api_key(active_key),
		"input_file": input_path.get(),
		"output_file": output_path.get(),
		"model": model_var.get(),
		"quick_model": quick_model_var.get(),
		"thinking_level": thinking_level_var.get(),
		"model_fallback_order": model_fallback_order_var.get(),
		"threads": thread_var.get(),
		"chunk_size": chunk_size_var.get(),
		"chunk_split_mode": chunk_split_mode_var.get(),
		"max_output_tokens": max_output_tokens_var.get(),
		"scan_char_limit": scan_char_limit_var.get(),
		"temperature": temp_var.get(),
		"glossary": glossary_text.get("1.0", tk.END).strip(),
		"prompt": active_prompt,
		"theme": current_theme,
		"drive_upload_enabled": bool(drive_upload_var.get()),
		"drive_credentials_path": drive_credentials_path_var.get().strip(),
		"drive_folder_id": drive_folder_id_var.get().strip(),
		"api_keys": encrypted_api_keys,
		"current_key_name": curr_key,
		"prompts": prompts_dict,
		"current_prompt_name": curr_prompt
	}
	try:
		with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
			json.dump(settings, f, ensure_ascii=False, indent=2)
		add_log("💾 Đã lưu cài đặt thành công! (API Key đã được mã hóa)")
	except Exception as e:
		print(f"Không thể lưu cài đặt: {e}")

def apply_settings(settings):
	global current_theme, api_keys_dict, prompts_dict, last_selected_key, last_selected_prompt
	api_keys_dict = settings.get("api_keys", {"Mặc định": {"url": "https://api.xah.io", "key": ""}})
	prompts_dict = settings.get("prompts", {"Mặc định": DEFAULT_PROMPT})
	curr_key = settings.get("current_key_name", "Mặc định")
	if curr_key not in api_keys_dict:
		curr_key = list(api_keys_dict.keys())[0] if api_keys_dict else "Mặc định"
	current_key_name_var.set(curr_key)
	last_selected_key = curr_key
	curr_prompt = settings.get("current_prompt_name", "Mặc định")
	if curr_prompt not in prompts_dict:
		curr_prompt = list(prompts_dict.keys())[0] if prompts_dict else "Mặc định"
	current_prompt_name_var.set(curr_prompt)
	last_selected_prompt = curr_prompt
	try:
		api_key_cb.config(values=list(api_keys_dict.keys()))
		prompt_cb.config(values=list(prompts_dict.keys()))
	except NameError:
		pass
	profile_data = api_keys_dict.get(curr_key, {"url": "https://api.xah.io", "key": ""})
	if isinstance(profile_data, str):
		profile_data = {"url": "https://api.xah.io", "key": profile_data}
	vps_ip_entry.delete(0, tk.END)
	vps_ip_entry.insert(0, profile_data.get("url", "https://api.xah.io"))
	api_key_entry.delete(0, tk.END)
	api_key_entry.insert(0, profile_data.get("key", ""))
	input_path.set(settings.get("input_file", ""))
	output_path.set(settings.get("output_file", ""))
	model_var.set(settings.get("model", MODELS[0]))
	quick_model_var.set(settings.get("quick_model", MODELS[0]))
	thinking_level_var.set(settings.get("thinking_level", "medium"))
	model_fallback_order_var.set(settings.get("model_fallback_order", "|".join(MODELS)))
	thread_var.set(settings.get("threads", "3"))
	chunk_size_var.set(settings.get("chunk_size", str(CHUNK_SIZE)))
	chunk_split_mode_var.set(settings.get("chunk_split_mode", "keyword"))
	max_output_tokens_var.set(settings.get("max_output_tokens", str(MAX_OUTPUT_TOKENS)))
	scan_char_limit_var.set(settings.get("scan_char_limit", str(DEFAULT_SCAN_CHAR_LIMIT)))
	temp_var.set(settings.get("temperature", "0.5"))
	glossary_text.delete("1.0", tk.END)
	glossary_text.insert(tk.END, settings.get("glossary", DEFAULT_GLOSSARY))
	prompt_text.delete("1.0", tk.END)
	prompt_text.insert(tk.END, prompts_dict.get(curr_prompt, DEFAULT_PROMPT))
	current_theme = settings.get("theme", "dark")
	drive_upload_var.set(bool(settings.get("drive_upload_enabled", False)))
	drive_credentials_path_var.set(settings.get("drive_credentials_path", ""))
	drive_folder_id_var.set(settings.get("drive_folder_id", ""))

# ================= QUẢN LÝ NHIỀU API KEY & PROMPT =================
def on_api_key_select(event=None):
	global last_selected_key
	new_key_name = current_key_name_var.get()
	if not new_key_name: return
	if last_selected_key in api_keys_dict:
		api_keys_dict[last_selected_key] = {
			"url": vps_ip_entry.get().strip(),
			"key": api_key_entry.get().strip()
		}
	profile_data = api_keys_dict.get(new_key_name, {"url": "https://api.xah.io", "key": ""})
	if isinstance(profile_data, str):
		profile_data = {"url": "https://api.xah.io", "key": profile_data}
	vps_ip_entry.delete(0, tk.END)
	vps_ip_entry.insert(0, profile_data.get("url", ""))
	api_key_entry.delete(0, tk.END)
	api_key_entry.insert(0, profile_data.get("key", ""))
	last_selected_key = new_key_name

def add_new_api_key():
	global last_selected_key
	new_name = simpledialog.askstring("Thêm Profile mới", "Nhập tên cho API Profile mới:")
	if not new_name: return
	new_name = new_name.strip()
	if not new_name: return
	if new_name in api_keys_dict:
		messagebox.showerror("Lỗi", "Tên Profile đã tồn tại!")
		return
	if last_selected_key in api_keys_dict:
		api_keys_dict[last_selected_key] = {
			"url": vps_ip_entry.get().strip(),
			"key": api_key_entry.get().strip()
		}
	api_keys_dict[new_name] = {"url": "https://api.xah.io", "key": ""}
	api_key_cb.config(values=list(api_keys_dict.keys()))
	current_key_name_var.set(new_name)
	last_selected_key = new_name
	vps_ip_entry.delete(0, tk.END)
	vps_ip_entry.insert(0, "https://api.xah.io")
	api_key_entry.delete(0, tk.END)
	api_key_entry.focus_set()
	add_log(f"🔑 Đã thêm Profile mới: {new_name}")

def rename_api_key():
	curr_key = current_key_name_var.get()
	if not curr_key: return
	new_name = simpledialog.askstring("Đổi tên Profile", f"Nhập tên mới cho Profile '{curr_key}':", initialvalue=curr_key)
	if not new_name: return
	new_name = new_name.strip()
	if not new_name or new_name == curr_key: return
	if new_name in api_keys_dict:
		messagebox.showerror("Lỗi", "Tên Profile mới đã tồn tại!")
		return
	api_keys_dict[new_name] = api_keys_dict.pop(curr_key, {
		"url": vps_ip_entry.get().strip(),
		"key": api_key_entry.get().strip()
	})
	api_key_cb.config(values=list(api_keys_dict.keys()))
	current_key_name_var.set(new_name)
	global last_selected_key
	last_selected_key = new_name
	add_log(f"🔑 Đã đổi tên Profile '{curr_key}' thành '{new_name}'")

def delete_api_key():
	global last_selected_key
	curr_key = current_key_name_var.get()
	if not curr_key: return
	if len(api_keys_dict) <= 1:
		messagebox.showwarning("Cảnh báo", "Không thể xóa Profile cuối cùng!")
		return
	if messagebox.askyesno("Xác nhận", f"Bạn có chắc muốn xóa Profile '{curr_key}'?"):
		api_keys_dict.pop(curr_key, None)
		remaining_keys = list(api_keys_dict.keys())
		next_key = remaining_keys[0]
		api_key_cb.config(values=remaining_keys)
		current_key_name_var.set(next_key)
		last_selected_key = next_key
		profile_data = api_keys_dict.get(next_key, {"url": "https://api.xah.io", "key": ""})
		vps_ip_entry.delete(0, tk.END)
		vps_ip_entry.insert(0, profile_data.get("url", "https://api.xah.io"))
		api_key_entry.delete(0, tk.END)
		api_key_entry.insert(0, profile_data.get("key", ""))
		add_log(f"🔑 Đã xóa Profile: {curr_key}")

def on_prompt_select(event=None):
	global last_selected_prompt
	new_prompt_name = current_prompt_name_var.get()
	if not new_prompt_name: return
	if last_selected_prompt in prompts_dict:
		prompts_dict[last_selected_prompt] = prompt_text.get("1.0", tk.END).strip()
	prompt_text.delete("1.0", tk.END)
	prompt_text.insert(tk.END, prompts_dict.get(new_prompt_name, ""))
	last_selected_prompt = new_prompt_name

def add_new_prompt():
	global last_selected_prompt
	new_name = simpledialog.askstring("Thêm Prompt mới", "Nhập tên cho Prompt mới:")
	if not new_name: return
	new_name = new_name.strip()
	if not new_name: return
	if new_name in prompts_dict:
		messagebox.showerror("Lỗi", "Tên Prompt đã tồn tại!")
		return
	if last_selected_prompt in prompts_dict:
		prompts_dict[last_selected_prompt] = prompt_text.get("1.0", tk.END).strip()
	prompts_dict[new_name] = DEFAULT_PROMPT
	prompt_cb.config(values=list(prompts_dict.keys()))
	current_prompt_name_var.set(new_name)
	last_selected_prompt = new_name
	prompt_text.delete("1.0", tk.END)
	prompt_text.insert(tk.END, DEFAULT_PROMPT)
	prompt_text.focus_set()
	add_log(f"📝 Đã thêm Prompt mới: {new_name}")

def rename_prompt():
	curr_prompt = current_prompt_name_var.get()
	if not curr_prompt: return
	new_name = simpledialog.askstring("Đổi tên Prompt", f"Nhập tên mới cho Prompt '{curr_prompt}':", initialvalue=curr_prompt)
	if not new_name: return
	new_name = new_name.strip()
	if not new_name or new_name == curr_prompt: return
	if new_name in prompts_dict:
		messagebox.showerror("Lỗi", "Tên Prompt mới đã tồn tại!")
		return
	prompts_dict[new_name] = prompts_dict.pop(curr_prompt, prompt_text.get("1.0", tk.END).strip())
	prompt_cb.config(values=list(prompts_dict.keys()))
	current_prompt_name_var.set(new_name)
	global last_selected_prompt
	last_selected_prompt = new_name
	add_log(f"📝 Đã đổi tên Prompt '{curr_prompt}' thành '{new_name}'")

def delete_prompt():
	global last_selected_prompt
	curr_prompt = current_prompt_name_var.get()
	if not curr_prompt: return
	if len(prompts_dict) <= 1:
		messagebox.showwarning("Cảnh báo", "Không thể xóa Prompt cuối cùng!")
		return
	if messagebox.askyesno("Xác nhận", f"Bạn có chắc muốn xóa Prompt '{curr_prompt}'?"):
		prompts_dict.pop(curr_prompt, None)
		remaining_prompts = list(prompts_dict.keys())
		next_prompt = remaining_prompts[0]
		prompt_cb.config(values=remaining_prompts)
		current_prompt_name_var.set(next_prompt)
		last_selected_prompt = next_prompt
		prompt_text.delete("1.0", tk.END)
		prompt_text.insert(tk.END, prompts_dict.get(next_prompt, ""))
		add_log(f"📝 Đã xóa Prompt: {curr_prompt}")

def on_closing():
	save_settings()
	root.destroy()

# ================= HÀM HỖ TRỢ =================
def normalize_base_url(raw_input):
	value = raw_input.strip()
	if not value: return ""
	for suffix in ["/v1/chat/completions", "/v1/chat/completions/", "/v1/models", "/v1/models/", "/v1", "/v1/"]:
		if value.endswith(suffix):
			value = value[:-len(suffix)]
			break
	if not value.startswith("http://") and not value.startswith("https://"):
		host = value.split(":")[0]
		ip_parts = host.split(".")
		is_ip = len(ip_parts) == 4 and all(p.isdigit() for p in ip_parts)
		if is_ip or host.lower() == "localhost":
			value = f"http://{value}"
		else:
			value = f"https://{value}"
	parsed = urllib.parse.urlparse(value)
	netloc = parsed.netloc
	path = parsed.path.rstrip("/")
	if not netloc: return ""
	if ":" not in netloc:
		host = netloc
		ip_parts = host.split(".")
		is_ip = len(ip_parts) == 4 and all(p.isdigit() for p in ip_parts)
		if is_ip or host.lower() == "localhost":
			netloc = f"{netloc}:8000"
	scheme = parsed.scheme or "https"
	return f"{scheme}://{netloc}{path}".rstrip("/")

def get_checkpoint_path(input_file):
	base_name = os.path.splitext(input_file)[0]
	return f"{base_name}.resume.json"

def sanitize_filename_part(raw_value, fallback):
	if not raw_value: return fallback
	cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(raw_value).strip())
	cleaned = re.sub(r"-+", "-", cleaned).strip("-")
	return cleaned or fallback

def build_default_output_path(input_file, model_id=None):
	input_dir = os.path.dirname(input_file)
	input_name = os.path.splitext(os.path.basename(input_file))[0]
	random_suffix = random.randint(1000, 9999)
	model_token = sanitize_filename_part(model_id, "model")
	date_token = datetime.datetime.now().strftime("%Y-%m-%d")
	return os.path.join(input_dir, f"Dich_{input_name}_{model_token}_{date_token}_{random_suffix}.txt")

def ensure_drive_dependencies():
	return all([Credentials, build, MediaFileUpload, InstalledAppFlow, Request])

def get_drive_credentials(credentials_path, token_path):
	if not credentials_path or not os.path.isfile(credentials_path):
		raise FileNotFoundError("Không tìm thấy file credentials Google Drive.")
	creds = None
	if token_path and os.path.exists(token_path):
		creds = Credentials.from_authorized_user_file(token_path, DRIVE_SCOPES)
	if not creds or not creds.valid:
		if creds and creds.expired and creds.refresh_token:
			creds.refresh(Request())
		else:
			flow = InstalledAppFlow.from_client_secrets_file(credentials_path, DRIVE_SCOPES)
			creds = flow.run_local_server(port=0)
		if token_path:
			with open(token_path, "w", encoding="utf-8") as token_file:
				token_file.write(creds.to_json())
	return creds

def upload_file_to_drive(file_path, credentials_path, folder_id="", token_path=DRIVE_TOKEN_FILE):
	if not ensure_drive_dependencies():
		raise RuntimeError("Thiếu thư viện Google Drive API.")
	if not file_path or not os.path.isfile(file_path):
		raise FileNotFoundError("Không tìm thấy file output để upload.")
	creds = get_drive_credentials(credentials_path, token_path)
	service = build("drive", "v3", credentials=creds)
	mime_type, _ = mimetypes.guess_type(file_path)
	media = MediaFileUpload(file_path, mimetype=mime_type or "application/octet-stream", resumable=True)
	metadata = {"name": os.path.basename(file_path)}
	if folder_id:
		metadata["parents"] = [folder_id]
	result = service.files().create(body=metadata, media_body=media, fields="id,name,webViewLink").execute()
	file_id = result.get("id", "")
	web_link = result.get("webViewLink") or (f"https://drive.google.com/file/d/{file_id}/view" if file_id else "")
	return file_id, web_link

def add_log(message):
	timestamp = time.strftime("%H:%M:%S")
	log_message = f"[{timestamp}] {message}\n"
	def _append_to_log_box():
		if "log_box" in globals() and log_box.winfo_exists():
			log_box.config(state="normal")
			log_box.insert(tk.END, log_message)
			log_box.see(tk.END)
			log_box.config(state="disabled")
	if threading.current_thread() is threading.main_thread():
		_append_to_log_box()
	else:
		try:
			if "root" in globals() and root.winfo_exists():
				root.after(0, _append_to_log_box)
		except Exception:
			pass
	print(log_message.strip())

def show_completion_dialog(title, message, drive_link=""):
	if threading.current_thread() is not threading.main_thread():
		if "root" in globals() and root.winfo_exists():
			root.after(0, lambda: show_completion_dialog(title, message, drive_link))
		return
	win = tk.Toplevel(root)
	win.title(title)
	win.configure(bg=PALETTE["panel"])
	win.transient(root)
	win.grab_set()
	win.resizable(False, False)
	container = tk.Frame(win, bg=PALETTE["panel"], padx=16, pady=14)
	container.pack(fill="both", expand=True)
	msg_label = tk.Label(container, text=message, bg=PALETTE["panel"], fg=PALETTE["text"], justify="left", wraplength=520, font=("Segoe UI", 9))
	msg_label.pack(anchor="w")
	if drive_link:
		link_label = tk.Label(container, text=drive_link, bg=PALETTE["panel"], fg=PALETTE["accent_alt"], cursor="hand2", justify="left", wraplength=520, font=("Segoe UI", 9, "underline"))
		link_label.pack(anchor="w", pady=(8, 0))
		link_label.bind("<Button-1>", lambda _evt: webbrowser.open(drive_link))
	btn_row = tk.Frame(container, bg=PALETTE["panel"])
	btn_row.pack(fill="x", pady=(12, 0))
	def _copy_link():
		if not drive_link: return
		root.clipboard_clear()
		root.clipboard_append(drive_link)
	if drive_link:
		tk.Button(btn_row, text="Mở Google Drive", bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=10, pady=6, command=lambda: webbrowser.open(drive_link)).pack(side="left")
		tk.Button(btn_row, text="Copy link", bg=PALETTE["ok"], fg="#0b0f19", bd=0, padx=10, pady=6, command=_copy_link).pack(side="left", padx=(8, 0))
	tk.Button(btn_row, text="OK", bg=PALETTE["accent"], fg="#0b0f19", bd=0, padx=12, pady=6, command=win.destroy).pack(side="right")
	win.update_idletasks()
	win.geometry(f"{min(620, win.winfo_reqwidth())}x{win.winfo_reqheight()}")

def parse_glossary(raw_text):
	entries = []
	if not raw_text: return entries
	for line in raw_text.splitlines():
		clean = line.strip()
		if not clean or clean.startswith("#"): continue
		separator = None
		for candidate in ["=>", "->", ":"]:
			if candidate in clean:
				separator = candidate
				break
		if not separator: continue
		source, target = clean.split(separator, 1)
		source = source.strip()
		target = target.strip()
		if source and target:
			entries.append((source, target))
	return entries

def build_prompt_with_glossary(base_prompt, glossary_entries):
	if not glossary_entries: return base_prompt
	processed_entries = []
	for src, dst in glossary_entries:
		match = re.search(r'\(([^)]+)\)?', dst)
		dst_cleaned = match.group(1).strip() if match else dst
		processed_entries.append((src, dst_cleaned))
	glossary_lines = "\n".join([f"- {src} => {dst}" for src, dst in processed_entries])
	glossary_instruction = (
		"\nQUY TẮC THUẬT NGỮ BẮT BUỘC (ƯU TIÊN CAO):\n"
		"- Khi gặp thuật ngữ ở cột trái, phải dịch sang thuật ngữ ở cột phải tương ứng.\n"
		"- Giữ nhất quán tuyệt đối toàn bộ chương và các chương tiếp theo.\n"
		"- Không tự ý đổi biến thể khác nếu glossary đã quy định.\n"
		f"{glossary_lines}\n"
	)
	return f"{base_prompt}\n{glossary_instruction}"

checkpoint_lock = threading.Lock()

def read_file_content_safely(file_path):
	encodings = ["utf-8", "utf-8-sig", "utf-16", "cp1258", "cp1252", "latin-1"]
	for enc in encodings:
		try:
			with open(file_path, "r", encoding=enc) as f:
				return f.read()
		except UnicodeDecodeError:
			continue
	with open(file_path, "r", encoding="utf-8", errors="replace") as f:
		return f.read()

def save_checkpoint(cp_file, index, text):
	with checkpoint_lock:
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
	if seconds < 0: return "--:--"
	hours = int(seconds // 3600)
	minutes = int((seconds % 3600) // 60)
	secs = int(seconds % 60)
	if hours > 0: return f"{hours:02d}:{minutes:02d}:{secs:02d}"
	return f"{minutes:02d}:{secs:02d}"

def load_translation_history():
	try:
		if os.path.exists(HISTORY_FILE):
			with open(HISTORY_FILE, "r", encoding="utf-8") as f:
				data = json.load(f)
				if isinstance(data, list): return data
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

history_display_map = {}
request_display_map = {}
request_detail_tabs = {}
request_detail_tables = {}
request_minute_counts = {}
request_minute_lock = threading.Lock()

def show_history_entry_dialog(entry):
	status = str(entry.get("status", "--")).upper()
	start_at = entry.get("start_at", "--")
	end_at = entry.get("end_at", "--")
	duration_seconds = entry.get("duration_seconds", 0)
	output_file = entry.get("output_file", "")
	total_cost = float(entry.get("total_cost_usd", 0.0) or 0.0)
	total_cost_vnd = float(entry.get("total_cost_vnd", total_cost * USD_TO_VND) or 0.0)
	drive_link = entry.get("drive_link", "")
	message = (
		f"Trạng thái: {status}\n"
		f"Bắt đầu: {start_at}\n"
		f"Kết thúc: {end_at}\n"
		f"Thời gian: {format_time(duration_seconds)}\n"
		f"Tổng tiền: ${total_cost:.4f}\n"
		f"Tổng tiền Việt: {int(round(total_cost_vnd)):,} đ\n"
		f"Lưu tại: {output_file}"
	)
	show_completion_dialog("Lịch sử dịch", message, drive_link)

def on_history_row_click(event):
	if "history_table" not in globals(): return
	row_id = history_table.identify_row(event.y)
	if not row_id: return
	entry = history_display_map.get(row_id)
	if entry: show_history_entry_dialog(entry)

def refresh_history_display():
	if "history_table" not in globals(): return
	history_display_map.clear()
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
			total_cost = float(item.get("total_cost_usd", 0.0) or 0.0)
			total_cost_vnd = float(item.get("total_cost_vnd", total_cost * USD_TO_VND) or 0.0)
			threads = item.get("threads", "--")
			temperature = item.get("temperature", "--")
			error = item.get("error", "")
			tokens_text = f"in {input_tokens:,} | out {output_tokens:,}"
			cost_text = f"${total_cost:.4f}"
			cost_vnd_text = f"{int(round(total_cost_vnd)):,} đ"
			meta_text = f"{threads} luồng | temp {temperature}"
			error_text = (error[:80] + "...") if len(error) > 80 else error
			row_tag = "even" if idx % 2 == 0 else "odd"
			status_tag = f"status_{status.lower()}"
			row_id = history_table.insert(
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
					cost_vnd_text,
					duration,
					meta_text,
					f"{in_file} → {out_file}",
					error_text,
				),
				tags=(row_tag, status_tag),
			)
			history_display_map[row_id] = item
	try:
		refresh_request_stats_display()
	except NameError:
		pass

def clear_translation_history():
	if not messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa toàn bộ lịch sử dịch?"): return
	try:
		with open(HISTORY_FILE, "w", encoding="utf-8") as f:
			json.dump([], f, ensure_ascii=False, indent=2)
		refresh_history_display()
		try: refresh_request_stats_display()
		except NameError: pass
		try: refresh_cost_stats()
		except NameError: pass
		add_log("🧹 Đã xóa toàn bộ lịch sử dịch.")
	except Exception as e:
		messagebox.showerror("Lỗi", f"Không thể xóa lịch sử dịch: {e}")

def reset_request_metrics():
	with request_minute_lock:
		request_minute_counts.clear()

def record_request_event(model_id=None):
	minute_key = time.strftime("%Y-%m-%d %H:%M")
	model_key = str(model_id or "unknown")
	with request_minute_lock:
		if minute_key not in request_minute_counts:
			request_minute_counts[minute_key] = {}
		request_minute_counts[minute_key][model_key] = request_minute_counts[minute_key].get(model_key, 0) + 1

def get_request_metrics_snapshot():
	with request_minute_lock:
		minute_items = sorted(request_minute_counts.items())
	result = []
	for minute, model_counts in minute_items:
		if isinstance(model_counts, dict):
			for model_name, count in sorted(model_counts.items()):
				result.append({"minute": minute, "model": str(model_name), "count": int(count or 0)})
		else:
			result.append({"minute": minute, "model": "unknown", "count": int(model_counts or 0)})
	return result

def build_request_entry_key(entry):
	start_at = str(entry.get("start_at", ""))
	output_file = str(entry.get("output_file", ""))
	model = str(entry.get("model", ""))
	return f"{start_at}|{output_file}|{model}"

def normalize_request_counts(entry):
	raw = entry.get("request_counts_by_minute", [])
	items = []
	if isinstance(raw, dict):
		for minute, count in raw.items():
			items.append({"minute": str(minute), "model": str(entry.get("model", "unknown")), "count": int(count or 0)})
	elif isinstance(raw, list):
		for item in raw:
			if not isinstance(item, dict): continue
			minute = item.get("minute")
			if minute is None: continue
			items.append({
				"minute": str(minute),
				"model": str(item.get("model", entry.get("model", "unknown"))),
				"count": int(item.get("count", 0) or 0),
			})
	items.sort(key=lambda x: (x["minute"], x["model"]))
	return items

def summarize_request_counts(counts):
	total_requests = sum(item["count"] for item in counts)
	minute_totals = {}
	model_totals = {}
	for item in counts:
		minute = item["minute"]
		model = item.get("model", "unknown")
		minute_totals[minute] = minute_totals.get(minute, 0) + item["count"]
		model_totals[model] = model_totals.get(model, 0) + item["count"]
	peak_requests_per_minute = max(minute_totals.values(), default=0)
	return total_requests, peak_requests_per_minute, model_totals

def open_request_detail_tab(entry):
	if "tabs" not in globals(): return
	key = build_request_entry_key(entry)
	if key in request_detail_tabs:
		tabs.select(request_detail_tabs[key])
		return
	start_at = entry.get("start_at", "--")
	status = str(entry.get("status", "--")).upper()
	model = entry.get("model", "--")
	duration = format_time(entry.get("duration_seconds", 0))
	counts = normalize_request_counts(entry)
	default_total, default_peak, model_totals = summarize_request_counts(counts)
	total_requests = int(entry.get("total_requests", default_total) or 0)
	peak_rpm = int(entry.get("peak_requests_per_minute", default_peak) or 0)
	model_summary = ", ".join([f"{name}: {count:,}" for name, count in sorted(model_totals.items())]) or model
	detail_tab = tk.Frame(tabs, bg=PALETTE["bg"])
	tab_title = f"🕒 Request {start_at}"
	tabs.add(detail_tab, text=tab_title)
	request_detail_tabs[key] = detail_tab
	request_detail_tables[key] = None
	detail_tab.columnconfigure(0, weight=1)
	detail_tab.rowconfigure(1, weight=1)
	toolbar = tk.Frame(detail_tab, bg=PALETTE["panel"])
	toolbar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))
	toolbar.columnconfigure(0, weight=1)
	summary_text = (
		f"Bắt đầu: {start_at} | Trạng thái: {status} | "
		f"Model: {model_summary} | Tổng request: {total_requests:,} | "
		f"Peak/phút: {peak_rpm:,} | Thời gian: {duration}"
	)
	request_summary_label = tk.Label(toolbar, text=summary_text, bg=PALETTE["panel"], fg="#000000", font=("Segoe UI", 9))
	request_summary_label.grid(row=0, column=0, sticky="w", padx=8, pady=6)
	def _close_request_tab():
		if key in request_detail_tabs:
			request_detail_tabs.pop(key, None)
			request_detail_tables.pop(key, None)
			try: tabs.forget(detail_tab)
			except Exception: pass
			try: detail_tab.destroy()
			except Exception: pass
	close_btn = tk.Button(toolbar, text="❌ Đóng tab", font=("Segoe UI", 9, "bold"), bg=PALETTE["warn"], fg="#0b0f19", bd=0, padx=10, pady=5, command=_close_request_tab)
	close_btn.grid(row=0, column=1, padx=8, pady=4)
	table_frame = tk.Frame(detail_tab, bg=PALETTE["panel"])
	table_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
	table_frame.columnconfigure(0, weight=1)
	table_frame.rowconfigure(0, weight=1)
	columns = ("minute", "model", "count")
	request_detail_table = ttk.Treeview(table_frame, columns=columns, show="headings", style="History.Treeview")
	request_detail_table.grid(row=0, column=0, sticky="nsew")
	request_detail_table.heading("minute", text="Phút")
	request_detail_table.heading("model", text="Model")
	request_detail_table.heading("count", text="Số request")
	request_detail_table.column("minute", width=180, anchor="w")
	request_detail_table.column("model", width=200, anchor="w")
	request_detail_table.column("count", width=120, anchor="e")
	request_detail_table.tag_configure("odd", background=PALETTE["input_bg"])
	request_detail_table.tag_configure("even", background=PALETTE["panel"])
	scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=request_detail_table.yview)
	scroll_y.grid(row=0, column=1, sticky="ns")
	request_detail_table.configure(yscrollcommand=scroll_y.set)
	request_detail_tables[key] = request_detail_table
	if not counts:
		request_detail_table.insert("", tk.END, values=("Chưa có dữ liệu", "--", "0"), tags=("odd",))
	else:
		for idx, item in enumerate(counts, 1):
			row_tag = "even" if idx % 2 == 0 else "odd"
			request_detail_table.insert("", tk.END, values=(item["minute"], item.get("model", "unknown"), f"{item['count']:,}"), tags=(row_tag,))
	tabs.select(detail_tab)

def on_request_row_click(event):
	if "requests_table" not in globals(): return
	row_id = requests_table.identify_row(event.y)
	if not row_id: return
	entry = request_display_map.get(row_id)
	if entry: open_request_detail_tab(entry)

def refresh_request_stats_display():
	if "requests_table" not in globals(): return
	request_display_map.clear()
	for row_id in requests_table.get_children():
		requests_table.delete(row_id)
	history = load_translation_history()
	if not history:
		requests_hint_var.set("Chưa có lịch sử dịch.")
		return
	requests_hint_var.set("Hiển thị danh sách bản dịch (nhấn để xem request/phút).")
	for idx, item in enumerate(reversed(history), 1):
		start_at = item.get("start_at", "--")
		status = str(item.get("status", "--")).upper()
		model = item.get("model", "--")
		duration = format_time(item.get("duration_seconds", 0))
		counts = normalize_request_counts(item)
		default_total, default_peak, _ = summarize_request_counts(counts)
		total_requests = int(item.get("total_requests", default_total) or 0)
		peak_rpm = int(item.get("peak_requests_per_minute", default_peak) or 0)
		in_file = os.path.basename(item.get("input_file", ""))
		out_file = os.path.basename(item.get("output_file", ""))
		row_tag = "even" if idx % 2 == 0 else "odd"
		status_tag = f"status_{status.lower()}"
		row_id = requests_table.insert(
			"",
			tk.END,
			values=(
				start_at,
				status,
				model,
				f"{total_requests:,}",
				f"{peak_rpm:,}",
				duration,
				f"{in_file} → {out_file}",
			),
			tags=(row_tag, status_tag),
		)
		request_display_map[row_id] = item

def update_stats_display():
	if stats["total_chunks"] == 0: return
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
	stats_input_cost_var.set(f"💵 Input Cost: ${stats['total_input_cost_usd']:.4f}")
	stats_output_cost_var.set(f"💵 Output Cost: ${stats['total_output_cost_usd']:.4f}")
	stats_total_cost_var.set(f"💰 Total Cost: ${stats['total_cost_usd']:.4f}")
	stats_total_cost_vnd_var.set(f"💸 Tổng tiền Việt: {int(round(stats['total_cost_usd'] * USD_TO_VND)):,} đ")

# ================= CHUYỂN ĐỔI THEME =================
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
	if "requests_table" in globals():
		requests_table.tag_configure("odd", background=PALETTE["input_bg"])
		requests_table.tag_configure("even", background=PALETTE["panel"])
		requests_table.tag_configure("status_completed", foreground="#000000")
		requests_table.tag_configure("status_stopped", foreground="#000000")
		requests_table.tag_configure("status_error", foreground="#000000")
	if "request_detail_tables" in globals():
		for table in request_detail_tables.values():
			if not table: continue
			table.tag_configure("odd", background=PALETTE["input_bg"])
			table.tag_configure("even", background=PALETTE["panel"])
	if "cost_tree_table" in globals():
		cost_tree_table.tag_configure("month_row", background=PALETTE["accent"], foreground="#000000", font=("Segoe UI", 10, "bold"))
		cost_tree_table.tag_configure("week_row", background=PALETTE["input_bg"], foreground=PALETTE["text"])
	if "history_hint_label" in globals(): history_hint_label.configure(bg=PALETTE["panel"], fg="#000000")
	if "requests_hint_label" in globals(): requests_hint_label.configure(bg=PALETTE["panel"], fg="#000000")
	main_container.configure(bg=PALETTE["bg"])
	main_frame.configure(bg=PALETTE["bg"])
	header.configure(bg=PALETTE["bg"])
	badge_row.configure(bg=PALETTE["bg"])
	for widget in main_container.winfo_children():
		update_widget_colors(widget)

def update_widget_colors(widget):
	try:
		widget_type = widget.winfo_class()
		if widget_type in ["Frame", "Labelframe"]:
			try: widget.configure(bg=PALETTE["bg"])
			except: pass
		elif widget_type == "Label":
			try:
				current_bg = widget.cget("bg")
				if current_bg not in [PALETTE["accent"], PALETTE["accent_alt"], "#f59e0b", "#38bdf8", "#0ea5e9"]:
					widget.configure(bg=PALETTE["panel"], fg=PALETTE["text"])
			except: pass
		elif widget_type in ["Entry", "Text"]:
			try:
				widget.configure(
					bg=PALETTE["input_bg"],
					fg=PALETTE["text"],
					insertbackground=PALETTE["accent"],
					highlightbackground=PALETTE["border"],
				)
			except: pass
		for child in widget.winfo_children():
			update_widget_colors(child)
	except Exception:
		pass

# ================= CHIA CHUNK =================
def split_text(text, size=CHUNK_SIZE, split_mode="keyword"):
	chunks = []
	current_chunk = ""
	keyword_patterns = [
		r"^\s*(chương|chap(?:ter)?|hồi|quyển|tập|thiên|phần|mục|tiết|ngoại\s*(truyện|chương)|phiên\s*ngoại|đệ\s+\w+\s+chương|thứ\s+\w+\s+chương)\b",
		r"^\s*(ch\.|chap\.|c\.|q\.|t\.)\s*\d+\b",
	]
	_equals_pattern = r"^\s*={3,}\s*(thứ\s+\w+\s+chương|chương\s+\w+|chap(?:ter)?\s+\w+|hồi\s+\w+|quyển\s+\w+|tập\s+\w+|thiên\s+\w+|phần\s+\w+|mục\s+\w+|tiết\s+\w+)\b.*(?:={3,}\s*)?$"
	active_patterns = [_equals_pattern] if split_mode == "equals" else keyword_patterns
	active_matchers = [re.compile(p, re.IGNORECASE) for p in active_patterns]
	lines = text.splitlines(True)
	blocks = []
	current_block = ""
	for line in lines:
		if any(matcher.match(line) for matcher in active_matchers):
			if current_block.strip(): blocks.append(current_block)
			current_block = line
		else:
			current_block += line
	if current_block.strip(): blocks.append(current_block)
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
						if temp_str.strip(): chunks.append(temp_str)
						if len(p_text) > size:
							temp_str2 = ""
							sentences = re.split(r'(?<=[.!?]) +|\n', p_text)
							for s in sentences:
								s_text = s + " "
								if len(temp_str2) + len(s_text) > size:
									if temp_str2.strip():
										chunks.append(temp_str2)
										temp_str2 = ""
									if len(s_text) > size:
										for k in range(0, len(s_text), size):
											sub_s = s_text[k:k+size]
											if len(sub_s) < size or k + size >= len(s_text): temp_str2 = sub_s
											else: chunks.append(sub_s)
									else: temp_str2 = s_text
								else: temp_str2 += s_text
							temp_str = temp_str2
						else: temp_str = p_text
					else: temp_str += p_text
				if temp_str.strip(): current_chunk = temp_str
			else:
				current_chunk = block
		else:
			current_chunk += block
	if current_chunk.strip(): chunks.append(current_chunk)
	return chunks

def extract_json_from_response(raw_text):
	if not raw_text: return None
	text = raw_text.strip()
	if text.startswith("```"):
		lines = text.splitlines()
		if lines:
			lines = lines[1:]
			if lines and lines[-1].strip().startswith("```"):
				lines = lines[:-1]
			text = "\n".join(lines).strip()
	try: return json.loads(text)
	except Exception: pass
	start = text.find("{")
	end = text.rfind("}")
	if start != -1 and end != -1 and end > start:
		candidate = text[start : end + 1]
		try: return json.loads(candidate)
		except Exception: return None
	return None

def is_gemini_v3_or_above(model_name):
	if not model_name: return False
	return "gemini" in str(model_name).lower()

def translate_with_proxy(model_id, prompt, chunk, temperature, max_output_tokens):
	base_url = normalize_base_url(vps_ip_entry.get())
	token = api_key_entry.get().strip()
	if not base_url or not token:
		return None, 0, 0, "Lỗi: Chưa cấu hình kết nối"
	endpoint = f"{base_url}/v1/chat/completions"
	payload = {
		"model": model_id,
		"messages": [{"role": "user", "content": f"{prompt}\n\n--- NOI DUNG CAN DICH ---\n{chunk}"}],
		"temperature": temperature,
		"max_tokens": max_output_tokens,
		"stream": False
	}
	body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
	}
	request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
	try:
		with urllib.request.urlopen(request, timeout=180) as response:
			raw = response.read().decode("utf-8")
	except urllib.error.HTTPError as e:
		try:
			err_body = e.read().decode("utf-8")
			err_str = f"HTTP Error {e.code}: {e.reason} | Chi tiết: {err_body}" if err_body else f"HTTP Error {e.code}: {e.reason}"
		except:
			err_str = f"HTTP Error {e.code}: {e.reason}"
		if "429" in err_str or "quota" in err_str.lower() or "rate limit" in err_str.lower():
			return None, 0, 0, "QUOTA"
		return None, 0, 0, err_str
	except Exception as e:
		return None, 0, 0, str(e)
	try:
		data = json.loads(raw)
		choices = data.get("choices", [])
		if not choices: return None, 0, 0, "API không trả về choices"
		content = choices[0].get("message", {}).get("content", "")
		if isinstance(content, list):
			merged = [part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"]
			content = "\n".join(merged)
		content = (content or "").strip()
		if not content: return None, 0, 0, "Model trả về nội dung rỗng"
		usage = data.get("usage", {})
		in_t = usage.get("prompt_tokens", 0)
		out_t = usage.get("completion_tokens", 0)
		if in_t == 0: in_t = int(len(chunk)/2.5) + int(len(prompt)/3.5)
		if out_t == 0: out_t = int(len(content)/3.5)
		return content, in_t, out_t, None
	except Exception as e:
		return None, 0, 0, f"JSON Parse Error: {e}"

# ================= DỊCH 1 CHUNK =================
def translate_chunk(model_id, prompt, chunk, index, cp_file, temperature, max_output_tokens, model_fallback_order=None, retries=3):
	global is_stopped
	pause_event.wait()
	if is_stopped: return index, None
	if model_fallback_order is None: model_fallback_order = [model_id]
	last_error = None
	current_model_index = 0
	for attempt in range(retries):
		if is_stopped: return index, None
		pause_event.wait()
		try:
			current_model = model_fallback_order[current_model_index] if current_model_index < len(model_fallback_order) else model_fallback_order[0]
			add_log(f"⏳ Đang dịch đoạn {index + 1} (model: {current_model})... (lần thử {attempt + 1}/{retries})")
			record_request_event(current_model)
			translated_text, input_tokens, output_tokens, error_code = translate_with_proxy(current_model, prompt, chunk, temperature, max_output_tokens)
			if error_code == 'QUOTA':
				if current_model_index + 1 < len(model_fallback_order):
					current_model_index += 1
					next_model = model_fallback_order[current_model_index]
					add_log(f"⚠️ Đoạn {index + 1}: Vượt quota model '{current_model}', chuyển sang '{next_model}'...")
					time.sleep(1)
					continue
				else:
					add_log(f"❌ Đoạn {index + 1}: Tất cả model đều vượt quota!")
					last_error = "Tất cả model vượt quota"
					time.sleep(2 + attempt * 2)
					continue
			if error_code:
				last_error = f"Lỗi API: {error_code}"
				add_log(f"⚠️ Đoạn {index + 1} gặp lỗi (lần {attempt + 1}): {last_error}")
				time.sleep(2 + attempt * 2)
				continue
			if not translated_text: raise RuntimeError("API trả về nội dung rỗng.")
			save_checkpoint(cp_file, index, translated_text)
			stats["chunks_done"] += 1
			stats["total_input_chars"] += len(chunk)
			stats["total_output_chars"] += len(translated_text)
			stats["total_input_tokens"] += input_tokens
			stats["total_output_tokens"] += output_tokens
			input_price_per_1m, output_price_per_1m = get_model_prices_usd_per_1m(current_model, input_tokens)
			input_cost = (input_tokens / 1_000_000) * input_price_per_1m
			output_cost = (output_tokens / 1_000_000) * output_price_per_1m
			stats["total_input_cost_usd"] += input_cost
			stats["total_output_cost_usd"] += output_cost
			stats["total_cost_usd"] = stats["total_input_cost_usd"] + stats["total_output_cost_usd"]
			add_log(f"✅ Hoàn thành đoạn {index + 1}")
			return index, translated_text
		except Exception as e:
			last_error = str(e)
			add_log(f"❌ Đoạn {index + 1} gặp lỗi (lần {attempt + 1}): {last_error}")
			time.sleep(2 + attempt * 2)
	add_log(f"🔴 Đoạn {index + 1} thất bại sau {retries} lần thử: {last_error}")
	return index, None

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
	base_url = normalize_base_url(vps_ip_entry.get())
	if not base_url:
		messagebox.showerror("Lỗi", "Vui lòng nhập IP VPS hoặc Base URL hợp lệ.")
		return False
	api_key = api_key_entry.get().strip()
	if not api_key:
		messagebox.showerror("Lỗi", "Vui lòng nhập API Key / Token.")
		return False
	if drive_upload_var.get():
		if not ensure_drive_dependencies():
			messagebox.showerror("Thiếu thư viện", "Chưa cài thư viện Google Drive.\nCài bằng lệnh: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
			return False
		credentials_path = drive_credentials_path_var.get().strip()
		if not credentials_path or not os.path.isfile(credentials_path):
			messagebox.showerror("Lỗi", "Vui lòng chọn file credentials Google Drive hợp lệ.")
			return False
	if not input_path.get() or not os.path.isfile(input_path.get()):
		messagebox.showerror("Lỗi", "Vui lòng chọn file truyện đầu vào hợp lệ.")
		return False
	try:
		thread_count = int(thread_var.get())
		if thread_count <= 0 or thread_count > 20: raise ValueError
	except:
		messagebox.showerror("Lỗi", "Số luồng phải là số nguyên từ 1 đến 20.")
		return False
	try:
		chunk_size = int(chunk_size_var.get())
		if chunk_size < 500 or chunk_size > 70000: raise ValueError
	except:
		messagebox.showerror("Lỗi", "Chunk size phải là số nguyên từ 500 đến 70000.")
		return False
	try:
		max_output_tokens = int(max_output_tokens_var.get())
		if max_output_tokens < 256 or max_output_tokens > 70000: raise ValueError
	except:
		messagebox.showerror("Lỗi", "Max output tokens phải là số nguyên từ 256 đến 70000.")
		return False
	try:
		temp = float(temp_var.get())
		if temp < 0 or temp > 2: raise ValueError
	except:
		messagebox.showerror("Lỗi", "Nhiệt độ phải nằm trong khoảng 0 đến 2.")
		return False
	return True

def normalize_scanned_glossary(raw_text):
	if not raw_text: return ""
	cleaned_lines = []
	seen = set()
	for line in raw_text.splitlines():
		clean = line.strip().lstrip("-•* ").strip()
		if not clean: continue
		separator = None
		for candidate in ["=>", "->", "→", ":", "="]:
			if candidate in clean:
				separator = candidate
				break
		if not separator: continue
		source, target = clean.split(separator, 1)
		source = source.strip(" \t\"'“”‘’[](){}")
		target = target.strip(" \t\"'“”‘’[]{}")
		if not source or not target: continue
		normalized = f"{source} => {target}"
		key = normalized.lower()
		if key in seen: continue
		seen.add(key)
		cleaned_lines.append(normalized)
	return "\n".join(cleaned_lines)

def get_scan_char_limit():
	try:
		scan_char_limit = int(scan_char_limit_var.get())
		if scan_char_limit < 500 or scan_char_limit > 200000: raise ValueError
		return scan_char_limit
	except:
		messagebox.showerror("Lỗi", "Giới hạn ký tự quét phải là số nguyên từ 500 đến 200000.")
		return None

def build_scan_segments(text, segment_size=12000, max_segments=12):
	if not text: return []
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
	if bucket.strip(): segments.append(bucket)
	if not segments: segments = [text[:segment_size]]
	if len(segments) <= max_segments: return segments
	selected = []
	selected_positions = set()
	for i in range(max_segments):
		pos = int(round(i * (len(segments) - 1) / (max_segments - 1))) if max_segments > 1 else 0
		if pos not in selected_positions:
			selected_positions.add(pos)
			selected.append(segments[pos])
	return selected

def scan_story():
	if not validate_inputs(): return
	scan_char_limit = get_scan_char_limit()
	if scan_char_limit is None: return
	in_file = input_path.get()
	model_id = model_var.get()
	temperature = float(temp_var.get())
	def run_scan():
		try:
			add_log(f"🔍 Đang quét thuật ngữ (tối đa {scan_char_limit:,} ký tự, có thể mất 10-60 giây)...")
			full_text = read_file_content_safely(in_file)
			limited_text = full_text[:scan_char_limit]
			scan_segments = build_scan_segments(limited_text, segment_size=12000, max_segments=12)
			add_log(f"🧩 Quét {len(scan_segments)} đoạn mẫu để tăng độ phủ thuật ngữ.")
			scan_prompt = (
				"Bạn là chuyên gia biên tập truyện dịch từ Trung sang Việt.\n"
				"Hãy trích xuất danh sách thuật ngữ quan trọng từ đoạn sau để đưa vào từ điển đồng nhất (Glossary), ưu tiên:\n\n"
				"1. TÊN RIÊNG (Tên nhân vật, địa danh, môn phái, thế lực, thần khí, bảo vật):\n"
				"   VD: 张三 => Trương Tam, 青云门 => Thanh Vân Môn (Cổng Mây Xanh), 轩辕剑 => Kiếm Hiên Viên\n\n"
				"2. CẢNH GIỚI TU LUYỆN, CHIÊU THỨC, CÔNG PHÁP (Các danh từ cài đặt đặc thù của truyện):\n"
				"   VD: 筑基 => Trúc Cơ (xây dựng nền móng tu luyện), 炼气 => Luyện Khí (rèn luyện khí trong người), 降龙十八掌 => Giáng Long Thập Bát Chưởng (mười tám chưởng rồng bay)\n\n"
				"3. CÁCH XƯNG HÔ ĐẶC THÙ (Cách xưng hô cổ trang hoặc đặc trưng của nhân vật):\n"
				"   VD: 师兄 => Sư huynh (đàn anh), 本座 => Bổn tọa (ta), 朕 => Trẫm (ta)\n\n"
				"ĐỊNH DẠNG BẮT BUỘC: mỗi dòng một mục theo mẫu: Nguồn => Đích\n\n"
				"YÊU CẦU DỊCH VÀ GIẢI THÍCH (CỰC KỲ QUAN TRỌNG):\n"
				"- Hãy ưu tiên dịch từ đích sang Thuần Việt dễ hiểu nhất có thể để người đọc hiểu luôn ý nghĩa của câu văn.\n"
				"- Nếu bắt buộc phải giữ Hán Việt (do là thuật ngữ cảnh giới, địa danh đặc thù...), hãy giữ Hán Việt và BẮT BUỘC phải ghi chú giải thích ý nghĩa trong dấu ngoặc đơn ngay sau từ đó.\n"
				"  LƯU Ý CỐT LÕI: Phần giải thích trong ngoặc đơn sẽ được hệ thống dùng trực tiếp để thay thế làm từ dịch chính vào truyện. Do đó, hãy viết phần giải thích này cực kỳ ngắn gọn, tự nhiên và phù hợp để thay thế trực tiếp vào câu văn (Ví dụ: thay vì giải thích dài dòng 'người lớn hơn cùng môn phái', hãy ghi ngắn gọn trong ngoặc đơn là 'đàn anh' hoặc 'anh lớn' để thay thế trực tiếp vào câu văn dịch).\n\n"
				"YÊU CẦU CỰC KỲ QUAN TRỌNG:\n"
				"- Chỉ quét các danh từ riêng, thuật ngữ đặc thù cần giữ đồng nhất. KHÔNG quét các từ vựng thông thường (VD: KHÔNG đưa 'phát hiện => tìm thấy', 'chuẩn bị => sắp sửa' vào vì chúng làm cứng nhắc văn phong).\n"
				"- Không giải thích gì ngoài cấu trúc 'Nguồn => Đích' (ngoại trừ phần giải thích trong ngoặc đơn ở cột đích như yêu cầu ở trên), không đánh số đầu dòng kết quả trả về, không thêm tiêu đề.\n"
				"- Không lặp mục đã có.\n"
				"- Nếu không có thuật ngữ phù hợp thì trả về duy nhất từ: Không có"
			)
			merged_terms = []
			seen_terms = set()
			for seg_idx, segment in enumerate(scan_segments, 1):
				add_log(f"🔎 Quét đoạn mẫu {seg_idx}/{len(scan_segments)}...")
				raw_result, _, _, _ = translate_with_proxy(model_id, scan_prompt, segment, temperature, 3072)
				if not raw_result or "không có" in raw_result.lower(): continue
				normalized = normalize_scanned_glossary(raw_result)
				if not normalized: continue
				for term_line in normalized.splitlines():
					term_key = term_line.strip().lower()
					if not term_key or term_key in seen_terms: continue
					seen_terms.add(term_key)
					merged_terms.append(term_line.strip())
				time.sleep(0.35)
			extracted_terms = "\n".join(merged_terms)
			if extracted_terms:
				add_log(f"✅ Quét xong thuật ngữ! Tìm thấy {len(merged_terms)} mục.")
				def ask_user():
					if messagebox.askyesno("Kết quả quét thuật ngữ", f"Đã tìm thấy các thuật ngữ:\n\n{extracted_terms}\n\nBạn có muốn thêm vào Glossary không?"):
						current_glossary = glossary_text.get("1.0", tk.END).strip()
						new_glossary = (current_glossary + "\n" + extracted_terms) if current_glossary else extracted_terms
						glossary_text.delete("1.0", tk.END)
						glossary_text.insert(tk.END, new_glossary)
						add_log("📝 Đã thêm thuật ngữ vào Glossary.")
				root.after(0, ask_user)
			else:
				add_log("ℹ️ Không tìm thấy thuật ngữ đặc biệt nào.")
				root.after(0, lambda: messagebox.showinfo("Kết quả", "Không tìm thấy thuật ngữ đặc biệt nào từ các đoạn đầu truyện."))
		except Exception as e:
			add_log(f"🛑 Lỗi khi quét thuật ngữ: {e}")
			root.after(0, lambda: messagebox.showerror("Lỗi", f"Có lỗi xảy ra: {e}"))
	threading.Thread(target=run_scan, daemon=True).start()

def fetch_models():
	base_url = normalize_base_url(vps_ip_entry.get())
	token = api_key_entry.get().strip()
	if not base_url:
		messagebox.showerror("Lỗi", "Vui lòng nhập IP VPS hoặc Base URL hợp lệ")
		return
	if not token:
		messagebox.showerror("Lỗi", "Vui lòng nhập API Key / Token")
		return
	def _worker():
		endpoint = f"{base_url}/v1/models"
		headers = {
			"Content-Type": "application/json",
			"Authorization": f"Bearer {token}",
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
		}
		request = urllib.request.Request(endpoint, headers=headers, method="GET")
		try:
			add_log("⏳ Đang tải danh sách model từ proxy...")
			with urllib.request.urlopen(request, timeout=20) as response:
				payload = json.loads(response.read().decode("utf-8"))
			model_ids = []
			for item in payload.get("data", []):
				if isinstance(item, dict) and item.get("id"):
					model_ids.append(str(item["id"]))
			if not model_ids: raise ValueError("Không lấy được model nào.")
			def _update_ui():
				model_cb["values"] = model_ids
				quick_model_cb["values"] = model_ids
				model_var.set(model_ids[0])
				quick_model_var.set(model_ids[0])
				model_fallback_order_var.set("|".join(model_ids))
				add_log(f"✅ Đã tải {len(model_ids)} model từ VPS/Proxy.")
				messagebox.showinfo("Thành công", f"Đã tải {len(model_ids)} model thành công!")
			root.after(0, _update_ui)
		except Exception as e:
			def _show_error():
				add_log(f"❌ Tải model thất bại: {e}")
				messagebox.showerror("Lỗi", f"Không thể tải danh sách model:\n{e}")
			root.after(0, _show_error)
	threading.Thread(target=_worker, daemon=True).start()

# ================= 1. PHƯƠNG THỨC KÍCH HOẠT (START) =================
def start_translation():
	global is_stopped, is_paused
	if not validate_inputs(): return
	is_stopped = False
	is_paused = False
	pause_event.set()
	output_path.set(build_default_output_path(input_path.get(), model_var.get()))
	add_log(f"📄 File output mặc định: {output_path.get()}")
	save_settings()
	task_thread = threading.Thread(target=process_translation_logic)
	task_thread.daemon = True
	task_thread.start()
	stats_thread = threading.Thread(target=stats_update_loop)
	stats_thread.daemon = True
	stats_thread.start()
	add_log("🚀 Đã kích hoạt luồng dịch thuật ngầm (Proxy)...")

def stats_update_loop():
	while not is_stopped and btn_start["state"] == "disabled":
		update_stats_display()
		time.sleep(1)

# ================= 2. PHƯƠNG THỨC LOGIC CHÍNH (LOGIC) =================
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
	reset_request_metrics()
	history_status = "error"
	history_error = ""
	drive_file_id = ""
	drive_link = ""
	in_file = input_path.get()
	out_file = output_path.get()
	model = model_var.get()
	threads = thread_var.get()
	temperature = temp_var.get()
	try:
		in_file = input_path.get()
		out_file = output_path.get()
		model = model_var.get()
		model_fallback_order_str = model_fallback_order_var.get()
		model_fallback_order = [m.strip() for m in model_fallback_order_str.split("|") if m.strip()]
		if not model_fallback_order: model_fallback_order = [model]
		if model in model_fallback_order: model_fallback_order = [m for m in model_fallback_order if m != model]
		model_fallback_order = [model] + model_fallback_order
		fallback_order_hint_var.set(f"Thứ tự fallback hiệu lực: {' -> '.join(model_fallback_order)}")
		add_log(f"🔄 Model fallback order: {' -> '.join(model_fallback_order)}")
		cp_file = get_checkpoint_path(in_file)
		threads = int(thread_var.get())
		chunk_size = int(chunk_size_var.get())
		max_output_tokens = int(max_output_tokens_var.get())
		temperature = float(temp_var.get())
		prompt = prompt_text.get("1.0", tk.END).strip()
		glossary_raw = glossary_text.get("1.0", tk.END).strip()
		glossary_entries = parse_glossary(glossary_raw)
		prompt = build_prompt_with_glossary(prompt, glossary_entries)
		if glossary_entries: add_log(f"📚 Áp dụng glossary: {len(glossary_entries)} mục thuật ngữ.")
		chunks = split_text(read_file_content_safely(in_file), size=chunk_size, split_mode=chunk_split_mode_var.get())
		total = len(chunks)
		stats["total_chunks"] = total
		results = [None] * total
		has_checkpoint = False
		saved_data = {}
		with checkpoint_lock:
			if os.path.exists(cp_file):
				try:
					with open(cp_file, "r", encoding="utf-8") as f:
						saved_data = json.load(f)
					has_checkpoint = True
				except Exception as e:
					add_log(f"⚠️ Không thể đọc file checkpoint: {e}")
		if has_checkpoint and saved_data:
			if messagebox.askyesno("Khôi phục", f"Tìm thấy bản dịch dở dang ({len(saved_data)}/{total} đoạn). Dịch tiếp chứ?"):
				for idx_str, text in saved_data.items():
					idx = int(idx_str)
					if 0 <= idx < total: results[idx] = text
				stats["chunks_done"] = len([r for r in results if r is not None])
				add_log(f"🔄 Đã khôi phục {stats['chunks_done']} đoạn từ file checkpoint.")
		else:
			with checkpoint_lock:
				with open(cp_file, "w", encoding="utf-8") as f:
					json.dump({}, f)
		progress_bar["maximum"] = total
		pending_indices = [i for i in range(total) if results[i] is None]
		progress_bar["value"] = total - len(pending_indices)
		add_log(f"📦 Bắt đầu dịch {len(pending_indices)} đoạn còn lại bằng {model}...")
		add_log(f"⚙️ Chunk size: {chunk_size} | Max output tokens: {max_output_tokens}")
		add_log(f"🌡️ Temperature: {temperature}")
		with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
			futures = {
				executor.submit(
					translate_chunk, model, prompt, chunks[i], i, cp_file, temperature, max_output_tokens, model_fallback_order
				): i for i in pending_indices
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
			final_text = []
			for idx, r in enumerate(results):
				if r is not None: final_text.append(r)
				else: final_text.append(f"\n\n--- [LỖI DỊCH ĐOẠN {idx + 1} - DÙNG BẢN GỐC] ---\n{chunks[idx]}\n-----------------------------------------\n\n")
			f.write("\n\n".join(final_text))
		if drive_upload_var.get():
			try:
				add_log("☁️ Đang upload file lên Google Drive...")
				drive_file_id, drive_link = upload_file_to_drive(out_file, drive_credentials_path_var.get().strip(), drive_folder_id_var.get().strip())
				if drive_link: add_log(f"✅ Upload Google Drive thành công: {drive_link}")
				else: add_log("✅ Upload Google Drive thành công.")
			except Exception as e:
				add_log(f"⚠️ Upload Google Drive thất bại: {e}")
		total_time = time.time() - stats["start_time"]
		add_log(f"🎊 HOÀN TẤT! Tổng thời gian: {format_time(total_time)}")
		add_log(f"📊 Đã dịch {stats['total_input_chars']:,} → {stats['total_output_chars']:,} ký tự")
		add_log(f"🔢 Input Token: {stats['total_input_tokens']:,} | Output Token: {stats['total_output_tokens']:,}")
		add_log(f"💰 Total Cost: ${stats['total_cost_usd']:.4f} ({int(round(stats['total_cost_usd'] * USD_TO_VND)):,} đ)")
		history_status = "completed"
		completion_message = (
			f"Truyện đã được dịch xong!\n"
			f"Thời gian: {format_time(total_time)}\n"
			f"Tổng tiền: ${stats['total_cost_usd']:.4f}\n"
			f"Tổng tiền Việt: {int(round(stats['total_cost_usd'] * USD_TO_VND)):,} đ\n"
			f"Lưu tại: {out_file}"
		)
		show_completion_dialog("Hoàn tất", completion_message, drive_link)
	except Exception as e:
		error_msg = str(e)
		history_error = error_msg
		add_log(f"🛑 LỖI HỆ THỐNG: {error_msg}")
		messagebox.showerror("Lỗi", f"Quá trình dịch bị gián đoạn: {error_msg}")
	finally:
		end_time = time.time()
		duration_seconds = max(0, int(end_time - stats["start_time"])) if stats["start_time"] else 0
		request_metrics = get_request_metrics_snapshot()
		total_requests, peak_requests_per_minute, _ = summarize_request_counts(request_metrics)
		history_entry = {
			"engine": "API Proxy / VPS",
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
			"total_cost_vnd": int(round(stats["total_cost_usd"] * USD_TO_VND)),
			"request_counts_by_minute": request_metrics,
			"total_requests": total_requests,
			"peak_requests_per_minute": peak_requests_per_minute,
			"drive_file_id": drive_file_id,
			"drive_link": drive_link,
			"error": history_error,
		}
		save_translation_history_entry(history_entry)
		refresh_history_display()
		try: refresh_cost_stats()
		except: pass
		btn_start.config(state="normal")
		btn_pause.config(state="disabled", text="⏸️ TẠM DỪNG", bg="#FFC107")
		btn_stop.config(state="disabled")
		status_var.set("Sẵn sàng")
		is_stopped = True

# ================= 2. DIFF VIEWER - SO SÁNH FILE =================
def show_diff_window(original_text: str, translated_text: str, input_file: str, output_file: str):
	diff_win = tk.Toplevel(root)
	diff_win.title("🔄 Diff Viewer - So sánh gốc vs dịch")
	diff_win.geometry("1200x700")
	diff_win.configure(bg=PALETTE["bg"])
	toolbar = tk.Frame(diff_win, bg=PALETTE["panel"])
	toolbar.pack(fill="x", padx=10, pady=10)
	file_info = f"Gốc: {os.path.basename(input_file)} | Dịch: {os.path.basename(output_file)}"
	tk.Label(toolbar, text=file_info, bg=PALETTE["panel"], fg=PALETTE["text"], font=("Segoe UI", 9)).pack(anchor="w")
	main_frame = tk.Frame(diff_win, bg=PALETTE["bg"])
	main_frame.pack(fill="both", expand=True, padx=10, pady=10)
	main_frame.columnconfigure(0, weight=1, uniform="diff_group")
	main_frame.columnconfigure(1, weight=1, uniform="diff_group")
	left_label = tk.Label(main_frame, text="📄 Bản gốc (Trung)", bg=PALETTE["panel"], fg=PALETTE["text"], font=("Segoe UI", 10, "bold"))
	left_label.grid(row=0, column=0, sticky="ew", padx=(0, 5))
	left_text = scrolledtext.ScrolledText(main_frame, bg=PALETTE["input_bg"], fg=PALETTE["text"], wrap="word", height=25)
	left_text.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
	left_text.insert(tk.END, original_text)
	left_text.config(state="disabled")
	right_label = tk.Label(main_frame, text="📝 Bản dịch (Việt)", bg=PALETTE["panel"], fg=PALETTE["text"], font=("Segoe UI", 10, "bold"))
	right_label.grid(row=0, column=1, sticky="ew", padx=(5, 0))
	right_text = scrolledtext.ScrolledText(main_frame, bg=PALETTE["input_bg"], fg=PALETTE["text"], wrap="word", height=25)
	right_text.grid(row=1, column=1, sticky="nsew", padx=(5, 0))
	right_text.insert(tk.END, translated_text)
	right_text.config(state="disabled")
	def sync_scroll_y(event=None):
		left_text.yview_moveto(right_text.yview()[0])
	right_text.bind("<MouseWheel>", sync_scroll_y)
	right_text.bind("<Button-4>", sync_scroll_y)
	right_text.bind("<Button-5>", sync_scroll_y)
	main_frame.rowconfigure(1, weight=1)
	close_btn = tk.Button(diff_win, text="Đóng", bg=PALETTE["accent"], fg="#0b0f19", bd=0, padx=15, pady=8, command=diff_win.destroy)
	close_btn.pack(pady=10)
	diff_win.transient(root)
	diff_win.grab_set()

# ================= 3. CLIPBOARD - PASTE FROM CLIPBOARD =================
def paste_from_clipboard():
	try:
		clipboard_text = root.clipboard_get()
		quick_input_text.config(state="normal")
		quick_input_text.delete("1.0", tk.END)
		quick_input_text.insert(tk.END, clipboard_text)
		quick_status_var.set(f"✅ Đã paste: {len(clipboard_text)} ký tự")
	except Exception as e:
		messagebox.showerror("Lỗi", f"Không thể lấy từ clipboard: {e}")

def copy_to_clipboard():
	output_text = quick_output_text.get("1.0", tk.END).strip()
	if not output_text:
		messagebox.showwarning("Cảnh báo", "Chưa có kết quả dịch để copy!")
		return
	try:
		root.clipboard_clear()
		root.clipboard_append(output_text)
		quick_status_var.set("✅ Đã copy kết quả vào clipboard!")
	except Exception as e:
		messagebox.showerror("Lỗi", f"Không thể copy: {e}")

def translate_clipboard_text():
	api_key = api_key_entry.get().strip()
	if not api_key:
		messagebox.showerror("Lỗi", "Vui lòng nhập API Key")
		return
	input_text = quick_input_text.get("1.0", tk.END).strip()
	if not input_text:
		messagebox.showwarning("Cảnh báo", "Vui lòng paste text vào trước!")
		return
	quick_status_var.set("⏳ Đang dịch...")
	def _worker():
		try:
			model_id = quick_model_var.get()
			temperature = float(temp_var.get())
			max_tokens = int(max_output_tokens_var.get())
			prompt = prompt_text.get("1.0", tk.END).strip()
			glossary_raw = glossary_text.get("1.0", tk.END).strip()
			glossary_entries = parse_glossary(glossary_raw)
			final_prompt = build_prompt_with_glossary(prompt, glossary_entries)
			result, input_tokens, output_tokens, error_code = translate_with_proxy(
				model_id, final_prompt, input_text, temperature, max_tokens
			)
			if error_code: result = f"[LỖI: {error_code}]"
			def _update_ui():
				quick_output_text.config(state="normal")
				quick_output_text.delete("1.0", tk.END)
				quick_output_text.insert(tk.END, result or "")
				quick_status_var.set(f"✅ Dịch xong! Input: {input_tokens:,} | Output: {output_tokens:,}")
			root.after(0, _update_ui)
		except Exception as e:
			def _show_error(): quick_status_var.set(f"❌ Lỗi: {str(e)[:80]}")
			root.after(0, _show_error)
	threading.Thread(target=_worker, daemon=True).start()

# ================= GUI (Giao diện) =================
root = tk.Tk()
root.title("📖 App Dịch Truyện – API Proxy / VPS Client")
root.geometry("1100x950")
root.bind_class("TCombobox", "<MouseWheel>", lambda e: "break")
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
style.configure("History.Treeview", background=PALETTE["input_bg"], fieldbackground=PALETTE["input_bg"], foreground="#000000", bordercolor=PALETTE["border"], rowheight=28)
style.map("History.Treeview", background=[("selected", PALETTE["accent_alt"])], foreground=[("selected", "#000000")])
style.configure("History.Treeview.Heading", background=PALETTE["panel"], foreground="#000000", relief="flat", font=("Segoe UI", 9, "bold"))
style.map("History.Treeview.Heading", background=[("active", PALETTE["accent"])], foreground=[("active", "#000000")])

canvas_bg = tk.Canvas(root, highlightthickness=0, bd=0, bg=PALETTE["bg"])
scrollbar = tk.Scrollbar(root, orient="vertical", command=canvas_bg.yview, bg=PALETTE["border"], troughcolor=PALETTE["bg"])
canvas_bg.configure(yscrollcommand=scrollbar.set)
scrollbar.pack(side="right", fill="y")
canvas_bg.pack(side="left", fill="both", expand=True)

def _hex_to_rgb(hex_color):
	hex_color = hex_color.lstrip("#")
	return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

def _rgb_to_hex(rgb): return "#%02x%02x%02x" % rgb

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
for col in range(2): main_frame.columnconfigure(col, weight=1)

header = tk.Frame(main_frame, bg=PALETTE["bg"])
header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
header_top = tk.Frame(header, bg=PALETTE["bg"])
header_top.pack(fill="x")
header_title_frame = tk.Frame(header_top, bg=PALETTE["bg"])
header_title_frame.pack(side="left", fill="both", expand=True)

ttk.Label(header_title_frame, text="App Dịch Truyện – API Proxy & VPS Client", style="Header.TLabel").pack(anchor="w")
ttk.Label(header_title_frame, text="Đa luồng, chia chunk, dịch glossary, diff viewer và checkpoint resume.", style="SubHeader.TLabel").pack(anchor="w", pady=(4, 6))

btn_theme = tk.Button(header_top, text="🌙 Tối", font=("Segoe UI", 10, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=15, pady=8, command=toggle_theme, cursor="hand2")
btn_theme.pack(side="right", padx=(10, 0))

badge_row = tk.Frame(header, bg=PALETTE["bg"])
badge_row.pack(anchor="w", pady=(4, 0))
for text, color in [("OpenAI-Compatible Proxy", PALETTE["accent"]), ("Fast Translation & Glossary", PALETTE["accent_alt"])]:
	tk.Label(badge_row, text=text, bg=color, fg="#0b0f19", font=("Segoe UI", 9, "bold"), padx=10, pady=4, bd=0).pack(side="left", padx=(0, 8))

def build_card(parent, title, col, row, colspan=1, rowspan=1):
	card = ttk.Frame(parent, style="Card.TFrame")
	card.grid(row=row, column=col, columnspan=colspan, rowspan=rowspan, sticky="nsew", padx=6, pady=6, ipadx=8, ipady=8)
	card.columnconfigure(0, weight=1)
	tk.Label(card, text=title, bg=PALETTE["panel"], fg=PALETTE["text"], font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
	return card

tabs = ttk.Notebook(main_frame)
tabs.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 6))
main_frame.rowconfigure(1, weight=1)

translate_tab = tk.Frame(tabs, bg=PALETTE["bg"])
preview_tab = tk.Frame(tabs, bg=PALETTE["bg"])
quick_translate_tab = tk.Frame(tabs, bg=PALETTE["bg"])
diff_tab = tk.Frame(tabs, bg=PALETTE["bg"])
history_tab = tk.Frame(tabs, bg=PALETTE["bg"])
requests_tab = tk.Frame(tabs, bg=PALETTE["bg"])
stats_tab = tk.Frame(tabs, bg=PALETTE["bg"])

tabs.add(translate_tab, text="🚀 Dịch truyện")
tabs.add(preview_tab, text="🔍 Xem Chunk")
tabs.add(quick_translate_tab, text="📋 Dịch nhanh")
tabs.add(diff_tab, text="🔄 Diff Viewer")
tabs.add(history_tab, text="🗂️ Lịch sử dịch")
tabs.add(requests_tab, text="📈 Request/phút")
tabs.add(stats_tab, text="💰 Thống kê chi phí")

for col in range(2): translate_tab.columnconfigure(col, weight=1, uniform="col_group")
quick_translate_tab.columnconfigure(0, weight=1)
quick_translate_tab.rowconfigure(1, weight=1)
quick_translate_tab.rowconfigure(3, weight=1)
diff_tab.columnconfigure(0, weight=1)
diff_tab.rowconfigure(1, weight=1)
history_tab.columnconfigure(0, weight=1)
history_tab.rowconfigure(1, weight=1)
requests_tab.columnconfigure(0, weight=1)
requests_tab.rowconfigure(1, weight=1)
stats_tab.columnconfigure(0, weight=1)
stats_tab.rowconfigure(1, weight=1)

# ================= THỐNG KÊ CHI PHÍ TAB =================
stats_toolbar = tk.Frame(stats_tab, bg=PALETTE["panel"])
stats_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 6), padx=6)
stats_toolbar.columnconfigure(1, weight=1)
total_cost_label_var = tk.StringVar(value="Tổng chi phí từ trước đến nay: $0.00 (0 đ)")
tk.Label(stats_toolbar, textvariable=total_cost_label_var, bg=PALETTE["panel"], fg=PALETTE["warn"], font=("Segoe UI", 12, "bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")

def refresh_cost_stats():
	if "cost_tree_table" not in globals(): return
	for row_id in cost_tree_table.get_children(): cost_tree_table.delete(row_id)
	history = load_translation_history()
	if not history: return
	stats_tree = {}
	overall_cost = 0.0
	overall_cost_vnd = 0.0
	for entry in history:
		start_at = entry.get("start_at", "")
		if not start_at or start_at == "--": continue
		try: dt = datetime.datetime.strptime(start_at, "%Y-%m-%d %H:%M:%S")
		except: continue
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
		m_node = cost_tree_table.insert("", tk.END, text=month_key, values=(
			f"${data['cost']:.4f}", f"{int(data['cost_vnd']):,} đ", f"{data['tokens']:,}", f"{data['chars']:,}"
		), tags=("month_row",), open=True)
		weeks = data["weeks"]
		for week_key in sorted(weeks.keys(), key=lambda k: weeks[k]["sort_val"], reverse=True):
			w_data = weeks[week_key]
			cost_tree_table.insert(m_node, tk.END, text=week_key, values=(
				f"${w_data['cost']:.4f}", f"{int(w_data['cost_vnd']):,} đ", f"{w_data['tokens']:,}", f"{w_data['chars']:,}"
			), tags=("week_row",))

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
cost_tree_table.heading("#0", text="Thời gian (Tháng / Tuần)")
cost_tree_table.heading("total_cost", text="Tổng USD")
cost_tree_table.heading("total_cost_vnd", text="Tổng VNĐ")
cost_tree_table.heading("total_tokens", text="Tokens")
cost_tree_table.heading("total_chars", text="Ký tự nhập")
cost_tree_table.column("#0", width=320, anchor="w")
cost_tree_table.column("total_cost", width=120, anchor="e")
cost_tree_table.column("total_cost_vnd", width=150, anchor="e")
cost_tree_table.column("total_tokens", width=150, anchor="e")
cost_tree_table.column("total_chars", width=150, anchor="e")
cost_tree_table.tag_configure("month_row", background=PALETTE["accent"], foreground="#000000", font=("Segoe UI", 10, "bold"))
cost_tree_table.tag_configure("week_row", background=PALETTE["input_bg"], foreground=PALETTE["text"])

# ================= CHUNK PREVIEW TAB =================
preview_tab.columnconfigure(0, weight=1)
preview_tab.columnconfigure(1, weight=3)
preview_tab.rowconfigure(1, weight=1)
preview_toolbar = tk.Frame(preview_tab, bg=PALETTE["panel"])
preview_toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6), padx=6)
preview_info_var = tk.StringVar(value="Tổng số chunk: 0")
previewed_chunks = []
translated_preview_chunks = {}

def load_and_preview_chunks():
	global previewed_chunks, translated_preview_chunks
	translated_preview_chunks = {}
	try: input_file = input_path.get()
	except:
		messagebox.showerror("Lỗi", "Giao diện chưa sẵn sàng!")
		return
	if not input_file or not os.path.exists(input_file):
		messagebox.showerror("Lỗi", "Vui lòng chọn file nguồn hợp lệ ở tab 'Dịch truyện' trước!")
		return
	try: size_limit = int(chunk_size_var.get())
	except: size_limit = CHUNK_SIZE
	try:
		text = read_file_content_safely(input_file)
		previewed_chunks = split_text(text, size_limit, split_mode=chunk_split_mode_var.get())
		chunk_listbox.delete(0, tk.END)
		for i, chunk in enumerate(previewed_chunks):
			lines = chunk.strip().split("\n")
			first_line = lines[0][:35] + "..." if len(lines[0]) > 35 else lines[0]
			chunk_listbox.insert(tk.END, f"Chunk {i+1} ({len(chunk)} ký tự) - {first_line}")
		cp_file = get_checkpoint_path(input_file)
		with checkpoint_lock:
			if os.path.exists(cp_file):
				try:
					with open(cp_file, "r", encoding="utf-8") as f:
						saved_data = json.load(f)
						for k, v in saved_data.items(): translated_preview_chunks[int(k)] = v
				except: pass
		preview_info_var.set(f"Tổng số chunk: {len(previewed_chunks)}")
		chunk_content_text.config(state="normal")
		chunk_content_text.delete("1.0", tk.END)
		chunk_content_text.config(state="disabled")
		chunk_translated_text.config(state="normal")
		chunk_translated_text.delete("1.0", tk.END)
		chunk_translated_text.config(state="disabled")
	except Exception as e:
		messagebox.showerror("Lỗi", f"Không thể chia chunk: {str(e)}")

tk.Button(preview_toolbar, text="🔄 Tải & Chia Chunk", font=("Segoe UI", 9, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=10, pady=5, command=load_and_preview_chunks).pack(side="left", padx=5, pady=5)
regenerate_chunk_btn = tk.Button(preview_toolbar, text="✨ Dịch lại đoạn này", font=("Segoe UI", 9, "bold"), bg=PALETTE["warn"], fg="#0b0f19", bd=0, padx=10, pady=5, command=lambda: open_regenerate_dialog(), state="disabled")
regenerate_chunk_btn.pack(side="left", padx=5, pady=5)
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
chunk_content_paned = tk.PanedWindow(chunk_content_frame, orient=tk.VERTICAL, bg=PALETTE["panel"], bd=0, sashwidth=4)
chunk_content_paned.pack(fill="both", expand=True, padx=5, pady=5)
chunk_content_text = scrolledtext.ScrolledText(chunk_content_paned, bg=PALETTE["input_bg"], fg=PALETTE["text"], wrap="word", font=("Consolas", 10), relief="flat", highlightthickness=1, highlightbackground=PALETTE["border"])
chunk_content_text.config(state="disabled")
chunk_content_paned.add(chunk_content_text, minsize=100)
chunk_translated_text = scrolledtext.ScrolledText(chunk_content_paned, bg=PALETTE["input_bg"], fg=PALETTE.get("text_accent", PALETTE["text"]), wrap="word", font=("Consolas", 10), relief="flat", highlightthickness=1, highlightbackground=PALETTE["border"])
chunk_translated_text.config(state="disabled")
chunk_content_paned.add(chunk_translated_text, minsize=100)

def on_chunk_select(event):
	selection = chunk_listbox.curselection()
	if selection:
		index = selection[0]
		chunk_content_text.config(state="normal")
		chunk_content_text.delete("1.0", tk.END)
		chunk_content_text.insert(tk.END, "--- BẢN GỐC ---\n" + previewed_chunks[index])
		chunk_content_text.config(state="disabled")
		chunk_translated_text.config(state="normal")
		chunk_translated_text.delete("1.0", tk.END)
		if index in translated_preview_chunks:
			chunk_translated_text.insert(tk.END, "--- BẢN DỊCH ---\n" + translated_preview_chunks[index])
		else:
			chunk_translated_text.insert(tk.END, "--- CHƯA DỊCH ---")
		chunk_translated_text.config(state="disabled")
		regenerate_chunk_btn.config(state="normal")

chunk_listbox.bind('<<ListboxSelect>>', on_chunk_select)

def open_regenerate_dialog():
	selection = chunk_listbox.curselection()
	if not selection: return
	index = selection[0]
	chunk_text = previewed_chunks[index]
	dialog = tk.Toplevel(root)
	dialog.title(f"Dịch lại cục bộ - Chunk {index+1}")
	dialog.geometry("800x650")
	dialog.configure(bg=PALETTE["bg"])
	dialog.transient(root)
	dialog.grab_set()
	tk.Label(dialog, text="Bản gốc:", bg=PALETTE["bg"], fg=PALETTE["text"]).pack(anchor="w", padx=10, pady=(10, 0))
	orig_text = scrolledtext.ScrolledText(dialog, height=8, bg=PALETTE["input_bg"], fg=PALETTE["text"], wrap="word")
	orig_text.pack(fill="x", padx=10, pady=5)
	orig_text.insert(tk.END, chunk_text)
	orig_text.config(state="disabled")
	tk.Label(dialog, text="Tùy chỉnh Prompt (Ví dụ: Đổi xưng hô thành huynh-đệ):", bg=PALETTE["bg"], fg=PALETTE["text"]).pack(anchor="w", padx=10, pady=(10, 0))
	prompt_entry = tk.Entry(dialog, bg=PALETTE["input_bg"], fg=PALETTE["text"], font=("Segoe UI", 10))
	prompt_entry.pack(fill="x", padx=10, pady=5)
	tk.Label(dialog, text="Bản dịch hiện tại (Có thể sửa tay rồi lưu luôn):", bg=PALETTE["bg"], fg=PALETTE["text"]).pack(anchor="w", padx=10, pady=(10, 0))
	trans_text = scrolledtext.ScrolledText(dialog, height=10, bg=PALETTE["input_bg"], fg=PALETTE["text"], wrap="word")
	trans_text.pack(fill="both", expand=True, padx=10, pady=5)
	if index in translated_preview_chunks:
		trans_text.insert(tk.END, translated_preview_chunks[index])
	def do_regenerate():
		custom_prompt = prompt_entry.get().strip()
		base_prompt = prompt_text.get("1.0", tk.END).strip()
		glossary_raw = glossary_text.get("1.0", tk.END).strip()
		glossary_entries = parse_glossary(glossary_raw)
		full_prompt = build_prompt_with_glossary(base_prompt, glossary_entries)
		if custom_prompt:
			full_prompt = f"Yêu cầu đặc biệt cho đoạn này: {custom_prompt}\n\n{full_prompt}"
		model = model_var.get()
		temperature = float(temp_var.get())
		max_tokens = int(max_output_tokens_var.get())
		trans_text.config(state="disabled")
		trans_text.delete("1.0", tk.END)
		trans_text.insert(tk.END, "Đang dịch lại bằng AI...")
		def run():
			try:
				_, result = translate_chunk(model, full_prompt, chunk_text, index, get_checkpoint_path(input_path.get()), temperature, max_tokens)
				dialog.after(0, lambda: [
					trans_text.config(state="normal"),
					trans_text.delete("1.0", tk.END),
					trans_text.insert(tk.END, result if result else "LỖI DỊCH THUẬT (Kết quả rỗng)"),
				])
			except Exception as e:
				dialog.after(0, lambda: [
					trans_text.config(state="normal"),
					trans_text.delete("1.0", tk.END),
					trans_text.insert(tk.END, f"LỖI: {e}"),
				])
		threading.Thread(target=run, daemon=True).start()
	def save_and_close():
		new_trans = trans_text.get("1.0", tk.END).strip()
		if not new_trans:
			messagebox.showwarning("Cảnh báo", "Bản dịch đang trống!")
			return
		translated_preview_chunks[index] = new_trans
		cp_file = get_checkpoint_path(input_path.get())
		with checkpoint_lock:
			saved_data = {}
			if os.path.exists(cp_file):
				try:
					with open(cp_file, "r", encoding="utf-8") as f:
						saved_data = json.load(f)
				except: pass
			saved_data[str(index)] = new_trans
			with open(cp_file, "w", encoding="utf-8") as f:
				json.dump(saved_data, f, ensure_ascii=False, indent=2)
		on_chunk_select(None)
		dialog.destroy()
		messagebox.showinfo("Thành công", f"Đã cập nhật bản dịch mới cho Chunk {index+1} vào checkpoint.")
	btn_frame = tk.Frame(dialog, bg=PALETTE["bg"])
	btn_frame.pack(fill="x", padx=10, pady=10)
	tk.Button(btn_frame, text="✨ Dịch lại bằng AI", bg=PALETTE["accent"], fg="#0b0f19", font=("Segoe UI", 10, "bold"), command=do_regenerate).pack(side="left", padx=5)
	tk.Button(btn_frame, text="💾 Lưu và Đóng", bg=PALETTE["ok"], fg="#0b0f19", font=("Segoe UI", 10, "bold"), command=save_and_close).pack(side="right", padx=5)

# ================= QUICK TRANSLATE TAB (CLIPBOARD) =================
quick_status_var = tk.StringVar(value="Sẵn sàng paste text từ clipboard")
quick_model_var = tk.StringVar(value=MODELS[0])
quick_input_toolbar = tk.Frame(quick_translate_tab, bg=PALETTE["panel"])
quick_input_toolbar.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
quick_input_toolbar.columnconfigure(1, weight=1)
tk.Label(quick_input_toolbar, text="📋 Paste từ Clipboard:", bg=PALETTE["panel"], fg=PALETTE["text"], font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=8, pady=8)
quick_model_frame = tk.Frame(quick_input_toolbar, bg=PALETTE["panel"])
quick_model_frame.grid(row=0, column=1, sticky="w", padx=(15, 8))
tk.Label(quick_model_frame, text="Model dịch nhanh:", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
quick_model_cb = ttk.Combobox(quick_model_frame, values=MODELS, textvariable=quick_model_var, state="readonly", width=30)
quick_model_cb.pack(side="left")
tk.Button(quick_input_toolbar, text="📥 Paste from Clipboard", font=("Segoe UI", 9, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=12, pady=6, command=paste_from_clipboard).grid(row=0, column=2, padx=(8, 4), pady=8)
tk.Button(quick_input_toolbar, text="🗑️ Clear", font=("Segoe UI", 9, "bold"), bg=PALETTE["warn"], fg="#0b0f19", bd=0, padx=12, pady=6, command=lambda: (quick_input_text.config(state="normal"), quick_input_text.delete("1.0", tk.END), quick_input_text.config(state="normal"))).grid(row=0, column=3, padx=4, pady=8)

quick_input_frame = tk.Frame(quick_translate_tab, bg=PALETTE["panel"])
quick_input_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
tk.Label(quick_input_frame, text="📝 Nội dung gốc (Trung):", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=8, pady=(8, 4))
quick_input_text = scrolledtext.ScrolledText(quick_input_frame, height=10, bg=PALETTE["input_bg"], fg=PALETTE["text"], wrap="word", relief="flat", highlightthickness=1, highlightbackground=PALETTE["border"])
quick_input_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

quick_output_toolbar = tk.Frame(quick_translate_tab, bg=PALETTE["panel"])
quick_output_toolbar.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 6))
quick_output_toolbar.columnconfigure(0, weight=1)
tk.Label(quick_output_toolbar, textvariable=quick_status_var, bg=PALETTE["panel"], fg=PALETTE["text"], font=("Segoe UI", 9, "italic")).grid(row=0, column=0, sticky="w", padx=8, pady=8)
translate_quick_btn = tk.Button(quick_output_toolbar, text="🚀 DỊCH NGAY", font=("Segoe UI", 9, "bold"), bg=PALETTE["accent"], fg="#0b0f19", bd=0, padx=12, pady=6, command=translate_clipboard_text)
translate_quick_btn.grid(row=0, column=1, padx=(8, 4), pady=8)
tk.Button(quick_output_toolbar, text="📋 Copy to Clipboard", font=("Segoe UI", 9, "bold"), bg=PALETTE["ok"], fg="#0b0f19", bd=0, padx=12, pady=6, command=copy_to_clipboard).grid(row=0, column=2, padx=4, pady=8)

quick_output_frame = tk.Frame(quick_translate_tab, bg=PALETTE["panel"])
quick_output_frame.grid(row=3, column=0, sticky="nsew", padx=6, pady=(0, 6))
tk.Label(quick_output_frame, text="✨ Kết quả dịch (Việt):", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=8, pady=(8, 4))
quick_output_text = scrolledtext.ScrolledText(quick_output_frame, height=10, bg=PALETTE["input_bg"], fg=PALETTE["text"], wrap="word", relief="flat", highlightthickness=1, highlightbackground=PALETTE["border"])
quick_output_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
quick_output_text.config(state="disabled")

# ================= DIFF VIEWER TAB =================
diff_toolbar = tk.Frame(diff_tab, bg=PALETTE["panel"])
diff_toolbar.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
diff_toolbar.columnconfigure(1, weight=1)
tk.Label(diff_toolbar, text="So sánh file gốc vs dịch side-by-side:", bg=PALETTE["panel"], fg=PALETTE["text"], font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=8, pady=8)

def open_diff_viewer():
	input_file = input_path.get()
	output_file = output_path.get()
	if not input_file or not os.path.exists(input_file):
		messagebox.showerror("Lỗi", "Chọn file input hợp lệ trước")
		return
	if not output_file or not os.path.exists(output_file):
		messagebox.showerror("Lỗi", "Chọn file output hợp lệ trước")
		return
	try:
		original = read_file_content_safely(input_file)
		translated = read_file_content_safely(output_file)
		show_diff_window(original, translated, input_file, output_file)
	except Exception as e:
		messagebox.showerror("Lỗi", f"Không thể mở file: {e}")

tk.Button(diff_toolbar, text="📂 Chọn file gốc", font=("Segoe UI", 9, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=12, pady=6, command=lambda: input_path.set(filedialog.askopenfilename(filetypes=[("Text files", "*.txt")]))).grid(row=0, column=2, padx=(8, 4), pady=8)
tk.Button(diff_toolbar, text="📂 Chọn file dịch", font=("Segoe UI", 9, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=12, pady=6, command=lambda: output_path.set(filedialog.askopenfilename(filetypes=[("Text files", "*.txt")]))).grid(row=0, column=3, padx=(0, 4), pady=8)
tk.Button(diff_toolbar, text="🔄 Mở Diff Viewer", font=("Segoe UI", 10, "bold"), bg=PALETTE["accent"], fg="#0b0f19", bd=0, padx=15, pady=8, command=open_diff_viewer).grid(row=0, column=4, padx=(0, 8), pady=8)

diff_info_frame = tk.Frame(diff_tab, bg=PALETTE["panel"])
diff_info_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
diff_info_frame.columnconfigure(0, weight=1)
diff_info_frame.rowconfigure(0, weight=1)
diff_info_text = scrolledtext.ScrolledText(diff_info_frame, height=30, bg=PALETTE["input_bg"], fg=PALETTE["text"], wrap="word", relief="flat", highlightthickness=1, highlightbackground=PALETTE["border"])
diff_info_text.pack(fill="both", expand=True, padx=8, pady=8)
diff_info_text.insert(tk.END, 
	"🔄 DIFF VIEWER - SO SÁNH GỐC VÀ DỊCH\n\n"
	"Tính năng này cho phép bạn xem side-by-side (cạnh nhau) bản gốc và bản dịch.\n\n"
	"Cách dùng:\n"
	"1. Chọn file gốc (input) bên trên\n"
	"2. Chọn file dịch (output) bên trên\n"
	"3. Nhấn 'Mở Diff Viewer'\n"
	"4. Một cửa sổ mới sẽ hiện ra với 2 cột:\n"
	"   - Trái: Bản gốc (tiếng Trung)\n"
	"   - Phải: Bản dịch (tiếng Việt)\n\n"
	"Lợi ích:\n"
	"✅ Review nhanh chóng\n"
	"✅ So sánh độ dài output\n"
	"✅ Kiểm tra tính tự nhiên của dịch\n"
	"✅ Phát hiện lỗi dịch dễ dàng\n\n"
	"💡 Tips: Scroll cả 2 cột sẽ đồng bộ với nhau!"
)
diff_info_text.config(state="disabled")

# ================= ĐĂNG KÝ CÁC BIẾN TKINTER =================
input_path = tk.StringVar()
output_path = tk.StringVar()
model_var = tk.StringVar(value=MODELS[0])
thinking_level_var = tk.StringVar(value="medium")
model_fallback_order_var = tk.StringVar(value="|".join(MODELS))
fallback_order_hint_var = tk.StringVar(value="Thứ tự fallback hiệu lực: --")
thread_var = tk.StringVar(value="3")
chunk_size_var = tk.StringVar(value=str(CHUNK_SIZE))
chunk_split_mode_var = tk.StringVar(value="keyword")
max_output_tokens_var = tk.StringVar(value=str(MAX_OUTPUT_TOKENS))
scan_char_limit_var = tk.StringVar(value=str(DEFAULT_SCAN_CHAR_LIMIT))
temp_var = tk.StringVar(value="0.5")
drive_upload_var = tk.BooleanVar(value=False)
drive_credentials_path_var = tk.StringVar()
drive_folder_id_var = tk.StringVar()
current_key_name_var = tk.StringVar(value="Mặc định")
current_prompt_name_var = tk.StringVar(value="Mặc định")

def get_effective_fallback_order():
	model = model_var.get().strip()
	order = [m.strip() for m in model_fallback_order_var.get().split("|") if m.strip()]
	if not order: return [model] if model else []
	if model:
		order = [m for m in order if m != model]
		order = [model] + order
	return order

def update_fallback_hint(*args):
	order = get_effective_fallback_order()
	if order: fallback_order_hint_var.set(f"Thứ tự fallback hiệu lực: {' -> '.join(order)}")
	else: fallback_order_hint_var.set("Thứ tự fallback hiệu lực: --")

def update_thinking_level_state(*args):
	model_name = model_var.get()
	if is_gemini_v3_or_above(model_name): thinking_level_cb.config(state="readonly")
	else: thinking_level_cb.config(state="disabled")

entry_opts = {
	"bg": PALETTE["input_bg"],
	"fg": PALETTE["text"],
	"insertbackground": PALETTE["accent"],
	"relief": "flat",
	"highlightthickness": 1,
	"highlightbackground": PALETTE["border"],
}

# ================= CARD: API CONNECTION & PROFILE =================
card_api = build_card(translate_tab, "🔐 Kết nối API / VPS", 0, 1, colspan=2)
tk.Label(card_api, text="Dịch qua proxy AI hoặc VPS (OpenAI-compatible). URL và Key được mã hóa.", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9)).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 6))
api_key_select_frame = tk.Frame(card_api, bg=PALETTE["panel"])
api_key_select_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
tk.Label(api_key_select_frame, text="Chọn Profile:", bg=PALETTE["panel"], fg=PALETTE["text"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
api_key_cb = ttk.Combobox(api_key_select_frame, values=[], textvariable=current_key_name_var, state="readonly", width=25)
api_key_cb.pack(side="left", padx=4)
api_key_cb.bind("<<ComboboxSelected>>", on_api_key_select)
tk.Button(api_key_select_frame, text="Đổi tên", font=("Segoe UI", 8, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=8, pady=3, command=rename_api_key).pack(side="left", padx=4)
tk.Button(api_key_select_frame, text="Thêm mới", font=("Segoe UI", 8, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=8, pady=3, command=add_new_api_key).pack(side="left", padx=4)
tk.Button(api_key_select_frame, text="Xóa", font=("Segoe UI", 8, "bold"), bg=PALETTE["warn"], fg="#0b0f19", bd=0, padx=8, pady=3, command=delete_api_key).pack(side="left", padx=4)

url_label_frame = tk.Frame(card_api, bg=PALETTE["panel"])
url_label_frame.grid(row=3, column=0, sticky="ew", pady=(0, 4))
tk.Label(url_label_frame, text="Base URL / IP VPS:", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).pack(side="left")
vps_ip_entry = tk.Entry(card_api, width=70, **entry_opts)
vps_ip_entry.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 8))

key_label_frame = tk.Frame(card_api, bg=PALETTE["panel"])
key_label_frame.grid(row=5, column=0, sticky="ew", pady=(0, 4))
tk.Label(key_label_frame, text="API Key / Token:", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).pack(side="left")
api_key_frame = tk.Frame(card_api, bg=PALETTE["panel"])
api_key_frame.grid(row=6, column=0, columnspan=2, sticky="ew")
api_key_frame.columnconfigure(0, weight=1)
api_key_entry = tk.Entry(api_key_frame, show="*", width=60, **entry_opts)
api_key_entry.grid(row=0, column=0, sticky="ew")

def toggle_api_key_visibility():
	if api_key_entry.cget('show') == '*':
		api_key_entry.config(show='')
		btn_toggle_api.config(text='🙈 Ẩn')
	else:
		api_key_entry.config(show='*')
		btn_toggle_api.config(text='Hiện')

btn_toggle_api = tk.Button(api_key_frame, text="Hiện", font=("Segoe UI", 9, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=10, pady=2, command=toggle_api_key_visibility)
btn_toggle_api.grid(row=0, column=1, padx=(6, 0))

# ================= CARD: FILES OPTION =================
card_files = build_card(translate_tab, "📂 Chọn file nguồn / đích", 0, 2)
tk.Label(card_files, text="File truyện đầu vào (.txt)", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w")
frame_input = tk.Frame(card_files, bg=PALETTE["panel"])
frame_input.grid(row=2, column=0, sticky="ew", pady=(2, 8))
frame_input.columnconfigure(0, weight=1)
tk.Entry(frame_input, textvariable=input_path, **entry_opts).grid(row=0, column=0, sticky="ew")
tk.Button(frame_input, text="Chọn file", bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=10, pady=6, command=lambda: input_path.set(filedialog.askopenfilename(filetypes=[("Text files", "*.txt")]))).grid(row=0, column=1, padx=(8, 0))
tk.Label(card_files, text="Output tự động lưu cạnh file input.", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9)).grid(row=3, column=0, sticky="w", pady=(6, 0))
tk.Label(card_files, text="Google Drive (tùy chọn)", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=4, column=0, sticky="w", pady=(10, 2))
tk.Checkbutton(card_files, text="Tự động upload lên Google Drive sau khi dịch xong", variable=drive_upload_var, bg=PALETTE["panel"], fg=PALETTE["text"], selectcolor=PALETTE["panel"], activebackground=PALETTE["panel"], activeforeground=PALETTE["text"]).grid(row=5, column=0, sticky="w")
tk.Label(card_files, text="Credentials OAuth (.json)", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9)).grid(row=6, column=0, sticky="w", pady=(6, 2))
drive_cred_frame = tk.Frame(card_files, bg=PALETTE["panel"])
drive_cred_frame.grid(row=7, column=0, sticky="ew", pady=(0, 6))
drive_cred_frame.columnconfigure(0, weight=1)
tk.Entry(drive_cred_frame, textvariable=drive_credentials_path_var, **entry_opts).grid(row=0, column=0, sticky="ew")
tk.Button(drive_cred_frame, text="Chọn file", bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=10, pady=6, command=lambda: drive_credentials_path_var.set(filedialog.askopenfilename(filetypes=[("Google OAuth", "*.json")]))).grid(row=0, column=1, padx=(8, 0))
tk.Label(card_files, text="Folder ID (tùy chọn)", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9)).grid(row=8, column=0, sticky="w", pady=(4, 2))
tk.Entry(card_files, textvariable=drive_folder_id_var, **entry_opts).grid(row=9, column=0, sticky="ew")

# ================= CARD: TRANSLATION CONFIGS =================
card_config = build_card(translate_tab, "⚙️ Cấu hình dịch", 1, 2)
tk.Label(card_config, text="Model", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w")
model_frame = tk.Frame(card_config, bg=PALETTE["panel"])
model_frame.grid(row=2, column=0, sticky="ew", pady=(2, 8))
model_frame.columnconfigure(0, weight=1)
model_cb = ttk.Combobox(model_frame, values=MODELS, textvariable=model_var, state="readonly")
model_cb.grid(row=0, column=0, sticky="ew", padx=(0, 6))
model_cb.bind("<<ComboboxSelected>>", lambda e: [update_fallback_hint(), update_thinking_level_state()])
model_var.trace_add("write", lambda *args: [update_fallback_hint(), update_thinking_level_state()])
model_fallback_order_var.trace_add("write", update_fallback_hint)

tk.Button(model_frame, text="⚙️ Model Fallback", font=("Segoe UI", 8, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=8, pady=6, command=lambda: open_model_fallback_dialog()).grid(row=0, column=1, padx=2, sticky="ew")
tk.Button(model_frame, text="🔄 Tải Model", font=("Segoe UI", 8, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=8, pady=6, command=fetch_models).grid(row=0, column=2, padx=2, sticky="ew")
tk.Label(card_config, textvariable=fallback_order_hint_var, bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 8, "italic")).grid(row=3, column=0, sticky="w", pady=(0, 6))

tk.Label(card_config, text="Thinking Level (chỉ áp dụng với Gemini 3+)", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=4, column=0, sticky="w")
thinking_level_cb = ttk.Combobox(card_config, values=["minimal", "low", "medium", "high"], textvariable=thinking_level_var, state="readonly")
thinking_level_cb.grid(row=5, column=0, sticky="ew", pady=(2, 8))

perf_frame = tk.Frame(card_config, bg=PALETTE["panel"])
perf_frame.grid(row=6, column=0, sticky="ew", pady=(2, 8))
for col in range(3): perf_frame.columnconfigure(col, weight=1)
tk.Label(perf_frame, text="Số luồng", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
thread_box = tk.Entry(perf_frame, textvariable=thread_var, width=8, **entry_opts)
thread_box.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(2, 0))
tk.Label(perf_frame, text="Chunk size", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w")
chunk_size_box = tk.Entry(perf_frame, textvariable=chunk_size_var, width=10, **entry_opts)
chunk_size_box.grid(row=1, column=1, sticky="ew", padx=3, pady=(2, 0))
tk.Label(perf_frame, text="Max output tokens", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w")
max_output_tokens_box = tk.Entry(perf_frame, textvariable=max_output_tokens_var, width=12, **entry_opts)
max_output_tokens_box.grid(row=1, column=2, sticky="ew", padx=(6, 0), pady=(2, 0))

tk.Label(card_config, text="Chia chunk theo", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=7, column=0, sticky="w")
split_mode_frame = tk.Frame(card_config, bg=PALETTE["panel"])
split_mode_frame.grid(row=8, column=0, sticky="w", pady=(2, 8))
tk.Radiobutton(split_mode_frame, text="Dòng === Thứ/Chương ===", variable=chunk_split_mode_var, value="equals", bg=PALETTE["panel"], fg=PALETTE["text"], selectcolor=PALETTE["panel"], activebackground=PALETTE["panel"], activeforeground=PALETTE["text"]).pack(side="left", padx=(0, 12))
tk.Radiobutton(split_mode_frame, text="Từ khóa Thứ/Chương/Chap", variable=chunk_split_mode_var, value="keyword", bg=PALETTE["panel"], fg=PALETTE["text"], selectcolor=PALETTE["panel"], activebackground=PALETTE["panel"], activeforeground=PALETTE["text"]).pack(side="left")

tk.Label(card_config, text="Nhiệt độ (0-2)", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).grid(row=9, column=0, sticky="w")
temp_scale = ttk.Scale(card_config, from_=0.0, to=2.0, variable=temp_var, orient="horizontal", length=200, style="Accent.Horizontal.TScale")
temp_scale.grid(row=10, column=0, sticky="ew")
temp_label = tk.Label(card_config, textvariable=temp_var, bg=PALETTE["panel"], fg=PALETTE["accent"], font=("Segoe UI", 10, "bold"))
temp_label.grid(row=10, column=1, padx=(8, 0))
def update_temp_label(event=None): temp_var.set(f"{float(temp_var.get()):.2f}")
temp_scale.bind("<Motion>", update_temp_label)
temp_scale.bind("<ButtonRelease-1>", update_temp_label)

def open_model_fallback_dialog():
	dialog = tk.Toplevel(root)
	dialog.title("Cấu hình Model Fallback")
	dialog.geometry("400x350")
	dialog.resizable(False, False)
	dialog.configure(bg=PALETTE["bg"])
	tk.Label(dialog, text="Sắp xếp thứ tự model khi vượt quota:", bg=PALETTE["bg"], fg=PALETTE["text"], font=("Segoe UI", 10)).pack(padx=10, pady=10)
	frame = tk.Frame(dialog, bg=PALETTE["panel"], bd=1, relief="solid")
	frame.pack(padx=10, pady=(0, 10), fill="both", expand=True)
	current_order = [m.strip() for m in model_fallback_order_var.get().split("|") if m.strip()]
	if not current_order: current_order = MODELS
	listbox = tk.Listbox(frame, bg=PALETTE["input_bg"], fg=PALETTE["text"], selectbackground=PALETTE["accent_alt"], font=("Segoe UI", 10), activestyle="none", bd=0, highlightthickness=0)
	for model in current_order: listbox.insert(tk.END, model)
	listbox.pack(fill="both", expand=True, padx=5, pady=5)
	btn_frame = tk.Frame(dialog, bg=PALETTE["bg"])
	btn_frame.pack(padx=10, pady=(0, 10), fill="x")
	def move_up():
		sel = listbox.curselection()
		if sel and sel[0] > 0:
			idx = sel[0]
			items = list(listbox.get(0, tk.END))
			items[idx], items[idx-1] = items[idx-1], items[idx]
			listbox.delete(0, tk.END)
			listbox.insert(0, *items)
			listbox.selection_set(idx-1)
	def move_down():
		sel = listbox.curselection()
		if sel and sel[0] < listbox.size() - 1:
			idx = sel[0]
			items = list(listbox.get(0, tk.END))
			items[idx], items[idx+1] = items[idx+1], items[idx]
			listbox.delete(0, tk.END)
			listbox.insert(0, *items)
			listbox.selection_set(idx+1)
	def save_order():
		items = list(listbox.get(0, tk.END))
		model_fallback_order_var.set("|".join(items))
		add_log(f"Fallback order: {' -> '.join(items)}")
		update_fallback_hint()
		dialog.destroy()
	tk.Button(btn_frame, text="Up", bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=10, pady=6, command=move_up).pack(side="left", padx=2)
	tk.Button(btn_frame, text="Down", bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=10, pady=6, command=move_down).pack(side="left", padx=2)
	tk.Button(btn_frame, text="Save", bg=PALETTE["ok"], fg="#0b0f19", bd=0, padx=10, pady=6, command=save_order).pack(side="right", padx=2)
	tk.Button(btn_frame, text="Cancel", bg=PALETTE["warn"], fg="#0b0f19", bd=0, padx=10, pady=6, command=dialog.destroy).pack(side="right", padx=2)
	dialog.transient(root)
	dialog.grab_set()

# ================= CARD: TRANSLATOR PROMPTS =================
card_prompt = build_card(translate_tab, "📝 Prompt dịch giả & Glossary", 0, 3, colspan=2)
glossary_header_frame = tk.Frame(card_prompt, bg=PALETTE["panel"])
glossary_header_frame.grid(row=1, column=0, sticky="ew", pady=(0, 4))
glossary_header_frame.columnconfigure(0, weight=1)
tk.Label(glossary_header_frame, text="Glossary/Từ điển thuật ngữ (mỗi dòng: nguồn => đích)", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 9, "bold")).pack(side="left")
scan_limit_frame = tk.Frame(glossary_header_frame, bg=PALETTE["panel"])
scan_limit_frame.pack(side="right")
tk.Label(scan_limit_frame, text="Giới hạn quét:", bg=PALETTE["panel"], fg=PALETTE["text_muted"], font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 4))
scan_limit_entry = tk.Entry(scan_limit_frame, textvariable=scan_char_limit_var, width=8, **entry_opts)
scan_limit_entry.pack(side="left", padx=(0, 8))
tk.Button(scan_limit_frame, text="🔍 Quét thuật ngữ", font=("Segoe UI", 8, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=8, pady=2, cursor="hand2", command=scan_story).pack(side="right")

glossary_text = tk.Text(card_prompt, height=4, bg=PALETTE["input_bg"], fg=PALETTE["text"], insertbackground=PALETTE["accent"], wrap="word", relief="flat", highlightthickness=1, highlightbackground=PALETTE["border"])
glossary_text.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
glossary_text.insert(tk.END, DEFAULT_GLOSSARY)

prompt_header_frame = tk.Frame(card_prompt, bg=PALETTE["panel"])
prompt_header_frame.grid(row=3, column=0, sticky="ew", pady=(0, 4))
tk.Label(prompt_header_frame, text="Chọn Prompt:", bg=PALETTE["panel"], fg=PALETTE["text"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
prompt_cb = ttk.Combobox(prompt_header_frame, values=[], textvariable=current_prompt_name_var, state="readonly", width=25)
prompt_cb.pack(side="left", padx=4)
prompt_cb.bind("<<ComboboxSelected>>", on_prompt_select)
tk.Button(prompt_header_frame, text="Đổi tên", font=("Segoe UI", 8, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=8, pady=3, command=rename_prompt).pack(side="left", padx=4)
tk.Button(prompt_header_frame, text="Thêm mới", font=("Segoe UI", 8, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=8, pady=3, command=add_new_prompt).pack(side="left", padx=4)
tk.Button(prompt_header_frame, text="Xóa", font=("Segoe UI", 8, "bold"), bg=PALETTE["warn"], fg="#0b0f19", bd=0, padx=8, pady=3, command=delete_prompt).pack(side="left", padx=4)

prompt_text = tk.Text(card_prompt, height=5, bg=PALETTE["input_bg"], fg=PALETTE["text"], insertbackground=PALETTE["accent"], wrap="word", relief="flat", highlightthickness=1, highlightbackground=PALETTE["border"])
prompt_text.grid(row=4, column=0, sticky="nsew", pady=(0, 6))
prompt_text.insert(tk.END, DEFAULT_PROMPT)
card_prompt.rowconfigure(2, weight=1)
card_prompt.rowconfigure(4, weight=1)

# ================= CARD: STATISTICS PANEL =================
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
stats_total_cost_vnd_var = tk.StringVar(value="💸 Tổng tiền Việt: 0 đ")
for i, var in enumerate([stats_time_var, stats_eta_var, stats_speed_var, stats_chars_var, stats_input_tokens_var, stats_output_tokens_var, stats_input_cost_var, stats_output_cost_var, stats_total_cost_var, stats_total_cost_vnd_var]):
	tk.Label(card_stats, textvariable=var, bg=PALETTE["panel"], fg=PALETTE["text"], font=("Consolas", 10)).grid(row=1 + i // 2, column=i % 2, sticky="w", padx=8, pady=4)

# ================= CARD: TRANSLATE CONTROLS =================
card_progress = build_card(translate_tab, "🚀 Điều khiển & tiến độ", 1, 4)
progress_bar = ttk.Progressbar(card_progress, style="Accent.Horizontal.TProgressbar", length=100, mode="determinate")
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
for c in range(3): card_progress.columnconfigure(c, weight=1)

# ================= CARD: LOG SYSTEM =================
card_log = build_card(translate_tab, "📋 Nhật ký hoạt động", 0, 5, colspan=2)
log_box = scrolledtext.ScrolledText(card_log, height=8, state="disabled", bg=PALETTE["input_bg"], fg=PALETTE["text"], insertbackground=PALETTE["accent"], relief="flat", highlightthickness=1, highlightbackground=PALETTE["border"])
log_box.grid(row=1, column=0, sticky="nsew")
card_log.rowconfigure(1, weight=1)

# ================= CARD: HISTORY SYSTEM =================
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
history_columns = ("start_at", "status", "model", "progress", "chars", "tokens", "cost", "cost_vnd", "duration", "meta", "files", "error")
history_table = ttk.Treeview(history_table_frame, columns=history_columns, show="headings", style="History.Treeview")
history_table.grid(row=0, column=0, sticky="nsew")
history_table.bind("<ButtonRelease-1>", on_history_row_click)
history_scroll_y = ttk.Scrollbar(history_table_frame, orient="vertical", command=history_table.yview)
history_scroll_y.grid(row=0, column=1, sticky="ns")
history_scroll_x = ttk.Scrollbar(history_table_frame, orient="horizontal", command=history_table.xview)
history_scroll_x.grid(row=1, column=0, sticky="ew")
history_table.configure(yscrollcommand=history_scroll_y.set, xscrollcommand=history_scroll_x.set)

cols_info = [
	("start_at", "Bắt đầu", 145, "w"),
	("status", "Trạng thái", 95, "center"),
	("model", "Model", 180, "w"),
	("progress", "Tiến độ", 90, "center"),
	("chars", "Ký tự", 160, "e"),
	("tokens", "Token", 190, "e"),
	("cost", "Tổng tiền", 100, "e"),
	("cost_vnd", "Tổng tiền Việt", 140, "e"),
	("duration", "Thời gian", 90, "center"),
	("meta", "Thiết lập", 130, "center"),
	("files", "File", 340, "w"),
	("error", "Lỗi", 220, "w")
]
for col_id, col_name, w, anchor in cols_info:
	history_table.heading(col_id, text=col_name)
	history_table.column(col_id, width=w, anchor=anchor)

history_table.tag_configure("odd", background=PALETTE["input_bg"])
history_table.tag_configure("even", background=PALETTE["panel"])
history_table.tag_configure("status_completed", foreground="#000000")
history_table.tag_configure("status_stopped", foreground="#000000")
history_table.tag_configure("status_error", foreground="#000000")
card_history.rowconfigure(2, weight=1)

# ================= CARD: REQ STATS SYSTEM =================
card_requests = build_card(requests_tab, "📈 Request / phút", 0, 0, colspan=1)
requests_toolbar = tk.Frame(card_requests, bg=PALETTE["panel"])
requests_toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 6))
requests_toolbar.columnconfigure(0, weight=1)
requests_hint_var = tk.StringVar(value="Hiển thị danh sách bản dịch (nhấn để xem request/phút).")
requests_hint_label = tk.Label(requests_toolbar, textvariable=requests_hint_var, bg=PALETTE["panel"], fg="#000000", font=("Segoe UI", 9))
requests_hint_label.grid(row=0, column=0, sticky="w")
tk.Button(requests_toolbar, text="🔄 Làm mới", font=("Segoe UI", 9, "bold"), bg=PALETTE["accent_alt"], fg="#0b0f19", bd=0, padx=10, pady=5, command=refresh_request_stats_display).grid(row=0, column=1, padx=(8, 0))

requests_table_frame = tk.Frame(card_requests, bg=PALETTE["panel"])
requests_table_frame.grid(row=2, column=0, sticky="nsew")
requests_table_frame.columnconfigure(0, weight=1)
requests_table_frame.rowconfigure(0, weight=1)
requests_columns = ("start_at", "status", "model", "total_requests", "peak_rpm", "duration", "files")
requests_table = ttk.Treeview(requests_table_frame, columns=requests_columns, show="headings", style="History.Treeview")
requests_table.grid(row=0, column=0, sticky="nsew")
requests_table.bind("<ButtonRelease-1>", on_request_row_click)
requests_scroll_y = ttk.Scrollbar(requests_table_frame, orient="vertical", command=requests_table.yview)
requests_scroll_y.grid(row=0, column=1, sticky="ns")
requests_scroll_x = ttk.Scrollbar(requests_table_frame, orient="horizontal", command=requests_table.xview)
requests_scroll_x.grid(row=1, column=0, sticky="ew")
requests_table.configure(yscrollcommand=requests_scroll_y.set, xscrollcommand=requests_scroll_x.set)

req_cols_info = [
	("start_at", "Bắt đầu", 145, "w"),
	("status", "Trạng thái", 95, "center"),
	("model", "Model", 180, "w"),
	("total_requests", "Tổng request", 120, "e"),
	("peak_rpm", "Peak/phút", 110, "e"),
	("duration", "Thời gian", 90, "center"),
	("files", "File", 360, "w")
]
for col_id, col_name, w, anchor in req_cols_info:
	requests_table.heading(col_id, text=col_name)
	requests_table.column(col_id, width=w, anchor=anchor)

requests_table.tag_configure("odd", background=PALETTE["input_bg"])
requests_table.tag_configure("even", background=PALETTE["panel"])
requests_table.tag_configure("status_completed", foreground="#000000")
requests_table.tag_configure("status_stopped", foreground="#000000")
requests_table.tag_configure("status_error", foreground="#000000")
card_requests.rowconfigure(2, weight=1)

# ================= KÍCH HOẠT =================
for i in range(6): translate_tab.rowconfigure(i, weight=1 if i in [3, 5] else 0)

saved_settings = load_settings()
apply_settings(saved_settings)
if saved_settings.get("theme"):
	current_theme = saved_settings["theme"]
	PALETTE = THEMES[current_theme]
	theme_icon = "🌙" if current_theme == "dark" else "☀️"
	btn_theme.config(text=f"{theme_icon} {'Tối' if current_theme == 'dark' else 'Sáng'}")
	apply_theme()

root.protocol("WM_DELETE_WINDOW", on_closing)
add_log("📂 Đã tải cấu hình kết nối proxy.")
add_log("🔐 API Key và URL được lưu mã hóa, an toàn bảo mật.")
if not ensure_drive_dependencies():
	add_log("⚠️ Chưa cài Google Drive. Muốn dùng hãy chạy: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
refresh_history_display()
try: refresh_cost_stats()
except: pass
try: update_thinking_level_state()
except: pass

root.mainloop()
