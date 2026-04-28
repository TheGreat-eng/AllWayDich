# DichTruyen - Bộ công cụ dịch truyện bằng AI trên Windows

DichTruyen là bộ ứng dụng desktop Tkinter chuyên dịch truyện `.txt` sang tiếng Việt thuần, ưu tiên văn phong tự nhiên, mượt và giữ đúng ý nghĩa gốc. Dự án có nhiều app riêng cho từng nhà cung cấp hoặc kiểu triển khai, cùng chung một triết lý:

- Dịch theo chunk để xử lý file lớn ổn định
- Chạy đa luồng để tăng tốc
- Có thể tạm dừng, tiếp tục và dừng hẳn
- Có cơ chế checkpoint để resume khi đang dịch dở
- Lưu lịch sử dịch và thống kê token/chi phí
- Cho phép chỉnh prompt, glossary và các tham số dịch
- Có giao diện tối/sáng, cài đặt được lưu lại theo từng app

## Tổng quan nhanh

Trong repo hiện có các app sau:

- `AWSDichTruyen/`: dịch bằng AWS Bedrock
- `GoogleDichTruyen/`: dịch bằng Google Gemini
- `ClaudeDichTruyen/`: dịch bằng Anthropic Claude qua proxy
- `DeepSeekDichTruyen/`: dịch bằng DeepSeek API
- `AiLocal/`: dịch bằng local API trên máy của bạn
- `CLIProxyDichTruyen/`: dịch qua VPS + refresh token theo kiểu proxy/CLI
- `MultiProviderAi/`: app đa nhà cung cấp, đổi provider ngay trong cùng một giao diện

Ngoài ra, trong `GoogleDichTruyen/` còn có biến thể `GoogleDichTruyenRateLimit.py` dành cho luồng xử lý/chia đoạn có kiểm soát chặt hơn.

## Tính năng chung của các app

Phần lớn các app trong repo có chung các chức năng sau:

- Chọn file truyện `.txt` đầu vào và tự sinh file đầu ra
- Chia văn bản thành các chunk theo độ dài cấu hình được
- Dịch song song bằng nhiều thread
- Tạm dừng, tiếp tục, dừng hẳn trong lúc đang chạy
- Tự lưu checkpoint để resume sau khi đóng app hoặc gặp sự cố
- Lưu lịch sử dịch để xem lại lần chạy trước
- Thống kê số chunk đã dịch, số token, chi phí ước tính và trạng thái chạy
- Cho phép chỉnh prompt dịch giả để đổi văn phong hoặc độ nhất quán thuật ngữ
- Hỗ trợ theme tối/sáng ở nhiều app

## Mô tả từng app

### 1) `AWSDichTruyen/` - AWS Bedrock

App này dùng AWS Bedrock để dịch truyện bằng các model Bedrock được cấu hình sẵn trong giao diện. Đây là bản phù hợp nếu bạn đã có tài khoản AWS và quyền truy cập model Bedrock.

Điểm nổi bật:

- Nhập API key AWS Bedrock
- Chọn model Bedrock từ danh sách có sẵn
- Dịch đa luồng theo chunk
- Có checkpoint resume
- Có lịch sử dịch và thống kê chi phí
- Lưu API key theo dạng mã hóa trong `app_settings.json`

Phù hợp khi:

- Bạn muốn chạy trên hạ tầng AWS
- Bạn có sẵn quyền truy cập model Bedrock
- Bạn cần app GUI đơn giản, ổn định cho file `.txt`

### 2) `GoogleDichTruyen/` - Google Gemini

App này dịch truyện bằng Google Gemini, có đầy đủ luồng xử lý dịch file lớn, quản lý lịch sử và chi phí. Đây là một trong những bản hoàn thiện nhất của repo về mặt tính năng dịch truyện.

Điểm nổi bật:

- Dùng Gemini API key từ Google AI Studio
- Có ô nhập glossary để map thuật ngữ nhất quán như cảnh giới, xưng hô, tên riêng
- Chia chunk thông minh theo đoạn/chương
- Dịch đa luồng
- Có checkpoint resume
- Theo dõi lịch sử dịch và chi phí USD + VNĐ
- Có các tab xem chunk, lịch sử, thống kê chi phí
- Lưu key mã hóa trong cấu hình

Phù hợp khi:

- Bạn muốn dùng Gemini làm engine chính
- Bạn cần giao diện có nhiều tab để kiểm soát tiến trình dịch
- Bạn muốn theo dõi chi phí tương đối sát trong từng lần dịch

### 3) `GoogleDichTruyen/GoogleDichTruyenRateLimit.py` - biến thể Gemini có kiểm soát rate-limit

Đây là biến thể riêng của app Gemini, thiên về xử lý an toàn hơn khi quét thuật ngữ hoặc làm việc với văn bản lớn.

Điểm đáng chú ý:

- Vẫn là giao diện Tkinter cho Gemini
- Có `scan_char_limit` để giới hạn số ký tự quét thuật ngữ
- Có các kiểm tra giới hạn cho chunk size và scan limit
- Phù hợp khi bạn muốn kiểm soát tải request chặt hơn

Nếu bạn hay gặp giới hạn quota, nghẽn request hoặc muốn cấu hình quét thuật ngữ thận trọng hơn, bản này là lựa chọn nên xem.

### 4) `ClaudeDichTruyen/` - Anthropic Claude qua proxy

App này dùng Claude thông qua endpoint proxy `https://1gw.gwai.cloud/v1/messages`, nên không gọi trực tiếp Claude API theo kiểu thông thường. Đây là bản dành cho người dùng có nguồn key phù hợp với proxy đang được tích hợp sẵn trong code.

Điểm nổi bật:

- Chọn trong các model Claude đang được cấu hình sẵn
- Lưu API key mã hóa trong `app_settings.json`
- Dịch đa luồng theo chunk
- Có checkpoint resume
- Có lịch sử dịch và thống kê chi phí
- Giao diện Tkinter riêng theo tông Claude

Phù hợp khi:

- Bạn muốn dùng Claude nhưng đang đi qua proxy được dự án hỗ trợ
- Bạn muốn giữ workflow giống các app còn lại trong repo

### 5) `DeepSeekDichTruyen/` - DeepSeek API

App này tích hợp DeepSeek API, có cách tính chi phí riêng theo cache-hit/cache-miss và hỗ trợ theo dõi token chi tiết hơn một số bản khác.

Điểm nổi bật:

- Nhập DeepSeek API key
- Chọn model DeepSeek trong danh sách có sẵn
- Dịch đa luồng
- Có checkpoint resume
- Có lịch sử dịch và thống kê chi phí
- Có xử lý giá cache-hit/cache-miss khi ước tính chi phí
- Lưu key mã hóa theo máy/user

Phù hợp khi:

- Bạn dùng DeepSeek thường xuyên
- Bạn cần ước tính chi phí theo token tương đối sát

### 6) `AiLocal/` - local AI trên máy cá nhân

Đây là app dành cho mô hình local chạy trên máy bạn, mặc định gọi endpoint kiểu OpenAI-compatible ở `http://localhost:1234/v1/chat/completions`.

Điểm nổi bật:

- Không cần API key cloud nếu backend local của bạn không yêu cầu
- Có thể đổi endpoint local
- Có danh sách model local gợi ý sẵn
- Có prompt, glossary, chunk size, số luồng, max output tokens và nhiệt độ
- Lưu cài đặt riêng trong `app_settings_local.json`
- Có lịch sử dịch riêng `translation_history_local.json`

Phù hợp khi:

- Bạn muốn chạy offline hoặc gần như offline
- Bạn có sẵn local server như LM Studio, Ollama bridge, hoặc dịch vụ OpenAI-compatible khác

### 7) `CLIProxyDichTruyen/` - proxy qua VPS + refresh token

App này có hướng triển khai khác với các app API trực tiếp. Nó dùng VPS và refresh token để đi qua một lớp proxy, phù hợp khi bạn muốn chạy theo mô hình trung gian thay vì nhập key trực tiếp cho từng provider.

Điểm nổi bật:

- Nhập địa chỉ VPS
- Nhập refresh token
- Chọn model
- Dịch theo chunk, đa luồng
- Có giao diện Tkinter riêng để quản lý kết nối proxy
- Lưu trạng thái và cấu hình riêng

Phù hợp khi:

- Bạn có hạ tầng proxy riêng
- Bạn muốn luồng xử lý tập trung qua VPS

### 8) `MultiProviderAi/` - app đa nhà cung cấp

Đây là bản tổng hợp mạnh nhất trong repo: một giao diện có thể đổi provider ngay trong app, thay vì phải mở từng app riêng lẻ.

Provider hiện có:

- Gemini
- Claude
- ChatGPT/OpenAI
- Grok/xAI
- DeepSeek
- Qwen

Điểm nổi bật:

- Chọn provider ngay trong giao diện
- Mỗi provider có API key riêng, lưu mã hóa theo từng nhà cung cấp
- Có danh sách model riêng theo từng provider
- Có checkpoint riêng theo provider, giúp tránh đè file resume giữa các provider
- Có lịch sử dịch riêng
- Có thống kê chi phí theo provider và model
- Có palette/theme thay đổi theo provider để nhìn trực quan hơn
- Có prompt preset theo thể loại truyện như tiên hiệp, huyền huyễn, đô thị hiện đại, ngôn tình, lịch sự/chuẩn mực

Phù hợp khi:

- Bạn muốn thử nhiều provider nhưng chỉ cần một app duy nhất
- Bạn cần so sánh chất lượng dịch giữa các model khác nhau
- Bạn thích quản lý key, lịch sử và chi phí tập trung

## Hướng dẫn cài đặt nhanh

Yêu cầu chung:

- Windows
- Python 3.10+ là khuyến nghị

### Chạy app AWS

```powershell
cd AWSDichTruyen
pip install boto3
python AWSDichTruyen.py
```

### Chạy app Google Gemini

```powershell
cd GoogleDichTruyen
pip install google-generativeai
python GoogleDichTruyen.py
```

### Chạy biến thể Google Rate Limit

```powershell
cd GoogleDichTruyen
python GoogleDichTruyenRateLimit.py
```

### Chạy Claude

```powershell
cd ClaudeDichTruyen
python ClaudeDichTruyen.py
```

### Chạy DeepSeek

```powershell
cd DeepSeekDichTruyen
python DeepSeekDichTruyen.py
```

### Chạy local AI

```powershell
cd AiLocal
python DichTruyenLocal.py
```

### Chạy CLI Proxy

```powershell
cd CLIProxyDichTruyen
python Dichtruyen.py
```

### Chạy MultiProvider AI

```powershell
cd MultiProviderAi
python DichTruyen.py
```

## File được tạo ra khi chạy app

Tùy app, các file sau thường được sinh ra trong cùng thư mục app hoặc cạnh file input:

- `app_settings.json` hoặc `app_settings_local.json`: lưu cài đặt gần nhất
- `translation_history.json` hoặc `translation_history_local.json`: lịch sử dịch
- `*.resume.json`: checkpoint để resume
- `*.txt`: file output dịch

Một số app còn có biến thể checkpoint hoặc history riêng theo provider, để không ghi đè lẫn nhau.

## Gợi ý sử dụng an toàn

- Không chia sẻ file cấu hình nếu trong đó có key hoặc dữ liệu nhạy cảm
- Không commit `app_settings*.json`, `translation_history*.json` và `*.resume*.json` nếu bạn không muốn lộ cấu hình chạy thực tế
- Nếu API báo lỗi hoặc quota thấp, hãy giảm số luồng hoặc giảm chunk size trước khi đổi model
- Nếu muốn giữ thuật ngữ nhất quán, hãy dùng ô prompt/glossary thay vì sửa trực tiếp nội dung file nguồn

## Tài liệu chi tiết hơn

- [Hướng dẫn AWS](AWSDichTruyen/HUONG_DAN_SU_DUNG.md)
- [Hướng dẫn Google Gemini](GoogleDichTruyen/HUONG_DAN_SU_DUNG.md)

## Tóm tắt ngắn

Nếu bạn cần một app riêng cho một provider thì dùng các thư mục theo từng nhà cung cấp. Nếu bạn muốn đổi provider trong cùng một giao diện, `MultiProviderAi/` là bản đáng dùng nhất. Nếu muốn chạy local hoặc không phụ thuộc cloud, hãy xem `AiLocal/` và `CLIProxyDichTruyen/`.
