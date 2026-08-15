import os
import json
import time
import threading
from .config import (
	MODEL_PRICING, USD_TO_VND, SETTINGS_FILE, HISTORY_FILE,
	MODELS, CHUNK_SIZE, MAX_OUTPUT_TOKENS, DEFAULT_SCAN_CHAR_LIMIT,
	DEFAULT_PROMPT, DEFAULT_GLOSSARY
)
from .crypto import encrypt_api_key, decrypt_api_key

request_minute_lock = threading.Lock()
request_minute_counts = {}

def get_model_prices_usd_per_1m(model_id: str, input_tokens: int = 0) -> tuple[float, float]:
	p = MODEL_PRICING.get(model_id, {"input_per_1m": 0.0, "output_per_1m": 0.0})
	if "input_per_1m_le_200k" in p:
		if input_tokens <= 200_000:
			return p["input_per_1m_le_200k"], p["output_per_1m_le_200k"]
		else:
			return p["input_per_1m_gt_200k"], p["output_per_1m_gt_200k"]
	return p.get("input_per_1m", 0.0), p.get("output_per_1m", 0.0)


def load_settings() -> dict:
	default_settings = {
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
				for k_name, k_enc in api_keys.items():
					decrypted_api_keys[k_name] = decrypt_api_key(k_enc)
				
				if old_api_key and "Mặc định" not in decrypted_api_keys:
					decrypted_api_keys["Mặc định"] = old_api_key
				if "Mặc định" not in decrypted_api_keys:
					decrypted_api_keys["Mặc định"] = ""
					
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


def save_settings(settings_dict: dict):
	try:
		to_save = dict(settings_dict)
		api_keys = to_save.get("api_keys", {})
		encrypted_api_keys = {}
		for k_name, k_val in api_keys.items():
			encrypted_api_keys[k_name] = encrypt_api_key(k_val)
		to_save["api_keys"] = encrypted_api_keys

		if "Mặc định" in api_keys:
			to_save["api_key_encrypted"] = encrypt_api_key(api_keys["Mặc định"])

		with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
			json.dump(to_save, f, ensure_ascii=False, indent=4)
	except Exception as e:
		print(f"Không thể lưu cài đặt: {e}")


def load_translation_history() -> list[dict]:
	if not os.path.exists(HISTORY_FILE):
		return []
	try:
		with open(HISTORY_FILE, "r", encoding="utf-8") as f:
			data = json.load(f)
			if isinstance(data, list):
				return data
	except Exception as e:
		print(f"Không thể tải lịch sử dịch: {e}")
	return []


def save_translation_history_entry(entry: dict, max_entries: int = 200):
	try:
		history = load_translation_history()
		history.insert(0, entry)
		if len(history) > max_entries:
			history = history[:max_entries]
		with open(HISTORY_FILE, "w", encoding="utf-8") as f:
			json.dump(history, f, ensure_ascii=False, indent=2)
	except Exception as e:
		print(f"Không thể lưu lịch sử dịch: {e}")


def clear_translation_history():
	if os.path.exists(HISTORY_FILE):
		try:
			os.remove(HISTORY_FILE)
		except Exception as e:
			print(f"Không thể xóa lịch sử dịch: {e}")


def reset_request_metrics():
	with request_minute_lock:
		request_minute_counts.clear()


def record_request_event(model_id: str = None):
	minute_key = time.strftime("%Y-%m-%d %H:%M")
	model_key = str(model_id or "unknown")
	with request_minute_lock:
		if minute_key not in request_minute_counts:
			request_minute_counts[minute_key] = {}
		request_minute_counts[minute_key][model_key] = request_minute_counts[minute_key].get(model_key, 0) + 1


def get_request_metrics_snapshot() -> list[dict]:
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


def build_request_entry_key(entry: dict) -> str:
	start_at = str(entry.get("start_at", ""))
	output_file = str(entry.get("output_file", ""))
	model = str(entry.get("model", ""))
	return f"{start_at}|{output_file}|{model}"


def normalize_request_counts(entry: dict) -> list[dict]:
	raw = entry.get("request_counts_by_minute", [])
	items = []
	if isinstance(raw, dict):
		for minute, count in raw.items():
			items.append({"minute": str(minute), "model": str(entry.get("model", "unknown")), "count": int(count or 0)})
	elif isinstance(raw, list):
		for item in raw:
			if not isinstance(item, dict):
				continue
			minute = item.get("minute")
			if minute is None:
				continue
			items.append({
				"minute": str(minute),
				"model": str(item.get("model", entry.get("model", "unknown"))),
				"count": int(item.get("count", 0) or 0),
			})
	items.sort(key=lambda x: (x["minute"], x["model"]))
	return items


def summarize_request_counts(counts: list[dict]) -> tuple[int, int, dict]:
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
