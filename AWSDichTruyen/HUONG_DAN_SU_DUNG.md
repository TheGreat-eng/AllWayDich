# Hướng dẫn sử dụng AWSDichTruyen

## 1) Mục đích
`AWSDichTruyen.py` là app GUI (Tkinter) để dịch truyện `.txt` bằng AWS Bedrock, có:
- Chia văn bản thành chunk
- Dịch đa luồng
- Tạm dừng / tiếp tục / dừng hẳn
- Resume khi app bị dừng giữa chừng
- Lưu lịch sử và thống kê chi phí

## 2) Yêu cầu môi trường
- Windows + Python 3.10+ (khuyến nghị)
- Thư viện Python:
  - `boto3`

Cài thư viện:
```powershell
pip install boto3
```

## 3) Cách chạy app
Mở terminal tại thư mục `AWSDichTruyen` rồi chạy:
```powershell
python AWSDichTruyen.py
```

## 4) Chuẩn bị trước khi dịch
### API key
- Nhập **Bedrock API Key** bắt đầu bằng `ABSK`.
- App sẽ lưu key dưới dạng mã hóa vào `app_settings.json` (chỉ dùng lại tốt trên cùng máy/user).

### File đầu vào
- Chọn file truyện `.txt` ở mục **Chọn file nguồn / đích**.
- File output sẽ tự sinh cùng thư mục input, dạng:
  - `Dich_tenfile_XXXX.txt`

## 5) Các thông số quan trọng
- **Model**: chọn model Bedrock trong danh sách app.
- **Số luồng**: số request chạy song song (nên tăng từ từ để tránh lỗi API/quota).
- **Chunk size**: kích thước mỗi đoạn dịch.
  - Hợp lệ: `500` đến `50000`
- **Max output tokens**: giới hạn token đầu ra.
  - Hợp lệ: `256` đến `65536`
- **Nhiệt độ**: mức sáng tạo (0-1).

## 6) Quy trình dịch
1. Nhập API key + chọn file input
2. Chọn model và thông số
3. (Tuỳ chọn) chỉnh prompt trong ô **Prompt dịch giả**
4. Bấm **🚀 BẮT ĐẦU DỊCH**
5. Theo dõi tiến độ ở thanh progress + nhật ký

Trong lúc chạy:
- **⏸️ TẠM DỪNG**: tạm ngưng tất cả luồng
- **▶️ TIẾP TỤC**: chạy lại
- **🛑 DỪNG HẲN**: dừng và giữ tiến trình để resume

## 7) Cơ chế Resume (dịch tiếp)
- App tạo file checkpoint cạnh file input:
  - `tenfile.resume.json`
- Khi chạy lại, nếu thấy checkpoint, app hỏi có dịch tiếp không.
- Dịch xong hoàn toàn, checkpoint sẽ bị xóa.

## 8) Các tab trong giao diện
- **🚀 Dịch truyện**: cấu hình + chạy dịch
- **👀 Xem Chunk**: xem trước cách văn bản bị chia chunk
- **🗂️ Lịch sử dịch**: các lần dịch gần nhất, trạng thái, token, chi phí
- **💰 Thống kê chi phí**: tổng hợp theo tháng/tuần

## 9) File dữ liệu app
- `app_settings.json`: lưu cấu hình lần gần nhất
- `translation_history.json`: lịch sử dịch
- `*.resume.json`: checkpoint tạm thời theo từng file input

## 10) Lỗi thường gặp & cách xử lý
### "Vui lòng nhập mã API Key ABSK chính xác"
- Kiểm tra key Bedrock đúng định dạng `ABSK...`

### Lỗi khi gọi model / timeout / quota
- Giảm **Số luồng**
- Giảm **Chunk size**
- Đổi model khác trong danh sách
- Kiểm tra quyền truy cập model trong AWS Bedrock

### App báo lỗi file
- Đảm bảo file input tồn tại và đọc được
- Nên dùng file mã hóa UTF-8 để tránh lỗi ký tự

## 11) Lưu ý an toàn
- Không chia sẻ `app_settings.json` (dù key được mã hóa vẫn là dữ liệu nhạy cảm).
- Không commit file lịch sử và file checkpoint nếu làm việc với Git.
