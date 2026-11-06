INTENT_LABELS = {
    "service": "Service Page",
    "informational": "Informational Page",
    "blog": "Blog Post",
    "product": "Product Page",
    "category": "Category / Listing Page",
}

TITLE_TEMPLATES = {
    "service": "{keyword} Services | {brand}",
    "informational": "{keyword}: A Complete Guide",
    "blog": "{keyword}: What You Need to Know",
    "product": "{keyword} | {brand}",
    "category": "{keyword} | Browse Options at {brand}",
}

H1_TEMPLATES = {
    "service": "{keyword}",
    "informational": "{keyword}: A Complete Guide",
    "blog": "{keyword}",
    "product": "{keyword}",
    "category": "{keyword}",
}


_MINOR_WORDS = {
    "a", "an", "and", "as", "at", "but", "by", "for", "if", "in", "nor", "of",
    "on", "or", "so", "the", "to", "up", "yet", "vs",
}


def _title_case(text):
    words = text.split()
    if not words:
        return text
    result = []
    for i, word in enumerate(words):
        lower = word.lower()
        is_boundary = i == 0 or i == len(words) - 1 or words[i - 1].endswith(":")
        if not is_boundary and lower in _MINOR_WORDS:
            result.append(lower)
        else:
            result.append(lower[0].upper() + lower[1:] if lower else lower)
    return " ".join(result)


def _brand_from_url(client_url):
    if not client_url:
        return "Your Brand"
    host = client_url.replace("https://", "").replace("http://", "").split("/")[0]
    host = host[4:] if host.startswith("www.") else host
    name = host.split(".")[0]
    return name.replace("-", " ").title() if name else "Your Brand"


def suggest_title_and_h1(intent, primary_keyword, client_url=None):
    intent = intent if intent in TITLE_TEMPLATES else "informational"
    brand = _brand_from_url(client_url)
    keyword = _title_case(primary_keyword)
    title = TITLE_TEMPLATES[intent].format(keyword=keyword, brand=brand)
    h1 = H1_TEMPLATES[intent].format(keyword=keyword, brand=brand)
    return {"title": title, "h1": h1, "intent_label": INTENT_LABELS.get(intent, intent)}
