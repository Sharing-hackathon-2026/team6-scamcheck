// Wrapper fetch cho backend API structured (L1-03).
import { API_BASE } from './config.js';

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
