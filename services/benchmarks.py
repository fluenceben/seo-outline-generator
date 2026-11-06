import statistics


def _trimmed(values):
    """Drop the single lowest and highest value when there's enough data to do so safely,
    so one outlier page (a nav-heavy listing page, a discussion thread with no real
    headers) doesn't distort the target range."""
    if len(values) >= 4:
        ordered = sorted(values)
        return ordered[1:-1]
    return values


def compute_benchmarks(pages):
    """Word-count and header-count stats across successfully-scraped competitor pages,
    used to keep a generated outline in the same ballpark as what's actually ranking."""
    word_counts = []
    header_counts = []
    for page in pages:
        if page.get("error"):
            continue
        body = page.get("body_text", "")
        if body:
            word_counts.append(len(body.split()))
        headers = [h for h in page.get("headers", []) if h.get("level") != "H1"]
        header_counts.append(len(headers))

    if not header_counts:
        return None

    trimmed_words = _trimmed(word_counts) if word_counts else []
    trimmed_headers = _trimmed(header_counts)

    return {
        "page_count": len(header_counts),
        "typical_word_count": round(statistics.median(trimmed_words)) if trimmed_words else None,
        "min_word_count": min(trimmed_words) if trimmed_words else None,
        "max_word_count": max(trimmed_words) if trimmed_words else None,
        "typical_header_count": round(statistics.median(trimmed_headers)),
        "min_header_count": min(trimmed_headers),
        "max_header_count": max(trimmed_headers),
    }
