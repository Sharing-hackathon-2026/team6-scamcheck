// Wrapper fetch cho backend API. Cấp 1: chỉ có check().
import { API_BASE } from './config.js';

/** Lỗi thân thiện khi gọi API. */
export class ApiError extends Error {
  constructor(message, { status } = {}) {
    super(message);
    this.status = status;
  }
}

/**
 * Gọi POST /api/check với nội dung tin nhắn.
 * @param {string} text
 * @returns {Promise<{result?: string, errors?: string[], error?: string}>}
 */
export async function check(text) {
  let resp;
  try {
    resp = await fetch(`${API_BASE}/api/check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
  } catch (e) {
    // Mất kết nối / network.
    throw new ApiError('Không kết nối được tới máy chủ. Vui lòng kiểm tra mạng và thử lại.');
  }

  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const msg = (data.errors && data.errors.join(' ')) || data.error || 'Có lỗi xảy ra. Vui lòng thử lại.';
    throw new ApiError(msg, { status: resp.status });
  }
  return data;
}
