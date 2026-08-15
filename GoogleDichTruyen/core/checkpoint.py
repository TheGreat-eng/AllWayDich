import os
import json
import time
import hashlib
import threading

checkpoint_lock = threading.Lock()

def build_checkpoint_metadata(source_text: str, chunk_size: int, split_mode: str, total_chunks: int) -> dict:
	return {
		"source_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
		"chunk_size": chunk_size,
		"split_mode": split_mode,
		"total_chunks": total_chunks,
	}


def read_checkpoint_data(file_path: str) -> tuple[dict, dict]:
	if not os.path.exists(file_path):
		return {}, {}
	with open(file_path, "r", encoding="utf-8") as f:
		data = json.load(f)
	if not isinstance(data, dict):
		raise ValueError("Nội dung checkpoint không hợp lệ")
	if isinstance(data.get("translations"), dict):
		metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
		return metadata, data["translations"]
	return {}, {str(k): v for k, v in data.items() if str(k).isdigit() and isinstance(v, str)}


def write_checkpoint_data(file_path: str, metadata: dict, translations: dict):
	payload = {
		"version": 2,
		"metadata": metadata,
		"translations": translations,
	}
	temp_path = f"{file_path}.tmp"
	with open(temp_path, "w", encoding="utf-8") as f:
		json.dump(payload, f, ensure_ascii=False, indent=2)
	os.replace(temp_path, file_path)


def reset_checkpoint(file_path: str, metadata: dict):
	with checkpoint_lock:
		write_checkpoint_data(file_path, metadata, {})


def checkpoint_matches(metadata: dict, expected_metadata: dict) -> bool:
	return not metadata or metadata == expected_metadata


def save_checkpoint(cp_file: str, index: int, text: str):
	with checkpoint_lock:
		try:
			metadata, data = read_checkpoint_data(cp_file)
			data[str(index)] = text
			write_checkpoint_data(cp_file, metadata, data)
		except Exception as e:
			print(f"Lỗi khi lưu checkpoint: {e}")


def load_failed_chunks(failed_file: str) -> dict:
	with checkpoint_lock:
		try:
			if not os.path.exists(failed_file):
				return {}
			with open(failed_file, "r", encoding="utf-8") as f:
				data = json.load(f)
			return data if isinstance(data, dict) else {}
		except Exception as e:
			print(f"Could not load failed chunk records: {e}")
			return {}


def save_failed_chunk(failed_file: str, index: int, chunk: str, error: str, attempts: int):
	with checkpoint_lock:
		try:
			data = {}
			if os.path.exists(failed_file):
				with open(failed_file, "r", encoding="utf-8") as f:
					loaded = json.load(f)
					if isinstance(loaded, dict):
						data = loaded

			data[str(index)] = {
				"index": index,
				"source_text": chunk,
				"last_error": error or "Unknown error",
				"attempts": attempts,
				"failed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
			}
			with open(failed_file, "w", encoding="utf-8") as f:
				json.dump(data, f, ensure_ascii=False, indent=2)
		except Exception as e:
			print(f"Could not save failed chunk: {e}")


def load_current_failed_chunks(failed_file: str, chunks: list[str]) -> dict:
	records = load_failed_chunks(failed_file)
	valid_records = {}
	for key, record in records.items():
		try:
			index = int(key)
		except (TypeError, ValueError):
			continue
		if (
			isinstance(record, dict)
			and 0 <= index < len(chunks)
			and record.get("source_text") == chunks[index]
		):
			valid_records[str(index)] = record

	if valid_records == records:
		return valid_records

	with checkpoint_lock:
		try:
			if valid_records:
				with open(failed_file, "w", encoding="utf-8") as f:
					json.dump(valid_records, f, ensure_ascii=False, indent=2)
			elif os.path.exists(failed_file):
				os.remove(failed_file)
		except Exception as e:
			print(f"Could not clean stale failed chunk records: {e}")
	return valid_records


def clear_failed_chunk(failed_file: str, index: int):
	if not failed_file:
		return
	with checkpoint_lock:
		try:
			if not os.path.exists(failed_file):
				return
			with open(failed_file, "r", encoding="utf-8") as f:
				data = json.load(f)
			if not isinstance(data, dict) or str(index) not in data:
				return
			del data[str(index)]
			if data:
				with open(failed_file, "w", encoding="utf-8") as f:
					json.dump(data, f, ensure_ascii=False, indent=2)
			else:
				os.remove(failed_file)
		except Exception as e:
			print(f"Could not clear failed chunk: {e}")
