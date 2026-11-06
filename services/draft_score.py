import re

from services import page_diff, tfidf

HEADER_LINE_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def parse_markdown_draft(text):
    """Split pasted draft text into {level, text} headers (markdown '#' lines) plus
    the full body text (headers included) for word-count and keyword-usage checks."""
    headers = []
    body_lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = HEADER_LINE_RE.match(line)
        if match:
            level = min(len(match.group(1)), 6)
            header_text = match.group(2).strip()
            headers.append({"level": f"H{level}", "text": header_text})
            body_lines.append(header_text)
        elif line:
            body_lines.append(line)
    return headers, " ".join(body_lines)


def _score_headers(outline_headers, draft_headers):
    results = []
    covered = 0
    for header in outline_headers:
        text = header.get("text", "")
        covered_flag = page_diff.is_covered(text, draft_headers)
        if covered_flag:
            covered += 1
        results.append({"level": header.get("level", "H2"), "text": text, "covered": covered_flag})
    ratio = covered / len(outline_headers) if outline_headers else 1.0
    return results, ratio


def _score_terms(tfidf_terms, full_text):
    usable = [t for t in tfidf_terms if t.get("max_uses")]
    results = []
    on_target = 0
    for term in usable:
        count = tfidf.count_occurrences(term["term"], full_text)
        min_uses = term.get("min_uses", 0)
        max_uses = term.get("max_uses", 0)
        if count < min_uses:
            status = "under"
        elif count > max_uses:
            status = "over"
        else:
            status = "within"
            on_target += 1
        results.append({
            "term": term["term"],
            "count": count,
            "min_uses": min_uses,
            "max_uses": max_uses,
            "status": status,
        })
    ratio = on_target / len(usable) if usable else 1.0
    return results, ratio


def _score_length(word_count, content_benchmarks):
    if not content_benchmarks or content_benchmarks.get("min_word_count") is None:
        return None, 1.0
    lo = content_benchmarks["min_word_count"]
    hi = content_benchmarks["max_word_count"]
    if word_count < lo:
        status, ratio = "under", 0.5
    elif word_count > hi:
        status, ratio = "over", 0.5
    else:
        status, ratio = "within", 1.0
    return {
        "word_count": word_count,
        "typical_word_count": content_benchmarks.get("typical_word_count"),
        "min_word_count": lo,
        "max_word_count": hi,
        "status": status,
    }, ratio


def score_draft(full_text, draft_headers, tfidf_terms, outline_headers, content_benchmarks):
    word_count = len(full_text.split())
    header_results, header_ratio = _score_headers(outline_headers, draft_headers)
    term_results, term_ratio = _score_terms(tfidf_terms, full_text)
    length_result, length_ratio = _score_length(word_count, content_benchmarks)

    if length_result is None:
        weights = {"header": 0.5, "term": 0.5, "length": 0.0}
    else:
        weights = {"header": 0.4, "term": 0.4, "length": 0.2}

    overall = round(100 * (
        weights["header"] * header_ratio + weights["term"] * term_ratio + weights["length"] * length_ratio
    ))

    return {
        "score": overall,
        "word_count": word_count,
        "headers": header_results,
        "terms": term_results,
        "length": length_result,
    }
