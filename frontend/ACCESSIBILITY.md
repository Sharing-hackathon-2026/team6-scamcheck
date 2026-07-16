# Tự kiểm khả năng tiếp cận — Frontend

Mục tiêu: WCAG 2.1/2.2 mức AA cho luồng chính trên iPhone Safari và desktop responsive, cho cả **light và dark tự động theo hệ điều hành**. Đây là bảng tự kiểm kỹ thuật; vẫn cần kiểm thử thủ công với người dùng và VoiceOver trước khi phát hành rộng rãi.

| Hạng mục AA | Cách triển khai | Tự kiểm |
|---|---|---|
| Ngôn ngữ trang | `<html lang="vi">` để trình đọc màn hình phát âm đúng | Đạt |
| Cấu trúc và landmark | Có `header`, `main`, `section`, `aside`, `footer`; tiêu đề theo thứ bậc; có liên kết bỏ qua | Đạt |
| Cỡ chữ | Token thân bài `18px`; textarea, hành động và nội dung kết quả không dưới 18px | Đạt |
| Reflow 320 CSS px | Grid một cột trên màn hình hẹp, không dùng chiều rộng cố định; nội dung dài tự xuống dòng | Đạt bằng kiểm tra CSS |
| iPhone Safari viewport | `min-height: 100dvh`, `viewport-fit=cover`, `-webkit-text-size-adjust: 100%` | Đạt bằng kiểm tra CSS |
| Touch target | Mọi nút tối thiểu `44px × 44px`; nút chính tối thiểu 52px | Đạt bằng kiểm tra CSS |
| Bàn phím | Dùng phần tử `button` thật; thứ tự DOM hợp lý; hỗ trợ Ctrl/Cmd+Enter | Đạt |
| Focus nhìn thấy | `:focus-visible` outline xanh 3px, offset 3px; không chỉ dựa vào màu nền | Đạt |
| Không phụ thuộc hover | Mọi chức năng chính dùng được bằng chạm/click/focus; hover chỉ tăng phản hồi | Đạt |
| Tương phản chữ (light) | Chữ chính `#1c211c` trên nền giấy ấm `#f4f1ea`; chữ phụ `#57544a`; semantic text dùng sắc độ đậm | Đạt: `#57544a`/`#f4f1ea` = 6.72:1, vượt AA 4.5:1 |
| Tự động light/dark | `color-scheme: light dark` trên `:root`; dark override nguyên qua `@media (prefers-color-scheme: dark)`; **không có toggle thủ công** | Đạt bằng kiểm tra CSS |
| Tương phản chữ (dark) | Chữ trắng ấm `#eceadd` trên nền than ấm `#171a16`/`#21241e`; chữ phụ `#b3b0a2` | Đạt: `#b3b0a2`/`#171a16` = 8.07:1, `#b3b0a2`/`#21241e` = 7.22:1 |
| Giảm chói dark | Dark không phải đảo màu: nền than ấm (không đen thuần), chữ trắng ấm (không trắng thuần), thẻ rủi ro giữ sắc thái nhận diện nhưng giảm bão hòa/độ sáng; bóng tối hơn và viền nhẹ tạo chiều sâu thay vì đổ bóng nặng | Đạt bằng kiểm tra trực quan + đo màu |
| Không chỉ dùng màu | Thẻ rủi ro luôn có nhãn chữ “An toàn/Nghi ngờ/Nguy hiểm/Không liên quan”, biểu tượng và viền | Đạt |
| Trạng thái động | `role=status`, `role=alert`, `aria-live`, `aria-busy`; kết quả có thể nhận focus | Đạt |
| Loading | Có câu trạng thái, spinner và skeleton rõ; spinner bị ẩn với AT để tránh nhiễu | Đạt |
| Giảm chuyển động | `prefers-reduced-motion: reduce` tắt gần như toàn bộ animation/transition | Đạt |
| Form label/help | Textarea có `<label>` và `aria-describedby`; cảnh báo không nhập OTP/mật khẩu | Đạt |
| Giọng nói | Nút bật/tắt có `aria-pressed`; trạng thái/quyền/lỗi microphone được thông báo bằng chữ | Đạt |
| Safari không hỗ trợ Speech API | Ẩn nút không dùng được và hiện hướng dẫn nhập bàn phím/dán nội dung | Đạt |
| Lịch sử | Nút xem lại và xoá tách biệt; nút xoá có accessible name chứa nội dung mục; xoá có confirm | Đạt |
| XSS khi tô vàng | Không dùng HTML từ nội dung/AI; helper tạo text node và `<mark>` bằng `textContent` | Đạt, có unit test |
| Phóng to 200% | Không khóa zoom; bố cục fluid và chuyển một cột | Đạt bằng kiểm tra mã; cần kiểm tra trực quan |

## Checklist kiểm thử thủ công trước khi demo

1. iPhone Safari: 320/375/390px, portrait và landscape; kiểm tra không cuộn ngang.
2. VoiceOver iOS: đi từ đầu trang, nhập tin, chạy kiểm tra, nghe trạng thái loading/error/result, mở lại lịch sử.
3. Bàn phím desktop: Tab/Shift+Tab toàn bộ điều khiển, focus luôn nhìn thấy; Enter/Space kích hoạt đúng nút.
4. Bật **Reduce Motion** trên hệ điều hành: skeleton/spinner không gây chuyển động kéo dài.
5. Zoom trình duyệt 200% và tăng cỡ chữ iOS: không mất nút, không che kết quả, lịch sử vẫn dùng được.
6. Kiểm ba thẻ màu bằng công cụ contrast và ảnh xám để bảo đảm nhãn chữ vẫn truyền đạt trạng thái.
7. Từ chối quyền microphone, không có microphone, và Safari không có Web Speech API: luồng nhập bàn phím vẫn hoàn chỉnh.
8. Dán chuỗi có HTML/script vào tin nhắn: nội dung phải hiện nguyên văn, không thực thi.

## Stage 3

- Hai phần “Thám tử” và “Cô tâm lý” dùng heading riêng; lỗi Cô tâm lý là text trạng thái, không che verdict.
- Bộ lọc thư viện là button có `aria-pressed`, dùng được bằng bàn phím và không reload trang.
- Trạng thái tải/lỗi/số mục thư viện có `role=status`/`role=alert`; card giữ cỡ chữ ≥18px.
- Grid thư viện về một cột trên mobile; mọi nút lọc giữ touch target tối thiểu 44px.

## Stage 4

- Trạng thái tiến trình soi link/luật/AI dùng `role=status` hiện ngay; nút “Dừng kiểm tra”
  là button thật và AbortController trả lỗi thân thiện, không để UI treo.
- Technical analysis dùng heading/list/chữ và lý do; không chỉ dựa màu severity. Domain dài
  có `overflow-wrap:anywhere`, không gây cuộn ngang ở 320px.
- Trang `/practice.html` có landmark/footer pháp lý riêng, native buttons, nhóm đáp án có
  accessible name, `aria-pressed`, feedback live, focus chuyển tới câu/tổng kết và restart thật.
- Hai lựa chọn luyện tập luôn có nhãn chữ “Có dấu hiệu lừa đảo”/“Có vẻ an toàn”; màu đỏ/xanh
  chỉ là tín hiệu bổ sung. Touch target tối thiểu 60px.
- Cả trang chính và luyện tập giữ font thân bài 18px, reflow một cột và reduced-motion.

## Visual refinement sau Stage 4 — gần gũi + auto light/dark

Mục tiêu thiết kế: cảm giác **human-made, ấm, bình tĩnh, như một công cụ cộng đồng đáng tin**
thay vì dashboard/SaaS template hay AI concept art. Giữ hướng xanh tin cậy, làm ấm
màu trung tính và nền (giấy ấm thay vì xám), thêm một đường accent ngắn dưới tiêu đề chính kiểu
"đầu mục bản tin cộng đồng". Không thêm font/asset mạng ngoài; giữ stack font Việt an toàn
đã chốt từ Stage 2.

Quyết định anti-AI đã tuân thủ:

- Không gradient blob/glass rẻ; nền chỉ có một vệt ánh nắng rất nhẹ neo góc trên phải +
  các bề mặt phẳng có viền thật và bóng nhiều lớp tinh tế (không đổ bóng mờ lớn).
- Không emoji; logo vẫn là shield+check vector vẽ tay, cùng họ icon stroke-width 2 nhất quán.
- Mọi màu dùng token (foundation `tokens.css`) để dark mode tự thích ứng; không còn hex cứng
  rải rác trong `app.css` (trừ token nội bộ).
- Giữ DOM ngữ nghĩa và contract JS/API; bổ sung disclosure thật cho technical/library,
  progress luyện tập và retry có trạng thái, không làm mất interaction Stage 1–4.

Auto light/dark:

- Hoàn toàn dựa trên `prefers-color-scheme`; không có toggle thủ công.
- `color-scheme: light dark` để native controls (scrollbar, autofill, caret, popup) theo hệ điều hành.
- `<meta name="theme-color">` khai báo hai nhánh theo `media=(prefers-color-scheme: ...)`
  để màu thanh trình duyệt theo giao diện.
- Dark giảm chói thật: chữ trắng ấm `#eceadd`, nền than ấm `#171a16`, thẻ rủi ro giữ sắc
  nhận diện (xanh/lục đỏ/xám) nhưng giảm bão hòa và độ sáng; `mark`, focus ring, footer
  pháp lý, technical analysis đều có biến thể dark với tương phản AA.
- `prefers-reduced-motion` vẫn tắt gần như toàn bộ animation/transition ở cả hai giao diện.

Bằng chứng kiểm thử (Browse CLI, headless Chromium thật):

- `--force-dark-mode` được xác nhận flips `prefers-color-scheme` thật (đây là media query thật,
  không phải giả lập JS).
- Light desktop: token giải ra nền ấm `#f4f1ea`, primary `#1d5a44`; check nguy_hiem thật trả
  đủ risk card + technical analysis (links/signals) + highlight + Cô tâm lý; tin mẫu thứ hai
  trùng khớp báo "đã dùng kết quả trong bộ nhớ đệm".
- Dark desktop: nền `#171a16`, chữ `#eceadd`, nút `#46b488` với chữ tối `#06241a`; risk card
  nguy_hiem/an_toan, footer, mark, eyebrow, accent rule đều đúng token dark.
- Practice dark: câu hỏi → feedback đúng/sai (warning) → tổng kết điểm → restart thật.
- Mobile 390px (light + dark): không cuộn ngang, mọi nút ≥ 44px (lựa chọn quiz 86px),
  bố cục về một cột, actions full-width.

Fresh UX gate theo `utility-ui-eval`:

- Builder: Pi session riêng dùng `glm-5.2` + `anti-ai-design`.
- Evaluator: các Pi session **fresh** dùng vision model `gpt-5.6-terra`, chỉ nhận screenshot,
  rubric và interaction probe qua Browse CLI; builder/orchestrator không tự chấm.
- Main screen vòng đầu phát hiện result mobile quá dài; đã đưa ba hành động lên ngay dưới
  verdict, collapse technical analysis + thư viện và thêm shortcut thật. Re-eval: **8,6/10**,
  `true_operational_tool`, không critical/major, `recommend=ship`.
- Practice vòng đầu phát hiện error không có retry; đã thêm retry thật, đếm từng lần thất bại,
  progressbar, completion/restart evidence và shortcut bàn phím. Fresh re-eval cuối:
  **8,0/10**, `true_operational_tool`, không critical/major, `recommend=ship`.
- Evidence tóm tắt nằm ở `backend/reports/human-dark-ux-gate.json`.

## Stage 5 — Người ứng cứu, chia sẻ và tùy chọn đọc

- Cụm “Hiển thị” có native buttons ≥44px, `aria-pressed`, live announcement và dùng chung
  localStorage giữa `/` với `/practice.html`. Ba mức chữ thật là 100%/115%/130%; storage
  hỏng/bị chặn rơi về mặc định, không khóa UI.
- Tương phản cao là lớp token riêng cho cả system light/dark, tăng border/focus/muted text;
  không thay dark mode tự động bằng toggle và không dùng màu làm tín hiệu duy nhất.
- Câu “Bác đã làm gì rồi?” chỉ xuất hiện cho `nghi_ngo`/`nguy_hiem`, gồm đúng bốn native
  button. Một click gọi API ngay; có busy/live status, error + retry, chống race và khóa lựa
  chọn sau thành công để không gọi ứng cứu lặp.
- Kế hoạch ứng cứu dùng ordered list; liên hệ là `tel:` hoặc `sms:` đúng channel, có tên,
  nguồn và ngày đối chiếu. Số `113` luôn kèm chữ “Chỉ gọi khi khẩn cấp”, không chỉ bằng màu.
- Share card được tạo theo yêu cầu thay vì tự mở rộng result. Canvas có accessible label;
  model ảnh loại toàn văn/excerpt, che URL/email/dãy số dài và chỉ giữ tối đa ba nhãn dấu hiệu.
- QR lấy từ endpoint same-origin chuẩn; PNG hỗ trợ Web Share file, download fallback và hướng
  dẫn chạm giữ/Lưu vào Ảnh trên iOS không có file-share.
- Browse Chromium thật đã xác nhận ở 390×844 và 1440×900: không cuộn ngang; minimum button
  nhìn thấy 47,9px; 130% tương ứng body 23,4px; setting giữ qua điều hướng; share canvas
  1080×1350 xuất PNG không rỗng.

Fresh Stage 5 UX gate:

- Builder frontend: Pi session riêng `zai/glm-5.2` + `anti-ai-design`; không commit/deploy.
- Evaluator: fresh Pi `gpt-5.6-terra` + `utility-ui-eval`, 28 chiều, screenshot + Browse probes.
- Kết quả **7,7/10**, `true_operational_tool`, usable, không critical/major,
  `recommend=ship`. Minor chính: crisis plan đầy đủ nên vẫn dài trên mobile; bước gọi ngân
  hàng đã nằm đầu tiên và không collapse để tránh giấu bước an toàn.
- Evidence machine-readable: `backend/reports/stage5-ux-gate.json`.

Caveat còn lại: cần kiểm tra iPhone Safari thật, thao tác “Lưu vào Ảnh”, quét QR bằng camera
vật lý và VoiceOver trước demo chính thức; headless Chromium không mô phỏng hoàn toàn native
share sheet hay cách iOS lưu ảnh.
