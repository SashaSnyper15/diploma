from dataclasses import dataclass

from .models import Project
from .schemas import ModerationRequest, SignalOut


@dataclass
class EngineResult:
    status: str
    recommended_action: str
    risk_score: int
    signals: list[SignalOut]


def _normalize(value: str) -> str:
    return value.strip().lower()


def _contains_any(text: str, phrases: list[str]) -> list[str]:
    lowered = _normalize(text)
    matches: list[str] = []
    for phrase in phrases:
        normalized_phrase = _normalize(phrase)
        if normalized_phrase and normalized_phrase in lowered:
            matches.append(phrase)
    return matches


def evaluate_payload(project: Project, payload: ModerationRequest) -> EngineResult:
    text = " ".join([payload.title, payload.description])
    signals: list[SignalOut] = []
    score = 0

    normalized_category = _normalize(payload.category)
    banned_categories = {_normalize(item) for item in project.banned_categories}
    cert_categories = {_normalize(item) for item in project.certificate_required_categories}

    if normalized_category in banned_categories:
        signals.append(
            SignalOut(
                code="BANNED_CATEGORY",
                severity="critical",
                score=95,
                message=f"Категория '{payload.category}' запрещена для публикации",
            )
        )
        score += 95

    banned_matches = _contains_any(text, project.banned_keywords)
    if banned_matches:
        signals.append(
            SignalOut(
                code="BANNED_KEYWORDS",
                severity="high",
                score=80,
                message=f"Обнаружены запрещенные формулировки: {', '.join(banned_matches)}",
            )
        )
        score += 80

    risky_matches = _contains_any(text, project.risky_keywords)
    if risky_matches:
        signals.append(
            SignalOut(
                code="RISKY_KEYWORDS",
                severity="medium",
                score=40,
                message=f"Обнаружены рискованные формулировки: {', '.join(risky_matches)}",
            )
        )
        score += 40

    missing_fields: list[str] = []
    for field_name in project.required_fields:
        value = payload.attributes.get(field_name)
        if value in (None, "", [], {}):
            missing_fields.append(field_name)
    if missing_fields:
        signals.append(
            SignalOut(
                code="MISSING_REQUIRED_FIELDS",
                severity="medium",
                score=35,
                message=f"Отсутствуют обязательные атрибуты: {', '.join(missing_fields)}",
            )
        )
        score += 35

    if normalized_category in cert_categories:
        has_certificate = bool(payload.attributes.get("certificate_number") or payload.attributes.get("has_certificate"))
        if not has_certificate:
            signals.append(
                SignalOut(
                    code="CERTIFICATE_REQUIRED",
                    severity="high",
                    score=70,
                    message="Для этой категории нужно подтверждение сертификата или декларации",
                )
            )
            score += 70

    risky_images: list[str] = []
    image_markers = ["weapon", "drug", "18+", "counterfeit"]
    for image_url in payload.image_urls:
        lowered = _normalize(image_url)
        if any(marker in lowered for marker in image_markers):
            risky_images.append(image_url)
    if risky_images:
        signals.append(
            SignalOut(
                code="RISKY_IMAGE_MARKER",
                severity="medium",
                score=30,
                message=f"Найдены рискованные маркеры в URL изображений: {len(risky_images)} шт.",
            )
        )
        score += 30

    if any(signal.severity == "critical" for signal in signals):
        status = "rejected"
        action = "reject"
    elif score >= project.risk_threshold or any(signal.severity in {"high", "medium"} for signal in signals):
        status = "manual_review"
        action = "send_to_manual_review"
    else:
        status = "approved"
        action = "approve"

    bounded_score = min(score, 100)
    return EngineResult(
        status=status,
        recommended_action=action,
        risk_score=bounded_score,
        signals=signals,
    )

