"""Redact raw captures into tracked fixtures with synthetic personal data."""

import json
import uuid
from pathlib import Path
from typing import Any

from aiofarmad.const import CLAIM_ACCOUNT_ID

REPO = Path(__file__).resolve().parent.parent
SYNTHETIC_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_OID, "aiofarmad redaction")

REDACTIONS: tuple[tuple[str, str], ...] = (
    ("captures/baskets_raw.json", "tests/fixtures/baskets.json"),
    ("captures/patient_raw.json", "tests/fixtures/patient.json"),
)

NAME_FIELDS = {
    "name": "USER",
    "firstName": "TEST",
    "nameMyCareNet": "USER",
    "firstNameMyCareNet": "TEST",
}
EMAIL_FIELDS = {"email": "user@example.com"}
DATE_FIELDS = {"dateOfBirth": "1990-01-01T00:00:00+00:00", "lastVisit": "2000-01-01T00:00:00+00:00"}
APB_FIELDS = {"apb", "apbNumber"}


def synthetic_uuid(value: str) -> str:
    """Map one identifier to a stable synthetic identifier."""
    return str(uuid.uuid5(SYNTHETIC_NAMESPACE, value))


def synthetic_apb(value: str) -> str:
    """Map one pharmacy number to a stable synthetic pharmacy number."""
    return f"34{uuid.uuid5(SYNTHETIC_NAMESPACE, 'apb' + value).int % 10000:04d}"


def is_uuid(value: str) -> bool:
    """Return True when a string parses as a UUID."""
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


KEY_REPLACEMENTS = NAME_FIELDS | EMAIL_FIELDS


def redact_scalar(value: Any, key: str) -> Any:
    """Replace one scalar in place when its key marks personal data."""
    if key in KEY_REPLACEMENTS:
        return KEY_REPLACEMENTS[key]
    if key in DATE_FIELDS and isinstance(value, str):
        return DATE_FIELDS[key]
    if key in APB_FIELDS and isinstance(value, str):
        return synthetic_apb(value)
    if key == "customerNumber" and isinstance(value, int):
        return 10000 + (uuid.uuid5(SYNTHETIC_NAMESPACE, str(value)).int % 90000)
    if isinstance(value, str) and is_uuid(value):
        return synthetic_uuid(value)
    return value


def redact(value: Any, key: str = "") -> Any:
    """Replace personal data in one value, recursing into containers."""
    if isinstance(value, dict):
        if key == "patient_in_apbs":
            return {
                synthetic_apb(apb): redact(record)
                for apb, record in value.items()
                if isinstance(apb, str)
            }
        return {
            name: redact(item, name) for name, item in value.items() if name != CLAIM_ACCOUNT_ID
        }
    if isinstance(value, list):
        return [redact(item, key) for item in value]
    return redact_scalar(value, key)


def main() -> None:
    """Rewrite every tracked fixture from its raw capture."""
    for source, target in REDACTIONS:
        raw_path = REPO / source
        if not raw_path.is_file():
            print("skipping missing capture", source)
            continue
        payload = json.loads(raw_path.read_text())
        (REPO / target).write_text(json.dumps(redact(payload), indent=2, ensure_ascii=False) + "\n")
        print("redacted", source, "->", target)


if __name__ == "__main__":
    main()
