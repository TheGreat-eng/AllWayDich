import time
import threading
from .config import API_REQUEST_TIMEOUT_MS
from .history import get_model_prices_usd_per_1m, record_request_event
from .checkpoint import save_checkpoint, clear_failed_chunk, save_failed_chunk

try:
	from google import genai
	from google.genai import types as genai_types
except ImportError:
	genai = None
	genai_types = None

active_gemini_clients = set()
active_gemini_clients_lock = threading.Lock()

def register_gemini_client(client):
	with active_gemini_clients_lock:
		active_gemini_clients.add(client)

def unregister_gemini_client(client):
	with active_gemini_clients_lock:
		active_gemini_clients.discard(client)

def close_active_gemini_clients():
	with active_gemini_clients_lock:
		clients = list(active_gemini_clients)
	for client in clients:
		try:
			client.close()
		except Exception:
			pass


def is_quota_exceeded_error(error_str: str) -> bool:
	if not error_str:
		return False
	s = str(error_str).lower()
	return any(kw in s for kw in [
		"429", "resource_exhausted", "quota", "rate limit",
		"too many requests", "exceeded your current quota"
	])


def is_gemini_v3_or_above(model_name: str) -> bool:
	if not model_name:
		return False
	name = str(model_name).lower()
	return "gemini-3" in name or "gemma-4" in name


class TranslationEngine:
	def __init__(self, log_callback=None):
		self.log_callback = log_callback or (lambda msg: print(msg))
		self.is_paused = False
		self.is_stopped = False
		self.pause_event = threading.Event()
		self.pause_event.set()
		
		self.stats = {
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

	def log(self, message: str):
		if self.log_callback:
			self.log_callback(message)

	def reset_stats(self, total_chunks: int = 0):
		self.stats = {
			"start_time": time.time(),
			"chunks_done": 0,
			"total_chunks": total_chunks,
			"total_input_chars": 0,
			"total_output_chars": 0,
			"total_input_tokens": 0,
			"total_output_tokens": 0,
			"total_input_cost_usd": 0.0,
			"total_output_cost_usd": 0.0,
			"total_cost_usd": 0.0,
		}

	def pause(self):
		self.is_paused = True
		self.pause_event.clear()

	def resume(self):
		self.is_paused = False
		self.pause_event.set()

	def stop(self):
		self.is_stopped = True
		self.pause_event.set()
		close_active_gemini_clients()

	def translate_with_gemini(self, model_id: str, prompt: str, chunk: str, temperature: float, max_output_tokens: int, thinking_level: str = None, api_key: str = None):
		def _safe_int(val):
			try:
				return int(val)
			except Exception:
				return 0

		def _usage_get(usage_obj, keys):
			for key in keys:
				value = usage_obj.get(key)
				if value is not None:
					return _safe_int(value)
			return 0

		def _safe_str(val):
			if val is None:
				return ""
			try:
				return str(val)
			except Exception:
				return ""

		if genai is None:
			return None, 0, 0, 'ERROR'

		client = None
		try:
			client = genai.Client(
				api_key=api_key or "",
				http_options=genai_types.HttpOptions(timeout=API_REQUEST_TIMEOUT_MS),
			)
			register_gemini_client(client)
			full_prompt = prompt + "\n\nNỘI DUNG CẦN DỊCH:\n" + chunk
			
			config_args = {
				"temperature": temperature,
				"max_output_tokens": max_output_tokens,
			}
			
			if is_gemini_v3_or_above(model_id):
				level = (thinking_level or "medium").lower().strip()
				if level not in ["minimal", "low", "medium", "high"]:
					level = "medium"
				config_args["thinking_config"] = genai_types.ThinkingConfig(thinking_level=level)
				
			config = genai_types.GenerateContentConfig(**config_args)
			response = client.models.generate_content(
				model=model_id,
				contents=full_prompt,
				config=config
			)

			usage = getattr(response, "usage_metadata", None)
			if usage is None:
				usage_data = {}
			elif isinstance(usage, dict):
				usage_data = usage
			elif hasattr(usage, "to_dict"):
				usage_data = usage.to_dict()
			else:
				usage_data = {
					"prompt_token_count": getattr(usage, "prompt_token_count", None),
					"candidates_token_count": getattr(usage, "candidates_token_count", None),
					"thoughts_token_count": getattr(usage, "thoughts_token_count", None),
				}

			input_tokens = _usage_get(usage_data, ["prompt_token_count", "promptTokenCount"])
			candidates_tokens = _usage_get(usage_data, ["candidates_token_count", "candidatesTokenCount", "response_token_count", "responseTokenCount"])
			thoughts_tokens = _usage_get(usage_data, ["thoughts_token_count", "thoughtsTokenCount"])
			output_tokens = candidates_tokens + thoughts_tokens

			response_text = ""
			try:
				response_text = _safe_str(getattr(response, "text", "")).strip()
			except Exception:
				response_text = ""

			if response_text:
				return response_text, input_tokens, output_tokens, None

			candidates = getattr(response, "candidates", None) or []
			for candidate in candidates:
				content = getattr(candidate, "content", None)
				parts = getattr(content, "parts", None) or []
				texts = [getattr(p, "text", "") for p in parts if getattr(p, "text", "")]
				if texts:
					return "".join(texts).strip(), input_tokens, output_tokens, None

			return None, input_tokens, output_tokens, "ERROR"
		except Exception as exc:
			err_msg = str(exc)
			if is_quota_exceeded_error(err_msg):
				return None, 0, 0, "QUOTA"
			return None, 0, 0, err_msg
		finally:
			if client:
				unregister_gemini_client(client)
				try:
					client.close()
				except Exception:
					pass

	def translate_chunk(self, model_id: str, prompt: str, chunk: str, index: int, cp_file: str, temperature: float, max_output_tokens: int, model_fallback_order: list = None, retries: int = 3, failed_file: str = None, api_key: str = None, thinking_level: str = None):
		self.pause_event.wait()
		if self.is_stopped:
			return index, None

		if model_fallback_order is None:
			model_fallback_order = [model_id]

		last_error = None
		current_model_index = 0

		for attempt in range(retries):
			if self.is_stopped:
				return index, None

			self.pause_event.wait()

			try:
				current_model = model_fallback_order[current_model_index] if current_model_index < len(model_fallback_order) else model_fallback_order[0]
				self.log(f"⏳ Đang dịch đoạn {index + 1} (model: {current_model})... (lần thử {attempt + 1}/{retries})")
				record_request_event(current_model)
				translated_text, input_tokens, output_tokens, error_code = self.translate_with_gemini(
					current_model, prompt, chunk, temperature, max_output_tokens,
					thinking_level=thinking_level, api_key=api_key
				)

				if error_code == "QUOTA":
					if current_model_index + 1 < len(model_fallback_order):
						current_model_index += 1
						next_model = model_fallback_order[current_model_index]
						self.log(f"⚠️ Đoạn {index + 1}: Vượt quota model '{current_model}', chuyển sang '{next_model}'...")
						time.sleep(1)
						continue
					else:
						self.log(f"❌ Đoạn {index + 1}: Tất cả model đều vượt quota!")
						last_error = "Tất cả model vượt quota"
						time.sleep(2 + attempt * 2)
						continue

				if error_code:
					last_error = f"Lỗi API: {error_code}"
					self.log(f"⚠️ Đoạn {index + 1} gặp lỗi (lần {attempt + 1}): {last_error}")
					time.sleep(2 + attempt * 2)
					continue

				if not translated_text:
					raise RuntimeError("Gemini trả về nội dung rỗng.")

				save_checkpoint(cp_file, index, translated_text)
				clear_failed_chunk(failed_file, index)

				self.stats["chunks_done"] += 1
				self.stats["total_input_chars"] += len(chunk)
				self.stats["total_output_chars"] += len(translated_text)
				self.stats["total_input_tokens"] += input_tokens
				self.stats["total_output_tokens"] += output_tokens
				input_price_per_1m, output_price_per_1m = get_model_prices_usd_per_1m(current_model, input_tokens)
				input_cost = (input_tokens / 1_000_000) * input_price_per_1m
				output_cost = (output_tokens / 1_000_000) * output_price_per_1m
				self.stats["total_input_cost_usd"] += input_cost
				self.stats["total_output_cost_usd"] += output_cost
				self.stats["total_cost_usd"] = self.stats["total_input_cost_usd"] + self.stats["total_output_cost_usd"]

				self.log(f"✅ Hoàn thành đoạn {index + 1}")
				return index, translated_text

			except Exception as e:
				last_error = str(e)
				self.log(f"❌ Đoạn {index + 1} gặp lỗi (lần {attempt + 1}): {last_error}")
				time.sleep(2 + attempt * 2)

		if failed_file:
			save_failed_chunk(failed_file, index, chunk, last_error, retries)
		self.log(f"🔴 Đoạn {index + 1} thất bại sau {retries} lần thử: {last_error}")
		return index, None
