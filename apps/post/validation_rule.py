"""Category-specific validation helpers for post creation/update."""

from dataclasses import dataclass
from typing import Optional

from apps.post.models import CategoryType


class CategoryValidationError(ValueError):
    """Raised when a category-specific constraint is violated."""


@dataclass(frozen=True)
class CategoryValidationResult:
    """Normalized payload fragments coming from the validation step."""

    place_id: Optional[int] = None
    hazard_payload: Optional[str] = None


def _sanitize_optional_string(value) -> Optional[str]:
    """Return a stripped string or ``None`` when the input is empty."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_optional_positive_int(raw_value, field_label: str) -> Optional[int]:
    """Parse optional integer form inputs and enforce positivity."""

    normalized = _sanitize_optional_string(raw_value)
    if normalized is None:
        return None
    try:
        parsed = int(normalized)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise CategoryValidationError(f"{field_label}는 숫자여야 합니다.") from exc
    if parsed <= 0:
        raise CategoryValidationError(f"{field_label}는 1 이상의 값이어야 합니다.")
    return parsed


def validate_category_payload(
    category: str,
    *,
    place_id: Optional[int] = None,
    hazard_payload: Optional[str] = None,
) -> CategoryValidationResult:
    """Validate category-dependent payload requirements.

    Args:
            category: Canonical category name (already validated against ``CategoryType``).
            has_route_payload: ``True`` when any route/location information is supplied.
            place_id: Optional validated place identifier.
            hazard_payload: Optional hazard metadata (string/JSON coming from the client).

    Returns:
            :class:`CategoryValidationResult` with the normalized fragments.

    Raises:
            CategoryValidationError: If the payload violates category requirements.
    """

    if not category:
        raise CategoryValidationError("카테고리가 비어 있습니다.")

    if category == CategoryType.STORY:
        if place_id is not None:
            raise CategoryValidationError("STORY 카테고리는 장소를 연결할 수 없습니다.")
        if hazard_payload is not None:
            raise CategoryValidationError(
                "STORY 카테고리는 hazard 정보를 포함할 수 없습니다."
            )

    elif category == CategoryType.ROUTE:
        # ROUTE 카테고리는 route_id가 필요 (place_id 불필요)
        pass

    elif category == CategoryType.REVIEW:
        if place_id is None:
            raise CategoryValidationError("REVIEW 카테고리는 place_id가 필요합니다.")

    elif category == CategoryType.REPORT:
        if hazard_payload is None:
            raise CategoryValidationError("REPORT 카테고리는 hazard 정보가 필요합니다.")

    return CategoryValidationResult(place_id=place_id, hazard_payload=hazard_payload)
