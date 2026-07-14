# ScamCheck

Công cụ web giúp người từ 45 tuổi trở lên kiểm tra nhanh tin nhắn nghi ngờ lừa đảo.
Hackathon FCT — Team 6. Stack: Python Flask + Jinja2 + Tailwind (CDN), AI Google Gemini.

## Deploy target

- **VM:** `team6-scamcheck.exe.xyz`
- **Public proxy:** `https://team6-scamcheck.exe.xyz:8000/` (proxy xác thực người dùng; service backend chạy trong VM ở port nội bộ, proxy forward ra :8000).
- Source: `https://hackathon-project.int.exe.xyz/Sharing-hackathon-2026/team6-scamcheck`

Chi tiết kế hoạch: [`PLAN.md`](PLAN.md). Kiến trúc: [`ARCHITECTURE.md`](ARCHITECTURE.md).
