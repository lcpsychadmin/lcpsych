"""Utilities for parsing HTTP referrer URLs into human-readable sources."""

from urllib.parse import parse_qs, urlparse

# Maps (sub)domain → (display name, query param that carries the search term).
# Google no longer forwards the query string due to HTTPS referrer policy, but
# we still recognise the domain so we can label the source correctly.
_SEARCH_ENGINES: dict[str, tuple[str, str]] = {
    "google.com": ("Google", "q"),
    "bing.com": ("Bing", "q"),
    "duckduckgo.com": ("DuckDuckGo", "q"),
    "yahoo.com": ("Yahoo", "p"),
    "yandex.com": ("Yandex", "text"),
    "baidu.com": ("Baidu", "wd"),
    "ecosia.org": ("Ecosia", "q"),
    "startpage.com": ("Startpage", "query"),
    "brave.com": ("Brave Search", "q"),
    "ask.com": ("Ask", "q"),
}


def parse_referrer(url: str) -> dict:
    """Return a dict with keys: domain, search_engine, search_query.

    - ``domain``: cleaned hostname (www. stripped), empty string for direct traffic.
    - ``search_engine``: display name if the referrer is a known search engine, else None.
    - ``search_query``: the search term extracted from the URL params, or None.
      Note: Google (and most major engines on HTTPS) no longer pass the query
      string, so ``search_query`` will typically be None even for Google traffic.
    """
    if not url:
        return {"domain": "", "search_engine": None, "search_query": None}

    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        domain = hostname.removeprefix("www.")

        search_engine: str | None = None
        search_query: str | None = None

        for se_domain, (se_name, query_param) in _SEARCH_ENGINES.items():
            if domain == se_domain or domain.endswith("." + se_domain):
                search_engine = se_name
                qs = parse_qs(parsed.query)
                terms = qs.get(query_param, [])
                if terms:
                    search_query = terms[0]
                break

        return {"domain": domain, "search_engine": search_engine, "search_query": search_query}

    except Exception:
        return {"domain": url[:100], "search_engine": None, "search_query": None}
