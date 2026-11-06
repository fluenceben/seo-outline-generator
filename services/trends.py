import re
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urlparse

SIMILARITY_THRESHOLD = 0.6


def _domain(url):
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _normalize(text):
    text = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return " ".join(text.split())


def _cluster(items):
    """Greedily group headers with similar wording into topic clusters."""
    clusters = []
    for item in items:
        best, best_score = None, 0.0
        for cluster in clusters:
            score = SequenceMatcher(None, item["norm"], cluster["norm"]).ratio()
            if score > best_score:
                best, best_score = cluster, score
        if best is not None and best_score >= SIMILARITY_THRESHOLD:
            best["items"].append(item)
        else:
            clusters.append({"norm": item["norm"], "items": [item]})
    return clusters


def build_header_recommendations(pages):
    """Group similar headers across competitor pages into topics, then order them
    by where they typically sit within a competitor's page (intro topics first,
    closing topics last) so the result reads like a real content flow rather than
    a raw popularity ranking. Topics covered by enough competitors are flagged
    `recommended`; the rest are lower-confidence alternates."""
    usable_pages = [p for p in pages if not p.get("error")]
    total_pages = len(usable_pages)
    if total_pages == 0:
        return []

    flat = []
    for page in usable_pages:
        domain = _domain(page.get("url", ""))
        page_headers = [h for h in page.get("headers", []) if h.get("level") != "H1"]
        denom = max(len(page_headers) - 1, 1)
        seen_on_page = set()
        for position, header in enumerate(page_headers):
            text = (header.get("text") or "").strip()
            norm = _normalize(text)
            if not text or not norm or norm in seen_on_page:
                continue
            seen_on_page.add(norm)
            flat.append({
                "text": text,
                "level": header.get("level", "H2"),
                "domain": domain,
                "norm": norm,
                "position": position / denom,
            })

    recommend_threshold = 2 if total_pages >= 2 else 1
    recommendations = []
    for cluster in _cluster(flat):
        items = cluster["items"]
        domains = sorted({item["domain"] for item in items})
        representative = Counter(item["text"] for item in items).most_common(1)[0][0]
        level = Counter(item["level"] for item in items).most_common(1)[0][0]
        avg_position = sum(item["position"] for item in items) / len(items)
        recommendations.append({
            "text": representative,
            "level": level,
            "coverage": len(domains),
            "total_pages": total_pages,
            "sources": domains,
            "recommended": len(domains) >= recommend_threshold,
            "avg_position": round(avg_position, 4),
        })

    recommendations.sort(key=lambda r: r["avg_position"])
    return recommendations
