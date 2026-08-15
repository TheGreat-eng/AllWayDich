import re

def parse_glossary(raw_text: str) -> list[tuple[str, str]]:
	"""Parse glossary lines. Format: source => target (or source -> target, source: target)"""
	entries = []
	if not raw_text:
		return entries

	for line in raw_text.splitlines():
		clean = line.strip()
		if not clean or clean.startswith("#"):
			continue

		separator = None
		for candidate in ["=>", "->", ":"]:
			if candidate in clean:
				separator = candidate
				break

		if not separator:
			continue

		source, target = clean.split(separator, 1)
		source = source.strip()
		target = target.strip()
		if source and target:
			entries.append((source, target))

	return entries


def build_prompt_with_glossary(base_prompt: str, glossary_entries: list[tuple[str, str]]) -> str:
	"""Attach glossary terms into prompt instructions for consistent terminology."""
	if not glossary_entries:
		return base_prompt

	processed_entries = []
	for src, dst in glossary_entries:
		match = re.search(r'\(([^)]+)\)?', dst)
		if match:
			dst_cleaned = match.group(1).strip()
		else:
			dst_cleaned = dst
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


def normalize_scanned_glossary(raw_text: str) -> str:
	"""Normalize AI scanned glossary output into 'source => target' format."""
	if not raw_text:
		return ""

	cleaned_lines = []
	seen = set()
	for line in raw_text.splitlines():
		clean = line.strip().lstrip("-•* ").strip()
		if not clean:
			continue

		separator = None
		for candidate in ["=>", "->", "→", ":", "="]:
			if candidate in clean:
				separator = candidate
				break

		if not separator:
			continue

		source, target = clean.split(separator, 1)
		source = source.strip(" \t\"'“”‘’[](){}")
		target = target.strip(" \t\"'“”‘’[]{}")
		if not source or not target:
			continue

		normalized = f"{source} => {target}"
		key = normalized.lower()
		if key in seen:
			continue
		seen.add(key)
		cleaned_lines.append(normalized)

	return "\n".join(cleaned_lines)


def build_scan_segments(text: str, segment_size: int = 12000, max_segments: int = 12) -> list[str]:
	"""Sample text segments evenly across the story for glossary scanning."""
	if not text:
		return []

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

	if bucket.strip():
		segments.append(bucket)

	if not segments:
		segments = [text[:segment_size]]

	if len(segments) <= max_segments:
		return segments

	selected = []
	selected_positions = set()
	for i in range(max_segments):
		pos = int(round(i * (len(segments) - 1) / (max_segments - 1))) if max_segments > 1 else 0
		if pos not in selected_positions:
			selected_positions.add(pos)
			selected.append(segments[pos])

	return selected
