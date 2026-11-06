import re

from sklearn.feature_extraction.text import TfidfVectorizer


def count_occurrences(term, text):
    pattern = r"\b" + re.escape(term) + r"\b"
    return len(re.findall(pattern, text, flags=re.IGNORECASE))


def _trimmed(values):
    """Drop the single lowest and highest count when there's enough data to do so
    safely, so one outlier page doesn't blow out the usage-target range."""
    if len(values) >= 4:
        ordered = sorted(values)
        return ordered[1:-1]
    return values


# Storefront chrome that shows up on any e-commerce/listing page regardless of topic
# (cart, checkout, pricing widgets) — not a real content term, so never a usage target.
_BOILERPLATE_TERMS = {
    "cart", "add cart", "add to cart", "checkout", "shipping", "free shipping",
    "sign in", "log in", "login", "subscribe", "newsletter", "cookie", "cookies",
    "privacy policy", "terms use", "terms service",
}

# Individual words that only ever show up as e-commerce/spec-sheet chrome (price
# widgets, size selectors) — a phrase containing any of these is a scraped fragment of
# that widget, not prose, regardless of what else is in the phrase. Kept narrow and
# unambiguous on purpose: words like "price" or "buy" are excluded from this list
# because they're legitimate topic words in plenty of industries.
_CHROME_WORDS = {"cart", "checkout", "rrp", "qty", "subscribe", "newsletter", "cookie", "cookies"}


def _is_boilerplate(term):
    if term in _BOILERPLATE_TERMS or term.replace(",", "").replace(".", "").isdigit():
        return True
    return any(word in _CHROME_WORDS for word in term.split())


def _looks_like_brand(term, original_texts):
    """A term that's capitalized most of the time it appears across competitor pages is
    almost always a proper noun — a brand, product line, or publisher name — rather than
    a generic content term worth recommending. Genuine common nouns/phrases reliably turn
    up lowercase in running prose; proper nouns rarely do (a stray lowercase instance —
    e.g. duplicated alt text — shouldn't be enough to spare an otherwise-consistent brand)."""
    pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
    capitalized_hits = 0
    lowercase_hits = 0
    for text in original_texts:
        for m in pattern.finditer(text):
            # Ignore numeric tokens (model numbers, sizes) — they have no case of their
            # own and shouldn't break the capitalization check for "Gel Nimbus 28".
            words = [w for w in m.group(0).split() if w[:1].isalpha()]
            if not words:
                continue
            if all(w[:1].isupper() for w in words):
                capitalized_hits += 1
            elif any(w[:1].islower() for w in words):
                lowercase_hits += 1
    return capitalized_hits >= 1 and capitalized_hits > lowercase_hits


def _dedupe_subphrases(candidates):
    """Keep the longest version of an overlapping phrase and drop the fragments —
    e.g. keep "salt lake city" and drop "salt", "salt lake", "lake city" once the full
    phrase is present, instead of listing every sub-span as its own term."""
    by_length_desc = sorted(candidates, key=lambda pair: (-len(pair[0].split()), -pair[1]))
    accepted = []
    accepted_words = []
    for term, score in by_length_desc:
        words = term.split()
        n = len(words)
        is_subphrase = any(
            n < len(kept) and any(kept[i:i + n] == words for i in range(len(kept) - n + 1))
            for kept in accepted_words
        )
        if is_subphrase:
            continue
        accepted.append((term, score))
        accepted_words.append(words)
    accepted.sort(key=lambda pair: pair[1], reverse=True)
    return accepted


def top_terms(documents, primary_keyword="", secondary_keywords="", top_n=30):
    """documents: list of raw body-text strings (one per page). Returns top terms by
    summed TF-IDF score across the corpus, highest first, each annotated with the range
    of times competitors who used the term actually used it — a usage-frequency target
    for the new content. Filters out storefront boilerplate, brand/proper-noun terms,
    and sub-phrase fragments of a longer phrase already in the list. Terms that are part
    of the user's own target keywords are never filtered as brands, even if they're
    proper nouns (e.g. a city name that's part of the primary keyword)."""
    non_empty = [doc for doc in documents if doc and doc.strip()]
    if len(non_empty) < 1:
        return []

    protected_text = f"{primary_keyword} {secondary_keywords}".lower()

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 3),
        max_features=3000,
        min_df=1,
    )
    try:
        matrix = vectorizer.fit_transform(non_empty)
    except ValueError:
        return []

    scores = matrix.sum(axis=0).A1
    terms = vectorizer.get_feature_names_out()

    candidates = []
    for term, score in zip(terms, scores):
        if _is_boilerplate(term):
            continue
        if term not in protected_text and _looks_like_brand(term, non_empty):
            continue
        candidates.append((term, score))

    deduped = _dedupe_subphrases(candidates)
    ranked = deduped[:top_n]

    results = []
    for term, score in ranked:
        counts = [c for c in (count_occurrences(term, doc) for doc in non_empty) if c > 0]
        trimmed = _trimmed(counts)
        results.append({
            "term": term,
            "score": round(float(score), 4),
            "min_uses": min(trimmed) if trimmed else 0,
            "max_uses": max(trimmed) if trimmed else 0,
        })
    return results
