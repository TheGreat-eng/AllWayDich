import os
import re
import tempfile

def get_checkpoint_path(input_file: str) -> str:
	base, _ = os.path.splitext(input_file)
	return f"{base}.resume.json"


def get_translation_cache_path(input_file: str) -> str:
	base, _ = os.path.splitext(input_file)
	return f"{base}.chunks.json"


def get_chunk_storage_path(input_file: str) -> str:
	return get_translation_cache_path(input_file)


def get_failed_chunks_path(input_file: str) -> str:
	base, _ = os.path.splitext(input_file)
	return f"{base}.failed_chunks.json"


def sanitize_filename_part(raw_value: str, fallback: str) -> str:
	if not raw_value:
		return fallback
	cleaned = re.sub(r'[\/:*?"<>|]', "_", str(raw_value)).strip()
	cleaned = re.sub(r"\s+", "_", cleaned)
	return cleaned if cleaned else fallback


def build_default_output_path(input_file: str, model_id: str = None) -> str:
	if not input_file:
		return ""
	folder, filename = os.path.split(input_file)
	name, ext = os.path.splitext(filename)
	if not ext:
		ext = ".txt"

	model_suffix = sanitize_filename_part(model_id, "")
	if model_suffix:
		out_name = f"Dich_{name}_{model_suffix}{ext}"
	else:
		out_name = f"Dich_{name}{ext}"
	return os.path.join(folder, out_name)


def format_time(seconds: float) -> str:
	seconds = int(seconds)
	h = seconds // 3600
	m = (seconds % 3600) // 60
	s = seconds % 60
	if h > 0:
		return f"{h}h {m}m {s}s"
	elif m > 0:
		return f"{m}m {s}s"
	else:
		return f"{s}s"


def read_file_content_safely(file_path: str) -> str:
	if not file_path or not os.path.exists(file_path):
		return ""
	encodings = ["utf-8-sig", "utf-8", "utf-16", "gb18030", "gbk", "cp1252"]
	for enc in encodings:
		try:
			with open(file_path, "r", encoding=enc) as f:
				return f.read()
		except Exception:
			continue
	with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
		return f.read()


def write_text_atomically(file_path: str, content: str):
	target_dir = os.path.dirname(os.path.abspath(file_path))
	if target_dir:
		os.makedirs(target_dir, exist_ok=True)
	tmp_fd, tmp_path = tempfile.mkstemp(dir=target_dir, prefix=".tmp_dich_")
	try:
		with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
			f.write(content)
		os.replace(tmp_path, file_path)
	except Exception:
		if os.path.exists(tmp_path):
			try:
				os.remove(tmp_path)
			except Exception:
				pass
		raise
