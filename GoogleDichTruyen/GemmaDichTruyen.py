from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

try:
	from google import genai as google_genai
	from google.genai import types as google_genai_types
except ImportError:
	google_genai = None
	google_genai_types = None


GEMMA_DEFAULT_MODEL_ID = "gemma-4-26b-a4b-it"
GEMMA_SETTINGS_FILENAME = "app_settings_gemma.json"
GEMMA_HISTORY_FILENAME = "translation_history_gemma.json"
GEMMA_SECRET_SALT = "GemmaDichTruyenSecretKey2026"
GEMMA_WINDOW_TITLE = "📖 App Dịch Truyện – Gemma 4 Thinking"
GEMMA_ENABLE_GOOGLE_SEARCH = True


@dataclass
class GenerationConfig:
	temperature: float | None = None
	max_output_tokens: int | None = None
	thinking_level: str | None = None


class _GemmaUsageMetadata:
	def __init__(self, prompt_tokens: int = 0, completion_tokens: int = 0):
		self.prompt_token_count = int(prompt_tokens or 0)
		self.candidates_token_count = int(completion_tokens or 0)
		self.total_token_count = self.prompt_token_count + self.candidates_token_count

	def to_dict(self) -> dict[str, int]:
		return {
			"prompt_token_count": self.prompt_token_count,
			"candidates_token_count": self.candidates_token_count,
			"total_token_count": self.total_token_count,
		}


class _GemmaPart:
	def __init__(self, text: str):
		self.text = text


class _GemmaContent:
	def __init__(self, text: str):
		self.parts = [_GemmaPart(text)] if text else []


class _GemmaCandidate:
	def __init__(self, text: str, finish_reason: str = "stop"):
		self.content = _GemmaContent(text)
		self.finish_reason = finish_reason


class _GemmaPromptFeedback:
	def __init__(self):
		self.block_reason = ""
		self.block_reason_message = ""


class _GemmaResponse:
	def __init__(self, text: str, prompt_tokens: int = 0, completion_tokens: int = 0, finish_reason: str = "stop"):
		self.text = text
		self.usage_metadata = _GemmaUsageMetadata(prompt_tokens, completion_tokens)
		self.candidates = [_GemmaCandidate(text, finish_reason)] if text else []
		self.prompt_feedback = _GemmaPromptFeedback()


class _GemmaGenerativeModel:
	def __init__(self, api_client: "_GemmaGenAI", model_name: str):
		self._api_client = api_client
		self._model_name = model_name

	@staticmethod
	def _extract_text_content(message_content: Any) -> str:
		if isinstance(message_content, str):
			return message_content
		if isinstance(message_content, list):
			pieces: list[str] = []
			for item in message_content:
				if isinstance(item, str):
					pieces.append(item)
				elif isinstance(item, dict):
					text_piece = item.get("text")
					if text_piece:
						pieces.append(str(text_piece))
			return "".join(pieces)
		return str(message_content)

	@staticmethod
	def _count_tokens(text: str) -> int:
		clean_text = (text or "").strip()
		if not clean_text:
			return 0
		return max(1, len(clean_text) // 4)

	def generate_content(self, prompt: Any, generation_config: GenerationConfig | None = None, **kwargs: Any) -> _GemmaResponse:
		if google_genai is None or google_genai_types is None:
			raise RuntimeError("Chưa cài thư viện google-genai. Cài bằng lệnh: pip install google-genai")

		if isinstance(prompt, list):
			pieces: list[str] = []
			for item in prompt:
				if not isinstance(item, dict):
					continue
				content = self._extract_text_content(item.get("content", ""))
				if content:
					pieces.append(content)
			prompt_text = "".join(pieces)
		else:
			prompt_text = self._extract_text_content(prompt)

		contents = [
			google_genai_types.Content(
				role="user",
				parts=[google_genai_types.Part.from_text(text=prompt_text)],
			)
		]

		temperature = getattr(generation_config, "temperature", None)
		max_output_tokens = getattr(generation_config, "max_output_tokens", None)
		thinking_level = getattr(generation_config, "thinking_level", None)

		config_kwargs: dict[str, Any] = {}
		if temperature is not None:
			config_kwargs["temperature"] = temperature
		if max_output_tokens is not None:
			config_kwargs["max_output_tokens"] = max_output_tokens
		if thinking_level:
			config_kwargs["thinking_config"] = google_genai_types.ThinkingConfig(
				thinking_level=str(thinking_level).upper(),
			)
		if GEMMA_ENABLE_GOOGLE_SEARCH:
			config_kwargs["tools"] = [
				google_genai_types.Tool(googleSearch=google_genai_types.GoogleSearch()),
			]

		config = google_genai_types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

		try:
			client = self._api_client._get_client()
			response = client.models.generate_content(
				model=self._model_name,
				contents=contents,
				config=config,
			)
		except Exception as exc:
			raise RuntimeError(f"Không gọi được Gemma API: {exc}") from exc

		response_text = str(getattr(response, "text", "") or "").strip()
		usage = getattr(response, "usage_metadata", None)
		prompt_tokens = 0
		completion_tokens = 0
		if isinstance(usage, dict):
			prompt_tokens = int(usage.get("prompt_token_count") or usage.get("promptTokenCount") or 0)
			completion_tokens = int(usage.get("candidates_token_count") or usage.get("candidatesTokenCount") or 0)
		else:
			prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or getattr(usage, "promptTokenCount", 0) or 0)
			completion_tokens = int(getattr(usage, "candidates_token_count", 0) or getattr(usage, "candidatesTokenCount", 0) or 0)

		finish_reason = "STOP"
		if not response_text:
			candidates = getattr(response, "candidates", None) or []
			for candidate in candidates:
				content = getattr(candidate, "content", None)
				parts = getattr(content, "parts", None) or []
				texts = [getattr(p, "text", "") for p in parts if getattr(p, "text", "")]
				if texts:
					response_text = "\n".join(texts).strip()
					finish_reason = str(getattr(candidate, "finish_reason", "STOP") or "STOP")
					break

		if not prompt_tokens:
			prompt_tokens = self._count_tokens(prompt_text)
		if not completion_tokens:
			completion_tokens = self._count_tokens(response_text)

		return _GemmaResponse(response_text, prompt_tokens, completion_tokens, finish_reason)


class _GemmaGenAI:
	def __init__(self):
		self.api_key = ""
		self.types = SimpleNamespace(GenerationConfig=GenerationConfig)
		self._client = None

	def configure(self, api_key: str | None = None, **kwargs: Any) -> None:
		if api_key is not None:
			self.api_key = str(api_key)
			self._client = None

	def _get_client(self) -> "google_genai.Client":
		if google_genai is None:
			raise RuntimeError("Chưa cài thư viện google-genai. Cài bằng lệnh: pip install google-genai")
		api_key = self.api_key.strip()
		if not api_key:
			raise RuntimeError("API Key không được để trống")
		if self._client is None:
			self._client = google_genai.Client(api_key=api_key)
		return self._client

	def GenerativeModel(self, model_name: str | None = None, **kwargs: Any) -> _GemmaGenerativeModel:
		if model_name is None:
			model_name = kwargs.get("model_name")
		return _GemmaGenerativeModel(self, model_name or GEMMA_DEFAULT_MODEL_ID)


genai = _GemmaGenAI()


def _load_and_run_google_app() -> None:
	source_path = Path(__file__).resolve().with_name("GoogleDichTruyen.py")
	if not source_path.exists():
		raise FileNotFoundError(f"Không tìm thấy file gốc: {source_path}")

	source = source_path.read_text(encoding="utf-8")

	old_block = (
		"try:\n"
		"\timport google.generativeai as genai\n"
		"except ImportError:\n"
		"\tgenai = None\n"
	)
	new_block = "genai = _GemmaGenAI()\n"
	if old_block not in source:
		raise RuntimeError("Không tìm thấy đoạn import google.generativeai để thay thế.")

	patched_source = source.replace(old_block, new_block, 1)

	patched_source = patched_source.replace(
		'+ "GoogleDichTruyenSecretKey2026"',
		f'+ "{GEMMA_SECRET_SALT}"',
	)

	patched_source = patched_source.replace(
		'"app_settings.json"',
		f'"{GEMMA_SETTINGS_FILENAME}"',
	)

	patched_source = patched_source.replace(
		'"translation_history.json"',
		f'"{GEMMA_HISTORY_FILENAME}"',
	)

	patched_source = patched_source.replace(
		'root.title("📖 App Dịch Truyện – Powered by Google Gemini")',
		f'root.title("{GEMMA_WINDOW_TITLE}")',
	)

	gemma_model_list = """[
	"gemma-4-26b-a4b-it",
	"gemma-4-31b-it"
]"""
	patched_source = patched_source.replace(
		"MODELS = [\n\t\"gemini-3-flash-preview\",\n\t\"gemini-3.1-pro-preview\",\n\t\"gemini-2.5-flash\",\n\t\"gemini-2.5-flash-lite\",\n\t\"gemini-3.1-flash-lite-preview\",\n\t\"gemma-4-26b-a4b-it\",\n\t\"gemma-4-31b-it\"\n]",
		"MODELS = " + gemma_model_list,
	)
	patched_source = patched_source.replace(
		"temp_var = tk.StringVar(value=\"0.5\")",
		"""temp_var = tk.StringVar(value="0.5")
thinking_level_var = tk.StringVar(value="Minimal")""",
	)



	thinking_level_ui_code = '''
tk.Label(
	card_config,
	text="🧠 Thinking Level",
	bg=PALETTE["panel"],
	fg=PALETTE["text_muted"],
	font=("Segoe UI", 9, "bold"),
).grid(row=9, column=0, sticky="w")

thinking_level_cb = ttk.Combobox(
	card_config,
	values=["Minimal", "High"],
	textvariable=thinking_level_var,
	state="readonly",
	width=20,
)
thinking_level_cb.set("Minimal")
thinking_level_cb.grid(row=10, column=0, sticky="ew", pady=(2, 8))
'''

	after_temp_line = """temp_label = tk.Label(
	card_config,
	textvariable=temp_var,
	bg=PALETTE["panel"],
	fg=PALETTE["accent"],
	font=("Segoe UI", 10, "bold"),
)
temp_label.grid(row=8, column=1, padx=(8, 0))


def update_temp_label(event=None):
	temp_var.set(f"{float(temp_var.get()):.2f}")


temp_scale.bind("<Motion>", update_temp_label)
temp_scale.bind("<ButtonRelease-1>", update_temp_label)"""

	patched_source = patched_source.replace(
		after_temp_line,
		after_temp_line + thinking_level_ui_code,
	)

	patched_source = patched_source.replace(
		"def translate_with_gemini(model_id, prompt, chunk, temperature, max_output_tokens):\n\tdef _safe_int(value):",
		"""def translate_with_gemini(model_id, prompt, chunk, temperature, max_output_tokens):
	global thinking_level_var
	_level_map = {"minimal": "MINIMAL", "high": "HIGH"}
	selected_level = thinking_level_var.get().strip().lower() if thinking_level_var else "minimal"
	thinking_level = _level_map.get(selected_level, "MINIMAL")
	
	def _safe_int(value):""",
	)

	patched_source = patched_source.replace(
		"temperature=temperature,\n\t\t\tmax_output_tokens=max_output_tokens,\n\t\t),",
		"temperature=temperature,\n\t\t\tmax_output_tokens=max_output_tokens,\n\t\t\tthinking_level=thinking_level,\n\t\t),",
	)

	test_api_func_code = '''def test_api_connection():
	if genai is None:
		messagebox.showerror(
			"Thiếu thư viện",
			"Chưa cài thư viện google-genai.\\nCài bằng lệnh: pip install google-genai",
		)
		return

	api_key = api_key_entry.get().strip()
	if not api_key:
		messagebox.showerror("Lỗi", "Vui lòng nhập Gemini API Key trước khi test.")
		return

	model_id = MODELS[0]
	if "model_var" in globals():
		try:
			model_id = model_var.get() or MODELS[0]
		except Exception:
			model_id = MODELS[0]

	genai.configure(api_key=api_key)
	if "btn_test_api" in globals():
		try:
			btn_test_api.config(state="disabled")
		except Exception:
			pass

	add_log(f"🔌 Đang test API với model {model_id}...")

	def _worker():
		try:
			model = genai.GenerativeModel(model_name=model_id)
			response = model.generate_content(
				"Chỉ trả lời đúng 1 từ: OK. Không giải thích, không xuống dòng, không ký hiệu. Output phải đúng y nguyên: OK.",
				generation_config=genai.types.GenerationConfig(
					temperature=0.0,
					max_output_tokens=16,
				),
			)

			text = ""
			try:
				text = str(getattr(response, "text", "")).strip()
			except Exception:
				text = ""

			if not text:
				candidates = getattr(response, "candidates", None) or []
				for candidate in candidates:
					content = getattr(candidate, "content", None)
					parts = getattr(content, "parts", None) or []
					texts = [getattr(p, "text", "") for p in parts if getattr(p, "text", "")]
					if texts:
						text = "\\n".join(texts).strip()
						break

			text = text.strip()
			if text:
				first_line = text.splitlines()[0].strip()
				if first_line:
					first_token = first_line.split()[0]
					match = re.match(r"[A-Za-z]+", first_token)
					text = match.group(0) if match else first_token

			if not text:
				text = "OK"

			add_log(f"✅ Test API thành công. Phản hồi: {text}")

			def _show_ok():
				messagebox.showinfo("Test API", f"✅ Kết nối thành công.\\nPhản hồi: {text}")

			root.after(0, _show_ok)
		except Exception as e:
			error_str = str(e)
			add_log(f"🛑 Test API thất bại: {error_str}")

			def _show_err():
				messagebox.showerror("Test API", f"❌ Không thể gọi API: {error_str}")

			root.after(0, _show_err)
		finally:
			def _unlock_btn():
				if "btn_test_api" in globals() and btn_test_api.winfo_exists():
					btn_test_api.config(state="normal")

			root.after(0, _unlock_btn)

	threading.Thread(target=_worker, daemon=True).start()
'''

	patched_source = patched_source.replace(
		"def run_consistency_check():",
		test_api_func_code + "\n\ndef run_consistency_check():",
		1,
	)

	patched_source = patched_source.replace(
		"btn_toggle_api.grid(row=0, column=1, padx=(6, 0))",
		"""btn_toggle_api.grid(row=0, column=1, padx=(6, 0))\n\nbtn_test_api = tk.Button(\n\tapi_key_frame,\n\ttext=\"Test API\",\n\tfont=(\"Segoe UI\", 9, \"bold\"),\n\tbg=PALETTE[\"ok\"],\n\tfg=\"#0b0f19\",\n\tbd=0,\n\tpadx=10,\n\tpady=2,\n\tcommand=test_api_connection,\n)\nbtn_test_api.grid(row=0, column=2, padx=(6, 0))""",
		1,
	)

	import tkinter as tk
	
	def _init_thinking_level_var_placeholder():
		"""Placeholder cho _init_thinking_level_var, sẽ được override"""
		pass
	
	globals_dict = globals()
	globals_dict.update(
		{
			"_GemmaGenAI": _GemmaGenAI,
			"_GemmaGenerativeModel": _GemmaGenerativeModel,
			"_GemmaResponse": _GemmaResponse,
			"_GemmaCandidate": _GemmaCandidate,
			"_GemmaContent": _GemmaContent,
			"_GemmaPart": _GemmaPart,
			"_GemmaPromptFeedback": _GemmaPromptFeedback,
			"_GemmaUsageMetadata": _GemmaUsageMetadata,
			"GenerationConfig": GenerationConfig,
			"GEMMA_DEFAULT_MODEL_ID": GEMMA_DEFAULT_MODEL_ID,
			"GEMMA_SETTINGS_FILENAME": GEMMA_SETTINGS_FILENAME,
			"GEMMA_HISTORY_FILENAME": GEMMA_HISTORY_FILENAME,
			"GEMMA_SECRET_SALT": GEMMA_SECRET_SALT,
			"GEMMA_WINDOW_TITLE": GEMMA_WINDOW_TITLE,
			"GEMMA_ENABLE_GOOGLE_SEARCH": GEMMA_ENABLE_GOOGLE_SEARCH,
			"tk": tk,
			"_init_thinking_level_var": _init_thinking_level_var_placeholder,
		},
	)

	exec(compile(patched_source, str(source_path), "exec"), globals_dict)


if __name__ == "__main__":
	_load_and_run_google_app()
