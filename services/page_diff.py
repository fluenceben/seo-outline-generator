import re
from difflib import SequenceMatcher

SIMILARITY_THRESHOLD = 0.6


def _normalize(text):
    text = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())
    return " ".join(text.split())


def is_covered(text, existing_headers, threshold=SIMILARITY_THRESHOLD):
    """True if `text` is a close match for wording already on the existing page."""
    norm = _normalize(text)
    if not norm:
        return False
    for header in existing_headers:
        existing_norm = _normalize(header.get("text", ""))
        if existing_norm and SequenceMatcher(None, norm, existing_norm).ratio() >= threshold:
            return True
    return False


def flag_new_headers(headers, existing_headers):
    """Annotate each header dict in place with `is_new` when an existing page is set.

    Leaves headers untouched (no `is_new` key) when there's no existing page to
    diff against, so callers can distinguish "not applicable" from "covered".
    """
    if not existing_headers:
        return headers
    for header in headers:
        header["is_new"] = not is_covered(header.get("text", ""), existing_headers)
    return headers
