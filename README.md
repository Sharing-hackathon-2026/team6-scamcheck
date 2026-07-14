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

## Tài liệu

- Kế hoạch triển khai theo cấp: [`PLAN.md`](PLAN.md)
- Cấu trúc thư mục + sơ đồ luồng dữ liệu: [`ARCHITECTURE.md`](ARCHITECTURE.md)

