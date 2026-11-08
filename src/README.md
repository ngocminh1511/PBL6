# Ứng dụng web PBL6

Next.js ở `frontend`, FastAPI ở `backend`, lõi thuật toán tại `../labor_rag`.
Không còn Compose hoặc server API riêng trong thư mục này.

Từ thư mục gốc repository:

```powershell
pip install -e ".[api,rag,ocr,dev]"
python run_backend.py
```

Terminal khác:

```powershell
npm --prefix src/frontend ci
npm --prefix src/frontend run dev
```

[README chính](../README.md) có hướng dẫn cloud, cấu hình, Docker và kiểm thử.
[AGENTS.md](../AGENTS.md) quy định ranh giới module.
`UI/` và `doc/` chỉ lưu thiết kế ban đầu; không phản ánh hợp đồng API đang chạy.
