// Ảnh cảnh báo chia sẻ (Stage 5). Pure helpers (privacy model + bọc chữ + tên file)
// được tách riêng để test bằng node:test. Phần decode QR/draw canvas chạm DOM/canvas,
// chạy trong trình duyệt khi người dùng chọn chia sẻ.
//
// Nguyên tắc riêng tư: ảnh chỉ chứa TÓM TẮT (mức rủi ro, lý do ngắn, tối đa 3 dấu hiệu
// theo nhãn, lời nhắc an toàn, QR + URL sản phẩm). KHÔNG đưa toàn văn tin nhắn, excerpt,
// số tài khoản hay dữ liệu cá nhân vào ảnh.

import { RISK_META } from './result-model.js?v=stage5-tabs-v16';

const REASON_LIMIT = 132;
const SIGN_LIMIT = 56;
const MAX_SIGNS = 3;

/**
 * Màu sắc cố định cho ảnh xuất (luôn trên nền sáng để dễ chia sẻ/lưu trên mọi thiết bị).
 * Đây là asset xuất ra, tách biệt với token CSS của giao diện (giao diện vẫn 100% token).
 */
export const RISK_CARD_COLORS = Object.freeze({
  an_toan: { accent: '#166534', soft: '#e7f3ec', onSoft: '#124c29' },
  nghi_ngo: { accent: '#9a5a06', soft: '#fbeec6', onSoft: '#6f3d12' },
  nguy_hiem: { accent: '#b42318', soft: '#fbe3e3', onSoft: '#7f1d1d' },
});

export const SHARE_CARD_DEFAULTS = Object.freeze({
  width: 1080,
  height: 1350,
  reminder: 'Không gửi mã OTP, không chuyển tiền cho người lạ, dù họ xưng danh ngân hàng hay công an.',
  qualifier: 'Đây là kết quả hỗ trợ giáo dục, không phải xác nhận chính thức.',
  productName: 'ScamCheck',
});

/**
 * Dựng mô hình ảnh từ kết quả Thám tử. Lọc sạch excerpt/toàn văn; chỉ giữ nhãn dấu hiệu.
 * Trả về object KHÔNG chứa trường `text`, `excerpt` hay bất kỳ nội dung tin gốc nào.
 */
export function redactPrivateSequences(value) {
  return String(value || '')
    .replace(/https?:\/\/\S+|www\.\S+/gi, '[đường link đã ẩn]')
    .replace(/[\w.+-]+@[\w.-]+\.[a-z]{2,}/gi, '[email đã ẩn]')
    .replace(/(?<!\d)(?:\+?84|0|\d)[\d\s().-]{5,}\d(?!\d)/g, '[dãy số đã ẩn]')
    .replace(/\s+/g, ' ')
    .trim();
}

function truncateLabel(value, limit) {
  const text = String(value || '').trim();
  if (text.length <= limit) return text;
  const clipped = text.slice(0, Math.max(1, limit - 1)).trimEnd();
  const wordSafe = clipped.replace(/\s+\S*$/, '').trimEnd();
  return `${wordSafe || clipped}…`.slice(0, limit);
}

export function buildShareCardModel(detective, options = {}) {
  const normalized = detective && typeof detective === 'object' ? detective : {};
  const riskKey = Object.hasOwn(RISK_META, normalized.risk_level) ? normalized.risk_level : 'nghi_ngo';
  const signs = (Array.isArray(normalized.red_flags) ? normalized.red_flags : [])
    .map((flag) => {
      const raw = flag && typeof flag === 'object' && typeof flag.label === 'string' ? flag.label : '';
      return redactPrivateSequences(raw);
    })
    .filter(Boolean)
    .slice(0, MAX_SIGNS)
    .map((label) => truncateLabel(label, SIGN_LIMIT));
  const reason = truncateLabel(redactPrivateSequences(
    typeof normalized.reason === 'string' ? normalized.reason : '',
  ), REASON_LIMIT) || RISK_META[riskKey].label;
  return {
    productName: SHARE_CARD_DEFAULTS.productName,
    riskKey,
    riskLabel: RISK_META[riskKey].label,
    reason,
    signs,
    reminder: typeof options.reminder === 'string' && options.reminder.trim()
      ? options.reminder.trim().slice(0, 200)
      : SHARE_CARD_DEFAULTS.reminder,
    qualifier: typeof options.qualifier === 'string' && options.qualifier.trim()
      ? options.qualifier.trim().slice(0, 200)
      : SHARE_CARD_DEFAULTS.qualifier,
    url: typeof options.url === 'string' && options.url.trim() ? options.url.trim().slice(0, 120) : '',
  };
}

/**
 * Bọc chữ theo chiều rộng. `measure(text) -> số` thường là ctx.measureText(text).width,
 * nhưng ở đây nhận hàm để có thể test thuần với measure giả.
 */
export function wrapLines(measure, text, maxWidth) {
  if (typeof measure !== 'function' || typeof maxWidth !== 'number' || maxWidth <= 0) {
    return [String(text || '')];
  }
  const collapsed = String(text || '').replace(/\s+/g, ' ').trim();
  if (!collapsed) return [''];
  if (measure(collapsed) <= maxWidth) return [collapsed];

  const lines = [];
  const paragraphs = collapsed.split('\n');
  paragraphs.forEach((paragraph) => {
    const words = paragraph.split(' ').filter(Boolean);
    let current = '';
    words.forEach((word) => {
      const candidate = current ? `${current} ${word}` : word;
      if (measure(candidate) <= maxWidth || !current) {
        current = candidate;
        return;
      }
      lines.push(current);
      current = word;
    });
    if (current) lines.push(current);
  });
  return lines.length ? lines : [''];
}

/** Tên file an toàn cho tải về/chia sẻ: chỉ giữ chữ-số và gạch. */
export function safeFileName(stem, ext = 'png') {
  const decomposed = String(stem || SHARE_CARD_DEFAULTS.productName)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
  const base = decomposed
    .toLowerCase()
    .replace(/đ/g, 'd')
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48) || SHARE_CARD_DEFAULTS.productName.toLowerCase();
  const allowedExt = new Set(['png', 'jpg', 'jpeg', 'webp']);
  const rawExt = String(ext || 'png').toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 6);
  const cleanExt = allowedExt.has(rawExt) ? rawExt : 'png';
  return `${base}.${cleanExt}`;
}

/**
 * Giải mã SVG QR do backend trả để vẽ lên canvas (không dùng thư viện QR ngoài).
 * Đọc thuộc tính `d` của <path> (mỗi module tối là "M{x},{y}h1v1h-1z") và tọa độ đã
 * bao gồm quiet zone. Trả về danh sách module {x, y} theo đơn vị viewBox.
 */
export function decodeQrModules(svgText) {
  if (typeof DOMParser === 'undefined') {
    throw new Error('Trình duyệt không hỗ trợ phân tích SVG.');
  }
  const doc = new DOMParser().parseFromString(String(svgText || ''), 'image/svg+xml');
  if (doc.getElementsByTagName('parsererror').length > 0) {
    throw new Error('Mã QR chia sẻ không đúng định dạng.');
  }
  const svgEl = doc.documentElement;
  if (!svgEl || svgEl.nodeName.toLowerCase() !== 'svg') {
    throw new Error('Mã QR chia sẻ không hợp lệ.');
  }
  const path = Array.from(svgEl.getElementsByTagName('path')).find((node) => {
    const d = node.getAttribute('d') || '';
    return /M[\d.]+,[\d.]+h1v1h-1z/.test(d);
  });
  if (!path) throw new Error('Mã QR chia sẻ không có mã kẻ.');
  const d = path.getAttribute('d') || '';
  const re = /M([\d.]+),([\d.]+)h1v1h-1z/g;
  const modules = [];
  let match;
  while ((match = re.exec(d)) !== null) {
    modules.push({ x: Number(match[1]), y: Number(match[2]) });
  }
  if (!modules.length) throw new Error('Mã QR chia sẻ trống.');
  const viewBox = (svgEl.getAttribute('viewBox') || '').trim().split(/\s+/).map(Number);
  const span = viewBox.length === 4 && viewBox.every(Number.isFinite)
    && viewBox[0] === 0 && viewBox[1] === 0 && viewBox[2] === viewBox[3]
    && viewBox[2] >= 21 && viewBox[2] <= 177
    ? viewBox[2]
    : 0;
  if (!span || modules.some((item) => item.x < 0 || item.y < 0 || item.x >= span || item.y >= span)) {
    throw new Error('Mã QR chia sẻ thiếu vùng trắng an toàn.');
  }
  return { modules, span };
}

function roundedRect(ctx, x, y, w, h, r) {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
}

/**
 * Vẽ ảnh cảnh báo 1080×1350 lên canvas. KHÔNG ném khi thiếu dữ liệu — luôn vẽ được.
 * qrData: kết quả decodeQrModules (hoặc null nếu chưa có QR).
 */
export function drawShareCard(canvas, model, qrData, options = {}) {
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Trình duyệt không hỗ trợ vẽ ảnh.');
  const width = options.width || SHARE_CARD_DEFAULTS.width;
  const height = options.height || SHARE_CARD_DEFAULTS.height;
  canvas.width = width;
  canvas.height = height;
  if (canvas.style) {
    canvas.style.maxWidth = '100%';
    canvas.style.height = 'auto';
  }

  const ink = '#1c211c';
  const muted = '#57544a';
  const paper = '#fffdf9';
  const line = '#cabfb0';
  const colors = RISK_CARD_COLORS[model.riskKey] || RISK_CARD_COLORS.nghi_ngo;

  ctx.fillStyle = paper;
  ctx.fillRect(0, 0, width, height);

  const measure = (text) => ctx.measureText(text).width;
  const pad = 88;
  const contentWidth = width - pad * 2;
  let cursorY = pad;

  // Wordmark + đường accent ngắn kiểu "đầu mục bản tin".
  ctx.textBaseline = 'top';
  ctx.fillStyle = ink;
  ctx.font = '800 64px -apple-system, system-ui, "Segoe UI", "Noto Sans", sans-serif';
  ctx.fillText(model.productName, pad, cursorY);
  cursorY += 80;
  ctx.fillStyle = colors.accent;
  ctx.fillRect(pad, cursorY, 64, 6);
  cursorY += 28;

  // Lớp rủi ro.
  ctx.fillStyle = colors.soft;
  roundedRect(ctx, pad, cursorY, contentWidth, 150, 24);
  ctx.fill();
  ctx.fillStyle = colors.accent;
  roundedRect(ctx, pad, cursorY, 14, 150, 7);
  ctx.fill();
  ctx.fillStyle = muted;
  ctx.font = '700 30px -apple-system, system-ui, "Segoe UI", "Noto Sans", sans-serif';
  ctx.fillText('MỨC RỦI RO', pad + 44, cursorY + 26);
  ctx.fillStyle = colors.onSoft;
  ctx.font = '800 64px -apple-system, system-ui, "Segoe UI", "Noto Sans", sans-serif';
  ctx.fillText(model.riskLabel, pad + 44, cursorY + 66);
  cursorY += 150 + 32;

  // Lý do ngắn, giới hạn ba dòng để không đè vùng QR ở cuối ảnh.
  ctx.fillStyle = ink;
  ctx.font = '600 36px -apple-system, system-ui, "Segoe UI", "Noto Sans", sans-serif';
  wrapLines(measure, model.reason, contentWidth).slice(0, 3).forEach((line) => {
    ctx.fillText(line, pad, cursorY);
    cursorY += 46;
  });
  cursorY += 18;

  // Dấu hiệu chính: nhãn đã giới hạn độ dài, mỗi nhãn một dòng dễ quét mắt.
  if (model.signs.length) {
    ctx.fillStyle = muted;
    ctx.font = '700 28px -apple-system, system-ui, "Segoe UI", "Noto Sans", sans-serif';
    ctx.fillText('DẤU HIỆU CHÍNH', pad, cursorY);
    cursorY += 40;
    ctx.fillStyle = ink;
    ctx.font = '600 32px -apple-system, system-ui, "Segoe UI", "Noto Sans", sans-serif';
    model.signs.forEach((sign) => {
      let line = sign;
      while (line.length > 1 && measure(`${line}…`) > contentWidth - 44) line = line.slice(0, -1);
      if (line !== sign) line = `${line.trimEnd()}…`;
      ctx.fillStyle = colors.accent;
      ctx.beginPath();
      ctx.arc(pad, cursorY + 18, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = ink;
      ctx.fillText(line, pad + 32, cursorY);
      cursorY += 48;
    });
    cursorY += 10;
  }

  // Lời nhắc an toàn (hộp viền), tối đa ba dòng.
  const reminderTop = cursorY;
  ctx.font = '700 30px -apple-system, system-ui, "Segoe UI", "Noto Sans", sans-serif';
  const reminderLines = wrapLines(measure, model.reminder, contentWidth - 56).slice(0, 3);
  const reminderHeight = 24 + reminderLines.length * 40 + 24;
  ctx.fillStyle = colors.soft;
  roundedRect(ctx, pad, reminderTop, contentWidth, reminderHeight, 20);
  ctx.fill();
  ctx.strokeStyle = colors.accent;
  ctx.lineWidth = 4;
  roundedRect(ctx, pad, reminderTop, contentWidth, reminderHeight, 20);
  ctx.stroke();
  ctx.fillStyle = colors.onSoft;
  ctx.textBaseline = 'top';
  let reminderY = reminderTop + 24;
  reminderLines.forEach((line) => {
    ctx.fillText(line, pad + 28, reminderY);
    reminderY += 40;
  });
  cursorY = reminderTop + reminderHeight + 18;

  // Qualifier chỉ hai dòng để giữ khoảng thở trước QR.
  ctx.fillStyle = muted;
  ctx.font = '500 24px -apple-system, system-ui, "Segoe UI", "Noto Sans", sans-serif';
  wrapLines(measure, model.qualifier, contentWidth).slice(0, 2).forEach((line) => {
    ctx.fillText(line, pad, cursorY);
    cursorY += 32;
  });

  // Vùng QR + URL cố định ở đáy, không chồng lên phần tóm tắt.
  const footerTop = height - pad - 222;
  if (qrData && qrData.modules && qrData.modules.length) {
    const qrPixel = 6;
    const qrSize = qrData.span * qrPixel;
    const qrX = pad;
    const qrY = footerTop;
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(qrX, qrY, qrSize, qrSize);
    ctx.fillStyle = '#000000';
    qrData.modules.forEach((module) => {
      ctx.fillRect(qrX + module.x * qrPixel, qrY + module.y * qrPixel, qrPixel, qrPixel);
    });
    const textX = qrX + qrSize + 40;
    const textWidth = width - pad - textX;
    if (textWidth > 120) {
      ctx.fillStyle = ink;
      ctx.font = '700 34px -apple-system, system-ui, "Segoe UI", "Noto Sans", sans-serif';
      let labelY = qrY;
      ctx.fillText('Quét để tự kiểm tra', textX, labelY);
      labelY += 50;
      ctx.fillStyle = muted;
      ctx.font = '500 30px -apple-system, system-ui, "Segoe UI", "Noto Sans", sans-serif';
      if (model.url) {
        wrapLines(measure, model.url, textWidth).slice(0, 2).forEach((line) => {
          ctx.fillText(line, textX, labelY);
          labelY += 42;
        });
      }
      labelY += 12;
      ctx.fillStyle = muted;
      ctx.font = '400 26px -apple-system, system-ui, "Segoe UI", "Noto Sans", sans-serif';
      wrapLines(measure, 'Ảnh cảnh báo do ScamCheck tạo để chia sẻ cho người thân.', textWidth)
        .slice(0, 3)
        .forEach((line) => {
          ctx.fillText(line, textX, labelY);
          labelY += 36;
        });
    }
  } else {
    ctx.fillStyle = muted;
    ctx.font = '500 30px -apple-system, system-ui, "Segoe UI", "Noto Sans", sans-serif';
    ctx.fillText('Mã QR chưa sẵn sàng.', pad, footerTop);
  }

  return canvas;
}
