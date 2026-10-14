"""
hands/workspace_modules/url_matching.py
URL normalization and matching for smart tab deduplication.
"""


def normalize_url(url: str) -> str:
    """
    Normalize URL for comparison.
    Strips www, trailing slashes, fragments, and transient query parameters (like YouTube timestamp &t=).
    """
    if not url:
        return ""
    url = url.strip()
    if "#" in url:
        url = url[:url.index("#")]
    
    try:
        from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        path = parsed.path.rstrip("/")
        
        # Transient query parameters to strip for matching
        transient_params = {
            "t", "time", "index", "feature", "ab_channel", "pp", "start_radio",
            "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"
        }
        
        q_params = []
        for k, v in parse_qsl(parsed.query, keep_blank_values=True):
            if k.lower() not in transient_params:
                q_params.append((k.lower(), v))
        
        q_params.sort()
        new_query = urlencode(q_params)
        normalized = urlunparse((scheme, netloc, path, "", new_query, ""))
        return normalized.lower()
    except Exception:
        url = url.lower().rstrip("/")
        url = url.replace("://www.", "://")
        return url


def extract_domain(url: str) -> str:
    """
    Extract just the domain from a URL.
    https://app.outlier.ai/login  →  app.outlier.ai
    """
    url = url.strip().lower()
    for scheme in ("https://", "http://"):
        if url.startswith(scheme):
            url = url[len(scheme):]
            break
    if url.startswith("www."):
        url = url[4:]
    domain = url.split("/")[0]
    domain = domain.split(":")[0]
    return domain


def is_base_url(url: str) -> bool:
    """
    True if URL is just a homepage/base with no meaningful path.
    https://youtube.com        → True
    https://youtube.com/watch  → False
    """
    url = url.strip().rstrip("/").lower()
    url = url.replace("://www.", "://")
    for scheme in ("https://", "http://"):
        if url.startswith(scheme):
            url = url[len(scheme):]
            break
    parts = url.split("/", 1)
    if len(parts) == 1:
        return True
    path = parts[1].strip().rstrip("/")
    return path == ""


def url_matches(saved_url: str, open_urls: set, open_domains: set) -> bool:
    """
    Check if a saved URL is already open.
    Rule 1: exact normalized match → True
    Rule 2: base URL + domain open with any path → True
    """
    if not saved_url:
        return False

    normalized = normalize_url(saved_url)
    domain     = extract_domain(saved_url)

    if normalized in open_urls:
        return True

    if is_base_url(saved_url) and domain in open_domains:
        return True

    return False