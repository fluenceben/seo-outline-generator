import json
import os
from urllib.parse import urlparse

import anthropic

MODEL = "claude-sonnet-5"

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "headers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "level": {"type": "string", "enum": ["H2", "H3", "H4"]},
                    "text": {"type": "string"},
                },
                "required": ["level", "text"],
                "additionalProperties": False,
            },
        },
        "faqs": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["headers", "faqs"],
    "additionalProperties": False,
}

MAX_HEADERS_PER_PAGE = 40


class AIOutlineConfigError(Exception):
    pass


class AIOutlineError(Exception):
    pass


def _domain(url):
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _build_prompt(intent, primary_keyword, secondary_keywords, client_url, pages, tfidf_terms, content_benchmarks):
    lines = []
    lines.append(f"Page intent: {intent}")
    lines.append(f"Primary keyword: {primary_keyword}")
    if secondary_keywords:
        lines.append(f"Secondary keywords: {secondary_keywords}")
    if client_url:
        lines.append(f"Client site (do not copy their content, this is who we're writing for): {client_url}")

    if content_benchmarks:
        lines.append(
            "\nCompetitor length benchmark: {count} pages analyzed, typically {typ_words} words "
            "(range {min_words}-{max_words}) across {typ_headers} headers "
            "(range {min_headers}-{max_headers}). This range already excludes outlier pages "
            "(e.g. a thread or listing page with an unrepresentative header count).".format(
                count=content_benchmarks.get("page_count"),
                typ_words=content_benchmarks.get("typical_word_count"),
                min_words=content_benchmarks.get("min_word_count"),
                max_words=content_benchmarks.get("max_word_count"),
                typ_headers=content_benchmarks.get("typical_header_count"),
                min_headers=content_benchmarks.get("min_header_count"),
                max_headers=content_benchmarks.get("max_header_count"),
            )
        )
        lines.append(
            "Your header count MUST land within (or very close to) that competitor header "
            "range — do not add extra headers just because the topic could support them."
        )

    lines.append("")
    lines.append("Here is what competitors currently ranking for this keyword cover, page by page:")
    for page in pages:
        if page.get("error"):
            continue
        domain = _domain(page.get("url", ""))
        headers = [h for h in page.get("headers", []) if h.get("level") != "H1"][:MAX_HEADERS_PER_PAGE]
        if not headers:
            continue
        lines.append(f"\n[{domain}]")
        for h in headers:
            lines.append(f"  {h.get('level', 'H2')}: {h.get('text', '')}")

    if tfidf_terms:
        top_terms = ", ".join(t["term"] for t in tfidf_terms[:20])
        lines.append(f"\nTop topical terms across competitors (for coverage reference, not for stuffing): {top_terms}")

    return "\n".join(lines)


SYSTEM_PROMPT = """You are an SEO content strategist. Given a primary keyword and a \
breakdown of what pages currently ranking for that keyword cover, design an original \
content outline that would genuinely compete with them.

Do not copy competitor header wording. Use their coverage as research: notice which \
topics recur across multiple competitors (signals of what searchers expect), and notice \
gaps or weak spots you could cover better or more thoroughly. Then write your own \
headers and FAQs in your own words.

Requirements:
- Headers should read as a coherent piece of content, ordered the way a reader would \
move through it (introduction/context first, core substance in the middle, comparisons \
or decision-making help later, wrap-up last). Do not just rank topics by how often \
competitors mention them.
- Use H2 for main sections and H3/H4 for subsections within them.
- If a competitor length benchmark is provided, treat its header-count range as a hard \
constraint, not a suggestion. Competitors ranking with 5 headers means you write \
something close to 5, not 15 - more headers than the field is using is not a competitive \
advantage, it's padding. Only exceed the range if the primary keyword clearly demands \
structural depth none of the competitors bothered with.
- FAQs should be questions a real searcher would ask about this topic - grounded in \
what competitors' question-style headers suggest people ask, but written fresh. \
Write 4-8 FAQs.
- Match the tone and structure to the stated page intent (service, informational, \
blog, product, or category)."""


def generate_outline(intent, primary_keyword, secondary_keywords, client_url, pages, tfidf_terms, content_benchmarks=None):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise AIOutlineConfigError(
            "Claude isn't configured. Set ANTHROPIC_API_KEY in your .env file (see .env.example)."
        )

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_prompt(
        intent, primary_keyword, secondary_keywords, client_url, pages, tfidf_terms, content_benchmarks
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            output_config={
                "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
            },
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIStatusError as exc:
        raise AIOutlineError(f"Claude request failed ({exc.status_code}). {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise AIOutlineError(f"Could not reach Claude: {exc}") from exc

    if response.stop_reason == "refusal":
        raise AIOutlineError("Claude declined to generate an outline for this request.")

    text = next((block.text for block in response.content if block.type == "text"), None)
    if not text:
        raise AIOutlineError("Claude returned no output.")

    data = json.loads(text)
    return {"headers": data.get("headers", []), "faqs": data.get("faqs", [])}
