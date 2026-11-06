import hmac
import os
import re

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file

from services import ai_outline, benchmarks, docx_export, draft_score, faq, outline, page_diff, scraper, search, tfidf, trends

load_dotenv()

app = Flask(__name__)

def _parse_basic_auth_users(raw):
    users = {}
    for pair in (raw or "").split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        username, password = pair.split(":", 1)
        if username and password:
            users[username] = password
    return users


BASIC_AUTH_USERS = _parse_basic_auth_users(os.environ.get("BASIC_AUTH_USERS"))


@app.before_request
def require_basic_auth():
    if not BASIC_AUTH_USERS:
        return  # auth not configured (e.g. local-only use) — skip the gate
    auth = request.authorization
    expected = BASIC_AUTH_USERS.get(auth.username) if auth else None
    valid = auth and expected is not None and hmac.compare_digest(auth.password, expected)
    if not valid:
        return (
            "Authentication required.",
            401,
            {"WWW-Authenticate": 'Basic realm="SEO Outline Generator"'},
        )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.get_json(force=True) or {}
    primary_keyword = (data.get("primary_keyword") or "").strip()
    client_url = (data.get("client_url") or "").strip()

    if not primary_keyword:
        return jsonify({"error": "Primary keyword is required."}), 400

    try:
        results, people_also_ask = search.fetch_top_results(primary_keyword, client_url=client_url)
    except search.SearchConfigError as exc:
        return jsonify({"error": str(exc)}), 400
    except search.SearchAPIError as exc:
        return jsonify({"error": str(exc)}), 502

    return jsonify({"results": results, "people_also_ask": people_also_ask})


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json(force=True) or {}
    urls = data.get("urls") or []
    intent = (data.get("intent") or "informational").strip()
    primary_keyword = (data.get("primary_keyword") or "").strip()
    secondary_keywords = (data.get("secondary_keywords") or "").strip()
    existing_page_url = (data.get("existing_page_url") or "").strip()
    people_also_ask = data.get("people_also_ask") or []

    if not urls:
        return jsonify({"error": "Select at least one result to analyze."}), 400

    pages = []
    for url in urls:
        result = scraper.analyze_url(url)
        pages.append(result)

    existing_page = None
    if existing_page_url:
        scraped = scraper.analyze_url(existing_page_url)
        existing_page = {"url": scraped["url"], "headers": scraped["headers"], "error": scraped["error"]}

    body_texts = [page["body_text"] for page in pages if not page["error"]]
    tfidf_terms = tfidf.top_terms(body_texts, primary_keyword=primary_keyword, secondary_keywords=secondary_keywords)

    faq_candidates = faq.extract_faq_candidates(
        [p for p in pages if not p["error"]],
        intent=intent,
        primary_keyword=primary_keyword,
        people_also_ask=people_also_ask,
    )

    header_recommendations = trends.build_header_recommendations(pages)
    existing_headers = existing_page["headers"] if existing_page and not existing_page["error"] else []
    page_diff.flag_new_headers(header_recommendations, existing_headers)

    content_benchmarks = benchmarks.compute_benchmarks(pages)

    pages_out = [
        {
            "url": page["url"],
            "headers": page["headers"],
            "error": page["error"],
        }
        for page in pages
    ]

    return jsonify({
        "pages": pages_out,
        "header_recommendations": header_recommendations,
        "tfidf_terms": tfidf_terms,
        "faq_candidates": faq_candidates,
        "content_benchmarks": content_benchmarks,
        "existing_page": existing_page,
    })


@app.route("/api/ai-outline", methods=["POST"])
def api_ai_outline():
    data = request.get_json(force=True) or {}
    intent = (data.get("intent") or "informational").strip()
    primary_keyword = (data.get("primary_keyword") or "").strip()
    secondary_keywords = (data.get("secondary_keywords") or "").strip()
    client_url = (data.get("client_url") or "").strip()
    pages = data.get("pages") or []
    tfidf_terms = data.get("tfidf_terms") or []
    content_benchmarks = data.get("content_benchmarks")
    existing_headers = data.get("existing_headers") or []

    if not primary_keyword:
        return jsonify({"error": "Primary keyword is required."}), 400
    if not pages:
        return jsonify({"error": "Analyze at least one competitor page first."}), 400

    try:
        result = ai_outline.generate_outline(
            intent, primary_keyword, secondary_keywords, client_url, pages, tfidf_terms, content_benchmarks
        )
    except ai_outline.AIOutlineConfigError as exc:
        return jsonify({"error": str(exc)}), 400
    except ai_outline.AIOutlineError as exc:
        return jsonify({"error": str(exc)}), 502

    page_diff.flag_new_headers(result.get("headers", []), existing_headers)

    return jsonify(result)


@app.route("/api/export/docx", methods=["POST"])
def api_export_docx():
    data = request.get_json(force=True) or {}
    title = (data.get("title") or "").strip()
    h1 = (data.get("h1") or "").strip()
    primary_keyword = (data.get("primary_keyword") or "").strip()
    secondary_keywords = (data.get("secondary_keywords") or "").strip()
    client_url = (data.get("client_url") or "").strip()
    outline_rows = data.get("outline_rows") or []
    faqs = data.get("faqs") or []
    tfidf_terms = data.get("tfidf_terms") or []

    buffer = docx_export.build_docx(
        title, h1, primary_keyword, secondary_keywords, client_url, outline_rows, faqs, tfidf_terms
    )

    slug = re.sub(r"[^a-z0-9]+", "-", (primary_keyword or "outline").lower()).strip("-") or "content-outline"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{slug}.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.route("/api/score-draft", methods=["POST"])
def api_score_draft():
    data = request.get_json(force=True) or {}
    draft_text = data.get("draft_text") or ""
    draft_url = (data.get("draft_url") or "").strip()
    tfidf_terms = data.get("tfidf_terms") or []
    outline_headers = data.get("outline_headers") or []
    content_benchmarks = data.get("content_benchmarks")

    if draft_url:
        scraped = scraper.analyze_url(draft_url)
        if scraped["error"]:
            return jsonify({"error": f"Couldn't fetch that URL: {scraped['error']}"}), 502
        draft_headers = scraped["headers"]
        full_text = scraped["body_text"]
    elif draft_text.strip():
        draft_headers, full_text = draft_score.parse_markdown_draft(draft_text)
    else:
        return jsonify({"error": "Paste a draft or provide a URL to score."}), 400

    result = draft_score.score_draft(full_text, draft_headers, tfidf_terms, outline_headers, content_benchmarks)
    return jsonify(result)


@app.route("/api/title", methods=["POST"])
def api_title():
    data = request.get_json(force=True) or {}
    intent = (data.get("intent") or "informational").strip()
    primary_keyword = (data.get("primary_keyword") or "").strip()
    client_url = (data.get("client_url") or "").strip()

    if not primary_keyword:
        return jsonify({"error": "Primary keyword is required."}), 400

    suggestion = outline.suggest_title_and_h1(intent, primary_keyword, client_url)
    return jsonify(suggestion)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
