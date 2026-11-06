import os
from urllib.parse import urlparse

import requests

SERPER_SEARCH_ENDPOINT = "https://google.serper.dev/search"


class SearchConfigError(Exception):
    pass


class SearchAPIError(Exception):
    pass


def _normalize_domain(url_or_domain):
    if not url_or_domain:
        return ""
    parsed = urlparse(url_or_domain if "//" in url_or_domain else f"//{url_or_domain}")
    host = (parsed.netloc or parsed.path).lower()
    return host[4:] if host.startswith("www.") else host


def fetch_top_results(query, client_url=None, num=10):
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        raise SearchConfigError(
            "Serper isn't configured. Set SERPER_API_KEY in your .env file (see .env.example)."
        )

    client_domain = _normalize_domain(client_url)

    resp = requests.post(
        SERPER_SEARCH_ENDPOINT,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        # Ask for a few extra in case the client's own domain shows up in the top 10.
        json={"q": query, "num": num + 5},
        timeout=10,
    )
    if resp.status_code == 401 or resp.status_code == 403:
        raise SearchAPIError("Serper API key was rejected. Check SERPER_API_KEY in your .env file.")
    if resp.status_code == 429:
        raise SearchAPIError("Serper quota exceeded (check your remaining credits at serper.dev).")
    if resp.status_code != 200:
        detail = ""
        try:
            detail = resp.json().get("message", "")
        except ValueError:
            pass
        raise SearchAPIError(f"Serper request failed ({resp.status_code}). {detail}".strip())

    payload = resp.json()
    items = payload.get("organic", [])

    results = []
    for item in items:
        link = item.get("link", "")
        if client_domain and _normalize_domain(link) == client_domain:
            continue
        results.append({
            "title": item.get("title", ""),
            "link": link,
            "snippet": item.get("snippet", ""),
            "displayLink": _normalize_domain(link),
        })
        if len(results) >= num:
            break

    people_also_ask = [
        qa.get("question", "").strip()
        for qa in payload.get("peopleAlsoAsk", [])
        if qa.get("question")
    ]

    return results[:num], people_also_ask
