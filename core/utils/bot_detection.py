"""Bot / crawler user-agent detection helpers.

Used in two places:
  1. The ``/api/analytics/`` endpoint rejects requests from known bots so they
     never reach the database.
  2. The stats dashboard querysets exclude any rows that slipped through (e.g.
     from before this filter was added, or from unsophisticated headless clients
     that do send a User-Agent but whose JS execution is still bot-like).
"""
from __future__ import annotations

from functools import reduce

from django.db.models import Q

# ---------------------------------------------------------------------------
# Known-bot substrings (all compared case-insensitively against the UA string)
# ---------------------------------------------------------------------------
# Keep this list narrow enough to avoid false-positives on real browsers while
# covering the crawlers that skew single-page "bounce" sessions.
_BOT_PATTERNS: tuple[str, ...] = (
    # Generic crawler signals
    "bot",
    "crawl",
    "spider",
    "slurp",
    # Popular SEO / audit tools
    "semrush",
    "ahref",
    "mj12",
    "dotbot",
    "screaming frog",
    "sitebulb",
    "majestic",
    "dataforseo",
    # AI training crawlers
    "gptbot",
    "claudebot",
    "amazonbot",
    "bytespider",
    "perplexitybot",
    # Pure HTTP clients (not browsers)
    "python-requests",
    "python-urllib",
    "go-http-client",
    "okhttp",
    "axios",
    "wget",
    "curl/",
    # Headless / automation
    "headlesschrome",
    "phantomjs",
    "puppeteer",
    # Security scanners
    "nessus",
    "nuclei",
    "nikto",
    "zgrab",
    # Social link-preview fetchers
    "facebookexternalhit",
    "twitterbot",
    "linkedinbot",
    "slackbot",
    "whatsapp",
    "bingpreview",
    "googleimageproxy",
    # Monitoring / uptime pings
    "uptimerobot",
    "pingdom",
    "statuscake",
    "hetrixtools",
)


def is_bot_ua(user_agent: str) -> bool:
    """Return ``True`` if *user_agent* matches any known bot / crawler pattern."""
    if not user_agent:
        return False
    ua_lower = user_agent.lower()
    return any(pattern in ua_lower for pattern in _BOT_PATTERNS)


def bot_ua_exclude_q() -> Q:
    """Return a ``Q`` object suitable for ``.exclude()`` on an ``AnalyticsEvent`` queryset.

    Usage::

        events = AnalyticsEvent.objects.filter(...).exclude(bot_ua_exclude_q())
    """
    return reduce(lambda a, b: a | b, (Q(user_agent__icontains=p) for p in _BOT_PATTERNS))
