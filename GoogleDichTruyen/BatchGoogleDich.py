import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import os
import concurrent.futures
import time
import datetime
import json
import threading
import random
import base64
import hashlib
import re

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Minimal batch-focused Gemini app. Groups multiple chunks into one request
# and asks the model to return a JSON array of translations to reduce calls.
try:
    # Prefer canonical models/pricing from the existing Google implementation
    from GoogleDichTruyen import MODELS as GOOGLE_MODELS, MODEL_PRICING as GOOGLE_MODEL_PRICING
except Exception:
    GOOGLE_MODELS = None
    GOOGLE_MODEL_PRICING = None

if GOOGLE_MODELS:
    MODELS = GOOGLE_MODELS
else:
    MODELS = [
        "gemini-3-flash-preview",
        "gemini-3.1-pro-preview",
    ]

# Build a batch pricing table derived from canonical pricing (if available).
# Default discount applied to canonical rates to approximate batch pricing.
DEFAULT_CANONICAL_PRICING = {
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
}

CANONICAL_PRICING = GOOGLE_MODEL_PRICING or DEFAULT_CANONICAL_PRICING

# Apply a default batch discount (50%) to canonical rates. Adjust later if you
# have exact Google batch billing numbers.
BATCH_DISCOUNT = 0.5

def _build_batch_pricing(canonical, discount=BATCH_DISCOUNT):
    out = {}
    for m, v in canonical.items():
        nv = {}
        for k, val in v.items():
            try:
                nv[k] = float(val) * discount
            except Exception:
                nv[k] = val
        out[m] = nv
    return out

BATCH_MODEL_PRICING = _build_batch_pricing(CANONICAL_PRICING)

CHUNK_SIZE = 3000

def get_batch_prices_usd_per_1m(model_id, input_tokens=0):
    # Mirror logic of canonical helper: handle tiered pricing for specific models
    pricing = BATCH_MODEL_PRICING.get(model_id, {})
    # Example: gemini-3.1-pro-preview has tiered pricing keys
    if model_id == "gemini-3.1-pro-preview":
        if input_tokens <= 200_000:
            return pricing.get("input_per_1m_le_200k", 0.0), pricing.get("output_per_1m_le_200k", 0.0)
        return pricing.get("input_per_1m_gt_200k", 0.0), pricing.get("output_per_1m_gt_200k", 0.0)
    return pricing.get("input_per_1m", 0.0), pricing.get("output_per_1m", 0.0)
MAX_OUTPUT_TOKENS = 8192
DEFAULT_PROMPT = (
    "Bạn là một biên tập viên truyện dịch chuyên nghiệp, thành thạo tiếng Trung và tiếng Việt.\n"
    "Viết lại mỗi đoạn sau thành tiếng Việt tự nhiên, mượt, giống truyện, không thêm nội dung.\n"
)

is_paused = False
is_stopped = False
pause_event = threading.Event()
pause_event.set()

stats = {
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

USD_TO_VND = 27000

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_settings_batch_google.json")
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translation_history_batch_google.json")

def get_machine_key():
    unique_string = os.environ.get('COMPUTERNAME', 'PC') + os.environ.get('USERNAME', 'User') + "BatchGoogleDichSecret"
    return hashlib.sha256(unique_string.encode()).digest()

def xor_encrypt(data: str, key: bytes) -> str:
    if not data:
        return ""
    b = data.encode('utf-8')
    rep = (key * ((len(b) // len(key)) + 1))[:len(b)]
    res = bytes([a ^ b for a, b in zip(b, rep)])
    return base64.b64encode(res).decode('utf-8')

def xor_decrypt(data: str, key: bytes) -> str:
    if not data:
        return ""
    try:
        b = base64.b64decode(data.encode('utf-8'))
        rep = (key * ((len(b) // len(key)) + 1))[:len(b)]
        res = bytes([a ^ b for a, b in zip(b, rep)])
        return res.decode('utf-8')
    except Exception:
        return ""

def encrypt_api_key(api_key: str) -> str:
    return xor_encrypt(api_key, get_machine_key())

def decrypt_api_key(enc: str) -> str:
    return xor_decrypt(enc, get_machine_key())

def load_settings():
    default = {
        "api_key_encrypted": "",
        "input_file": "",
        "output_file": "",
        "model": MODELS[0],
        "threads": "3",
        "chunk_size": str(CHUNK_SIZE),
        "max_output_tokens": str(MAX_OUTPUT_TOKENS),
        "temperature": "0.5",
        "prompt": DEFAULT_PROMPT,
        "batch_size": "4",
        "theme": "dark",
    }
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                s = json.load(f)
                default.update(s)
                if s.get('api_key_encrypted'):
                    default['api_key'] = decrypt_api_key(s.get('api_key_encrypted'))
                else:
                    default['api_key'] = ''
    except Exception:
        pass
    return default

def save_settings():
    api = api_key_entry.get().strip()
    settings = {
        'api_key_encrypted': encrypt_api_key(api),
        'input_file': input_path.get(),
        'output_file': output_path.get(),
        'model': model_var.get(),
        'threads': thread_var.get(),
        'chunk_size': chunk_size_var.get(),
        'max_output_tokens': max_output_tokens_var.get(),
        'temperature': temp_var.get(),
        'prompt': prompt_text.get('1.0', tk.END).strip(),
        'batch_size': batch_size_var.get(),
        'theme': current_theme,
    }
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        add_log('💾 Đã lưu cài đặt batch Google')
    except Exception as e:
        add_log(f'Không lưu được: {e}')

def apply_settings(s):
    api_key_entry.insert(0, s.get('api_key', ''))
    input_path.set(s.get('input_file', ''))
    output_path.set(s.get('output_file', ''))
    model_var.set(s.get('model', MODELS[0]))
    thread_var.set(s.get('threads', '3'))
    chunk_size_var.set(s.get('chunk_size', str(CHUNK_SIZE)))
    max_output_tokens_var.set(s.get('max_output_tokens', str(MAX_OUTPUT_TOKENS)))
    temp_var.set(s.get('temperature', '0.5'))
    batch_size_var.set(s.get('batch_size', '4'))
    prompt_text.delete('1.0', tk.END)
    prompt_text.insert(tk.END, s.get('prompt', DEFAULT_PROMPT))

def get_checkpoint_path(input_file):
    return os.path.splitext(input_file)[0] + '.resume.batch.json'

def build_default_output_path(input_file):
    d = os.path.dirname(input_file)
    n = os.path.splitext(os.path.basename(input_file))[0]
    return os.path.join(d, f'Dich_{n}_{random.randint(1000,9999)}.txt')

def add_log(msg):
    ts = time.strftime('%H:%M:%S')
    s = f'[{ts}] {msg}\n'
    if 'log_box' in globals():
        try:
            log_box.config(state='normal')
            log_box.insert(tk.END, s)
            log_box.see(tk.END)
            log_box.config(state='disabled')
        except Exception:
            pass
    print(s.strip())

def save_checkpoint(cp_file, index, text):
    try:
        if os.path.exists(cp_file):
            with open(cp_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {}
        data[str(index)] = text
        with open(cp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        add_log(f'Lỗi khi save checkpoint: {e}')

def split_text(text, size=CHUNK_SIZE):
    chunks = []
    current = ''
    chapter_pattern = re.compile(r'^\s*(Chương\s+\d+|\d+\s*\||Quyển\s+\d+)', re.IGNORECASE)
    for line in text.splitlines(True):
        if chapter_pattern.match(line) and len(current) > 500:
            chunks.append(current)
            current = line
        elif len(current) + len(line) > size:
            if current.strip():
                chunks.append(current)
            current = line
        else:
            current += line
    if current.strip():
        chunks.append(current)
    return chunks

def extract_json_from_text(raw):
    if not raw:
        return None
    t = raw.strip()
    # Try to find first JSON array/object
    start = t.find('[')
    if start == -1:
        start = t.find('{')
    end = t.rfind(']') if '[' in t else t.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(t[start:end+1])
        except Exception:
            try:
                return json.loads(t[start:end+1].replace('\n', ' '))
            except Exception:
                return None
    return None

def batch_request_translate(model_id, prompt, chunks, temperature, max_output_tokens, api_key):
    """Send a single batched request: asks model to return a JSON list of {index, text}."""
    if genai is None:
        raise RuntimeError('Thiếu thư viện google-generativeai. pip install google-generativeai')

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name=model_id)

    # Build a compact prompt asking for JSON array
    numbered = []
    for i, c in enumerate(chunks):
        numbered.append({'i': i, 'text': c})

    # We'll include each chunk with a marker and request JSON output
    bundled = '\n\n'.join([f"[[CHUNK {item['i']}]]\n{item['text'].strip()}\n[[/CHUNK {item['i']}]]" for item in numbered])

    full_prompt = (
        prompt
        + "\n\nTôi sẽ gửi nhiều chunk, mỗi chunk được đánh dấu bằng [[CHUNK n]] ... [[/CHUNK n]]."
        + "\nNhiệm vụ: hãy trả về một mảng JSON hợp lệ gồm các object {\"i\": <n>, \"text\": \"dịch tiếng Việt của chunk\"}."
        + "\nKhông thêm diễn giải, không giải thích, chỉ trả JSON thuần. Giữ format escape hợp lệ."
        + "\n\n" + bundled
    )

    resp = model.generate_content(
        full_prompt,
        generation_config=genai.types.GenerationConfig(temperature=temperature, max_output_tokens=max_output_tokens),
    )

    # Try extract text
    raw = getattr(resp, 'text', '') or ''
    parsed = extract_json_from_text(raw)
    # Extract usage metadata if available
    usage = getattr(resp, 'usage_metadata', None)
    if usage is None and hasattr(resp, 'to_dict'):
        try:
            usage = resp.to_dict().get('usage_metadata')
        except Exception:
            usage = None

    def _safe_int(v):
        try:
            return int(v)
        except Exception:
            return 0

    in_tokens = 0
    out_tokens = 0
    if usage:
        if isinstance(usage, dict):
            in_tokens = _safe_int(usage.get('prompt_token_count') or usage.get('input_tokens') or 0)
            out_tokens = _safe_int(usage.get('candidates_token_count') or usage.get('output_tokens') or 0)
        else:
            try:
                ud = usage.to_dict()
                in_tokens = _safe_int(ud.get('prompt_token_count') or ud.get('input_tokens') or 0)
                out_tokens = _safe_int(ud.get('candidates_token_count') or ud.get('output_tokens') or 0)
            except Exception:
                pass

    if parsed is None:
        raise RuntimeError('Không parse được JSON trả về từ batch request')
    return parsed, in_tokens, out_tokens

def translate_worker_batch(bedrock_client, model_id, prompt, chunks_list, indices, cp_file, temperature, max_output_tokens, api_key):
    """Translate a group of chunks (batch) and return dict of index->text."""
    # chunks_list: list of chunk strings
    pause_event.wait()
    if is_stopped:
        return {}
    try:
        parsed, in_tokens, out_tokens = batch_request_translate(model_id, prompt, chunks_list, temperature, max_output_tokens, api_key)
        results = {}
        # Map parsed results to global indices
        for obj in parsed:
            try:
                idx = int(obj.get('i'))
                text = obj.get('text', '').strip()
                global_idx = indices[idx]
                results[global_idx] = text
                save_checkpoint(cp_file, global_idx, text)
            except Exception:
                continue

        # If token usage is available, distribute tokens/costs proportionally
        try:
            if in_tokens or out_tokens:
                total_input_len = sum(len(c) for c in chunks_list) or 1
                total_output_len = sum(len(results.get(g, '')) for g in indices) or 1
                input_price_per_1m, output_price_per_1m = get_batch_prices_usd_per_1m(model_id, in_tokens)

                for local_pos, global_idx in enumerate(indices):
                    in_share = len(chunks_list[local_pos]) / total_input_len
                    out_share = len(results.get(global_idx, '')) / total_output_len
                    in_tok_chunk = int(round(in_tokens * in_share))
                    out_tok_chunk = int(round(out_tokens * out_share))
                    in_cost = (in_tok_chunk / 1_000_000) * input_price_per_1m
                    out_cost = (out_tok_chunk / 1_000_000) * output_price_per_1m

                    stats['total_input_tokens'] += in_tok_chunk
                    stats['total_output_tokens'] += out_tok_chunk
                    stats['total_input_cost_usd'] += in_cost
                    stats['total_output_cost_usd'] += out_cost
                    stats['total_cost_usd'] = stats['total_input_cost_usd'] + stats['total_output_cost_usd']
        except Exception:
            pass

        return results
    except Exception as e:
        add_log(f'⚠️ Batch lỗi: {e}')
        # Mark each as failed
        return {gi: f'[LỖI BATCH: {e}]' for gi in indices}

def toggle_pause():
    global is_paused
    if is_paused:
        is_paused = False
        pause_event.set()
        btn_pause.config(text='⏸️ TẠM DỪNG', bg='#FFC107')
        add_log('▶️ Tiếp tục')
    else:
        is_paused = True
        pause_event.clear()
        btn_pause.config(text='▶️ TIẾP TỤC', bg='#4CAF50')
        add_log('⏸️ Tạm dừng')

def stop_translation():
    global is_stopped, is_paused
    if messagebox.askyesno('Xác nhận', 'Bạn có chắc muốn dừng?'):
        is_stopped = True
        is_paused = False
        pause_event.set()
        add_log('🛑 Dừng dịch')

def start_translation():
    global is_stopped, is_paused
    is_stopped = False
    is_paused = False
    pause_event.set()

    if genai is None:
        messagebox.showerror('Thiếu thư viện', 'Cài google-generativeai: pip install google-generativeai')
        return

    api_key = api_key_entry.get().strip()
    if not api_key:
        messagebox.showerror('Lỗi', 'Nhập Gemini API Key')
        return

    if not input_path.get() or not os.path.isfile(input_path.get()):
        messagebox.showerror('Lỗi', 'Chọn file input hợp lệ')
        return

    try:
        threads = int(thread_var.get())
        batch_size = int(batch_size_var.get())
        chunk_size = int(chunk_size_var.get())
        max_output = int(max_output_tokens_var.get())
        temp = float(temp_var.get())
    except Exception:
        messagebox.showerror('Lỗi', 'Thông số không hợp lệ')
        return

    output_path.set(build_default_output_path(input_path.get()))
    save_settings()
    task = threading.Thread(target=process_translation_logic, daemon=True)
    task.start()
    stats_thread = threading.Thread(target=stats_update_loop, daemon=True)
    stats_thread.start()
    add_log('🚀 Bắt đầu batch dịch')

def stats_update_loop():
    while not is_stopped and btn_start['state'] == 'disabled':
        update_stats_display()
        time.sleep(1)

def process_translation_logic():
    global is_stopped
    btn_start.config(state='disabled')
    btn_pause.config(state='normal')
    btn_stop.config(state='normal')

    stats['start_time'] = time.time()
    stats['chunks_done'] = 0
    stats['total_input_chars'] = 0
    stats['total_output_chars'] = 0

    in_file = input_path.get()
    out_file = output_path.get()
    cp_file = get_checkpoint_path(in_file)

    try:
        with open(in_file, 'r', encoding='utf-8') as f:
            chunks = split_text(f.read(), size=int(chunk_size_var.get()))

        total = len(chunks)
        stats['total_chunks'] = total
        try:
            progress_bar['maximum'] = total
            progress_bar['value'] = stats.get('chunks_done', 0)
        except Exception:
            pass
        results = [None] * total

        # resume
        if os.path.exists(cp_file):
            with open(cp_file, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            if messagebox.askyesno('Khôi phục', f'Tìm thấy checkpoint {len(saved)}/{total}. Dịch tiếp?'):
                for k, v in saved.items():
                    results[int(k)] = v
                stats['chunks_done'] = len(saved)

        pending = [i for i in range(total) if results[i] is None]
        add_log(f'📦 Tổng chunk: {total}. Còn lại: {len(pending)}')

        api_key = api_key_entry.get().strip()
        model_id = model_var.get()
        batch_size = int(batch_size_var.get())
        temperature = float(temp_var.get())
        max_output = int(max_output_tokens_var.get())
        threads = int(thread_var.get())

        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            futures = []
            # create batches of indices
            for i in range(0, len(pending), batch_size):
                batch_indices = pending[i:i+batch_size]
                batch_chunks = [chunks[j] for j in batch_indices]
                futures.append(executor.submit(translate_worker_batch, None, model_id, prompt_text.get('1.0', tk.END).strip(), batch_chunks, batch_indices, cp_file, temperature, max_output, api_key))

            for fut in concurrent.futures.as_completed(futures):
                if is_stopped:
                    break
                res = fut.result()
                for idx, txt in res.items():
                    results[idx] = txt
                    stats['chunks_done'] += 1
                    stats['total_input_chars'] += len(chunks[idx])
                    stats['total_output_chars'] += len(txt)
                    progress_bar['value'] = stats['chunks_done']
                    root.update_idletasks()

        if is_stopped:
            add_log('🛑 Đã dừng. Tiến trình lưu tại checkpoint')
            return

        with open(out_file, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join([r for r in results if r is not None]))

        if os.path.exists(cp_file):
            os.remove(cp_file)

        total_time = time.time() - stats['start_time']
        add_log(f'🎉 Hoàn thành trong {total_time:.1f}s')
        messagebox.showinfo('Hoàn thành', f'Hoàn tất. Lưu: {out_file}')

    except Exception as e:
        add_log(f'🛑 Lỗi: {e}')
        messagebox.showerror('Lỗi', str(e))

    finally:
        btn_start.config(state='normal')
        btn_pause.config(state='disabled')
        btn_stop.config(state='disabled')
        is_stopped = True

def update_stats_display():
    if stats['total_chunks'] == 0:
        return
    elapsed = time.time() - stats['start_time']
    done = stats['chunks_done']
    total = stats['total_chunks']
    stats_time_var.set(f"⏱️ Đã chạy: {format_time(elapsed)}")
    stats_eta_var.set(f"⏳ Còn lại: {format_time((elapsed/done)*(total-done) if done>0 else -1)}")
    stats_chars_var.set(f"📝 Ký tự: {stats['total_input_chars']:,} → {stats['total_output_chars']:,}")

def format_time(s):
    if s < 0:
        return '--:--'
    m = int(s // 60)
    sec = int(s % 60)
    return f"{m:02d}:{sec:02d}"

# ---------------- GUI (gọn nhẹ) ----------------
root = tk.Tk()
root.title('Batch Google DichTruyen')
root.geometry('1000x700')

style = ttk.Style()
style.theme_use('clam')

input_path = tk.StringVar()
output_path = tk.StringVar()
model_var = tk.StringVar(value=MODELS[0])
thread_var = tk.StringVar(value='3')
chunk_size_var = tk.StringVar(value=str(CHUNK_SIZE))
max_output_tokens_var = tk.StringVar(value=str(MAX_OUTPUT_TOKENS))
temp_var = tk.StringVar(value='0.5')
batch_size_var = tk.StringVar(value='4')

main = ttk.Frame(root)
main.pack(fill='both', expand=True, padx=12, pady=12)

top = ttk.Frame(main)
top.pack(fill='x')

tk.Label(top, text='API Key').pack(side='left')
api_key_entry = tk.Entry(top, width=60, show='*')
api_key_entry.pack(side='left', padx=6)
tk.Button(top, text='Chọn file', command=lambda: input_path.set(filedialog.askopenfilename(filetypes=[('Text files','*.txt')]))).pack(side='right')

file_frame = ttk.Frame(main)
file_frame.pack(fill='x', pady=8)
tk.Label(file_frame, text='Input').grid(row=0, column=0, sticky='w')
tk.Entry(file_frame, textvariable=input_path, width=80).grid(row=0, column=1, sticky='ew')
tk.Label(file_frame, text='Output').grid(row=1, column=0, sticky='w')
tk.Entry(file_frame, textvariable=output_path, width=80).grid(row=1, column=1, sticky='ew')

cfg = ttk.Frame(main)
cfg.pack(fill='x', pady=6)
tk.Label(cfg, text='Model').grid(row=0, column=0)
ttk.Combobox(cfg, values=MODELS, textvariable=model_var).grid(row=0, column=1)
tk.Label(cfg, text='Threads').grid(row=0, column=2)
tk.Entry(cfg, textvariable=thread_var, width=6).grid(row=0, column=3)
tk.Label(cfg, text='Batch size').grid(row=0, column=4)
tk.Entry(cfg, textvariable=batch_size_var, width=6).grid(row=0, column=5)

prompt_frame = ttk.Frame(main)
prompt_frame.pack(fill='both', expand=True)
prompt_text = tk.Text(prompt_frame, height=6)
prompt_text.pack(fill='both', expand=True)
prompt_text.insert(tk.END, DEFAULT_PROMPT)

control = ttk.Frame(main)
control.pack(fill='x', pady=6)
btn_start = tk.Button(control, text='🚀 Bắt đầu', bg='#34d399', command=start_translation)
btn_start.pack(side='left', padx=6)
btn_pause = tk.Button(control, text='⏸️ Tạm dừng', bg='#fbbf24', state='disabled', command=toggle_pause)
btn_pause.pack(side='left', padx=6)
btn_stop = tk.Button(control, text='🛑 Dừng', bg='#f87171', state='disabled', command=stop_translation)
btn_stop.pack(side='left', padx=6)
btn_save = tk.Button(control, text='💾 Lưu cài đặt', command=save_settings)
btn_save.pack(side='right')

progress_bar = ttk.Progressbar(main, length=600)
progress_bar.pack(fill='x', pady=6)

log_box = scrolledtext.ScrolledText(main, height=10, state='disabled')
log_box.pack(fill='both', expand=True)

stats_time_var = tk.StringVar(value='⏱️ Đã chạy: --:--')
stats_eta_var = tk.StringVar(value='⏳ Còn lại: --:--')
stats_chars_var = tk.StringVar(value='📝 Ký tự: -- → --')
tk.Label(main, textvariable=stats_time_var).pack(anchor='w')
tk.Label(main, textvariable=stats_eta_var).pack(anchor='w')
tk.Label(main, textvariable=stats_chars_var).pack(anchor='w')

# Load saved settings
apply_settings(load_settings())

root.protocol('WM_DELETE_WINDOW', lambda: (save_settings(), root.destroy()))

if __name__ == '__main__':
    root.mainloop()
