import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import urllib.error
import urllib.parse
import urllib.request
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk


SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_settings.json")
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translation_history.json")

DEFAULT_MODELS = [
	"kimi",
	"moonshot-v1",
	"moonshot-v1-8k",
	"moonshot-v1-32k",
	"moonshot-v1-128k",
]

DEFAULT_PROMPT = (
	"Bạn là biên tập viên truyện chuyên nghiệp. "
	"Hãy dịch đoạn sau sang tiếng Việt tự nhiên, mượt mà, giữ đúng ý nghĩa và bối cảnh. "
	"Không thêm bình luận, chỉ trả nội dung đã dịch."
)

PALETTE = {
	"bg": "#0b1220",
	"panel": "#111827",
	"panel_alt": "#0f172a",
	"border": "#23304a",
	"text": "#e5edf9",
	"muted": "#9fb0cc",
	"accent": "#22c55e",
	"accent_alt": "#38bdf8",
	"warn": "#f97316",
	"input_bg": "#0a1020",
}


def load_json_file(file_path, default_value):
	try:
		if os.path.exists(file_path):
			with open(file_path, "r", encoding="utf-8") as f:
				return json.load(f)
	except Exception:
		return default_value
	return default_value


def save_json_file(file_path, data):
	with open(file_path, "w", encoding="utf-8") as f:
		json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_base_url(raw_input):
	value = raw_input.strip()
	if not value:
		return ""

	if not value.startswith("http://") and not value.startswith("https://"):
		value = f"http://{value}"

	parsed = urllib.parse.urlparse(value)
	netloc = parsed.netloc
	path = parsed.path.rstrip("/")

	if not netloc:
		return ""

	if ":" not in netloc:
		netloc = f"{netloc}:8000"

	scheme = parsed.scheme or "http"
	return f"{scheme}://{netloc}{path}".rstrip("/")


def split_text_into_chunks(text, chunk_size):
	paragraphs = text.split("\n\n")
	chunks = []
	current = ""

	for paragraph in paragraphs:
		piece = paragraph.strip()
		if not piece:
			continue

		candidate = piece if not current else f"{current}\n\n{piece}"
		if len(candidate) <= chunk_size:
			current = candidate
			continue

		if current:
			chunks.append(current)

		while len(piece) > chunk_size:
			chunks.append(piece[:chunk_size])
			piece = piece[chunk_size:]
		current = piece

	if current:
		chunks.append(current)

	return chunks


class KimiTranslatorApp:
	def __init__(self, root):
		self.root = root
		self.root.title("DichTruyen - Kimi Proxy (VPS + Refresh Token)")
		self.root.geometry("1120x760")
		self.root.minsize(980, 700)

		self.stop_event = threading.Event()
		self.is_running = False
		self.show_token_var = tk.BooleanVar(value=False)
		self.progress_text_var = tk.StringVar(value="0%")

		self.settings = load_json_file(
			SETTINGS_FILE,
			{
				"vps_ip": "",
				"refresh_token": "",
				"model": DEFAULT_MODELS[-1],
				"input_file": "",
				"output_file": "",
				"chunk_size": "3500",
				"threads": "4",
				"temperature": "0.6",
				"max_output_tokens": "4096",
				"prompt": DEFAULT_PROMPT,
			},
		)

		self._setup_styles()
		self._build_ui()
		self._apply_settings()

	def _setup_styles(self):
		self.root.configure(bg=PALETTE["bg"])
		style = ttk.Style(self.root)
		style.theme_use("clam")

		style.configure("App.TFrame", background=PALETTE["bg"])
		style.configure("Header.TFrame", background=PALETTE["bg"])
		style.configure("Card.TLabelframe", background=PALETTE["panel"], bordercolor=PALETTE["border"], relief="solid")
		style.configure("Card.TLabelframe.Label", background=PALETTE["panel"], foreground=PALETTE["accent_alt"], font=("Segoe UI Semibold", 10))
		style.configure("TLabel", background=PALETTE["panel"], foreground=PALETTE["text"], font=("Segoe UI", 10))
		style.configure("Title.TLabel", background=PALETTE["bg"], foreground=PALETTE["text"], font=("Segoe UI Semibold", 16))
		style.configure("SubTitle.TLabel", background=PALETTE["bg"], foreground=PALETTE["muted"], font=("Segoe UI", 10))
		style.configure("Status.TLabel", background=PALETTE["panel_alt"], foreground=PALETTE["accent"], font=("Segoe UI Semibold", 10), padding=(10, 5))
		style.configure("Muted.TLabel", background=PALETTE["panel"], foreground=PALETTE["muted"], font=("Segoe UI", 9))

		style.configure(
			"Primary.TButton",
			background=PALETTE["accent"],
			foreground="#052e16",
			font=("Segoe UI Semibold", 10),
			borderwidth=0,
			padding=(12, 8),
		)
		style.map("Primary.TButton", background=[("active", "#16a34a"), ("disabled", "#365a43")], foreground=[("disabled", "#a0b8aa")])

		style.configure(
			"Secondary.TButton",
			background="#1f2a44",
			foreground=PALETTE["text"],
			font=("Segoe UI", 10),
			borderwidth=0,
			padding=(11, 8),
		)
		style.map("Secondary.TButton", background=[("active", "#263657"), ("disabled", "#1a2336")], foreground=[("disabled", "#7e8ca6")])

		style.configure("Warn.TButton", background="#7c2d12", foreground="#ffedd5", font=("Segoe UI Semibold", 10), borderwidth=0, padding=(12, 8))
		style.map("Warn.TButton", background=[("active", "#9a3412"), ("disabled", "#4b1a0d")], foreground=[("disabled", "#e8bda8")])

		style.configure(
			"TEntry",
			fieldbackground=PALETTE["input_bg"],
			foreground=PALETTE["text"],
			insertcolor=PALETTE["text"],
			bordercolor=PALETTE["border"],
			lightcolor=PALETTE["border"],
			darkcolor=PALETTE["border"],
			padding=6,
		)
		style.configure("TCombobox", fieldbackground=PALETTE["input_bg"], foreground=PALETTE["text"], arrowcolor=PALETTE["accent_alt"], padding=4)
		style.configure("TSpinbox", fieldbackground=PALETTE["input_bg"], foreground=PALETTE["text"], arrowsize=12, padding=4)

		style.configure("Horizontal.TProgressbar", troughcolor="#0a0f1a", bordercolor=PALETTE["border"], background=PALETTE["accent_alt"], lightcolor=PALETTE["accent_alt"], darkcolor=PALETTE["accent_alt"]) 

	def _build_ui(self):
		self.root.columnconfigure(0, weight=1)
		self.root.rowconfigure(0, weight=1)

		outer = ttk.Frame(self.root, style="App.TFrame")
		outer.grid(row=0, column=0, sticky="nsew")
		outer.columnconfigure(0, weight=1)
		outer.rowconfigure(0, weight=1)

		self.main_canvas = tk.Canvas(
			outer,
			bg=PALETTE["bg"],
			highlightthickness=0,
			bd=0,
		)
		self.main_canvas.grid(row=0, column=0, sticky="nsew")

		self.main_scrollbar = ttk.Scrollbar(outer, orient="vertical", command=self.main_canvas.yview)
		self.main_scrollbar.grid(row=0, column=1, sticky="ns")
		self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)

		main = ttk.Frame(self.main_canvas, style="App.TFrame", padding=14)
		self.main_canvas_window = self.main_canvas.create_window((0, 0), window=main, anchor="nw")
		self.main_canvas.bind("<Configure>", self._on_canvas_configure)
		main.bind("<Configure>", self._on_main_frame_configure)
		self.main_canvas.bind("<MouseWheel>", self._on_mousewheel)
		self.main_canvas.bind("<Button-4>", self._on_mousewheel)
		self.main_canvas.bind("<Button-5>", self._on_mousewheel)

		main.columnconfigure(0, weight=1)
		main.rowconfigure(7, weight=1)

		header = ttk.Frame(main, style="Header.TFrame")
		header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
		header.columnconfigure(0, weight=1)

		ttk.Label(header, text="Dich Truyen AI Proxy", style="Title.TLabel").grid(row=0, column=0, sticky="w")
		ttk.Label(
			header,
			text="Nhap VPS + refresh token, chon model, va dich nhanh theo chunk da luong.",
			style="SubTitle.TLabel",
		).grid(row=1, column=0, sticky="w", pady=(2, 0))

		conn_group = ttk.LabelFrame(main, text="Ket noi VPS", padding=12, style="Card.TLabelframe")
		conn_group.grid(row=1, column=0, sticky="ew", pady=(0, 10))
		conn_group.columnconfigure(1, weight=1)

		ttk.Label(conn_group, text="IP VPS / Base URL:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
		self.vps_ip_var = tk.StringVar()
		ttk.Entry(conn_group, textvariable=self.vps_ip_var).grid(row=0, column=1, columnspan=3, sticky="ew", pady=4)

		ttk.Label(conn_group, text="Refresh Token:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
		self.refresh_token_var = tk.StringVar()
		self.refresh_entry = ttk.Entry(conn_group, textvariable=self.refresh_token_var, show="*")
		self.refresh_entry.grid(
			row=1, column=1, columnspan=2, sticky="ew", pady=4
		)
		ttk.Checkbutton(conn_group, text="Hien token", variable=self.show_token_var, command=self.toggle_token_visibility).grid(
			row=1, column=3, sticky="w", pady=4
		)

		ttk.Label(conn_group, text="Model:").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
		self.model_var = tk.StringVar(value=DEFAULT_MODELS[-1])
		self.model_combo = ttk.Combobox(conn_group, textvariable=self.model_var, values=DEFAULT_MODELS, state="readonly")
		self.model_combo.grid(row=2, column=1, sticky="ew", pady=4)
		ttk.Button(conn_group, text="Tai model", command=self.fetch_models, style="Secondary.TButton").grid(row=2, column=2, sticky="w", padx=8)
		ttk.Button(conn_group, text="Luu cau hinh", command=self.save_settings, style="Secondary.TButton").grid(row=2, column=3, sticky="w")

		ttk.Label(
			conn_group,
			text="Meo: neu chi nhap IP, app se tu dong them http:// va cong 8000.",
			style="Muted.TLabel",
		).grid(row=3, column=0, columnspan=4, sticky="w", pady=(4, 0))

		file_group = ttk.LabelFrame(main, text="File truyen", padding=12, style="Card.TLabelframe")
		file_group.grid(row=2, column=0, sticky="ew", pady=(0, 10))
		file_group.columnconfigure(1, weight=1)

		self.input_file_var = tk.StringVar()
		self.output_file_var = tk.StringVar()

		ttk.Label(file_group, text="Input (.txt):").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
		ttk.Entry(file_group, textvariable=self.input_file_var).grid(row=0, column=1, sticky="ew", pady=4)
		ttk.Button(file_group, text="Chon", command=self.pick_input_file, style="Secondary.TButton").grid(row=0, column=2, padx=8, pady=4)

		ttk.Label(file_group, text="Output (.txt):").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
		ttk.Entry(file_group, textvariable=self.output_file_var).grid(row=1, column=1, sticky="ew", pady=4)
		ttk.Button(file_group, text="Chon", command=self.pick_output_file, style="Secondary.TButton").grid(row=1, column=2, padx=8, pady=4)

		options_group = ttk.LabelFrame(main, text="Tuy chon dich", padding=12, style="Card.TLabelframe")
		options_group.grid(row=3, column=0, sticky="ew", pady=(0, 10))

		self.chunk_size_var = tk.StringVar(value="3500")
		self.threads_var = tk.StringVar(value="4")
		self.temperature_var = tk.StringVar(value="0.6")
		self.max_output_tokens_var = tk.StringVar(value="4096")

		ttk.Label(options_group, text="Chunk size:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
		ttk.Entry(options_group, textvariable=self.chunk_size_var, width=10).grid(row=0, column=1, sticky="w", pady=4)

		ttk.Label(options_group, text="So luong:").grid(row=0, column=2, sticky="w", padx=(16, 8), pady=4)
		ttk.Spinbox(options_group, from_=1, to=20, textvariable=self.threads_var, width=8).grid(
			row=0, column=3, sticky="w", pady=4
		)

		ttk.Label(options_group, text="Temperature:").grid(row=0, column=4, sticky="w", padx=(16, 8), pady=4)
		ttk.Entry(options_group, textvariable=self.temperature_var, width=10).grid(row=0, column=5, sticky="w", pady=4)

		ttk.Label(options_group, text="Max output tokens:").grid(row=0, column=6, sticky="w", padx=(16, 8), pady=4)
		ttk.Entry(options_group, textvariable=self.max_output_tokens_var, width=10).grid(row=0, column=7, sticky="w", pady=4)

		prompt_group = ttk.LabelFrame(main, text="Prompt dich", padding=12, style="Card.TLabelframe")
		prompt_group.grid(row=4, column=0, sticky="nsew", pady=(0, 10))
		prompt_group.columnconfigure(0, weight=1)
		prompt_group.rowconfigure(0, weight=1)

		self.prompt_text = scrolledtext.ScrolledText(prompt_group, height=8, wrap=tk.WORD)
		self.prompt_text.grid(row=0, column=0, sticky="nsew")
		self.prompt_text.configure(bg=PALETTE["input_bg"], fg=PALETTE["text"], insertbackground=PALETTE["text"], relief=tk.FLAT, padx=8, pady=8)

		action_group = ttk.Frame(main)
		action_group.grid(row=5, column=0, sticky="ew", pady=(0, 10))
		action_group.columnconfigure(3, weight=1)

		self.start_button = ttk.Button(action_group, text="Bat dau dich", command=self.start_translation, style="Primary.TButton")
		self.start_button.grid(row=0, column=0, padx=(0, 8))

		self.stop_button = ttk.Button(action_group, text="Dung", command=self.stop_translation, state="disabled", style="Warn.TButton")
		self.stop_button.grid(row=0, column=1, padx=(0, 8))

		ttk.Button(action_group, text="Xoa log", command=self.clear_log, style="Secondary.TButton").grid(row=0, column=2)

		self.progress_var = tk.DoubleVar(value=0)
		self.progress_bar = ttk.Progressbar(action_group, variable=self.progress_var, maximum=100)
		self.progress_bar.grid(row=0, column=3, sticky="ew", padx=(12, 0))
		ttk.Label(action_group, textvariable=self.progress_text_var, style="SubTitle.TLabel").grid(row=0, column=4, padx=(8, 0), sticky="e")

		self.status_var = tk.StringVar(value="Sẵn sàng")
		ttk.Label(main, textvariable=self.status_var, style="Status.TLabel").grid(row=6, column=0, sticky="w", pady=(0, 6))

		log_group = ttk.LabelFrame(main, text="Log tien trinh", padding=12, style="Card.TLabelframe")
		log_group.grid(row=7, column=0, sticky="nsew")
		log_group.columnconfigure(0, weight=1)
		log_group.rowconfigure(0, weight=1)
		main.rowconfigure(7, weight=1)

		self.log_text = scrolledtext.ScrolledText(log_group, height=12, wrap=tk.WORD, state="disabled")
		self.log_text.grid(row=0, column=0, sticky="nsew")
		self.log_text.configure(bg="#090f1a", fg="#d6e4ff", insertbackground="#d6e4ff", relief=tk.FLAT, padx=8, pady=8)

	def _on_main_frame_configure(self, _event):
		self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

	def _on_canvas_configure(self, event):
		self.main_canvas.itemconfigure(self.main_canvas_window, width=event.width)

	def _on_mousewheel(self, event):
		if hasattr(event, "delta") and event.delta:
			self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
			return
		if getattr(event, "num", None) == 4:
			self.main_canvas.yview_scroll(-1, "units")
		elif getattr(event, "num", None) == 5:
			self.main_canvas.yview_scroll(1, "units")

	def _apply_settings(self):
		self.vps_ip_var.set(self.settings.get("vps_ip", ""))
		self.refresh_token_var.set(self.settings.get("refresh_token", ""))
		self.input_file_var.set(self.settings.get("input_file", ""))
		self.output_file_var.set(self.settings.get("output_file", ""))
		self.chunk_size_var.set(self.settings.get("chunk_size", "3500"))
		self.threads_var.set(self.settings.get("threads", "4"))
		self.temperature_var.set(self.settings.get("temperature", "0.6"))
		self.max_output_tokens_var.set(self.settings.get("max_output_tokens", "4096"))

		model = self.settings.get("model", DEFAULT_MODELS[-1])
		self.model_var.set(model if model else DEFAULT_MODELS[-1])

		self.prompt_text.delete("1.0", tk.END)
		self.prompt_text.insert(tk.END, self.settings.get("prompt", DEFAULT_PROMPT))

	def add_log(self, message):
		ts = datetime.now().strftime("%H:%M:%S")
		self.log_text.configure(state="normal")
		self.log_text.insert(tk.END, f"[{ts}] {message}\n")
		self.log_text.see(tk.END)
		self.log_text.configure(state="disabled")

	def toggle_token_visibility(self):
		self.refresh_entry.configure(show="" if self.show_token_var.get() else "*")

	def set_status(self, message):
		self.status_var.set(message)

	def clear_log(self):
		self.log_text.configure(state="normal")
		self.log_text.delete("1.0", tk.END)
		self.log_text.configure(state="disabled")

	def save_settings(self):
		data = {
			"vps_ip": self.vps_ip_var.get().strip(),
			"refresh_token": self.refresh_token_var.get().strip(),
			"model": self.model_var.get().strip(),
			"input_file": self.input_file_var.get().strip(),
			"output_file": self.output_file_var.get().strip(),
			"chunk_size": self.chunk_size_var.get().strip(),
			"threads": self.threads_var.get().strip(),
			"temperature": self.temperature_var.get().strip(),
			"max_output_tokens": self.max_output_tokens_var.get().strip(),
			"prompt": self.prompt_text.get("1.0", tk.END).strip(),
		}
		save_json_file(SETTINGS_FILE, data)
		self.add_log("Da luu app_settings.json")

	def pick_input_file(self):
		selected = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
		if not selected:
			return
		self.input_file_var.set(selected)

		if not self.output_file_var.get().strip():
			folder = os.path.dirname(selected)
			name = os.path.basename(selected)
			self.output_file_var.set(os.path.join(folder, f"Dich_{name}"))

	def pick_output_file(self):
		selected = filedialog.asksaveasfilename(
			defaultextension=".txt",
			filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
		)
		if selected:
			self.output_file_var.set(selected)

	def _build_headers(self):
		token = self.refresh_token_var.get().strip()
		return {
			"Content-Type": "application/json",
			"Authorization": f"Bearer {token}",
		}

	def fetch_models(self):
		base_url = normalize_base_url(self.vps_ip_var.get())
		token = self.refresh_token_var.get().strip()

		if not base_url:
			messagebox.showerror("Loi", "Vui long nhap IP VPS hoac Base URL hop le")
			return
		if not token:
			messagebox.showerror("Loi", "Vui long nhap refresh token")
			return

		endpoint = f"{base_url}/v1/models"
		request = urllib.request.Request(endpoint, headers=self._build_headers(), method="GET")
		try:
			with urllib.request.urlopen(request, timeout=20) as response:
				payload = json.loads(response.read().decode("utf-8"))

			model_ids = []
			for item in payload.get("data", []):
				if isinstance(item, dict) and item.get("id"):
					model_ids.append(str(item["id"]))

			if not model_ids:
				raise ValueError("Khong lay duoc model nao")

			self.model_combo["values"] = model_ids
			self.model_var.set(model_ids[0])
			self.add_log(f"Da tai {len(model_ids)} model tu VPS")
			self.set_status("Tai model thanh cong")
		except (urllib.error.HTTPError, urllib.error.URLError, ValueError, json.JSONDecodeError) as e:
			self.add_log(f"Tai model that bai: {e}")
			messagebox.showerror("Loi", f"Khong the tai danh sach model:\n{e}")

	def _request_chat_completion(self, base_url, model, prompt, chunk, temperature, max_output_tokens):
		endpoint = f"{base_url}/v1/chat/completions"
		payload = {
			"model": model,
			"messages": [
				{
					"role": "user",
					"content": f"{prompt}\n\n--- NOI DUNG CAN DICH ---\n{chunk}",
				}
			],
			"temperature": temperature,
			"max_tokens": max_output_tokens,
			"stream": False,
		}

		body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
		request = urllib.request.Request(endpoint, data=body, headers=self._build_headers(), method="POST")

		with urllib.request.urlopen(request, timeout=180) as response:
			raw_text = response.read().decode("utf-8")

		content = ""
		stripped = raw_text.lstrip()

		if stripped.startswith("{"):
			data = json.loads(raw_text)
			choices = data.get("choices", [])
			if not choices:
				raise ValueError("API khong tra ve choices")

			message = choices[0].get("message", {})
			content = message.get("content", "")

			if isinstance(content, list):
				merged = []
				for part in content:
					if isinstance(part, dict) and part.get("type") == "text":
						merged.append(part.get("text", ""))
				content = "\n".join([x for x in merged if x])
		else:
			pieces = []
			for line in raw_text.splitlines():
				line = line.strip()
				if not line or not line.startswith("data:"):
					continue

				data_part = line[len("data:") :].strip()
				if data_part == "[DONE]":
					break

				try:
					event = json.loads(data_part)
				except json.JSONDecodeError:
					continue

				choices = event.get("choices", [])
				if not choices:
					continue

				delta = choices[0].get("delta", {})
				piece = delta.get("content", "")
				if isinstance(piece, str) and piece:
					pieces.append(piece)

			content = "".join(pieces)

		content = (content or "").strip()
		if not content:
			raise ValueError("Model tra ve noi dung rong")
		return content

	def _append_history(self, history_item):
		history = load_json_file(HISTORY_FILE, [])
		if not isinstance(history, list):
			history = []
		history.append(history_item)
		save_json_file(HISTORY_FILE, history)

	def _set_running(self, running):
		self.is_running = running
		self.start_button.configure(state="disabled" if running else "normal")
		self.stop_button.configure(state="normal" if running else "disabled")

	def _validate_inputs(self):
		base_url = normalize_base_url(self.vps_ip_var.get())
		token = self.refresh_token_var.get().strip()
		model = self.model_var.get().strip()
		input_file = self.input_file_var.get().strip()
		output_file = self.output_file_var.get().strip()

		if not base_url:
			raise ValueError("Vui long nhap IP VPS hoac Base URL hop le")
		if not token:
			raise ValueError("Vui long nhap refresh token")
		if not model:
			raise ValueError("Vui long chon model")
		if not input_file or not os.path.exists(input_file):
			raise ValueError("File input khong ton tai")
		if not output_file:
			raise ValueError("Vui long chon file output")

		chunk_size = int(self.chunk_size_var.get().strip())
		if chunk_size < 500 or chunk_size > 30000:
			raise ValueError("Chunk size phai trong khoang 500 den 30000")

		threads = int(self.threads_var.get().strip())
		if threads < 1 or threads > 20:
			raise ValueError("So luong phai trong khoang 1 den 20")

		temperature = float(self.temperature_var.get().strip())
		if temperature < 0 or temperature > 2:
			raise ValueError("Temperature phai trong khoang 0 den 2")

		max_output_tokens = int(self.max_output_tokens_var.get().strip())
		if max_output_tokens < 128 or max_output_tokens > 32768:
			raise ValueError("Max output tokens phai trong khoang 128 den 32768")

		prompt = self.prompt_text.get("1.0", tk.END).strip()
		if not prompt:
			raise ValueError("Prompt khong duoc de trong")

		return {
			"base_url": base_url,
			"model": model,
			"input_file": input_file,
			"output_file": output_file,
			"chunk_size": chunk_size,
			"threads": threads,
			"temperature": temperature,
			"max_output_tokens": max_output_tokens,
			"prompt": prompt,
		}

	def start_translation(self):
		if self.is_running:
			return

		try:
			config = self._validate_inputs()
			self.save_settings()
		except ValueError as e:
			messagebox.showerror("Loi", str(e))
			return

		self.progress_var.set(0)
		self.progress_text_var.set("0%")
		self.stop_event.clear()
		self._set_running(True)
		self.set_status("Dang dich...")
		self.add_log("Bat dau dich")

		worker = threading.Thread(target=self._run_translation, args=(config,), daemon=True)
		worker.start()

	def stop_translation(self):
		if self.is_running:
			self.stop_event.set()
			self.add_log("Da gui yeu cau dung")
			self.set_status("Dang dung...")

	def _run_translation(self, config):
		success = False
		error_message = ""
		completed_count = 0

		try:
			with open(config["input_file"], "r", encoding="utf-8") as f:
				source_text = f.read()

			chunks = split_text_into_chunks(source_text, config["chunk_size"])
			if not chunks:
				raise ValueError("Noi dung file input rong")

			total = len(chunks)
			self.root.after(0, lambda: self.add_log(f"Tong so chunk: {total} | So luong: {config['threads']}"))

			ordered_results = {}
			next_write_idx = 0

			def worker(index, piece):
				if self.stop_event.is_set():
					return index, None
				translated = self._request_chat_completion(
					base_url=config["base_url"],
					model=config["model"],
					prompt=config["prompt"],
					chunk=piece,
					temperature=config["temperature"],
					max_output_tokens=config["max_output_tokens"],
				)
				return index, translated

			with ThreadPoolExecutor(max_workers=config["threads"]) as executor:
				futures = [executor.submit(worker, idx, chunk) for idx, chunk in enumerate(chunks)]

				for future in as_completed(futures):
					if self.stop_event.is_set():
						for pending in futures:
							pending.cancel()
						break

					idx, translated = future.result()
					if translated is None:
						continue

					ordered_results[idx] = translated
					completed_count += 1
					percent = (completed_count / total) * 100

					def update_ui(n=completed_count, t=total, p=percent):
						self.progress_var.set(p)
						self.progress_text_var.set(f"{int(p)}%")
						self.set_status(f"Dang dich... {n}/{t} chunk")
						self.add_log(f"Xong chunk {n}/{t}")

					self.root.after(0, update_ui)

					while next_write_idx in ordered_results:
						next_write_idx += 1

					if next_write_idx > 0:
						contiguous = [ordered_results[i] for i in range(next_write_idx)]
						with open(config["output_file"], "w", encoding="utf-8") as out:
							out.write("\n\n".join(contiguous))

			if not self.stop_event.is_set() and completed_count != total:
				raise ValueError("Chua hoan tat toan bo chunk")

			if self.stop_event.is_set():
				self.root.after(0, lambda: self.add_log("Da dung theo yeu cau nguoi dung"))
			else:
				success = True

		except Exception as e:
			error_message = str(e)

		def finish():
			self._set_running(False)
			if success:
				self.progress_var.set(100)
				self.progress_text_var.set("100%")
				self.set_status("Hoan tat")
				self.add_log("Dich xong toan bo")
				messagebox.showinfo("Thanh cong", "Da dich xong file")

				self._append_history(
					{
						"status": "done",
						"model": config["model"],
						"input_file": config["input_file"],
						"output_file": config["output_file"],
						"chunks": completed_count,
						"threads": config["threads"],
					}
				)
			elif self.stop_event.is_set():
				self.set_status("Da dung")
				self.progress_text_var.set(f"{int(self.progress_var.get())}%")
				self._append_history(
					{
						"status": "stopped",
						"model": config["model"],
						"input_file": config["input_file"],
						"output_file": config["output_file"],
						"chunks": completed_count,
						"threads": config["threads"],
					}
				)
			else:
				self.set_status("Loi")
				self.progress_text_var.set(f"{int(self.progress_var.get())}%")
				self.add_log(f"Loi: {error_message}")
				messagebox.showerror("Loi", error_message)

				self._append_history(
					{
						"status": "error",
						"model": config.get("model", ""),
						"input_file": config.get("input_file", ""),
						"output_file": config.get("output_file", ""),
						"chunks": completed_count,
						"threads": config.get("threads", 0),
						"error": error_message,
					}
				)

		self.root.after(0, finish)


def main():
	root = tk.Tk()
	app = KimiTranslatorApp(root)

	def on_close():
		app.save_settings()
		root.destroy()

	root.protocol("WM_DELETE_WINDOW", on_close)
	root.mainloop()


if __name__ == "__main__":
	main()
