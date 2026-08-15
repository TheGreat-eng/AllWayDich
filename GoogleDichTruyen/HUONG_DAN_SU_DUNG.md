# Hướng dẫn sử dụng GoogleDichTruyen

## 1) Mục đích
`GoogleDichTruyen` là ứng dụng GUI chuyên nghiệp để dịch truyện `.txt` bằng Google Gemini AI, có:
- Giao diện CustomTkinter hiện đại, hỗ trợ Dark / Light mode linh hoạt
- Tách module sạch sẽ (`core/`, `ui/`) dễ dàng mở rộng & nâng cấp
- Chia chunk thông minh theo chương/đoạn
- Dịch đa luồng
- Tạm dừng / tiếp tục / dừng hẳn
- Resume tiến trình bằng checkpoint
- Quản lý từ điển Glossary & tự động scan thuật ngữ AI
- Xem, sửa & dịch lại từng chunk bị lỗi
- Theo dõi lịch sử dịch và chi phí chi tiết (USD + VNĐ)

## 2) Yêu cầu môi trường
- Windows + Python 3.10+ (khuyến nghị)
- Thư viện Python:
  - `google-genai`
  - `customtkinter`

Cài thư viện:
```powershell
pip install google-genai customtkinter
```

## 3) Cách chạy app
Mở terminal tại thư mục `GoogleDichTruyen` rồi chạy phiên bản CustomTkinter giao diện mới:
```powershell
python app.py
```

*(Lưu ý: Bạn vẫn có thể chạy `python GoogleDichTruyen.py` nếu muốn dùng phiên bản Tkinter truyền thống)*

## 4) Chuẩn bị trước khi dịch
### API key
- Nhập **Gemini API Key** lấy từ Google AI Studio.
- Key được mã hóa an toàn bằng khóa máy khi lưu trong `app_settings.json`.

### File đầu vào
- Chọn file truyện `.txt` trong tab **Dịch truyện**.
- Output tạo tự động cùng thư mục input theo dạng:
  - `Dich_tenfile_XXXX.txt`

## 5) Glossary / Từ điển thuật ngữ
- Có ô nhập riêng trong phần **Prompt dịch giả** để giữ nhất quán tên riêng, cảnh giới, xưng hô.
- Cú pháp mỗi dòng:
  - `nguồn => đích` (ví dụ: `筑基 => Trúc Cơ`, `师兄 => sư huynh`)
- Bấm **🔍 Scan Truyện** để AI tự động trích xuất các thuật ngữ quan trọng trong tác phẩm.

## 6) Quy trình dịch
1. Nhập Gemini API key
2. Chọn file input `.txt`
3. Chọn model, số luồng, chunk size, nhiệt độ
4. Bấm **🚀 BẮT ĐẦU DỊCH**

Trong lúc dịch:
- **⏸️ TẠM DỪNG**: dừng tạm tất cả luồng
- **▶️ TIẾP TỤC**: chạy lại
- **🛑 DỪNG HẲN**: dừng và giữ tiến trình để resume
