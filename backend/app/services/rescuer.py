"""Người ứng cứu Stage 5: playbook, parser chặt và fallback an toàn."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..prompts import (
    GEMINI_RESCUER_RESPONSE_SCHEMA,
    RESCUER_SYSTEM_PROMPT,
    build_rescuer_user_prompt,
)
from .gemini import GeminiError, generate_json
from .hotlines import (
    Hotline,
    HotlineTable,
    contains_untrusted_contact,
    hotline_prompt_payload,
    strip_unknown_phones,
)

REQUIRED_STEP_KEYS: dict[str, tuple[str, ...]] = {
    "chua_lam_gi": ("stop", "verify", "report"),
    "da_bam_link": ("disconnect", "secure_accounts", "check_device", "report"),
    "da_chuyen_tien": ("call_bank", "preserve_evidence", "report_police", "avoid_recovery_scam"),
    "da_cung_cap_otp": ("lock_bank_access", "change_credentials", "preserve_evidence", "report"),
}
_BLOCKED_ACTION_RE = re.compile(
    r"(?:đọc|gửi|cung cấp|nhập|chia sẻ).{0,30}(?:otp|pin|mật khẩu|mã xác nhận)|"
    r"(?:bấm|mở|truy cập).{0,24}(?:link|đường dẫn)|"
    r"cài.{0,24}(?:điều khiển|remote)|(?:chuyển|nộp|trả|đóng).{0,30}(?:tiền|phí)|"
    r"(?:chắc chắn|đảm bảo).{0,30}(?:an toàn|lấy lại|thu hồi)",
    re.I,
)
_SAFE_CONTEXT_RE = re.compile(r"\b(?:không|đừng|tránh|chớ|sau khi|đã lỡ)\b", re.I)
_IMPERATIVE_RE = re.compile(r"\b(?:hãy|cần|nên|phải|vui lòng|tiếp tục)\b", re.I)


def _has_unsafe_guidance(text: str) -> bool:
    """Chặn mệnh lệnh nguy hiểm; không nhầm mô tả sự cố/câu phủ định là chỉ dẫn."""
    for sentence in re.split(r"[.!?]+", text):
        for match in _BLOCKED_ACTION_RE.finditer(sentence):
            prefix = sentence[:match.start()]
            if _SAFE_CONTEXT_RE.search(prefix):
                continue
            if not prefix.strip() or _IMPERATIVE_RE.search(prefix[-48:]):
                return True
    return False


@dataclass(frozen=True)
class RescueStep:
    step: int
    key: str
    action: str
    detail: str
    hotlines: tuple[Hotline, ...] = ()

    def to_dict(self, reviewed_at: str) -> dict[str, Any]:
        return {
            "step": self.step,
            "key": self.key,
            "action": self.action,
            "detail": self.detail,
            "hotlines": [item.to_public_dict(reviewed_at) for item in self.hotlines],
        }


@dataclass(frozen=True)
class RescueResult:
    situation: str
    headline: str
    reassurance: str
    steps: tuple[RescueStep, ...]
    closing: str
    is_fallback: bool = False

    def to_dict(self, reviewed_at: str) -> dict[str, Any]:
        return {
            "situation": self.situation,
            "headline": self.headline,
            "reassurance": self.reassurance,
            "steps": [item.to_dict(reviewed_at) for item in self.steps],
            "closing": self.closing,
            "is_fallback": self.is_fallback,
        }


@dataclass(frozen=True)
class RescuePipelineOutcome:
    result: RescueResult
    status: str
    ai_called: bool
    error: str | None = None


def _clean_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().split())[:limit]


def _hotlines_for_case(
    situation: str,
    table: HotlineTable,
    matched_banks: list[Hotline],
) -> dict[str, Hotline]:
    by_id = table.by_id()
    selected = {item.id: item for item in matched_banks}
    for identifier in ("ais_156",):
        if identifier in by_id:
            selected[identifier] = by_id[identifier]
    # 113 vẫn nằm trong bảng public để đối chiếu nhưng không được gắn tự động vào
    # flow lừa đảo thông thường: bốn situation không chứng minh đang có nguy hiểm tức thời.
    return selected


def _hotline_ids_by_step(
    situation: str,
    allowed: dict[str, Hotline],
) -> dict[str, list[str]]:
    banks = [identifier for identifier, item in allowed.items() if item.type == "bank"]
    cyber = [identifier for identifier, item in allowed.items() if item.type == "cybersecurity"]
    mapping: dict[str, list[str]] = {key: [] for key in REQUIRED_STEP_KEYS[situation]}
    if situation == "chua_lam_gi":
        mapping["report"] = cyber
    elif situation == "da_bam_link":
        mapping["report"] = cyber
    elif situation == "da_chuyen_tien":
        mapping["call_bank"] = banks
    elif situation == "da_cung_cap_otp":
        mapping["lock_bank_access"] = banks
        mapping["report"] = cyber
    return mapping


def _make_step(
    number: int,
    key: str,
    action: str,
    detail: str,
    hotline_ids: tuple[str, ...],
    allowed: dict[str, Hotline],
) -> RescueStep:
    hotlines = tuple(allowed[item] for item in hotline_ids if item in allowed)[:2]
    whitelist = [item.phone for item in hotlines]
    safe_action = strip_unknown_phones(action, whitelist)
    safe_detail = strip_unknown_phones(detail, whitelist)
    return RescueStep(number, key, safe_action, safe_detail, hotlines)


def _bank_call_copy(matched_banks: list[Hotline], purpose: str) -> tuple[str, str, tuple[str, ...]]:
    if matched_banks:
        bank = matched_banks[0]
        return (
            f"Gọi ngay {bank.name}",
            purpose,
            (bank.id,),
        )
    return (
        "Gọi ngay ngân hàng bằng số trên mặt sau thẻ",
        purpose + " Không gọi số do người lạ gửi trong tin nhắn.",
        (),
    )


def build_deterministic_result(
    situation: str,
    table: HotlineTable,
    matched_banks: list[Hotline],
    *,
    fallback: bool,
) -> RescueResult:
    """Playbook bảo vệ luôn sẵn sàng, kể cả Gemini lỗi hoặc trả nội dung không an toàn."""
    allowed = _hotlines_for_case(situation, table, matched_banks)
    if situation == "chua_lam_gi":
        specs = [
            ("stop", "Bác đã dừng đúng lúc", "Không bấm link, không chuyển tiền và không đưa OTP hay mật khẩu.", ()),
            ("verify", "Tự mở kênh chính thức để kiểm tra", "Đóng tin nhắn rồi tự mở ứng dụng hoặc gõ địa chỉ website quen thuộc của đơn vị được nhắc đến.", ()),
            ("report", "Chặn và phản ánh tin lừa đảo", "Có thể gọi hệ thống phản ánh cuộc gọi, tin nhắn lừa đảo; không tiếp tục tranh luận với người gửi.", ("ais_156",)),
        ]
        headline = "Ba việc để giữ an toàn"
        reassurance = ""
        closing = "Nếu còn phân vân, bác hãy nhờ một người tin cậy cùng kiểm tra qua kênh chính thức."
    elif situation == "da_bam_link":
        specs = [
            ("disconnect", "Đóng trang lạ và ngắt thao tác", "Không nhập thêm thông tin, không tải tệp và không cấp quyền cho trang hoặc ứng dụng lạ.", ()),
            ("secure_accounts", "Đổi mật khẩu nếu bác đã nhập thông tin", "Dùng một thiết bị tin cậy, đổi mật khẩu tài khoản liên quan và bật xác thực hai bước nếu có.", ()),
            ("check_device", "Kiểm tra thiết bị", "Gỡ ứng dụng hoặc tệp vừa tải nếu có; kiểm tra quyền trợ năng, chia sẻ màn hình và ứng dụng điều khiển từ xa.", ()),
            ("report", "Theo dõi tài khoản và phản ánh đường link", "Nếu đã nhập thông tin ngân hàng, gọi số trên mặt sau thẻ ngay. Bác cũng có thể phản ánh tin lừa đảo.", ("ais_156",)),
        ]
        headline = "Dừng sử dụng đường link và bảo vệ tài khoản ngay"
        reassurance = "Bấm link chưa có nghĩa là chắc chắn mất tiền; điều quan trọng là bác ngừng thao tác và kiểm tra ngay bây giờ."
        closing = "Không trả phí cho bất kỳ ai hứa xóa dữ liệu hoặc thu hồi tiền từ đường link này."
    elif situation == "da_chuyen_tien":
        action, detail, ids = _bank_call_copy(
            matched_banks,
            "Nói rõ giao dịch nghi lừa đảo và đề nghị khóa giao dịch, tra soát hoặc giữ tiền nếu còn kịp.",
        )
        specs = [
            ("call_bank", action, detail, ids),
            ("preserve_evidence", "Giữ nguyên bằng chứng", "Chụp màn hình cuộc trò chuyện, biên lai, số tài khoản nhận, thời gian và mã giao dịch; không xóa tin nhắn.", ()),
            ("report_police", "Trình báo Công an", "Đến cơ quan Công an gần nhất với bằng chứng. Nếu đang bị đe dọa hoặc cần trợ giúp khẩn cấp, dùng số khẩn cấp đã tự đối chiếu.", ()),
            ("avoid_recovery_scam", "Không trả thêm phí để “thu hồi tiền”", "Kẻ xấu có thể giả người hỗ trợ và yêu cầu chuyển thêm tiền. Chỉ làm việc với ngân hàng và cơ quan chức năng qua kênh chính thức.", ()),
        ]
        headline = "Gọi ngân hàng ngay — từng phút đều có ích"
        reassurance = "Bác không cần tự trách mình. Hãy làm lần lượt từng bước và giữ lại mọi bằng chứng."
        closing = "ScamCheck không thể hứa lấy lại tiền; ngân hàng và cơ quan chức năng mới có quyền xử lý giao dịch."
    elif situation == "da_cung_cap_otp":
        action, detail, ids = _bank_call_copy(
            matched_banks,
            "Yêu cầu khóa ngân hàng số, thẻ hoặc giao dịch đang chờ và nói rõ bác đã lộ mã OTP.",
        )
        specs = [
            ("lock_bank_access", action, detail, ids),
            ("change_credentials", "Đổi thông tin đăng nhập trên thiết bị tin cậy", "Đổi mật khẩu ngân hàng, email liên kết và tài khoản có dùng lại mật khẩu; không cung cấp thêm mã xác nhận.", ()),
            ("preserve_evidence", "Giữ tin nhắn và kiểm tra giao dịch", "Chụp lại số gửi, nội dung, thời điểm lộ OTP và mọi biến động số dư để ngân hàng đối chiếu.", ()),
            ("report", "Phản ánh số điện thoại hoặc tin nhắn lừa đảo", "Chặn người gửi sau khi lưu bằng chứng và phản ánh qua hệ thống chính thức.", ("ais_156",)),
        ]
        headline = "Khóa quyền truy cập ngân hàng ngay"
        reassurance = "OTP có thể mở đường cho giao dịch trái phép, nhưng hành động nhanh vẫn giúp giảm thiệt hại."
        closing = "Nhân viên thật không yêu cầu bác đọc OTP; từ bây giờ không gửi thêm bất kỳ mã nào."
    else:
        raise ValueError("Tình huống không hợp lệ.")

    steps = tuple(
        _make_step(index, key, action, detail, tuple(ids), allowed)
        for index, (key, action, detail, ids) in enumerate(specs, start=1)
    )
    return RescueResult(situation, headline, reassurance, steps, closing, fallback)


def parse_rescuer(
    raw: Any,
    *,
    situation: str,
    table: HotlineTable,
    matched_banks: list[Hotline],
) -> RescueResult | None:
    """Chỉ nhận đủ playbook keys, lọc hotline id và chặn chỉ dẫn nguy hiểm/số lạ."""
    if not isinstance(raw, dict) or situation not in REQUIRED_STEP_KEYS:
        return None
    headline = _clean_text(raw.get("headline"), 120)
    reassurance = _clean_text(raw.get("reassurance"), 240)
    closing = _clean_text(raw.get("closing"), 240)
    raw_steps = raw.get("steps")
    if not headline or not reassurance or not closing or not isinstance(raw_steps, list):
        return None

    required = REQUIRED_STEP_KEYS[situation]
    by_key: dict[str, dict[str, Any]] = {}
    for item in raw_steps:
        if not isinstance(item, dict):
            continue
        key = item.get("step_key")
        if key in required and key not in by_key:
            by_key[key] = item
    if tuple(key for key in required if key in by_key) != required:
        return None

    allowed = _hotlines_for_case(situation, table, matched_banks)
    ids_by_step = _hotline_ids_by_step(situation, allowed)
    text_fields = [headline, reassurance, closing] + [
        str(value)
        for item in by_key.values()
        for value in (item.get("action"), item.get("detail"))
    ]
    all_text = " ".join(text_fields)
    whitelist = [item.phone for item in allowed.values()]
    if any(_has_unsafe_guidance(field) for field in text_fields) or contains_untrusted_contact(all_text, whitelist):
        return None

    steps: list[RescueStep] = []
    for index, key in enumerate(required, start=1):
        item = by_key[key]
        action = _clean_text(item.get("action"), 180)
        detail = _clean_text(item.get("detail"), 360)
        raw_ids = item.get("hotline_ids")
        ids = tuple(
            identifier for identifier in raw_ids or []
            if isinstance(identifier, str) and identifier in ids_by_step[key]
        )[:2]
        if not action or not detail:
            return None
        steps.append(_make_step(index, key, action, detail, ids, allowed))

    return RescueResult(
        situation=situation,
        headline=strip_unknown_phones(headline, whitelist),
        reassurance=strip_unknown_phones(reassurance, whitelist),
        steps=tuple(steps),
        closing=strip_unknown_phones(closing, whitelist),
        is_fallback=False,
    )


def build_rescue_pipeline(
    *,
    situation: str,
    table: HotlineTable,
    matched_banks: list[Hotline],
    context: dict[str, Any],
    api_key: str,
    model: str,
    ai_enabled: bool = True,
) -> RescuePipelineOutcome:
    """Gọi Rescuer một lần rồi fail closed sang playbook deterministic."""
    if situation == "chua_lam_gi":
        return RescuePipelineOutcome(
            build_deterministic_result(situation, table, matched_banks, fallback=False),
            status="not_needed",
            ai_called=False,
        )
    if not ai_enabled:
        return RescuePipelineOutcome(
            build_deterministic_result(situation, table, matched_banks, fallback=True),
            status="guarded_fallback",
            ai_called=False,
            error="Người ứng cứu tự động đang được tạm tắt; đang dùng quy trình an toàn có sẵn.",
        )
    allowed = _hotlines_for_case(situation, table, matched_banks)
    prompt = build_rescuer_user_prompt(
        situation=situation,
        required_step_keys=list(REQUIRED_STEP_KEYS[situation]),
        allowed_hotlines=hotline_prompt_payload(table),
        allowed_hotline_ids=list(allowed),
        hotline_ids_by_step=_hotline_ids_by_step(situation, allowed),
        context=context,
    )
    try:
        raw = generate_json(
            api_key=api_key,
            model=model,
            user_prompt=prompt,
            system_prompt=RESCUER_SYSTEM_PROMPT,
            response_schema=GEMINI_RESCUER_RESPONSE_SCHEMA,
            timeout=6.0,
            max_retries=0,
        )
        parsed = parse_rescuer(
            raw,
            situation=situation,
            table=table,
            matched_banks=matched_banks,
        )
        if parsed is not None:
            # Không render bất kỳ crisis prose nào do model sinh. AI call chỉ xác nhận đủ
            # step keys theo schema; toàn bộ copy người dùng thấy là playbook đã review.
            fixed = build_deterministic_result(
                situation, table, matched_banks, fallback=False
            )
            return RescuePipelineOutcome(fixed, status="complete", ai_called=True)
        return RescuePipelineOutcome(
            build_deterministic_result(situation, table, matched_banks, fallback=True),
            status="guarded_fallback",
            ai_called=True,
            error="Người ứng cứu tự động trả lời chưa đạt guardrail; đang dùng quy trình an toàn có sẵn.",
        )
    except GeminiError:
        return RescuePipelineOutcome(
            build_deterministic_result(situation, table, matched_banks, fallback=True),
            status="guarded_fallback",
            ai_called=True,
            error="Người ứng cứu tự động đang tạm bận; đang dùng quy trình an toàn có sẵn.",
        )
