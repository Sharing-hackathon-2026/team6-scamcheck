// Cấp 1: logic chính. Bắt sự kiện nút Kiểm tra, gọi API, hiện kết quả thô.
import { check, ApiError } from './api.js';

const textInput = document.getElementById('textInput');
const checkBtn = document.getElementById('checkBtn');
const clearBtn = document.getElementById('clearBtn');
const statusEl = document.getElementById('status');
const resultEl = document.getElementById('result');
const errorEl = document.getElementById('error');

function setLoading(on, msg = '') {
  checkBtn.disabled = on;
  statusEl.className = 'status' + (on ? ' loading' : '');
  statusEl.textContent = msg;
}

function showError(msg) {
  errorEl.textContent = msg;
  errorEl.style.display = 'block';
  resultEl.style.display = 'none';
}

function showResult(text) {
  resultEl.textContent = text || '(AI không trả về nội dung. Vui lòng thử lại.)';
  resultEl.style.display = 'block';
  errorEl.style.display = 'none';
}

async function onCheck() {
  const text = textInput.value.trim();
  resultEl.style.display = 'none';
  errorEl.style.display = 'none';

  if (!text) {
    showError('Vui lòng dán nội dung tin nhắn cần kiểm tra.');
    return;
  }

  setLoading(true, 'Đang kiểm tra, vui lòng chờ trong giây lát...');
  const started = Date.now();

  try {
    const data = await check(text);
    showResult(data.result || '');
    setLoading(false);
  } catch (e) {
    const elapsed = Date.now() - started;
    // Đảm bảo loading tối thiểu ~0.4s cho mượt (không giật).
    setTimeout(() => setLoading(false), Math.max(0, 400 - elapsed));
    showError(e instanceof ApiError ? e.message : 'Có lỗi không xác định. Vui lòng thử lại.');
  }
}

checkBtn.addEventListener('click', onCheck);
clearBtn.addEventListener('click', () => {
  textInput.value = '';
  textInput.focus();
  resultEl.style.display = 'none';
  errorEl.style.display = 'none';
  statusEl.textContent = '';
});
textInput.addEventListener('keydown', (e) => {
  // Ctrl/Cmd + Enter để kiểm tra nhanh.
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') onCheck();
});
