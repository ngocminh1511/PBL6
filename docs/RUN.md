# Lệnh chạy PBL6 trên Windows

Hướng dẫn dùng PowerShell. Các lệnh chạy từ thư mục gốc dự án:

```text
D:\Work\Learn\HK7_2026-2027\PBL6
```

Venv hiện có trên máy này nằm ở `labor_rag/venv`, dùng Python 3.12. File `.env` nằm ở gốc dự án. README hướng dẫn tạo `.venv` ở gốc cho môi trường mới; mục cuối ghi cách thiết lập đó.

## 1. Chạy hằng ngày

Mở hai terminal riêng và giữ cả hai chạy khi dùng ứng dụng.

### Terminal 1: backend

```powershell
Set-Location 'D:\Work\Learn\HK7_2026-2027\PBL6'
.\labor_rag\venv\Scripts\Activate.ps1
python run_backend.py
```

Nếu PowerShell chặn script kích hoạt, gọi trực tiếp Python trong venv:

```powershell
Set-Location 'D:\Work\Learn\HK7_2026-2027\PBL6'
.\labor_rag\venv\Scripts\python.exe run_backend.py
```

Chọn một trong hai cách trên. Chỉ chạy một backend; ứng dụng dùng một ingestion worker.

### Terminal 2: frontend

```powershell
Set-Location 'D:\Work\Learn\HK7_2026-2027\PBL6'
npm --prefix src/frontend run dev
```

Frontend dùng Node.js/npm, nên terminal này không cần kích hoạt venv.

### Địa chỉ truy cập

| Chức năng | Địa chỉ |
| --- | --- |
| Giao diện | http://localhost:3000 |
| Chat | http://localhost:3000/chat |
| Quản trị và cấu hình | http://localhost:3000/admin |
| Phụ lục | http://localhost:3000/appendices |
| Tài liệu API | http://127.0.0.1:8000/docs |

### Dừng ứng dụng

Nhấn `Ctrl+C` trong từng terminal. Sau khi dừng backend, có thể thoát venv bằng:

```powershell
deactivate
```

Lệnh `deactivate` chỉ dùng nếu đã kích hoạt venv bằng `Activate.ps1`.

## 2. Cài hoặc cập nhật thư viện

Chạy khi thiết lập môi trường hoặc khi dependency trong `pyproject.toml` hay `src/frontend/package-lock.json` thay đổi. Dừng server liên quan trước khi cập nhật thư viện.

```powershell
Set-Location 'D:\Work\Learn\HK7_2026-2027\PBL6'
.\labor_rag\venv\Scripts\python.exe -m pip install -e ".[api,rag,ocr,dev]"
npm --prefix src/frontend ci
```

Các lệnh trên dùng venv hiện có. Nếu thiết lập máy mới, tạo venv theo mục 4 trước.

### Cấu hình môi trường

Dùng `.env` hiện có. Khi thiết lập lần đầu và chưa có file này:

```powershell
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

Điền kết nối và API key vào `.env` trước khi khởi động backend. Mặc định dùng dịch vụ cloud; các bước chạy hằng ngày không cần bật database local bằng Docker.

PostgreSQL phục vụ lịch sử chat, upload và lưu cấu hình; thiếu kết nối sẽ làm các chức năng này trả `503`. Thiếu Redis thì ứng dụng bỏ cache. Chi tiết cấu hình nằm trong [README](../README.md#chạy-ứng-dụng-sau-khi-hợp-nhất).

## 3. Kiểm tra Python đang dùng

Sau khi kích hoạt venv:

```powershell
python -c "import sys; print(sys.executable)"
```

Với môi trường hiện tại, kết quả cần trỏ tới:

```text
D:\Work\Learn\HK7_2026-2027\PBL6\labor_rag\venv\Scripts\python.exe
```

Trong VS Code, mở `Python: Select Interpreter` và chọn Python tương ứng với venv đang dùng.

## 4. Tùy chọn: tạo `.venv` ở gốc dự án

Đây là hướng dẫn thiết lập riêng; việc thêm tài liệu này chưa chuyển venv hiện có. Dùng Python 3.11 trở lên theo `pyproject.toml`.

Tạo môi trường mới rồi cài dependency. Venv có thể chứa đường dẫn tuyệt đối, nên [tài liệu Python khuyến nghị tạo lại khi đổi vị trí](https://docs.python.org/3.12/library/venv.html#how-venvs-work).

```powershell
Set-Location 'D:\Work\Learn\HK7_2026-2027\PBL6'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[api,rag,ocr,dev]"
```

Từ đó, terminal backend dùng:

```powershell
Set-Location 'D:\Work\Learn\HK7_2026-2027\PBL6'
.\.venv\Scripts\Activate.ps1
python run_backend.py
```

Hoặc gọi trực tiếp `.\.venv\Scripts\python.exe run_backend.py`. Các lệnh frontend giữ như mục 1. Khi cập nhật thư viện Python, dùng `.\.venv\Scripts\python.exe -m pip install -e ".[api,rag,ocr,dev]"`.

Chọn `.venv\Scripts\python.exe` trong VS Code. Giữ venv cũ cho tới khi môi trường mới được kiểm tra chạy ổn.

Xem thêm [README](../README.md) và [SYSTEM.md](SYSTEM.md) về kiến trúc, cấu hình và vận hành.

