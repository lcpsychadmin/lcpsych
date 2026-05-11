"""
Utilities for formatting and sending social posts.

- build_message(template, post, char_limit) → rendered + trimmed text
- post_to_x(profile, text) → (ok: bool, message: str)
- post_to_all_platforms(post) → list[tuple[str, bool, str]]  (called on publish)
"""
from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import logging
import json
import mimetypes
import os
import time
import uuid
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import urllib.error

from django.conf import settings

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Message formatting
# ---------------------------------------------------------------------------

CHAR_LIMITS: dict[str, int] = {
    "instagram": 2200,
    # Twitter's weighted char count (twitter-text library) assigns weight 200 to
    # U+2026 (…) and other non-BMP-range characters instead of the usual 100.
    # Our trimming adds up to 2 ellipsis chars, each costing +1 weighted char,
    # so we cap at 276 Python chars → ≤280 Twitter-weighted chars.
    "x": 276,
    "facebook_page": 63206,
    "google_business": 1500,
    "linkedin_page": 3000,
}


def build_message(template: str, post, char_limit: int | None = None) -> str:
    """
    Render *template* with {title}, {excerpt}, {url} from *post*.

    The URL is constructed from settings.BASE_URL + post.get_absolute_url()
    (or just the path if BASE_URL is not set).  The result is trimmed to
    *char_limit* characters if supplied (trimming the excerpt first to fit).
    """
    base_url = (getattr(settings, "BASE_URL", "") or "").rstrip("/")
    try:
        path = post.get_absolute_url()
    except Exception:
        path = f"/blog/{post.slug}/"
    url = f"{base_url}{path}"

    title = post.title or ""
    excerpt = post.excerpt or ""

    # Quick substitution with full excerpt to check if trimming is needed.
    rendered = template.format(title=title, excerpt=excerpt, url=url)
    if char_limit and len(rendered) > char_limit:
        # Calculate how many characters we can spare for the excerpt.
        # The URL must never be truncated — only trim the excerpt (then title).
        overhead = len(template.format(title=title, excerpt="", url=url))
        available = char_limit - overhead
        if available > 3:
            excerpt = excerpt[: available - 1] + "…"
        else:
            excerpt = ""
        rendered = template.format(title=title, excerpt=excerpt, url=url)
        # Safety net: title is unusually long — trim it but keep the full URL.
        if len(rendered) > char_limit:
            url_tail = template.format(title="", excerpt="", url=url).lstrip()
            max_title = char_limit - len(url_tail) - 2  # room for "… "
            if max_title > 5:
                rendered = title[: max_title - 1] + "… " + url_tail
            else:
                rendered = url  # last resort: URL only
    return rendered


# ---------------------------------------------------------------------------
# Low-level HTTP helpers
# ---------------------------------------------------------------------------

def _http_post_json(url: str, payload: dict, headers: dict) -> tuple[int, dict]:
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", **headers}
    req = Request(url, data=data, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            return resp.status, body
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode())
        except Exception:
            body = {}
        return exc.code, body


def _http_post_form(url: str, payload: dict, headers: dict) -> tuple[int, dict]:
    data = urlencode(payload).encode()
    req = Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded", **headers}, method="POST")
    try:
        with urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            return resp.status, body
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode())
        except Exception:
            body = {}
        return exc.code, body


def _get_public_image_url(image_field) -> str | None:
    """Return a fully-qualified public URL for *image_field*, or None."""
    if not image_field:
        return None
    try:
        base_url = (getattr(settings, "BASE_URL", "") or "").rstrip("/")
        img_url = image_field.url  # raises ValueError if no file
        if base_url:
            return base_url + img_url
        # In local dev there's no public BASE_URL, but return the path anyway
        # so callers can decide whether to use it.
        return img_url
    except Exception:
        return None


# ---------------------------------------------------------------------------
# OAuth 1.0a helpers (X / Twitter)
# ---------------------------------------------------------------------------

def _pct(s: str) -> str:
    return quote(str(s), safe="")


def _oauth1_header(
    method: str,
    url: str,
    consumer_key: str,
    consumer_secret: str,
    token: str,
    token_secret: str,
) -> str:
    """Build an OAuth 1.0a HMAC-SHA1 Authorization header (RFC 5849)."""
    nonce = uuid.uuid4().hex
    timestamp = str(int(time.time()))

    params: dict[str, str] = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": nonce,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": timestamp,
        "oauth_token": token,
        "oauth_version": "1.0",
    }

    param_string = "&".join(f"{_pct(k)}={_pct(v)}" for k, v in sorted(params.items()))
    base_string = "&".join([method.upper(), _pct(url), _pct(param_string)])
    signing_key = f"{_pct(consumer_secret)}&{_pct(token_secret)}"
    sig = _hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    params["oauth_signature"] = base64.b64encode(sig).decode()

    return "OAuth " + ", ".join(f'{_pct(k)}="{_pct(v)}"' for k, v in sorted(params.items()))


def _upload_media_x(profile, image_field) -> tuple[str | None, str]:
    """
    Upload an image to Twitter v1.1 media/upload via multipart form.
    Returns (media_id_string, error_msg). error_msg is empty on success.
    OAuth 1.0a signing for multipart does NOT include body params.
    """
    if not image_field:
        return None, ""
    try:
        name = getattr(image_field, "name", "") or ""
        mime_type, _ = mimetypes.guess_type(name)
        if not mime_type:
            mime_type = "image/jpeg"
        with image_field.open("rb") as f:
            image_data = f.read()
    except Exception as exc:
        return None, f"Could not read image: {exc}"

    boundary = uuid.uuid4().hex
    filename = os.path.basename(name) or "image"
    # media_category=tweet_image is required for use with the v2 /2/tweets API.
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media_category"\r\n\r\n'
        f"tweet_image\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8") + image_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    upload_url = "https://upload.twitter.com/1.1/media/upload.json"
    auth = _oauth1_header(
        method="POST",
        url=upload_url,
        consumer_key=profile.client_id,
        consumer_secret=profile.client_secret,
        token=profile.access_token,
        token_secret=profile.refresh_token,
    )
    req = Request(
        upload_url,
        data=body,
        headers={"Authorization": auth, "Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            err_body = json.loads(exc.read().decode())
        except Exception:
            err_body = {}
        errors = err_body.get("errors", [{}])
        msg = errors[0].get("message", f"HTTP {exc.code}") if errors else f"HTTP {exc.code}"
        return None, f"X media upload failed: {msg}"

    media_id = result.get("media_id_string")
    if not media_id:
        return None, "No media_id returned."

    # Poll for processing completion (required for GIFs/video, sometimes images).
    processing_info = result.get("processing_info")
    if processing_info:
        status_url = f"https://upload.twitter.com/1.1/media/upload.json?command=STATUS&media_id={media_id}"
        max_polls = 10
        for _ in range(max_polls):
            state = processing_info.get("state", "")
            if state == "succeeded":
                break
            if state == "failed":
                return None, "X media processing failed."
            wait = processing_info.get("check_after_secs", 3)
            time.sleep(int(wait))
            poll_auth = _oauth1_header(
                method="GET",
                url=status_url.split("?")[0],
                consumer_key=profile.client_id,
                consumer_secret=profile.client_secret,
                token=profile.access_token,
                token_secret=profile.refresh_token,
            )
            poll_req = Request(status_url, headers={"Authorization": poll_auth}, method="GET")
            try:
                with urlopen(poll_req, timeout=30) as pr:
                    poll_result = json.loads(pr.read().decode())
                    processing_info = poll_result.get("processing_info", {})
            except Exception:
                break

    return media_id, ""


# ---------------------------------------------------------------------------
# Platform posters
# ---------------------------------------------------------------------------

def post_to_x(profile, text: str, image_field=None) -> tuple[bool, str]:
    """
    Post *text* as a tweet using OAuth 1.0a.
    Optionally attaches *image_field* (a Django ImageField / FieldFile).
    Returns (ok, human-readable message).
    """
    if not profile.client_id or not profile.client_secret:
        return False, "X: Missing API Key or API Secret."
    if not profile.access_token:
        return False, "X: Missing Access Token."
    if not profile.refresh_token:
        return False, "X: Missing Access Token Secret."

    payload: dict = {"text": text}

    image_err = ""
    if image_field:
        media_id, err = _upload_media_x(profile, image_field)
        if media_id:
            payload["media"] = {"media_ids": [media_id]}
        else:
            image_err = err or "upload returned no media_id"
            _logger.warning("X image upload skipped: %s", image_err)

    url = "https://api.twitter.com/2/tweets"
    auth = _oauth1_header(
        method="POST",
        url=url,
        consumer_key=profile.client_id,
        consumer_secret=profile.client_secret,
        token=profile.access_token,
        token_secret=profile.refresh_token,
    )
    status, body = _http_post_json(url, payload, {"Authorization": auth})
    if status in (200, 201) and "data" in body:
        tweet_id = body["data"].get("id", "")
        had_image = "media" in payload
        msg = f"Posted to X{' with image' if had_image else ''}. Tweet ID: {tweet_id}"
        if image_err:
            msg += f" (image skipped: {image_err})"
        return True, msg
    _logger.error("X API tweet failure — HTTP %s — full body: %s", status, body)
    errors = body.get("errors") or body.get("detail", f"HTTP {status}")
    if isinstance(errors, list):
        errors = errors[0].get("message", str(errors[0]))
    return False, f"X error: {errors}"


def post_to_instagram(profile, text: str, image_field=None) -> tuple[bool, str]:
    if not profile.access_token or not profile.account_id:
        return False, "Instagram: Missing access token or account ID."
    # Instagram feed posts require an image_url. Fall back to a text-only
    # carousel workaround is complex, so we skip if no public image URL.
    image_url = _get_public_image_url(image_field)
    # Need a publicly reachable URL (BASE_URL must be set).
    base_url = (getattr(settings, "BASE_URL", "") or "").rstrip("/")
    if not image_url or not base_url:
        return False, "Instagram: A public image URL is required (set BASE_URL and use a post with a feature image)."
    url = f"https://graph.instagram.com/v19.0/{profile.account_id}/media"
    status, body = _http_post_form(
        url,
        {"caption": text, "image_url": image_url, "access_token": profile.access_token},
        {},
    )
    if status in (200, 201) and "id" in body:
        container_id = body["id"]
        pub_url = f"https://graph.instagram.com/v19.0/{profile.account_id}/media_publish"
        s2, b2 = _http_post_form(
            pub_url,
            {"creation_id": container_id, "access_token": profile.access_token},
            {},
        )
        if s2 in (200, 201):
            return True, f"Posted to Instagram with image. Media ID: {b2.get('id', '')}"
        return False, f"Instagram publish error: {b2}"
    return False, f"Instagram error: {body.get('error', {}).get('message', f'HTTP {status}')}"


def post_to_facebook(profile, text: str, image_field=None) -> tuple[bool, str]:
    if not profile.access_token or not profile.account_id:
        return False, "Facebook: Missing access token or page ID."
    image_url = _get_public_image_url(image_field)
    base_url = (getattr(settings, "BASE_URL", "") or "").rstrip("/")
    if image_url and base_url:
        # Use /photos endpoint to attach an image and caption in one call.
        url = f"https://graph.facebook.com/v19.0/{profile.account_id}/photos"
        params = {"caption": text, "url": image_url, "access_token": profile.access_token}
    else:
        url = f"https://graph.facebook.com/v19.0/{profile.account_id}/feed"
        params = {"message": text, "access_token": profile.access_token}
    status, body = _http_post_form(url, params, {})
    if status in (200, 201) and "id" in body:
        had_image = image_url and base_url
        return True, f"Posted to Facebook{' with image' if had_image else ''}. Post ID: {body['id']}"
    return False, f"Facebook error: {body.get('error', {}).get('message', f'HTTP {status}')}"


def post_to_google_business(profile, text: str, image_field=None) -> tuple[bool, str]:
    if not profile.access_token or not profile.account_id:
        return False, "Google Business: Missing access token or location resource name."
    location = profile.account_id.rstrip("/")
    url = f"https://mybusiness.googleapis.com/v4/{location}/localPosts"
    status, body = _http_post_json(
        url,
        {"languageCode": "en-US", "summary": text, "topicType": "STANDARD"},
        {"Authorization": f"Bearer {profile.access_token}"},
    )
    if status in (200, 201) and "name" in body:
        return True, f"Posted to Google Business."
    return False, f"Google Business error: {body.get('error', {}).get('message', f'HTTP {status}')}"


def post_to_linkedin(profile, text: str, image_field=None) -> tuple[bool, str]:
    if not profile.access_token or not profile.account_id:
        return False, "LinkedIn: Missing access token or organization ID."
    org_id = profile.account_id
    if not org_id.startswith("urn:"):
        org_id = f"urn:li:organization:{org_id}"
    image_url = _get_public_image_url(image_field)
    base_url = (getattr(settings, "BASE_URL", "") or "").rstrip("/")
    if image_url and base_url:
        share_media = [
            {
                "status": "READY",
                "description": {"text": ""},
                "originalUrl": image_url,
                "title": {"text": ""},
            }
        ]
        media_category = "ARTICLE"
    else:
        share_media = []
        media_category = "NONE"
    payload = {
        "author": org_id,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": media_category,
                **(  {"media": share_media} if share_media else {}),
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    status, body = _http_post_json(
        "https://api.linkedin.com/v2/ugcPosts",
        payload,
        {"Authorization": f"Bearer {profile.access_token}", "X-Restli-Protocol-Version": "2.0.0"},
    )
    if status in (200, 201):
        had_image = bool(share_media)
        return True, f"Posted to LinkedIn{' with image' if had_image else ''}."
    msg = body.get("message") or body.get("serviceErrorCode") or f"HTTP {status}"
    return False, f"LinkedIn error: {msg}"


# ---------------------------------------------------------------------------
# Dispatch: post to all enabled platforms for a given blog post
# ---------------------------------------------------------------------------

_POSTERS = {
    "instagram": post_to_instagram,
    "x": post_to_x,
    "facebook_page": post_to_facebook,
    "google_business": post_to_google_business,
    "linkedin_page": post_to_linkedin,
}


def post_to_all_platforms(post) -> list[tuple[str, bool, str]]:
    """
    Post *post* to every configured + enabled platform.
    Returns a list of (platform_display_name, ok, message) tuples.
    """
    from core.models import SocialProfile  # avoid circular import at module level

    image_field = post.feature_image if (post.feature_image and post.feature_image.name) else None

    results: list[tuple[str, bool, str]] = []
    profiles = SocialProfile.objects.filter(auto_post_on_publish=True)
    for profile in profiles:
        if not profile.access_token:
            continue
        poster = _POSTERS.get(profile.platform)
        if not poster:
            continue
        char_limit = CHAR_LIMITS.get(profile.platform)
        text = build_message(profile.message_template, post, char_limit)
        try:
            ok, msg = poster(profile, text, image_field=image_field)
        except Exception as exc:
            ok, msg = False, f"Unexpected error: {exc}"
        results.append((profile.get_platform_display(), ok, msg))
    return results
