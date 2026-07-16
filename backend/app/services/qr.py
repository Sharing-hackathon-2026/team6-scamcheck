"""QR Code Version 3-L byte encoder tối thiểu, thuần standard library.

Chỉ dùng để mã hóa URL ngắn dẫn về ScamCheck. Không phụ thuộc dịch vụ QR mạng
hay package runtime. Thuật toán theo ISO/IEC 18004: byte mode, Reed–Solomon,
mask 0 và format BCH.
"""
from __future__ import annotations

import html
from collections.abc import Iterable
from urllib.parse import urlparse

_VERSION = 3
_SIZE = 17 + 4 * _VERSION
_DATA_CODEWORDS = 55
_ECC_CODEWORDS = 15
_MAX_BYTES = 53


def approved_share_url(
    configured_url: str,
    request_root: str,
    allowed_hosts: Iterable[str],
) -> str:
    """Chỉ nhận origin ScamCheck allowlisted; fail closed trước Host-header/config xấu."""
    candidate = configured_url.strip() or request_root.strip()
    try:
        parsed = urlparse(candidate)
        host = (parsed.hostname or "").casefold()
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Địa chỉ chia sẻ không hợp lệ.") from exc
    allowed = {item.strip().casefold() for item in allowed_hosts if item.strip()}
    is_local = host in {"localhost", "127.0.0.1"}
    if (
        host not in allowed
        or parsed.scheme not in ({"http", "https"} if is_local else {"https"})
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("Địa chỉ chia sẻ không thuộc origin ScamCheck đã phê duyệt.")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Cổng chia sẻ không hợp lệ.")
    # Origin public không được lộ cổng dịch vụ nội bộ. HTTPS :443 được
    # canonicalize về URL không port; localhost vẫn giữ port phục vụ dev.
    if not is_local and port not in {None, 443}:
        raise ValueError("Địa chỉ chia sẻ public không được chứa cổng nội bộ.")
    netloc = parsed.netloc if is_local else host
    return f"{parsed.scheme}://{netloc}/"


def _gf_multiply(x: int, y: int) -> int:
    result = 0
    for shift in reversed(range(8)):
        result = (result << 1) ^ ((result >> 7) * 0x11D)
        result ^= ((y >> shift) & 1) * x
    return result & 0xFF


def _rs_divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for index in range(degree):
            result[index] = _gf_multiply(result[index], root)
            if index + 1 < degree:
                result[index] ^= result[index + 1]
        root = _gf_multiply(root, 0x02)
    return result


def _rs_remainder(data: list[int], divisor: list[int]) -> list[int]:
    result = [0] * len(divisor)
    for byte in data:
        factor = byte ^ result.pop(0)
        result.append(0)
        for index, coefficient in enumerate(divisor):
            result[index] ^= _gf_multiply(coefficient, factor)
    return result


def _append_bits(bits: list[int], value: int, length: int) -> None:
    for shift in reversed(range(length)):
        bits.append((value >> shift) & 1)


def _encode_codewords(text: str) -> list[int]:
    payload = text.encode("utf-8")
    if len(payload) > _MAX_BYTES:
        raise ValueError("URL quá dài cho QR chia sẻ cố định.")
    bits: list[int] = []
    _append_bits(bits, 0b0100, 4)  # byte mode
    _append_bits(bits, len(payload), 8)
    for byte in payload:
        _append_bits(bits, byte, 8)
    capacity = _DATA_CODEWORDS * 8
    bits.extend([0] * min(4, capacity - len(bits)))
    bits.extend([0] * ((8 - len(bits) % 8) % 8))
    data = [sum(bits[index + bit] << (7 - bit) for bit in range(8)) for index in range(0, len(bits), 8)]
    pads = (0xEC, 0x11)
    while len(data) < _DATA_CODEWORDS:
        data.append(pads[(len(data) - ((len(bits) + 7) // 8)) % 2])
    return data + _rs_remainder(data, _rs_divisor(_ECC_CODEWORDS))


def _set_function(
    modules: list[list[bool]],
    functions: list[list[bool]],
    x: int,
    y: int,
    dark: bool,
) -> None:
    if 0 <= x < _SIZE and 0 <= y < _SIZE:
        modules[y][x] = dark
        functions[y][x] = True


def _draw_finder(modules: list[list[bool]], functions: list[list[bool]], cx: int, cy: int) -> None:
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            distance = max(abs(dx), abs(dy))
            _set_function(modules, functions, cx + dx, cy + dy, distance not in {2, 4})


def _draw_alignment(modules: list[list[bool]], functions: list[list[bool]], cx: int, cy: int) -> None:
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            _set_function(modules, functions, cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)


def _format_bits(mask: int = 0) -> int:
    data = (0b01 << 3) | mask  # error correction level L
    remainder = data
    for _ in range(10):
        remainder = (remainder << 1) ^ ((remainder >> 9) * 0x537)
    return ((data << 10) | remainder) ^ 0x5412


def _draw_format(modules: list[list[bool]], functions: list[list[bool]], mask: int = 0) -> None:
    bits = _format_bits(mask)
    for index in range(0, 6):
        _set_function(modules, functions, 8, index, ((bits >> index) & 1) != 0)
    _set_function(modules, functions, 8, 7, ((bits >> 6) & 1) != 0)
    _set_function(modules, functions, 8, 8, ((bits >> 7) & 1) != 0)
    _set_function(modules, functions, 7, 8, ((bits >> 8) & 1) != 0)
    for index in range(9, 15):
        _set_function(modules, functions, 14 - index, 8, ((bits >> index) & 1) != 0)
    for index in range(0, 8):
        _set_function(modules, functions, _SIZE - 1 - index, 8, ((bits >> index) & 1) != 0)
    for index in range(8, 15):
        _set_function(modules, functions, 8, _SIZE - 15 + index, ((bits >> index) & 1) != 0)
    _set_function(modules, functions, 8, _SIZE - 8, True)


def encode_qr_matrix(text: str) -> tuple[tuple[bool, ...], ...]:
    """Mã hóa URL UTF-8 ngắn thành ma trận QR 29×29 hợp lệ."""
    codewords = _encode_codewords(text)
    modules = [[False] * _SIZE for _ in range(_SIZE)]
    functions = [[False] * _SIZE for _ in range(_SIZE)]

    for index in range(8, _SIZE - 8):
        _set_function(modules, functions, 6, index, index % 2 == 0)
        _set_function(modules, functions, index, 6, index % 2 == 0)
    _draw_finder(modules, functions, 3, 3)
    _draw_finder(modules, functions, _SIZE - 4, 3)
    _draw_finder(modules, functions, 3, _SIZE - 4)
    _draw_alignment(modules, functions, 22, 22)
    _draw_format(modules, functions, 0)  # also reserves all format modules

    bit_length = len(codewords) * 8
    bit_index = 0
    right = _SIZE - 1
    upward = True
    while right >= 1:
        if right == 6:
            right -= 1
        for vertical in range(_SIZE):
            y = _SIZE - 1 - vertical if upward else vertical
            for offset in range(2):
                x = right - offset
                if functions[y][x]:
                    continue
                dark = False
                if bit_index < bit_length:
                    dark = ((codewords[bit_index >> 3] >> (7 - (bit_index & 7))) & 1) != 0
                bit_index += 1
                if (x + y) % 2 == 0:  # mask pattern 0
                    dark = not dark
                modules[y][x] = dark
        upward = not upward
        right -= 2
    if bit_index < bit_length:
        raise AssertionError("QR matrix không đủ chỗ cho codeword.")
    return tuple(tuple(row) for row in modules)


def qr_svg(text: str, *, scale: int = 8, border: int = 4) -> str:
    """Render SVG có quiet zone; màu cố định đen/trắng để máy quét nhận ổn định."""
    if scale < 1 or border < 4:
        raise ValueError("QR cần scale dương và quiet zone ít nhất 4 module.")
    matrix = encode_qr_matrix(text)
    dimension = (len(matrix) + border * 2) * scale
    cells = []
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark:
                cells.append(f"M{x + border},{y + border}h1v1h-1z")
    path = "".join(cells)
    label = html.escape(f"Mã QR dẫn tới {text}", quote=True)
    view = len(matrix) + border * 2
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{dimension}" height="{dimension}" '
        f'viewBox="0 0 {view} {view}" role="img" aria-label="{label}" shape-rendering="crispEdges">'
        f'<rect width="100%" height="100%" fill="#fff"/><path d="{path}" fill="#000"/></svg>'
    )
