# DichTruyen - Bộ công cụ dịch truyện bằng AI

Dự án gồm 2 ứng dụng desktop (Tkinter) để dịch truyện `.txt` theo hướng thuần Việt, có hỗ trợ:
- Dịch đa luồng
- Tạm dừng / tiếp tục / dừng hẳn
- Resume tiến trình bằng checkpoint
- Lưu lịch sử dịch và thống kê chi phí

## 1) Cấu trúc dự án
- `AWSDichTruyen/`: app dịch bằng AWS Bedrock
- `GoogleDichTruyen/`: app dịch bằng Google Gemini

## 2) Bắt đầu nhanh (cho người mới)
Yêu cầu: Python 3.10+ trên Windows.

### Chạy app AWS Bedrock
1. Mở terminal tại thư mục `AWSDichTruyen`
2. Cài thư viện:
   ```powershell
   pip install boto3
   ```
3. Chạy app:
   ```powershell
   python AWSDichTruyen.py
   ```
4. Nhập API key Bedrock dạng `ABSK...`, chọn file `.txt`, bấm Bắt đầu dịch

### Chạy app Google Gemini
1. Mở terminal tại thư mục `GoogleDichTruyen`
2. Cài thư viện:
   ```powershell
   pip install google-generativeai
   ```
3. Chạy app:
   ```powershell
   python GoogleDichTruyen.py
   ```
4. Nhập Gemini API key, chọn file `.txt`, bấm Bắt đầu dịch

## 3) Tài liệu chi tiết từng app
- AWS: xem `AWSDichTruyen/HUONG_DAN_SU_DUNG.md`
- Google: xem `GoogleDichTruyen/HUONG_DAN_SU_DUNG.md`

## 4) Resume khi đang dịch dở
- Mỗi app tạo file checkpoint `*.resume.json` cạnh file input
- Mở app chạy lại sẽ được hỏi có muốn dịch tiếp không
- Dịch xong hoàn toàn thì checkpoint tự xóa

## 5) Lưu ý an toàn
- Không chia sẻ file `app_settings.json` (chứa dữ liệu cấu hình nhạy cảm)
- Không commit file lịch sử và checkpoint nếu không cần thiết
- Đã có `.gitignore` ở thư mục gốc để hạn chế đẩy nhầm dữ liệu quan trọng
