"""Client HTTP gọi Google Gemini REST API với retry có kiểm soát (L1-05)."""
from __future__ import annotations

import json
import time
from typing import Any, Callable

import requests

from ..config import Config
from ..prompts import GEMINI_DETECTIVE_RESPONSE_SCHEMA


class GeminiError(Exception):
    """Lỗi khi gọi Gemini: mạng, HTTP, parse hoặc cấu hình."""


class GeminiRateLimitError(GeminiError):
    """Gemini tạm hết quota/rate limited sau khi đã retry."""


def _endpoint(api_key: str, model: str) -> str:
    """Tạo URL generateContent cho model đã cho."""
    if not api_key:
        raise GeminiError("Chưa cấu hình GEMINI_API_KEY.")
    return f"{Config.GEMINI_ENDPOINT}/{model}:generateContent?key={api_key}"


def _extract_text(payload: dict[str, Any]) -> str:
    """Bóc phần text từ phản hồi Gemini; trả chuỗi rỗng nếu cấu trúc thiếu."""
    try:
        parts = payload["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        return ""
    return "".join(part.get("text", "") for part in parts if isinstance(part, dict))


def _handle_response_error(payload: dict[str, Any]) -> None:
    """Ném lỗi có thông điệp Gemini khi payload chứa object ``error``."""
    err = payload.get("error")
    if isinstance(err, dict):
        message = err.get("message", "Lỗi không xác định từ Gemini.")
        raise GeminiError(str(message))


def _post_with_retry(
    *,
    url: str,
    body: dict[str, Any],
    timeout: float,
    max_retries: int,
    sleep: Callable[[float], None] | None = None,
) -> Any:
    """POST Gemini, retry tối đa ``max_retries`` cho 429/503 với backoff tăng dần."""
    if sleep is None:
        sleep = time.sleep
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(url, json=body, timeout=timeout)
        except requests.RequestException as exc:
            raise GeminiError(f"Không kết nối được tới AI. Vui lòng thử lại sau. ({exc})") from exc

        if response.status_code not in {429, 503}:
            return response
        if attempt == max_retries:
            raise GeminiRateLimitError(
                "AI đang quá tải hoặc tạm giới hạn lượt gọi. Vui lòng chờ ít phút rồi thử lại."
            )
        sleep(0.5 * (2**attempt))
    raise AssertionError("unreachable")


def _request(
    *,
    api_key: str,
    model: str,
    user_prompt: str,
    system_prompt: str,
    json_mode: bool,
    timeout: float | None,
    max_retries: int | None,
) -> dict[str, Any]:
    """Thực hiện một request Gemini và trả payload API đã decode."""
    url = _endpoint(api_key, model)
    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
    }
    if json_mode:
        body["generationConfig"] = {
            "response_mime_type": "application/json",
            "response_schema": GEMINI_DETECTIVE_RESPONSE_SCHEMA,
        }
    if system_prompt:
        body["system_instruction"] = {"parts": [{"text": system_prompt}]}

    response = _post_with_retry(
        url=url,
        body=body,
        timeout=Config.GEMINI_TIMEOUT if timeout is None else timeout,
        max_retries=Config.GEMINI_MAX_RETRIES if max_retries is None else max_retries,
    )
    try:
        payload = response.json()
    except ValueError as exc:
        raise GeminiError("AI trả về phản hồi không đọc được.") from exc

    # Với 429/503 exhausted đã được xử lý phía trên. Các lỗi khác ưu tiên message API.
    _handle_response_error(payload)
    if response.status_code >= 400:
        raise GeminiError(f"AI báo lỗi (HTTP {response.status_code}).")
    return payload


def generate_text(
    *,
    api_key: str,
    model: str,
    user_prompt: str,
    system_prompt: str = "",
    timeout: float | None = None,
    max_retries: int | None = None,
) -> str:
    """Gọi Gemini và trả text; giữ lại cho tương thích khi phát triển stage sau."""
    return _extract_text(
        _request(
            api_key=api_key,
            model=model,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            json_mode=False,
            timeout=timeout,
            max_retries=max_retries,
        )
    )


def generate_json(
    *,
    api_key: str,
    model: str,
    user_prompt: str,
    system_prompt: str = "",
    timeout: float | None = None,
    max_retries: int | None = None,
) -> dict[str, Any]:
    """Gọi Gemini JSON mode và lenient-parse phần text kết quả."""
    text = _extract_text(
        _request(
            api_key=api_key,
            model=model,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            json_mode=True,
            timeout=timeout,
            max_retries=max_retries,
        )
    )
    return _parse_json_lenient(text)


def _parse_json_lenient(text: str) -> dict[str, Any]:
    """Parse object JSON cả khi Gemini vô tình thêm text/code fence."""
    if not text.strip():
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            pass
    return {}
