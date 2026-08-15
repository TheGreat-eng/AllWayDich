import re
from .config import CHUNK_SIZE

def split_text(text: str, size: int = CHUNK_SIZE, split_mode: str = "keyword") -> list[str]:
	chunks = []
	current_chunk = ""
	
	keyword_patterns = [
		r"^\s*(chương|chap(?:ter)?|hồi|quyển|tập|thiên|phần|mục|tiết|ngoại\s*(truyện|chương)|phiên\s*ngoại|đệ\s+\w+\s+chương|thứ\s+\w+\s+chương)\b",
		r"^\s*(ch\.|chap\.|c\.|q\.|t\.)\s*\d+\b",
	]
	_equals_pattern = r"^\s*={3,}\s*(thứ\s+\w+\s+chương|chương\s+\w+|chap(?:ter)?\s+\w+|hồi\s+\w+|quyển\s+\w+|tập\s+\w+|thiên\s+\w+|phần\s+\w+|mục\s+\w+|tiết\s+\w+)\b.*(?:={3,}\s*)?$"
	active_patterns = [_equals_pattern] if split_mode == "equals" else keyword_patterns
	active_matchers = [re.compile(p, re.IGNORECASE) for p in active_patterns]
	
	lines = text.splitlines(True)
	
	blocks = []
	current_block = ""
	
	for line in lines:
		if any(matcher.match(line) for matcher in active_matchers):
			if current_block.strip():
				blocks.append(current_block)
			current_block = line
		else:
			current_block += line
			
	if current_block.strip():
		blocks.append(current_block)
		
	for block in blocks:
		if len(current_chunk) + len(block) > size:
			if current_chunk.strip():
				chunks.append(current_chunk)
				current_chunk = ""
			
			if len(block) > size:
				temp_str = ""
				paragraphs = block.split("\n\n")
				for p in paragraphs:
					p_text = p + "\n\n" if p != paragraphs[-1] else p
					if len(temp_str) + len(p_text) > size:
						if temp_str.strip():
							chunks.append(temp_str)
						
						if len(p_text) > size:
							temp_str2 = ""
							sentences = re.split(r'(?<=[.!?]) +|\n', p_text)
							for s in sentences:
								s_text = s + " "
								if len(temp_str2) + len(s_text) > size:
									if temp_str2.strip():
										chunks.append(temp_str2)
										temp_str2 = ""
									
									if len(s_text) > size:
										for k in range(0, len(s_text), size):
											sub_s = s_text[k:k+size]
											if len(sub_s) < size or k + size >= len(s_text):
												temp_str2 = sub_s
											else:
												chunks.append(sub_s)
									else:
										temp_str2 = s_text
								else:
									temp_str2 += s_text
							temp_str = temp_str2
						else:
							temp_str = p_text
					else:
						temp_str += p_text
				
				if temp_str.strip():
					current_chunk = temp_str
			else:
				current_chunk = block
		else:
			current_chunk += block
			
	if current_chunk.strip():
		chunks.append(current_chunk)
		
	return chunks
