# Hướng dẫn sử dụng DeepSeekDichTruyen

## 1) Mục đích
`DeepSeekDichTruyen.py` là app GUI (Tkinter) để dịch truyện `.txt` bằng DeepSeek API, có:
- Chia chunk thông minh theo chương/đoạn
- Dịch đa luồng
- Tạm dừng / tiếp tục / dừng hẳn
- Resume tiến trình bằng checkpoint
- Theo dõi lịch sử và chi phí (USD + VNĐ)
- Thống kê chi tiết yêu cầu của từng model

## 2) Yêu cầu môi trường
- Windows + Python 3.10+ (khuyến nghị)
- Không yêu cầu cài đặt thêm thư viện AI nào khác (sử dụng thư viện standard `urllib` của Python).
- Nếu sử dụng tính năng upload Google Drive (tùy chọn), cài đặt các thư viện sau:
  ```powershell
  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
  ```

## 3) Cách chạy app
Mở terminal tại thư mục `DeepSeekDichTruyen` rồi chạy:
```powershell
python DeepSeekDichTruyen.py
```

## 4) Chuẩn bị trước khi dịch
### API key
- Nhập **DeepSeek API Key** lấy từ platform.deepseek.com.
- Hỗ trợ quản lý và lưu trữ nhiều API Key khác nhau. Bạn có thể chọn nhanh từ thanh chọn, đổi tên, thêm mới hoặc xóa key.
- Key được mã hóa khi lưu trong `app_settings.json` (ưu tiên dùng lại trên cùng máy/user).

### File đầu vào
- Chọn file truyện `.txt` trong tab **Dịch truyện**.
- Output tạo tự động cùng thư mục input theo dạng:
  - `Dich_tenfile_XXXX.txt`

## 5) Các giới hạn tham số (app sẽ kiểm tra)
- **Số luồng**: `1` đến `20`
- **Chunk size**: `500` đến `70000` (Khuyến nghị dùng khoảng `3000` đến `5000` đối với DeepSeek để tối ưu chất lượng dịch)
- **Max output tokens**: `256` đến `70000`
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

Nếu nhập ngoài khoảng giới hạn, app sẽ báo lỗi trước khi chạy.

## 6) Quy trình dịch
1. Chọn hoặc thêm mới/đổi tên DeepSeek API key phù hợp
2. Chọn file input `.txt`
3. Chọn model (`deepseek-v4-flash`, `deepseek-v4-pro`, ...), số luồng, chunk size, max output tokens, nhiệt độ
4. Chọn hoặc thêm mới/đổi tên Prompt dịch giả trong ô **Prompt dịch giả**
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
- **💰 Thống kê chi phí**: tổng hợp chi phí theo tháng/tuần, có cả VNĐ (được chia chi tiết theo Cache-Hit và Cache-Miss đối với DeepSeek)

## 9) File dữ liệu app
- `app_settings.json`: lưu cấu hình lần gần nhất
- `translation_history.json`: lịch sử dịch
- `*.resume.json`: checkpoint theo từng file truyện

## 10) Lỗi thường gặp & cách xử lý
### Lỗi API / giới hạn quota
- Giảm **Số luồng**
- Giảm **Chunk size**
- Giảm **Max output tokens**
- Đổi sang model khác hoặc kiểm tra lại số dư tài khoản DeepSeek.

### Không chọn được file hoặc lỗi đọc file
- Đảm bảo file input tồn tại
- Nên dùng file UTF-8 để giảm lỗi ký tự

## 11) Lưu ý an toàn
- Không chia sẻ `app_settings.json` và `translation_history.json`.
- Không commit dữ liệu nhạy cảm lên Git.
