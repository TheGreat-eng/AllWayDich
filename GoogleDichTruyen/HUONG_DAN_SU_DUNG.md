# Hướng dẫn sử dụng GoogleDichTruyen

## 1) Mục đích
`GoogleDichTruyen.py` là app GUI (Tkinter) để dịch truyện `.txt` bằng Google Gemini, có:
- Chia chunk thông minh theo chương/đoạn
- Dịch đa luồng
- Tạm dừng / tiếp tục / dừng hẳn
- Resume tiến trình bằng checkpoint
- Theo dõi lịch sử và chi phí (USD + VNĐ)

## 2) Yêu cầu môi trường
- Windows + Python 3.10+ (khuyến nghị)
- Thư viện Python:
  - `google-generativeai`

Cài thư viện:
```powershell
pip install google-generativeai
```

## 3) Cách chạy app
Mở terminal tại thư mục `GoogleDichTruyen` rồi chạy:
```powershell
python GoogleDichTruyen.py
```

## 4) Chuẩn bị trước khi dịch
### API key
- Nhập **Gemini API Key** lấy từ Google AI Studio.
- Key được mã hóa khi lưu trong `app_settings.json` (ưu tiên dùng lại trên cùng máy/user).

### File đầu vào
- Chọn file truyện `.txt` trong tab **Dịch truyện**.
- Output tạo tự động cùng thư mục input theo dạng:
  - `Dich_tenfile_XXXX.txt`

## 5) Các giới hạn tham số (app sẽ kiểm tra)
- **Số luồng**: `1` đến `20`
- **Chunk size**: `500` đến `50000`
- **Max output tokens**: `256` đến `65536`
- **Nhiệt độ**: `0` đến `1`

### Glossary/Từ điển thuật ngữ
- Có ô nhập riêng trong phần **Prompt dịch giả** để giữ nhất quán tên riêng, cảnh giới, xưng hô.
- Cú pháp mỗi dòng:
  - `nguồn => đích`
  - hoặc `nguồn -> đích`
  - hoặc `nguồn: đích`
- Ví dụ:
  - `筑基 => Trúc Cơ`
  - `师兄 => sư huynh`
  - `本座 => bổn tọa`
- Dòng trống hoặc dòng bắt đầu bằng `#` sẽ được bỏ qua.
- Glossary được lưu cùng cài đặt và tự áp vào prompt khi bấm dịch.

Nếu nhập ngoài khoảng này, app sẽ báo lỗi trước khi chạy.

## 6) Quy trình dịch
1. Nhập Gemini API key
2. Chọn file input `.txt`
3. Chọn model, số luồng, chunk size, max output tokens, nhiệt độ
4. (Tuỳ chọn) chỉnh prompt trong ô **Prompt dịch giả**
5. Bấm **🚀 BẮT ĐẦU DỊCH**

Trong lúc dịch:
- **⏸️ TẠM DỪNG**: dừng tạm tất cả luồng
- **▶️ TIẾP TỤC**: chạy lại
- **🛑 DỪNG HẲN**: dừng và giữ tiến trình để resume

## 7) Resume / checkpoint
- App tạo file checkpoint cạnh file input:
  - `tenfile.resume.json`
- Mở lại app và chạy dịch, nếu có checkpoint app sẽ hỏi dịch tiếp.
- Khi hoàn tất toàn bộ, checkpoint bị xóa.

## 8) Ý nghĩa các tab
- **🚀 Dịch truyện**: cấu hình + điều khiển chạy
- **🔍 Xem Chunk**: tải và xem trước các chunk sau khi chia
- **🗂️ Lịch sử dịch**: xem trạng thái, token, chi phí từng lần dịch
- **💰 Thống kê chi phí**: tổng hợp theo tháng/tuần, có cả VNĐ

## 9) File dữ liệu app
- `app_settings.json`: lưu cấu hình lần gần nhất
- `translation_history.json`: lịch sử dịch
- `*.resume.json`: checkpoint theo từng file truyện

## 10) Lỗi thường gặp & cách xử lý
### Báo thiếu thư viện `google-generativeai`
- Cài lại:
```powershell
pip install google-generativeai
```

### Gemini trả về rỗng / lỗi API / giới hạn quota
- Giảm **Số luồng**
- Giảm **Chunk size**
- Giảm **Max output tokens**
- Đổi model khác
- Kiểm tra API key và hạn mức tài khoản

### Không chọn được file hoặc lỗi đọc file
- Đảm bảo file input tồn tại
- Nên dùng file UTF-8 để giảm lỗi ký tự

## 11) Lưu ý an toàn
- Không chia sẻ `app_settings.json` và `translation_history.json`.
- Không commit dữ liệu nhạy cảm lên Git.
