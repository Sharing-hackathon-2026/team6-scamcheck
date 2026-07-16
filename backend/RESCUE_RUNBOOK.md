# Stage 5 — Runbook Người ứng cứu

## Mục tiêu an toàn

`POST /api/rescue` hỗ trợ người có thể vừa bấm link, chuyển tiền hoặc lộ OTP. Endpoint
không có quyền khóa tài khoản, thu hồi tiền hay thay thế ngân hàng/Công an. Crisis flow
phải luôn trả được playbook tĩnh ngay cả khi Gemini lỗi.

## Guardrail bắt buộc

1. Frontend chỉ cho chọn một trong bốn `situation`; backend validate lại enum.
2. `message_text` chỉ dùng trong process để match alias ngân hàng, không đưa nguyên văn vào
   prompt Rescuer. Prompt chỉ nhận risk level và tối đa ba nhãn dấu hiệu.
3. Prompt nhận toàn bộ bảng hotline tĩnh và mapping hotline được phép theo từng safety step.
4. Parser đòi đủ mọi `REQUIRED_STEP_KEYS`; thiếu một bước hoặc có chỉ dẫn nguy hiểm thì bỏ
   toàn bộ output AI và dùng deterministic playbook.
5. Mọi chuỗi giống số điện thoại được post-filter. UI chỉ tạo `tel:` từ mảng `hotlines` do
   server dựng lại từ `backend/data/hotlines.json`.
6. `113` luôn có `emergency_only=true`: chỉ dùng khi đang bị đe dọa/cần trợ giúp khẩn cấp.
7. Không hứa lấy lại tiền, không giới thiệu dịch vụ thu hồi tiền, không yêu cầu OTP/PIN,
   cài remote app, bấm lại link hoặc chuyển thêm tiền.

## Kill switch

Nếu output Rescuer có dấu hiệu không ổn định:

```bash
# /etc/scamcheck.env
RESCUE_AI_ENABLED=false
sudo systemctl restart scamcheck-backend
```

Endpoint vẫn trả HTTP 200, `rescue_status=guarded_fallback`, `actual_ai_calls=0` và playbook
tĩnh cho ba tình huống đã sa bẫy. Khôi phục bằng `RESCUE_AI_ENABLED=true` sau khi test lại.

## Rà soát bảng hotline

Thực hiện trước demo và ít nhất mỗi 90 ngày:

1. Mở từng `source_url` trên domain chính thức; không dùng snippet quảng cáo hoặc bài tổng hợp.
2. Đối chiếu số trên website với số in sau thẻ/ứng dụng chính thức khi có thể.
3. Ghi exact quote chứa số vào `source_evidence`, ngày vào `source_checked_at`; loader sẽ
   từ chối nếu số chuẩn hóa không xuất hiện trong evidence.
4. Chạy `.venv/bin/python scripts/verify_hotlines.py`: tất cả URL phải HTTP 200 và visible
   text/PDF phải chứa đúng số; lưu report + SHA-256 tại `reports/stage5-hotline-verification.json`.
5. Hai người cùng duyệt report/thay đổi số; chạy `pytest -q tests/test_hotlines_filter.py tests/test_crisis_flow.py`.
6. Gọi `GET /api/hotlines`, kiểm tra tối thiểu 10 ngân hàng, Công an và kênh an toàn thông tin.
7. Không sửa số trực tiếp trong prompt, JS hoặc HTML.

Nếu chưa xác minh được một số, xóa entry đó thay vì đoán. Khi không match ngân hàng, playbook
bắt buộc hướng người dùng gọi số in sau thẻ, không tự chọn một ngân hàng gần giống.

## Xử lý sự cố

- **`503` từ `/api/rescue`:** bảng hotline không đọc/validate được. Không bật bypass; kiểm tra
  JSON, duplicate id/phone, nguồn HTTPS và quyền file.
- **`guarded_fallback`:** người dùng vẫn có quy trình an toàn. Kiểm tra log actor `rescuer`,
  Gemini rate limit và parser rejection; không biến fallback thành lỗi trắng.
- **Số lạ xuất hiện:** bật kill switch ngay, lưu response đã lọc (không lưu tin gốc), thêm
  regression test rồi mới deploy lại.
- **Nguồn hotline đổi:** cập nhật data + ngày rà soát + test, nhờ người thứ hai xác nhận.
- **QR không quét:** kiểm tra `BASE_URL` ngắn hơn 54 byte, HTTPS production, hostname nằm
  trong `SHARE_ALLOWED_HOSTS` và endpoint `/api/share/qr.svg`; request Host lạ phải trả 503.
  Encoder đã được đối chiếu byte-for-byte với QR Version 3-L/mask 0.

## Smoke test sau deploy

```bash
curl -fsS https://team6-scamcheck.exe.xyz:8000/api/hotlines
curl -fsS https://team6-scamcheck.exe.xyz:8000/api/share/qr.svg | head
curl -fsS -H 'Content-Type: application/json' \
  -d '{"situation":"chua_lam_gi"}' \
  https://team6-scamcheck.exe.xyz:8000/api/rescue
```

Xác minh thêm bằng browser: bốn lựa chọn chỉ bấm một lần; hotline là `tel:`; fallback có nhãn;
ảnh PNG không chứa tin gốc; high contrast/cỡ chữ lưu qua reload.
