import sys
from pathlib import Path

# Thêm thư mục gốc dự án (D:\PBL6_v2\PBL6) vào sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.backend.app.main:app", host="0.0.0.0", port=8000, reload=True)

