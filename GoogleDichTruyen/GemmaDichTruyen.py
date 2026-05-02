from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request


GEMMA_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMMA_MODEL_ID = "gemma-4-31b-it"
GEMMA_SETTINGS_FILENAME = "app_settings_gemma.json"
GEMMA_HISTORY_FILENAME = "translation_history_gemma.json"
GEMMA_SECRET_SALT = "GemmaDichTruyenSecretKey2026"
GEMMA_WINDOW_TITLE = "📖 App Dịch Truyện – Gemma 4 Thinking"


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
		if isinstance(prompt, list):
			parts = []
			for item in prompt:
				if not isinstance(item, dict):
					continue
				content = self._extract_text_content(item.get("content", ""))
				if content:
					parts.append({"text": content})
		else:
			parts = [{"text": self._extract_text_content(prompt)}]

		payload: dict[str, Any] = {
			"contents": [{"parts": parts}],
			"generationConfig": {},
		}

		temperature = getattr(generation_config, "temperature", None)
		max_output_tokens = getattr(generation_config, "max_output_tokens", None)
		thinking_level = getattr(generation_config, "thinking_level", None)

		if temperature is not None:
			payload["generationConfig"]["temperature"] = temperature
		if max_output_tokens is not None:
			payload["generationConfig"]["maxOutputTokens"] = max_output_tokens

		if thinking_level:
			payload["generationConfig"]["thinking_config"] = {
				"include_thoughts": True,
				"thinking_level": thinking_level,
			}

		api_key = self._api_client.api_key.strip()
		if not api_key:
			raise RuntimeError("API Key không được để trống")

		url = f"{GEMMA_BASE_URL}/{self._model_name}:generateContent?key={api_key}"
		headers = {
			"Content-Type": "application/json",
		}

		request = urllib_request.Request(
			url,
			data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
			headers=headers,
			method="POST",
		)

		try:
			with urllib_request.urlopen(request, timeout=180) as response:
				response_body = response.read().decode("utf-8", errors="replace")
		except urllib_error.HTTPError as exc:
			try:
				error_body = exc.read().decode("utf-8", errors="replace")
			except Exception:
				error_body = exc.reason if getattr(exc, "reason", None) else str(exc)
			raise RuntimeError(f"Gemma API error {exc.code}: {error_body}") from exc
		except Exception as exc:
			raise RuntimeError(f"Không gọi được Gemma API: {exc}") from exc

		try:
			data = json.loads(response_body)
		except json.JSONDecodeError as exc:
			raise RuntimeError(f"Gemma API trả về JSON không hợp lệ: {response_body[:500]}") from exc

		candidates = data.get("candidates") or []
		candidate0 = candidates[0] if candidates else {}
		content = candidate0.get("content") or {}
		parts = content.get("parts") or []

		full_text = ""
		for part in parts:
			if isinstance(part, dict):
				text = part.get("text", "")
				if text:
					full_text += str(text)

		usage = data.get("usageMetadata") or {}
		prompt_tokens = usage.get("promptTokenCount") or usage.get("prompt_tokens") or 0
		completion_tokens = usage.get("candidatesTokenCount") or usage.get("completion_tokens") or 0
		finish_reason = candidate0.get("finishReason") or "STOP"

		if not prompt_tokens:
			prompt_tokens = self._count_tokens("".join(p.get("text", "") for p in parts if isinstance(p, dict)))
		if not completion_tokens:
			completion_tokens = self._count_tokens(full_text)

		return _GemmaResponse(full_text, int(prompt_tokens), int(completion_tokens), str(finish_reason))


class _GemmaGenAI:
	def __init__(self):
		self.api_key = ""
		self.types = SimpleNamespace(GenerationConfig=GenerationConfig)

	def configure(self, api_key: str | None = None, **kwargs: Any) -> None:
		if api_key is not None:
			self.api_key = str(api_key)

	def GenerativeModel(self, model_name: str | None = None, **kwargs: Any) -> _GemmaGenerativeModel:
		if model_name is None:
			model_name = kwargs.get("model_name")
		return _GemmaGenerativeModel(self, GEMMA_MODEL_ID)


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

	gemma_model_list = """["gemma-4-31b-it", "gemma-4-26b-a4b-it"]"""
	patched_source = patched_source.replace(
		"temp_var = tk.StringVar(value=\"0.5\")",
		"""temp_var = tk.StringVar(value="0.5")
thinking_level_var = tk.StringVar(value="minimal")""",
	)



	thinking_level_ui_code = '''
tk.Label(
	card_config,
	text="🧠 Thinking Level",
	bg=PALETTE["panel"],
	fg=PALETTE["text_muted"],
	font=("Segoe UI", 9, "bold"),
).grid(row=6, column=0, sticky="w", pady=(8, 2))

thinking_level_frame = tk.Frame(card_config, bg=PALETTE["panel"])
thinking_level_frame.grid(row=7, column=0, sticky="ew", pady=(0, 8))

for level in ["minimal", "high"]:
	tk.Radiobutton(
		thinking_level_frame,
		text=level.capitalize(),
		variable=thinking_level_var,
		value=level,
		bg=PALETTE["panel"],
		fg=PALETTE["text"],
		selectcolor=PALETTE["accent"],
		font=("Segoe UI", 9),
	).pack(side="left", padx=6)
'''

	after_temp_line = """temp_label = tk.Label(
	card_config,
	textvariable=temp_var,
	bg=PALETTE["panel"],
	fg=PALETTE["accent"],
	font=("Segoe UI", 10, "bold"),
)
temp_label.grid(row=5, column=1, padx=(8, 0))


def update_temp_label(event=None):
	temp_var.set(f"{float(temp_var.get()):.2f}")


temp_scale.bind("<Motion>", update_temp_label)
temp_scale.bind("<ButtonRelease-1>", update_temp_label)"""

	patched_source = patched_source.replace(
		after_temp_line,
		after_temp_line + thinking_level_ui_code,
	)

	patched_source = patched_source.replace(
		"generation_config=genai.types.GenerationConfig(\n\t\t\ttemperature=temperature,\n\t\t\tmax_output_tokens=max_output_tokens,\n\t\t),",
		"""generation_config=genai.types.GenerationConfig(
			temperature=temperature,
			max_output_tokens=max_output_tokens,
			thinking_level=thinking_level,
		),""",
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
			"GEMMA_BASE_URL": GEMMA_BASE_URL,
			"GEMMA_MODEL_ID": GEMMA_MODEL_ID,
			"GEMMA_SETTINGS_FILENAME": GEMMA_SETTINGS_FILENAME,
			"GEMMA_HISTORY_FILENAME": GEMMA_HISTORY_FILENAME,
			"GEMMA_SECRET_SALT": GEMMA_SECRET_SALT,
			"GEMMA_WINDOW_TITLE": GEMMA_WINDOW_TITLE,
			"tk": tk,
			"_init_thinking_level_var": _init_thinking_level_var_placeholder,
		},
	)

	exec(compile(patched_source, str(source_path), "exec"), globals_dict)


if __name__ == "__main__":
	_load_and_run_google_app()
