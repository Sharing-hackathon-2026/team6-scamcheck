// Wrapper fetch cho backend API structured (L1-03).
import { API_BASE } from './config.js?v=stage5-tabs-v16';

/** Lỗi thân thiện khi gọi API. */
export class ApiError extends Error {
  constructor(message, { status, code } = {}) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function requestJson(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, options);
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new ApiError('Đã dừng lượt kiểm tra. Bác có thể thử lại khi sẵn sàng.', { code: 'cancelled' });
    }
    throw new ApiError('Không kết nối được tới máy chủ. Vui lòng kiểm tra mạng và thử lại.');
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = (data.errors && data.errors.join(' ')) || data.error || 'Có lỗi xảy ra. Vui lòng thử lại.';
    throw new ApiError(message, { status: response.status, code: data.code });
  }
  return data;
}

/** Gọi POST /api/check, hỗ trợ hủy request bằng AbortSignal. */
export function check(text, { signal } = {}) {
  return requestJson('/api/check', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
    signal,
  });
}

/** Gọi POST /api/rescue (Stage 5): một lần chọn tình huống là gửi ngay. */
export function rescue(payload, { signal } = {}) {
  return requestJson('/api/rescue', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });
}

/** Lấy SVG QR chuẩn dẫn về ScamCheck (same-origin, không gọi dịch vụ QR ngoài). */
export async function fetchShareQrSvg({ signal } = {}) {
  let response;
  try {
    // Bỏ qua SVG QR cũ trong HTTP cache (bản cũ từng chứa cổng Nginx nội bộ).
    response = await fetch(`${API_BASE}/api/share/qr.svg?v=portless-v1`, {
      signal,
      cache: 'no-store',
    });
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new ApiError('Đã dừng tạo ảnh chia sẻ.', { code: 'cancelled' });
    }
    throw new ApiError('Không tải được mã QR chia sẻ. Vui lòng kiểm tra mạng rồi thử lại.');
  }
  if (!response.ok) {
    throw new ApiError('Mã QR chia sẻ chưa sẵn sàng. Vui lòng thử lại sau.', { status: response.status });
  }
  const text = await response.text();
  if (!text.includes('<svg') || !text.includes('</svg>')) {
    throw new ApiError('Mã QR chia sẻ không đúng định dạng.');
  }
  return text;
}

export function getScamLibrary() {
  return requestJson('/api/scam-library');
}

export function getQuiz() {
  return requestJson('/api/quiz');
}

/** Đọc nhật ký metadata của đúng phiên hiện tại. */
export function getCheckLog() {
  return requestJson('/api/check/log');
}
