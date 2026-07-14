# ScamCheck

Công cụ web giúp người từ 45 tuổi trở lên kiểm tra nhanh tin nhắn nghi ngờ lừa đảo.
Hackathon FCT — Team 6. AI: Google Gemini.

## Kiến trúc (tách 2 phần)

| Phần | Thư mục | Công nghệ | Phục vụ bởi |
|---|---|---|---|
| **Frontend** | `frontend/` | HTML + CSS token hoá + JavaScript thuần | **Nginx** (static) |
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
cd backend && . .venv/bin/activate && pytest      # 150 test, dùng mock (không tốn lượt AI)
```

Chạy riêng bộ hồi quy 20 tin với Gemini thật (có tốn API):
```bash
cd backend && GEMINI_API_KEY=... python scripts/run_regression.py
```

Chạy báo cáo Stage 4 trên 60 tin (mặc định nghỉ 4,2 giây giữa calls để tôn trọng rate limit):
```bash
cd backend
GEMINI_API_KEY=... python scripts/run_stage4_evaluation.py \
  --prompt-mode stage3 --output-name baseline
GEMINI_API_KEY=... python scripts/run_stage4_evaluation.py \
  --prompt-mode stage4 --output-name improved
python scripts/combine_stage4_reports.py \
  reports/baseline.json reports/improved.json
```
Mỗi run tốn 60 calls; không chạy trong pytest/deploy. Report gần nhất nằm ở
`backend/reports/stage4-evaluation.{json,md}`.

### Frontend
Dev tách port: phục vụ `frontend/` ở `:5500`, trỏ tới backend `:5000`.
```bash
cd frontend
# Sửa assets/js/config.js: export const API_BASE = 'http://localhost:5000';
python -m http.server 5500
# → http://localhost:5500
```

Kiểm thử helper frontend (highlight, lịch sử, chuẩn hoá kết quả, giọng nói):
```bash
npm --prefix frontend test       # 29 test Node, không cần dependency ngoài
npm --prefix frontend run check  # syntax check toàn bộ JavaScript
```

Stage 2 bổ sung thẻ rủi ro, tô vàng excerpt an toàn XSS, lịch sử localStorage 10 mục,
3 tin mẫu, loading/error state, Web Speech API và giao diện ≥18px/touch target ≥44px.
Mọi text đi qua boundary API, textarea, speech và localStorage được chuẩn hoá Unicode NFC
(precomposed) để tiếng Việt render ổn định trên các trình duyệt cũ.
Stage 3 bổ sung terminal function-call handoff từ Thám tử sang Cô tâm lý, lỗi hai
phần độc lập, guardrail prompt injection, bộ hồi quy 20 tin và thư viện 12 kiểu
lừa đảo thuộc 4 nhóm với bộ lọc không reload.

Stage 4 bổ sung URL extraction/redirect resolver chống SSRF, phát hiện domain IDN/
homoglyph/lookalike, rule engine theo mệnh đề, cache hash TTL/LRU, bộ đánh giá 60 tin
và chế độ luyện tập 10 câu tại `/practice.html`. Báo cáo thật gần nhất: accuracy
`51,7% → 66,7%`, hard-case accuracy `53,6% → 71,4%`, danger recall giữ `100%`;
điểm yếu chính còn lại là phân biệt `nghi_ngo` với `nguy_hiem`.
Bảng tự kiểm tiếp cận nằm tại `frontend/ACCESSIBILITY.md`.

(Sửa `config.js` chỉ khi dev tách port. Prod để rỗng vì Nginx cùng origin.)

## Deploy (đang chạy trên VM target)

- **🟢 LIVE:** https://team6-scamcheck.exe.xyz:8000/
- `GET /api/health` → `{"ok":true,"ready":true}`
- `POST /api/check` → function-call Thám tử, chain Cô tâm lý khi cần, retry rate-limit; không giới hạn lượt theo phiên.

Deploy idempotent qua `deploy/deploy.sh` (chạy **trên VM target**, cần sudo):
```bash
# trên VM target:
ssh exedev@team6-scamcheck.exe.xyz
# đã có /etc/scamcheck.env (chứa GEMINI_API_KEY, root:exedev 640)
git clone https://hackathon-project.int.exe.xyz/Sharing-hackathon-2026/team6-scamcheck.git /tmp/d
bash /tmp/d/deploy/deploy.sh && rm -rf /tmp/d
```
Script tự: clone vào `/opt/scamcheck` → tạo venv → chạy pytest (phải xanh) → cài systemd
`scamcheck-backend` (gunicorn :5000) + nginx (frontend/ + `/api/*` proxy). Chạy lại = update.

## Tài liệu

- Kế hoạch triển khai theo cấp: [`PLAN.md`](PLAN.md)
- Cấu trúc thư mục + sơ đồ luồng dữ liệu: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Hợp đồng API: [`API.md`](API.md)

