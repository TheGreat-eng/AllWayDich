from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request


PROXY_CHAT_COMPLETIONS_URL = "https://llm.wokushop.com/v1/chat/completions"
PROXY_SETTINGS_FILENAME = "app_settings_proxy.json"
PROXY_HISTORY_FILENAME = "translation_history_proxy.json"
PROXY_SECRET_SALT = "WokushopProxySecretKey2026"
PROXY_WINDOW_TITLE = "📖 App Dịch Truyện – Proxy LLM"


@dataclass
class GenerationConfig:
	temperature: float | None = None
	max_output_tokens: int | None = None


class _ProxyUsageMetadata:
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


class _ProxyPart:
	def __init__(self, text: str):
		self.text = text


class _ProxyContent:
	def __init__(self, text: str):
		self.parts = [_ProxyPart(text)] if text else []


class _ProxyCandidate:
	def __init__(self, text: str, finish_reason: str = "stop"):
		self.content = _ProxyContent(text)
		self.finish_reason = finish_reason


class _ProxyPromptFeedback:
	def __init__(self):
		self.block_reason = ""
		self.block_reason_message = ""


class _ProxyResponse:
	def __init__(self, text: str, prompt_tokens: int = 0, completion_tokens: int = 0, finish_reason: str = "stop"):
		self.text = text
		self.usage_metadata = _ProxyUsageMetadata(prompt_tokens, completion_tokens)
		self.candidates = [_ProxyCandidate(text, finish_reason)] if text else []
		self.prompt_feedback = _ProxyPromptFeedback()


class _ProxyGenerativeModel:
	def __init__(self, api_client: "_ProxyGenAI", model_name: str):
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

	def generate_content(self, prompt: Any, generation_config: GenerationConfig | None = None, **kwargs: Any) -> _ProxyResponse:
		if isinstance(prompt, list):
			messages = []
			for item in prompt:
				if not isinstance(item, dict):
					continue
				role = item.get("role", "user")
				content = self._extract_text_content(item.get("content", ""))
				messages.append({"role": role, "content": content})
		else:
			messages = [{"role": "user", "content": self._extract_text_content(prompt)}]

		payload: dict[str, Any] = {
			"model": self._model_name,
			"messages": messages,
		}

		temperature = getattr(generation_config, "temperature", None)
		max_output_tokens = getattr(generation_config, "max_output_tokens", None)
		if temperature is not None:
			payload["temperature"] = temperature
		if max_output_tokens is not None:
			payload["max_tokens"] = max_output_tokens

		for key in ("temperature", "max_tokens", "top_p", "stream", "stop"):
			if key in kwargs and kwargs[key] is not None:
				payload[key] = kwargs[key]

		api_key = self._api_client.api_key.strip()
		headers = {
			"Content-Type": "application/json",
			"Accept": "application/json",
			"User-Agent": "curl/8.1.2",
			"Connection": "keep-alive",
		}
		if api_key:
			headers["Authorization"] = f"Bearer {api_key}"

		request = urllib_request.Request(
			PROXY_CHAT_COMPLETIONS_URL,
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
			raise RuntimeError(f"Proxy API error {exc.code}: {error_body}") from exc
		except Exception as exc:
			raise RuntimeError(f"Không gọi được proxy API: {exc}") from exc

		try:
			data = json.loads(response_body)
		except json.JSONDecodeError as exc:
			raise RuntimeError(f"Proxy API trả về JSON không hợp lệ: {response_body[:500]}") from exc

		choices = data.get("choices") or []
		choice0 = choices[0] if choices else {}
		message = choice0.get("message") or {}
		content = message.get("content")
		if content is None:
			content = choice0.get("text") or data.get("text") or data.get("output_text") or ""
		if isinstance(content, list):
			content = "".join(
				item.get("text", "") if isinstance(item, dict) else str(item)
				for item in content
			)
		content = str(content)

		usage = data.get("usage") or {}
		prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
		completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0
		finish_reason = choice0.get("finish_reason") or data.get("finish_reason") or "stop"

		if not prompt_tokens:
			prompt_tokens = self._count_tokens(messages[-1]["content"] if messages else "")
		if not completion_tokens:
			completion_tokens = self._count_tokens(content)

		return _ProxyResponse(content, int(prompt_tokens), int(completion_tokens), str(finish_reason))


class _ProxyGenAI:
	def __init__(self):
		self.api_key = ""
		self.types = SimpleNamespace(GenerationConfig=GenerationConfig)

	def configure(self, api_key: str | None = None, **kwargs: Any) -> None:
		if api_key is not None:
			self.api_key = str(api_key)

	def GenerativeModel(self, model_name: str | None = None, **kwargs: Any) -> _ProxyGenerativeModel:
		if model_name is None:
			model_name = kwargs.get("model_name")
		return _ProxyGenerativeModel(self, str(model_name or "gemini-3.1-flash-lite-preview"))


genai = _ProxyGenAI()


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
	new_block = "genai = _ProxyGenAI()\n"
	if old_block not in source:
		raise RuntimeError("Không tìm thấy đoạn import google.generativeai để thay thế.")

	patched_source = source.replace(old_block, new_block, 1)
	patched_source = patched_source.replace(
		'+ "GoogleDichTruyenSecretKey2026"',
		f'+ "{PROXY_SECRET_SALT}"',
	)
	patched_source = patched_source.replace(
		'"app_settings.json"',
		f'"{PROXY_SETTINGS_FILENAME}"',
	)
	patched_source = patched_source.replace(
		'"translation_history.json"',
		f'"{PROXY_HISTORY_FILENAME}"',
	)
	patched_source = patched_source.replace(
		'root.title("📖 App Dịch Truyện – Powered by Google Gemini")',
		f'root.title("{PROXY_WINDOW_TITLE}")',
	)
	globals_dict = globals()
	globals_dict.update(
		{
			"_ProxyGenAI": _ProxyGenAI,
			"_ProxyGenerativeModel": _ProxyGenerativeModel,
			"_ProxyResponse": _ProxyResponse,
			"_ProxyCandidate": _ProxyCandidate,
			"_ProxyContent": _ProxyContent,
			"_ProxyPart": _ProxyPart,
			"_ProxyPromptFeedback": _ProxyPromptFeedback,
			"_ProxyUsageMetadata": _ProxyUsageMetadata,
			"GenerationConfig": GenerationConfig,
			"PROXY_CHAT_COMPLETIONS_URL": PROXY_CHAT_COMPLETIONS_URL,
			"PROXY_SETTINGS_FILENAME": PROXY_SETTINGS_FILENAME,
			"PROXY_HISTORY_FILENAME": PROXY_HISTORY_FILENAME,
			"PROXY_SECRET_SALT": PROXY_SECRET_SALT,
			"PROXY_WINDOW_TITLE": PROXY_WINDOW_TITLE,
		},
	)
	exec(compile(patched_source, str(source_path), "exec"), globals_dict)


if __name__ == "__main__":
	_load_and_run_google_app()
