import requests
from bs4 import BeautifulSoup

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

STRIP_TAGS = ["script", "style", "nav", "header", "footer", "aside", "noscript", "form", "iframe"]
HEADER_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6"]


class ScrapeError(Exception):
    pass


def fetch_page(url, timeout=10):
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
    except requests.RequestException as exc:
        raise ScrapeError(f"Could not reach page: {exc}") from exc

    if resp.status_code != 200:
        raise ScrapeError(f"Page returned HTTP {resp.status_code}")

    content_type = resp.headers.get("Content-Type", "")
    if "html" not in content_type and not resp.text.strip().lower().startswith("<!doctype") \
            and not resp.text.strip().lower().startswith("<html"):
        raise ScrapeError("Response was not HTML")

    return resp.text


def extract_headers(soup):
    headers = []
    for tag in soup.find_all(HEADER_TAGS):
        text = tag.get_text(strip=True, separator=" ")
        text = " ".join(text.split())
        if text:
            headers.append({"level": tag.name.upper(), "text": text})
    return headers


def extract_body_text(soup):
    for tag in soup.find_all(STRIP_TAGS):
        tag.decompose()

    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(separator=" ", strip=True)
    return " ".join(text.split())


def analyze_url(url):
    """Fetch a URL and return its headers + main body text, or an error string."""
    try:
        html = fetch_page(url)
    except ScrapeError as exc:
        return {"url": url, "headers": [], "body_text": "", "error": str(exc)}

    soup = BeautifulSoup(html, "html.parser")
    headers = extract_headers(soup)
    body_text = extract_body_text(BeautifulSoup(html, "html.parser"))

    return {"url": url, "headers": headers, "body_text": body_text, "error": None}
