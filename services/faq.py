import re
from difflib import SequenceMatcher

QUESTION_STARTERS = (
    "what", "how", "why", "when", "where", "which", "who", "whose",
    "can", "could", "is", "are", "does", "do", "did", "should", "will", "would",
)

FALLBACK_TEMPLATES = {
    "service": [
        "How much does {keyword} cost?",
        "How long does {keyword} take?",
        "What is included in {keyword}?",
        "Why choose us for {keyword}?",
    ],
    "informational": [
        "What is {keyword}?",
        "How does {keyword} work?",
        "What are the benefits of {keyword}?",
        "What are common mistakes with {keyword}?",
    ],
    "blog": [
        "What is {keyword}?",
        "Why does {keyword} matter?",
        "How do you get started with {keyword}?",
    ],
    "product": [
        "What is {keyword} used for?",
        "How do I choose the right {keyword}?",
        "What is the difference between {keyword} options?",
    ],
    "category": [
        "What should I look for in {keyword}?",
        "How do I compare {keyword} options?",
    ],
}


def _looks_like_question(text):
    stripped = text.strip()
    if stripped.endswith("?"):
        return True
    first_word = re.split(r"\s+", stripped, maxsplit=1)[0].lower().strip(":,.!")
    return first_word in QUESTION_STARTERS


def _is_near_duplicate(candidate, existing, threshold=0.82):
    candidate_norm = candidate.lower().strip("? ")
    for item in existing:
        if SequenceMatcher(None, candidate_norm, item.lower().strip("? ")).ratio() >= threshold:
            return True
    return False


def extract_faq_candidates(pages, intent="informational", primary_keyword="", people_also_ask=None, min_count=5):
    candidates = []
    for question in people_also_ask or []:
        q = question.strip()
        if q and not _is_near_duplicate(q, candidates):
            candidates.append(q if q.endswith("?") else f"{q}?")

    for page in pages:
        for header in page.get("headers", []):
            text = header.get("text", "")
            if header.get("level") == "H1":
                continue
            if _looks_like_question(text) and not _is_near_duplicate(text, candidates):
                candidates.append(text if text.endswith("?") else f"{text}?")

    if len(candidates) < min_count and primary_keyword:
        templates = FALLBACK_TEMPLATES.get(intent, FALLBACK_TEMPLATES["informational"])
        for template in templates:
            if len(candidates) >= min_count:
                break
            suggestion = template.format(keyword=primary_keyword)
            if not _is_near_duplicate(suggestion, candidates):
                candidates.append(suggestion)

    return candidates
