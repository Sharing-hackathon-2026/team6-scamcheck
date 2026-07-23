import { normalizeNfc } from './unicode.js?v=stage5-tabs-v16';

export const SPEECH_MESSAGES = Object.freeze({
  unsupported: 'Trình duyệt này chưa hỗ trợ nhập bằng giọng nói. Bác vẫn có thể dán hoặc gõ tin nhắn.',
  listening: 'Đang nghe. Bác đọc tin nhắn, rồi bấm Dừng nghe khi xong.',
  stopped: 'Đã dừng nghe.',
  permission: 'Trình duyệt chưa được phép dùng microphone. Bác hãy cho phép trong cài đặt hoặc nhập bằng bàn phím.',
  noSpeech: 'Chưa nghe rõ nội dung. Bác có thể thử lại hoặc nhập bằng bàn phím.',
  audioCapture: 'Không tìm thấy microphone khả dụng. Bác vẫn có thể nhập bằng bàn phím.',
  network: 'Nhập giọng nói đang gặp lỗi mạng. Bác vui lòng thử lại hoặc nhập bằng bàn phím.',
  generic: 'Không thể nhập bằng giọng nói lúc này. Bác vẫn có thể nhập bằng bàn phím.',
});

export function getSpeechRecognitionConstructor(windowRef) {
  return windowRef?.SpeechRecognition || windowRef?.webkitSpeechRecognition || null;
}

export function speechErrorMessage(code) {
  if (code === 'not-allowed' || code === 'service-not-allowed') return SPEECH_MESSAGES.permission;
  if (code === 'no-speech') return SPEECH_MESSAGES.noSpeech;
  if (code === 'audio-capture') return SPEECH_MESSAGES.audioCapture;
  if (code === 'network') return SPEECH_MESSAGES.network;
  return SPEECH_MESSAGES.generic;
}

export function transcriptFromEvent(event) {
  const results = event?.results;
  if (!results) return '';
  const chunks = [];
  for (let index = event.resultIndex || 0; index < results.length; index += 1) {
    const transcript = results[index]?.[0]?.transcript;
    if (typeof transcript === 'string' && transcript.trim()) chunks.push(transcript.trim());
  }
  return normalizeNfc(chunks.join(' '));
}

export function appendTranscript(currentText, transcript) {
  return normalizeNfc(
    [String(currentText ?? '').trim(), String(transcript ?? '').trim()].filter(Boolean).join(' '),
  );
}
