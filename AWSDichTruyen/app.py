import os
import sys
import json
import time
import base64
import hashlib
import threading
import concurrent.futures
import random
import re
import datetime
import webview
import boto3

# ================= CẤU HÌNH AWS BEDROCK =================
MODELS = [
    "us.meta.llama4-maverick-17b-instruct-v1:0",
    "qwen.qwen3-next-80b-a3b",
    "qwen.qwen3-vl-235b-a22b",
    "google.gemma-3-27b-it",
    "google.gemma-3-4b-it",
    "us.meta.llama4-scout-17b-instruct-v1:0",
]

CHUNK_SIZE = 3000
MAX_TOKENS = 8192
REGION = "us-east-1"
USD_TO_VND = 25400

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

MODEL_PRICING = {
    "us.meta.llama4-maverick-17b-instruct-v1:0": {"input_per_1m": 0.24, "output_per_1m": 0.97},
    "qwen.qwen3-next-80b-a3b": {"input_per_1m": 0.14, "output_per_1m": 1.20},
    "qwen.qwen3-vl-235b-a22b": {"input_per_1m": 0.53, "output_per_1m": 2.66},
    "google.gemma-3-27b-it": {"input_per_1m": 0.23, "output_per_1m": 0.38},
    "google.gemma-3-4b-it": {"input_per_1m": 0.04, "output_per_1m": 0.08},
    "us.meta.llama4-scout-17b-instruct-v1:0": {"input_per_1m": 0.17, "output_per_1m": 0.66},
}

def get_model_prices_usd_per_1m(model_id):
    pricing = MODEL_PRICING.get(model_id, {"input_per_1m": 0.0, "output_per_1m": 0.0})
    return pricing.get("input_per_1m", 0.0), pricing.get("output_per_1m", 0.0)

# Clean Model ID for output filename formatting
def clean_model_name_for_filename(model_id):
    if not model_id:
        return "Model"
    parts = model_id.split(':')
    base = parts[0].split('.')[-1]
    # Replace invalid filename characters
    cleaned = re.sub(r'[^\w\-]', '_', base)
    return cleaned

def build_default_output_filename(input_file_path, model_id):
    if not input_file_path:
        return ""
    input_dir = os.path.dirname(input_file_path)
    input_name = os.path.splitext(os.path.basename(input_file_path))[0]
    model_name = clean_model_name_for_filename(model_id)
    date_str = datetime.datetime.now().strftime("%d-%m-%Y")
    random_num = random.randint(1000, 9999)
    # Quy tắc: Dich_{tên file}_{tên model}_{ngày/tháng/năm}_{số ngẫu nhiên}.txt
    output_filename = f"Dich_{input_name}_{model_name}_{date_str}_{random_num}.txt"
    return os.path.join(input_dir, output_filename)

# ================= MÃ HÓA API KEY =================
def get_machine_key():
    unique_string = os.environ.get('COMPUTERNAME', 'PC') + os.environ.get('USERNAME', 'User') + "DichTruyenSecretKey2025"
    return hashlib.sha256(unique_string.encode()).digest()

def xor_encrypt_decrypt(data: str, key: bytes) -> str:
    if not data:
        return ""
    data_bytes = data.encode('utf-8')
    key_repeated = (key * ((len(data_bytes) // len(key)) + 1))[:len(data_bytes)]
    result = bytes([a ^ b for a, b in zip(data_bytes, key_repeated)])
    return base64.b64encode(result).decode('utf-8')

def xor_decrypt(encrypted_data: str, key: bytes) -> str:
    if not encrypted_data:
        return ""
    try:
        data_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
        key_repeated = (key * ((len(data_bytes) // len(key)) + 1))[:len(data_bytes)]
        result = bytes([a ^ b for a, b in zip(data_bytes, key_repeated)])
        return result.decode('utf-8')
    except Exception:
        return ""

def encrypt_api_key(api_key: str) -> str:
    return xor_encrypt_decrypt(api_key, get_machine_key())

def decrypt_api_key(encrypted_key: str) -> str:
    return xor_decrypt(encrypted_key, get_machine_key())

# ================= THÔNG TIN CÀI ĐẶT & LỊCH SỬ =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "app_settings.json")
HISTORY_FILE = os.path.join(BASE_DIR, "translation_history.json")

def load_settings():
    default_settings = {
        "api_key": "",
        "input_file": "",
        "output_file": "",
        "model": MODELS[0],
        "threads": "3",
        "chunk_size": str(CHUNK_SIZE),
        "max_output_tokens": str(MAX_TOKENS),
        "temperature": "0.5",
        "prompt": DEFAULT_PROMPT,
        "theme": "dark"
    }
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for k in ["input_file", "output_file", "model", "threads", "chunk_size", "max_output_tokens", "temperature", "prompt", "theme"]:
                    if k in saved:
                        default_settings[k] = saved[k]
                if saved.get("api_key_encrypted"):
                    default_settings["api_key"] = decrypt_api_key(saved["api_key_encrypted"])
                elif saved.get("api_key"):
                    default_settings["api_key"] = saved["api_key"]
    except Exception as e:
        print(f"Error loading settings: {e}")
    return default_settings

def save_settings_to_file(settings_dict):
    try:
        save_data = dict(settings_dict)
        api_key = save_data.pop("api_key", "")
        save_data["api_key_encrypted"] = encrypt_api_key(api_key)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

def load_translation_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
    except Exception as e:
        print(f"Error loading history: {e}")
    return []

def save_translation_history_entry(entry, max_entries=200):
    try:
        history = load_translation_history()
        history.append(entry)
        history = history[-max_entries:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving history entry: {e}")

# ================= CHIA CHUNK =================
def split_text(text, size=CHUNK_SIZE):
    chunks = []
    current = ""
    chapter_pattern = re.compile(r'^\s*(\d+\s*\||Chương\s+\d+|Quyển\s+\d+|Đệ\s+\d+\s+Chương)', re.IGNORECASE)
    
    for line in text.splitlines(True):
        is_chapter_heading = chapter_pattern.match(line)
        if (is_chapter_heading and len(current) > 500) or (len(current) + len(line) > size):
            if current.strip():
                chunks.append(current)
            current = line
        else:
            current += line
            
    if current.strip():
        chunks.append(current)
    return chunks

# ================= BACKEND API FOR PYWEBVIEW =================
class Api:
    def __init__(self):
        self._window = None
        self.is_paused = False
        self.is_stopped = False
        self.pause_event = threading.Event()
        self.pause_event.set()
        
        self.batch_stats = {
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

    def set_window(self, window):
        self._window = window

    def log_to_js(self, message):
        if self._window:
            safe_msg = json.dumps(message)
            self._window.evaluate_js(f"window.onPyLog && window.onPyLog({safe_msg});")

    def update_progress_to_js(self, data):
        if self._window:
            safe_json = json.dumps(data)
            self._window.evaluate_js(f"window.onPyProgress && window.onPyProgress({safe_json});")

    # --- EXPOSED JS METHODS ---

    def get_initial_data(self):
        return {
            "models": MODELS,
            "settings": load_settings(),
            "history": load_translation_history(),
            "pricing": MODEL_PRICING,
            "usd_to_vnd": USD_TO_VND
        }

    def save_settings(self, settings):
        success = save_settings_to_file(settings)
        return {"success": success}

    def translate_text(self, params):
        try:
            text = params.get("text", "").strip()
            if not text:
                return {"success": False, "error": "Văn bản nhập vào rỗng."}

            api_key = params.get("api_key", "").strip()
            if not api_key.startswith("ABSK"):
                return {"success": False, "error": "Mã API Key AWS Bedrock (ABSK...) không hợp lệ."}

            model_id = params.get("model", MODELS[0])
            prompt = params.get("prompt", DEFAULT_PROMPT)
            target_lang = params.get("target_lang", "Tiếng Việt")
            temperature = float(params.get("temperature", 0.5))
            max_tokens = int(params.get("max_tokens", MAX_TOKENS))

            os.environ['AWS_BEARER_TOKEN_BEDROCK'] = api_key
            bedrock_client = boto3.client(service_name='bedrock-runtime', region_name=REGION)

            system_instruction = prompt
            if target_lang and "Tiếng Việt" not in target_lang:
                system_instruction += f"\nNgôn ngữ đích cần dịch sang: {target_lang}."

            messages = [
                {
                    "role": "user",
                    "content": [{"text": system_instruction + "\n\nNỘI DUNG CẦN DỊCH:\n" + text}]
                }
            ]

            response = bedrock_client.converse(
                modelId=model_id,
                messages=messages,
                inferenceConfig={
                    "maxTokens": max_tokens,
                    "temperature": temperature
                }
            )

            translated_text = response['output']['message']['content'][0]['text']
            usage = response.get("usage", {})
            input_tokens = int(usage.get("inputTokens", 0) or 0)
            output_tokens = int(usage.get("outputTokens", 0) or 0)

            in_price, out_price = get_model_prices_usd_per_1m(model_id)
            input_cost = (input_tokens / 1_000_000) * in_price
            output_cost = (output_tokens / 1_000_000) * out_price
            total_cost_usd = input_cost + output_cost
            total_cost_vnd = total_cost_usd * USD_TO_VND

            return {
                "success": True,
                "translated_text": translated_text.strip(),
                "input_chars": len(text),
                "output_chars": len(translated_text),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_cost_usd": round(total_cost_usd, 6),
                "total_cost_vnd": round(total_cost_vnd, 0)
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def select_input_file(self, current_model=MODELS[0]):
        if not self._window:
            return ""
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=('Text Files (*.txt)', 'All Files (*.*)')
        )
        if result and len(result) > 0:
            file_path = result[0]
            # Đường dẫn output mặc định chuẩn: Dich_{tên file}_{tên model}_{ngày-tháng-năm}_{số ngẫu nhiên}.txt
            default_out = build_default_output_filename(file_path, current_model)
            return {"input_file": file_path, "default_output_file": default_out}
        return {"input_file": "", "default_output_file": ""}

    def generate_default_output_path(self, input_file, current_model):
        if not input_file:
            return ""
        return build_default_output_filename(input_file, current_model)

    def select_output_file(self):
        if not self._window:
            return ""
        result = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename="Dich_Truyen.txt",
            file_types=('Text Files (*.txt)', 'All Files (*.*)')
        )
        if result:
            return result
        return ""

    def preview_chunks(self, file_path, chunk_size=CHUNK_SIZE):
        try:
            if not file_path or not os.path.exists(file_path):
                return {"success": False, "error": "File không tồn tại."}
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            chunks = split_text(text, int(chunk_size))
            previews = []
            for idx, c in enumerate(chunks):
                lines = c.strip().split("\n")
                first_line = lines[0][:40] + "..." if len(lines[0]) > 40 else lines[0]
                previews.append({
                    "index": idx + 1,
                    "length": len(c),
                    "summary": first_line,
                    "content": c
                })
            return {"success": True, "total_chunks": len(chunks), "chunks": previews}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def start_file_translation(self, params):
        if self.batch_stats["start_time"] != 0 and not self.is_stopped:
            return {"success": False, "error": "Đang có tiến trình dịch file đang chạy."}

        self.is_stopped = False
        self.is_paused = False
        self.pause_event.set()

        thread = threading.Thread(target=self._run_file_translation_thread, args=(params,))
        thread.daemon = True
        thread.start()
        return {"success": True}

    def pause_file_translation(self):
        if self.is_paused:
            self.is_paused = False
            self.pause_event.set()
            self.log_to_js("▶️ Đã tiếp tục tiến trình dịch.")
            return {"status": "resumed"}
        else:
            self.is_paused = True
            self.pause_event.clear()
            self.log_to_js("⏸️ Đã tạm dừng dịch file.")
            return {"status": "paused"}

    def stop_file_translation(self):
        self.is_stopped = True
        self.is_paused = False
        self.pause_event.set()
        self.log_to_js("🛑 Đã gửi yêu cầu dừng quá trình dịch.")
        return {"status": "stopped"}

    def get_history(self):
        return load_translation_history()

    def clear_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _run_file_translation_thread(self, params):
        in_file = params.get("input_file", "").strip()
        out_file = params.get("output_file", "").strip()
        api_key = params.get("api_key", "").strip()
        model_id = params.get("model", MODELS[0])
        prompt = params.get("prompt", DEFAULT_PROMPT)
        target_lang = params.get("target_lang", "Tiếng Việt")
        threads = int(params.get("threads", 3))
        chunk_size = int(params.get("chunk_size", CHUNK_SIZE))
        max_tokens = int(params.get("max_tokens", MAX_TOKENS))
        temperature = float(params.get("temperature", 0.5))

        if not api_key.startswith("ABSK"):
            self.log_to_js("❌ Lỗi: API Key AWS Bedrock không hợp lệ.")
            self.update_progress_to_js({"status": "error", "error": "API Key không hợp lệ."})
            return

        if not os.path.exists(in_file):
            self.log_to_js(f"❌ Lỗi: File {in_file} không tồn tại.")
            self.update_progress_to_js({"status": "error", "error": "File đầu vào không tồn tại."})
            return

        os.environ['AWS_BEARER_TOKEN_BEDROCK'] = api_key
        bedrock_client = boto3.client(service_name='bedrock-runtime', region_name=REGION)

        try:
            with open(in_file, "r", encoding="utf-8") as f:
                text_content = f.read()

            chunks = split_text(text_content, size=chunk_size)
            total = len(chunks)
            results = [None] * total

            self.batch_stats = {
                "start_time": time.time(),
                "chunks_done": 0,
                "total_chunks": total,
                "total_input_chars": 0,
                "total_output_chars": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_input_cost_usd": 0.0,
                "total_output_cost_usd": 0.0,
                "total_cost_usd": 0.0,
            }

            self.log_to_js(f"🚀 Bắt đầu dịch file: {os.path.basename(in_file)} ({total} đoạn)")
            self.log_to_js(f"⚙️ Model: {model_id} | Luồng: {threads} | Chunk: {chunk_size}")

            system_prompt = prompt
            if target_lang and "Tiếng Việt" not in target_lang:
                system_prompt += f"\nNgôn ngữ đích: {target_lang}."

            def process_chunk(idx, chunk_text):
                self.pause_event.wait()
                if self.is_stopped:
                    return idx, None

                messages = [
                    {
                        "role": "user",
                        "content": [{"text": system_prompt + "\n\nNỘI DUNG CẦN DỊCH:\n" + chunk_text}]
                    }
                ]

                last_err = None
                for attempt in range(3):
                    if self.is_stopped:
                        return idx, None
                    self.pause_event.wait()

                    try:
                        self.log_to_js(f"⏳ Đang dịch đoạn {idx + 1}/{total} (lần thử {attempt + 1})...")
                        res = bedrock_client.converse(
                            modelId=model_id,
                            messages=messages,
                            inferenceConfig={"maxTokens": max_tokens, "temperature": temperature}
                        )
                        trans = res['output']['message']['content'][0]['text'].strip()
                        usage = res.get("usage", {})
                        in_tok = int(usage.get("inputTokens", 0) or 0)
                        out_tok = int(usage.get("outputTokens", 0) or 0)

                        in_p, out_p = get_model_prices_usd_per_1m(model_id)
                        in_cost = (in_tok / 1_000_000) * in_p
                        out_cost = (out_tok / 1_000_000) * out_p

                        self.batch_stats["chunks_done"] += 1
                        self.batch_stats["total_input_chars"] += len(chunk_text)
                        self.batch_stats["total_output_chars"] += len(trans)
                        self.batch_stats["total_input_tokens"] += in_tok
                        self.batch_stats["total_output_tokens"] += out_tok
                        self.batch_stats["total_input_cost_usd"] += in_cost
                        self.batch_stats["total_output_cost_usd"] += out_cost
                        self.batch_stats["total_cost_usd"] = self.batch_stats["total_input_cost_usd"] + self.batch_stats["total_output_cost_usd"]

                        self.log_to_js(f"✅ Hoàn thành đoạn {idx + 1}/{total}")
                        
                        elapsed = max(1, time.time() - self.batch_stats["start_time"])
                        done = self.batch_stats["chunks_done"]
                        eta = ((total - done) * (elapsed / done)) if done > 0 else 0
                        speed = (done / elapsed) * 60

                        self.update_progress_to_js({
                            "status": "running",
                            "chunks_done": done,
                            "total_chunks": total,
                            "percentage": round((done / total) * 100, 1),
                            "elapsed_seconds": int(elapsed),
                            "eta_seconds": int(eta),
                            "speed_cpm": round(speed, 1),
                            "total_input_chars": self.batch_stats["total_input_chars"],
                            "total_output_chars": self.batch_stats["total_output_chars"],
                            "total_tokens": self.batch_stats["total_input_tokens"] + self.batch_stats["total_output_tokens"],
                            "total_cost_usd": round(self.batch_stats["total_cost_usd"], 6),
                            "total_cost_vnd": round(self.batch_stats["total_cost_usd"] * USD_TO_VND, 0)
                        })

                        return idx, trans
                    except Exception as ex:
                        last_err = ex
                        self.log_to_js(f"⚠️ Đoạn {idx + 1} thử lại lần {attempt + 1} thất bại: {str(ex)[:100]}")
                        time.sleep(2 + attempt * 2)

                self.batch_stats["chunks_done"] += 1
                return idx, f"[LỖI ĐOẠN {idx + 1}: {last_err}]"

            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                futures = {executor.submit(process_chunk, i, chunks[i]): i for i in range(total)}
                for future in concurrent.futures.as_completed(futures):
                    if self.is_stopped:
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    idx, res = future.result()
                    if res is not None:
                        results[idx] = res

            if self.is_stopped:
                self.log_to_js("🛑 Quá trình dịch đã bị dừng.")
                self.update_progress_to_js({"status": "stopped"})
                status_str = "stopped"
                err_str = "Người dùng dừng giữa chừng."
            else:
                final_text = "\n\n".join([r for r in results if r is not None])
                with open(out_file, "w", encoding="utf-8") as f:
                    f.write(final_text)

                total_time = time.time() - self.batch_stats["start_time"]
                self.log_to_js(f"🎉 HOÀN TẤT DỊCH FILE! Lưu tại: {out_file}")
                self.log_to_js(f"📊 Tổng thời gian: {int(total_time)}s | Chi phí: ${self.batch_stats['total_cost_usd']:.4f}")

                self.update_progress_to_js({
                    "status": "completed",
                    "output_file": out_file,
                    "total_cost_usd": round(self.batch_stats["total_cost_usd"], 6),
                    "total_cost_vnd": round(self.batch_stats["total_cost_usd"] * USD_TO_VND, 0)
                })
                status_str = "completed"
                err_str = ""

            history_entry = {
                "engine": "AWS Bedrock",
                "status": status_str,
                "start_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.batch_stats["start_time"])),
                "end_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_seconds": int(time.time() - self.batch_stats["start_time"]),
                "input_file": in_file,
                "output_file": out_file,
                "model": model_id,
                "threads": threads,
                "temperature": temperature,
                "chunks_done": self.batch_stats["chunks_done"],
                "total_chunks": total,
                "total_input_chars": self.batch_stats["total_input_chars"],
                "total_output_chars": self.batch_stats["total_output_chars"],
                "total_input_tokens": self.batch_stats["total_input_tokens"],
                "total_output_tokens": self.batch_stats["total_output_tokens"],
                "total_input_cost_usd": round(self.batch_stats["total_input_cost_usd"], 6),
                "total_output_cost_usd": round(self.batch_stats["total_output_cost_usd"], 6),
                "total_cost_usd": round(self.batch_stats["total_cost_usd"], 6),
                "total_cost_vnd": round(self.batch_stats["total_cost_usd"] * USD_TO_VND, 0),
                "error": err_str
            }
            save_translation_history_entry(history_entry)

        except Exception as e:
            self.log_to_js(f"❌ Lỗi hệ thống: {str(e)}")
            self.update_progress_to_js({"status": "error", "error": str(e)})

        finally:
            self.batch_stats["start_time"] = 0
            self.is_stopped = False


import http.server
import socketserver

def start_local_server(directory):
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)
        def log_message(self, format, *args):
            pass

    server = socketserver.TCPServer(('127.0.0.1', 0), QuietHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return f"http://127.0.0.1:{port}/index.html"

def run_app():
    api = Api()
    try:
        url = start_local_server(BASE_DIR)
    except Exception:
        url = os.path.join(BASE_DIR, 'index.html')
    
    window = webview.create_window(
        title='AWSDichTruyen 3D Studio - Powered by AWS Bedrock',
        url=url,
        js_api=api,
        width=1380,
        height=900,
        min_size=(960, 680),
        resizable=True,
        background_color='#030712'
    )
    api.set_window(window)
    webview.start(debug=True)

if __name__ == '__main__':
    run_app()

