import test from 'node:test';
import assert from 'node:assert/strict';
import {
  appendTranscript,
  getSpeechRecognitionConstructor,
  SPEECH_MESSAGES,
  speechErrorMessage,
  transcriptFromEvent,
} from '../assets/js/speech.js';

test('feature detection supports standard and Safari-prefixed constructors', () => {
  function Standard() {}
  function Safari() {}
  assert.equal(getSpeechRecognitionConstructor({ SpeechRecognition: Standard }), Standard);
  assert.equal(getSpeechRecognitionConstructor({ webkitSpeechRecognition: Safari }), Safari);
  assert.equal(getSpeechRecognitionConstructor({}), null);
});

test('microphone and recognition failures map to friendly Vietnamese guidance', () => {
  assert.equal(speechErrorMessage('not-allowed'), SPEECH_MESSAGES.permission);
  assert.equal(speechErrorMessage('service-not-allowed'), SPEECH_MESSAGES.permission);
  assert.equal(speechErrorMessage('no-speech'), SPEECH_MESSAGES.noSpeech);
  assert.equal(speechErrorMessage('audio-capture'), SPEECH_MESSAGES.audioCapture);
  assert.equal(speechErrorMessage('network'), SPEECH_MESSAGES.network);
  assert.equal(speechErrorMessage('other'), SPEECH_MESSAGES.generic);
});

test('transcriptFromEvent joins available recognition chunks', () => {
  const event = {
    resultIndex: 1,
    results: [
      [{ transcript: 'bỏ qua' }],
      [{ transcript: ' xin mã OTP ' }],
      [{ transcript: 'ngay' }],
    ],
  };
  assert.equal(transcriptFromEvent(event), 'xin mã OTP ngay');
  assert.equal(transcriptFromEvent(null), '');
});

test('appendTranscript preserves existing typed text with readable spacing', () => {
  assert.equal(appendTranscript('Tin cũ ', ' phần đọc mới '), 'Tin cũ phần đọc mới');
  assert.equal(appendTranscript('', 'nội dung'), 'nội dung');
});
