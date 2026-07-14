# ScamCheck

Công cụ web giúp người từ 45 tuổi trở lên kiểm tra nhanh tin nhắn nghi ngờ lừa đảo.
Hackathon FCT — Team 6. AI: Google Gemini.

## Kiến trúc (tách 2 phần)

| Phần | Thư mục | Công nghệ | Phục vụ bởi |
|---|---|---|---|
| **Frontend** | `frontend/` | HTML + Tailwind CSS + JavaScript thuần | **Nginx** (static) |
| **Backend** | `backend/` | **Python Flask REST API** (JSON, không Jinja2) | **gunicorn** + systemd |

- Trình duyệt gọi `fetch('/api/...')` → Nginx reverse-proxy `/api/*` sang Flask → **cùng origin, không lo CORS**.
- `GEMINI_API_KEY` chỉ tồn tại ở backend.

## Deploy target

- **VM:** `team6-scamcheck.exe.xyz` (**khác** VM dev).
- **Public proxy:** `https://team6-scamcheck.exe.xyz:8000/` (proxy xác thực user, forward vào Nginx trong VM).
- Nginx phục vụ `frontend/` tại `/` + proxy `/api/*` → `127.0.0.1:5000` (Flask/gunicorn).
- Source: `https://hackathon-project.int.exe.xyz/Sharing-hackathon-2026/team6-scamcheck`

## Chạy trên máy cá nhân (dev)

### Yêu cầu
- Python 3.11+ và `pip`.
- Một khóa API Gemini (test local dùng `gemini-3.1-flash-lite`).

### Backend
```bash
cd backend
python -m venv .venv && . .venv/bin/activate   # lần đầu
pip install -r requirements.txt                  # lần đầu

# Tạo .env (KHÔNG commit):
cp ../.env.example ../.env
# rồi điền GEMINI_API_KEY=... vào ../.env

# Chạy (auto-nạp .env qua python-dotenv nếu có; hoặc export thủ công):
set -a && . ../.env && set +a && python run.py
# → http://localhost:5000/api/health
```

Chạy test:
```bash
cd backend && . .venv/bin/activate && pytest      # 28 test, dùng mock (không tốn lượt AI)
```

### Frontend
Dev tách port: phục vụ `frontend/` ở `:5500`, trỏ tới backend `:5000`.
```bash
cd frontend
# Sửa assets/js/config.js: export const API_BASE = 'http://localhost:5000';
python -m http.server 5500
# → http://localhost:5500
```
(Sửa `config.js` chỉ khi dev tách port. Prod để rỗng vì Nginx cùng origin.)

## Tài liệu

- Kế hoạch triển khai theo cấp: [`PLAN.md`](PLAN.md)
- Cấu trúc thư mục + sơ đồ luồng dữ liệu: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Hợp đồng API: [`API.md`](API.md)

