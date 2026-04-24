import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk


SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_settings.json")
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translation_history.json")

DEFAULT_MODELS = [
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

		self.stop_event = threading.Event()
		self.is_running = False

		self.settings = load_json_file(
			SETTINGS_FILE,
			{
				"vps_ip": "",
				"refresh_token": "",
				"model": DEFAULT_MODELS[-1],
				"input_file": "",
				"output_file": "",
				"chunk_size": "3500",
				"temperature": "0.6",
				"max_output_tokens": "4096",
				"prompt": DEFAULT_PROMPT,
			},
		)

		self._build_ui()
		self._apply_settings()

	def _build_ui(self):
		self.root.columnconfigure(0, weight=1)
		self.root.rowconfigure(0, weight=1)

		main = ttk.Frame(self.root, padding=12)
		main.grid(row=0, column=0, sticky="nsew")
		main.columnconfigure(0, weight=1)
		main.rowconfigure(5, weight=1)

		conn_group = ttk.LabelFrame(main, text="Kết nối VPS", padding=10)
		conn_group.grid(row=0, column=0, sticky="ew", pady=(0, 8))
		conn_group.columnconfigure(1, weight=1)

		ttk.Label(conn_group, text="IP VPS / Base URL:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
		self.vps_ip_var = tk.StringVar()
		ttk.Entry(conn_group, textvariable=self.vps_ip_var).grid(row=0, column=1, columnspan=3, sticky="ew", pady=4)

		ttk.Label(conn_group, text="Refresh Token:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
		self.refresh_token_var = tk.StringVar()
		ttk.Entry(conn_group, textvariable=self.refresh_token_var, show="*").grid(
			row=1, column=1, columnspan=3, sticky="ew", pady=4
		)

		ttk.Label(conn_group, text="Model:").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
		self.model_var = tk.StringVar(value=DEFAULT_MODELS[-1])
		self.model_combo = ttk.Combobox(conn_group, textvariable=self.model_var, values=DEFAULT_MODELS, state="readonly")
		self.model_combo.grid(row=2, column=1, sticky="ew", pady=4)
		ttk.Button(conn_group, text="Tải model từ VPS", command=self.fetch_models).grid(row=2, column=2, sticky="w", padx=8)
		ttk.Button(conn_group, text="Lưu cấu hình", command=self.save_settings).grid(row=2, column=3, sticky="w")

		file_group = ttk.LabelFrame(main, text="File truyện", padding=10)
		file_group.grid(row=1, column=0, sticky="ew", pady=(0, 8))
		file_group.columnconfigure(1, weight=1)

		self.input_file_var = tk.StringVar()
		self.output_file_var = tk.StringVar()

		ttk.Label(file_group, text="Input (.txt):").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
		ttk.Entry(file_group, textvariable=self.input_file_var).grid(row=0, column=1, sticky="ew", pady=4)
		ttk.Button(file_group, text="Chọn", command=self.pick_input_file).grid(row=0, column=2, padx=8, pady=4)

		ttk.Label(file_group, text="Output (.txt):").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
		ttk.Entry(file_group, textvariable=self.output_file_var).grid(row=1, column=1, sticky="ew", pady=4)
		ttk.Button(file_group, text="Chọn", command=self.pick_output_file).grid(row=1, column=2, padx=8, pady=4)

		options_group = ttk.LabelFrame(main, text="Tùy chọn dịch", padding=10)
		options_group.grid(row=2, column=0, sticky="ew", pady=(0, 8))

		self.chunk_size_var = tk.StringVar(value="3500")
		self.temperature_var = tk.StringVar(value="0.6")
		self.max_output_tokens_var = tk.StringVar(value="4096")

		ttk.Label(options_group, text="Chunk size:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
		ttk.Entry(options_group, textvariable=self.chunk_size_var, width=10).grid(row=0, column=1, sticky="w", pady=4)

		ttk.Label(options_group, text="Temperature:").grid(row=0, column=2, sticky="w", padx=(16, 8), pady=4)
		ttk.Entry(options_group, textvariable=self.temperature_var, width=10).grid(row=0, column=3, sticky="w", pady=4)

		ttk.Label(options_group, text="Max output tokens:").grid(row=0, column=4, sticky="w", padx=(16, 8), pady=4)
		ttk.Entry(options_group, textvariable=self.max_output_tokens_var, width=10).grid(row=0, column=5, sticky="w", pady=4)

		prompt_group = ttk.LabelFrame(main, text="Prompt dịch", padding=10)
		prompt_group.grid(row=3, column=0, sticky="nsew", pady=(0, 8))
		prompt_group.columnconfigure(0, weight=1)
		prompt_group.rowconfigure(0, weight=1)

		self.prompt_text = scrolledtext.ScrolledText(prompt_group, height=8, wrap=tk.WORD)
		self.prompt_text.grid(row=0, column=0, sticky="nsew")

		action_group = ttk.Frame(main)
		action_group.grid(row=4, column=0, sticky="ew", pady=(0, 8))
		action_group.columnconfigure(3, weight=1)

		self.start_button = ttk.Button(action_group, text="Bắt đầu dịch", command=self.start_translation)
		self.start_button.grid(row=0, column=0, padx=(0, 8))

		self.stop_button = ttk.Button(action_group, text="Dừng", command=self.stop_translation, state="disabled")
		self.stop_button.grid(row=0, column=1, padx=(0, 8))

		ttk.Button(action_group, text="Xóa log", command=self.clear_log).grid(row=0, column=2)

		self.progress_var = tk.DoubleVar(value=0)
		self.progress_bar = ttk.Progressbar(action_group, variable=self.progress_var, maximum=100)
		self.progress_bar.grid(row=0, column=3, sticky="ew", padx=(12, 0))

		self.status_var = tk.StringVar(value="Sẵn sàng")
		ttk.Label(main, textvariable=self.status_var).grid(row=5, column=0, sticky="w", pady=(0, 4))

		log_group = ttk.LabelFrame(main, text="Log", padding=10)
		log_group.grid(row=6, column=0, sticky="nsew")
		log_group.columnconfigure(0, weight=1)
		log_group.rowconfigure(0, weight=1)
		main.rowconfigure(6, weight=1)

		self.log_text = scrolledtext.ScrolledText(log_group, height=12, wrap=tk.WORD, state="disabled")
		self.log_text.grid(row=0, column=0, sticky="nsew")

	def _apply_settings(self):
		self.vps_ip_var.set(self.settings.get("vps_ip", ""))
		self.refresh_token_var.set(self.settings.get("refresh_token", ""))
		self.input_file_var.set(self.settings.get("input_file", ""))
		self.output_file_var.set(self.settings.get("output_file", ""))
		self.chunk_size_var.set(self.settings.get("chunk_size", "3500"))
		self.temperature_var.set(self.settings.get("temperature", "0.6"))
		self.max_output_tokens_var.set(self.settings.get("max_output_tokens", "4096"))

		model = self.settings.get("model", DEFAULT_MODELS[-1])
		self.model_var.set(model if model else DEFAULT_MODELS[-1])

		self.prompt_text.delete("1.0", tk.END)
		self.prompt_text.insert(tk.END, self.settings.get("prompt", DEFAULT_PROMPT))

	def add_log(self, message):
		self.log_text.configure(state="normal")
		self.log_text.insert(tk.END, f"{message}\n")
		self.log_text.see(tk.END)
		self.log_text.configure(state="disabled")

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
		translated_chunks = []

		try:
			with open(config["input_file"], "r", encoding="utf-8") as f:
				source_text = f.read()

			chunks = split_text_into_chunks(source_text, config["chunk_size"])
			if not chunks:
				raise ValueError("Noi dung file input rong")

			total = len(chunks)
			self.root.after(0, lambda: self.add_log(f"Tong so chunk: {total}"))

			for idx, chunk in enumerate(chunks, start=1):
				if self.stop_event.is_set():
					break

				self.root.after(0, lambda n=idx, t=total: self.set_status(f"Dang dich chunk {n}/{t}"))

				translated = self._request_chat_completion(
					base_url=config["base_url"],
					model=config["model"],
					prompt=config["prompt"],
					chunk=chunk,
					temperature=config["temperature"],
					max_output_tokens=config["max_output_tokens"],
				)

				translated_chunks.append(translated)
				percent = (idx / total) * 100

				def update_ui(n=idx, t=total, p=percent):
					self.progress_var.set(p)
					self.add_log(f"Xong chunk {n}/{t}")

				self.root.after(0, update_ui)

				with open(config["output_file"], "w", encoding="utf-8") as out:
					out.write("\n\n".join(translated_chunks))

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
				self.set_status("Hoan tat")
				self.add_log("Dich xong toan bo")
				messagebox.showinfo("Thanh cong", "Da dich xong file")

				self._append_history(
					{
						"status": "done",
						"model": config["model"],
						"input_file": config["input_file"],
						"output_file": config["output_file"],
						"chunks": len(translated_chunks),
					}
				)
			elif self.stop_event.is_set():
				self.set_status("Da dung")
				self._append_history(
					{
						"status": "stopped",
						"model": config["model"],
						"input_file": config["input_file"],
						"output_file": config["output_file"],
						"chunks": len(translated_chunks),
					}
				)
			else:
				self.set_status("Loi")
				self.add_log(f"Loi: {error_message}")
				messagebox.showerror("Loi", error_message)

				self._append_history(
					{
						"status": "error",
						"model": config.get("model", ""),
						"input_file": config.get("input_file", ""),
						"output_file": config.get("output_file", ""),
						"chunks": len(translated_chunks),
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
