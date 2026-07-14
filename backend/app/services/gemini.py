"""Client HTTP gọi Google Gemini REST API.

Dùng `requests` (không SDK) để:
  - kiểm soát tuần tự các lời gọi (Cấp 3/5: Thám tử → Cô tâm lý → Người ứng cứu),
  - dễ mock trong test,
  - hiểu rõ luồng dữ liệu thật.

Mọi hàm ở đây là pure function nhận `api_key`/`model` làm tham số,
không đọc trực tiếp Flask → test được bằng pytest mà không cần server.
"""
from __future__ import annotations

import json
from typing import Any

import requests

from ..config import Config


class GeminiError(Exception):
    """Lỗi khi gọi Gemini: mạng, HTTP, parse hoặc cấu hình."""


def _endpoint(api_key: str, model: str) -> str:
    """Tạo URL generateContent cho model đã cho."""
    if not api_key:
        raise GeminiError("Chưa cấu hình GEMINI_API_KEY.")
    return f"{Config.GEMINI_ENDPOINT}/{model}:generateContent?key={api_key}"


def _extract_text(payload: dict[str, Any]) -> str:
    """Bóc phần text từ phản hồi generateContent.

    Gemini trả: candidates[0].content.parts[*].text.
    Trả "" nếu cấu trúc thiếu — caller tự xử lý fallback.
    """
    try:
        parts = payload["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        return ""

    return "".join(p.get("text", "") for p in parts if isinstance(p, dict))


def _handle_response_error(payload: dict[str, Any]) -> None:
    """Nếu payload chứa trường 'error' của Gemini, ném GeminiError."""
    err = payload.get("error")
    if isinstance(err, dict):
        msg = err.get("message", "Lỗi không xác định từ Gemini.")
        raise GeminiError(msg)


def generate_text(
    *,
    api_key: str,
    model: str,
    user_prompt: str,
    system_prompt: str = "",
    timeout: float | None = None,
) -> str:
    """Gọi Gemini, trả văn bản thô (Cấp 1).

    Args:
        api_key: khóa Gemini.
        model: tên model (vd "gemini-3.1-flash-lite").
        user_prompt: nội dung tin nhắn cần phân tích.
        system_prompt: hướng dẫn vai (Stage 2+: Thám tử).
        timeout: giây (mặc định Config.GEMINI_TIMEOUT).

    Returns:
        Văn bản AI trả về. Có thể rỗng nếu AI không sinh được text.

    Raises:
        GeminiError: lỗi mạng/HTTP/parse/cấu hình.
    """
    if timeout is None:
        timeout = Config.GEMINI_TIMEOUT

    url = _endpoint(api_key, model)
    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
    }
    if system_prompt:
        body["system_instruction"] = {"parts": [{"text": system_prompt}]}

    try:
        resp = requests.post(url, json=body, timeout=timeout)
    except requests.RequestException as exc:
        raise GeminiError(f"Không kết nối được tới AI. Vui lòng thử lại sau. ({exc})") from exc

    try:
        payload = resp.json()
    except ValueError as exc:
        raise GeminiError("AI trả về phản hồi không đọc được.") from exc

    _handle_response_error(payload)

    if resp.status_code >= 400:
        raise GeminiError(f"AI báo lỗi (HTTP {resp.status_code}).")

    return _extract_text(payload)


def generate_json(
    *,
    api_key: str,
    model: str,
    user_prompt: str,
    system_prompt: str = "",
    timeout: float | None = None,
) -> dict[str, Any]:
    """Gọi Gemini ở chế độ JSON, trả dict đã parse (Stage 2+).

    Yêu cầu response_mime_type=application/json để parse deterministic.
    Fallback parse thủ công nếu AI bọc JSON trong text.
    """
    if timeout is None:
        timeout = Config.GEMINI_TIMEOUT

    url = _endpoint(api_key, model)
    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"},
    }
    if system_prompt:
        body["system_instruction"] = {"parts": [{"text": system_prompt}]}

    try:
        resp = requests.post(url, json=body, timeout=timeout)
    except requests.RequestException as exc:
        raise GeminiError(f"Không kết nối được tới AI. ({exc})") from exc

    try:
        payload = resp.json()
    except ValueError as exc:
        raise GeminiError("AI trả về phản hồi không đọc được.") from exc

    _handle_response_error(payload)

    if resp.status_code >= 400:
        raise GeminiError(f"AI báo lỗi (HTTP {resp.status_code}).")

    text = _extract_text(payload)
    return _parse_json_lenient(text)


def _parse_json_lenient(text: str) -> dict[str, Any]:
    """Parse JSON từ text, chịu lỗi: bóc JSON trong code fence / text thừa.

    Stage 2 parser sẽ validate chặt hơn; hàm này chỉ đảm bảo trả dict.
    """
    if not text.strip():
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Thử bóc phần {...} đầu tiên.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {}
