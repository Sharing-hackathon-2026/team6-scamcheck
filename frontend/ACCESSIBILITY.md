# Tự kiểm khả năng tiếp cận — Frontend Stage 2

Mục tiêu: WCAG 2.1/2.2 mức AA cho luồng chính trên iPhone Safari và desktop responsive. Đây là bảng tự kiểm kỹ thuật; vẫn cần kiểm thử thủ công với người dùng và VoiceOver trước khi phát hành rộng rãi.

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
| Tương phản chữ | Chữ chính `#17231e` trên `#ffffff/#f5f7f4`; chữ phụ `#46554e`; semantic text dùng sắc độ đậm | Đạt: cặp thấp nhất đã tính là `#46554e`/`#f5f7f4` = 7.30:1, vượt AA 4.5:1 |
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
- Cần gate trực quan cuối Stage 4 trên iPhone-like + desktop cho empty/loading/result/link,
  quiz question/correct/incorrect/summary và error state trước demo chính thức.
