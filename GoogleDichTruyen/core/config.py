import os

MODELS = [
	"gemini-3-flash-preview",
	"gemini-3.6-flash",
	"gemini-3.5-flash",
	"gemini-3.5-flash-lite",
	"gemini-3.1-pro-preview",
	"gemini-2.5-flash",
	"gemini-2.5-flash-lite",
	"gemini-3.1-flash-lite-preview",
	"gemma-4-26b-a4b-it",
	"gemma-4-31b-it"
]

CHUNK_SIZE = 70000
MAX_OUTPUT_TOKENS = 70000
DEFAULT_SCAN_CHAR_LIMIT = 10000

DEFAULT_PROMPT = (
	"Bạn là một biên tập viên truyện dịch chuyên nghiệp, thành thạo tiếng Trung và tiếng Việt.\n"
	"Nhiệm vụ của bạn là viết lại đoạn văn sau thành tiếng Việt thuần, tự nhiên, mượt mà, "
	"loại bỏ cảm giác máy dịch, sao cho đọc giống truyện Việt.\n"
	"Không dịch sát từng chữ, ưu tiên ý nghĩa, ngữ cảnh và cảm xúc.\n"
	"Cho phép gộp hoặc tách câu, điều chỉnh trật tự câu cho phù hợp tiếng Việt.\n"
	"Giữ nguyên nội dung, nhân vật, xưng hô, bối cảnh và ý nghĩa gốc.\n"
	"Không thêm nội dung mới, không lược bỏ nội dung.\n"
	"Không giải thích, không bình luận.\n"
	"Giữ cách xuống dòng và bố cục đoạn văn hợp lý như truyện.\n\n"
)

DEFAULT_GLOSSARY = ""

API_REQUEST_TIMEOUT_MS = 180_000

MODEL_PRICING = {
	"gemini-3.6-flash": {"input_per_1m": 1.50, "output_per_1m": 7.50},
	"gemini-3.5-flash": {"input_per_1m": 1.50, "output_per_1m": 9.00},
	"gemini-3.5-flash-lite": {"input_per_1m": 0.30, "output_per_1m": 2.50},
	"gemini-3.1-pro-preview": {
		"input_per_1m_le_200k": 2.00,
		"input_per_1m_gt_200k": 4.00,
		"output_per_1m_le_200k": 12.00,
		"output_per_1m_gt_200k": 18.00,
	},
	"gemini-3.1-flash-lite-preview": {"input_per_1m": 0.25, "output_per_1m": 1.50},
	"gemini-3-flash-preview": {"input_per_1m": 0.50, "output_per_1m": 3.00},
	"gemini-2.5-flash": {"input_per_1m": 0.30, "output_per_1m": 2.50},
	"gemini-2.5-flash-lite": {"input_per_1m": 0.10, "output_per_1m": 0.40},
	"gemma-4-26b-a4b-it": {"input_per_1m": 0.15, "output_per_1m": 0.40},
	"gemma-4-31b-it": {"input_per_1m": 0.15, "output_per_1m": 0.40},
}

USD_TO_VND = 27000

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(BASE_DIR, "app_settings.json")
HISTORY_FILE = os.path.join(BASE_DIR, "translation_history.json")
DRIVE_TOKEN_FILE = os.path.join(BASE_DIR, "drive_token.json")
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
