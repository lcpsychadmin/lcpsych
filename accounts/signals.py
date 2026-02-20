import logging
from typing import Any

from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

import requests

from core.models import AnalyticsEvent, AnalyticsEventType


def _client_ip(request) -> str:
	xff = request.META.get("HTTP_X_FORWARDED_FOR", "") if request else ""
	if xff:
		return xff.split(",")[0].strip()
	return (request.META.get("REMOTE_ADDR", "") if request else "") or ""


def _geolocate_ip(ip: str) -> dict[str, str]:
	if not ip:
		return {"country_code": "", "region": "", "city": "", "timezone": ""}
	try:
		from django.contrib.gis.geoip2 import GeoIP2  # type: ignore
		geo = GeoIP2()
		res = geo.city(ip)
		return {
			"country_code": (res.get("country_code") or "")[:2],
			"region": (res.get("region") or res.get("subdivisions", [{}])[0].get("names", {}).get("en") or "")[:100] if isinstance(res.get("subdivisions"), list) else (res.get("region") or "")[:100],
			"city": (res.get("city") or "")[:100],
			"timezone": (res.get("time_zone") or res.get("timezone") or "")[:64],
		}
	except Exception as exc:  # pragma: no cover
		logging.getLogger(__name__).debug("GeoIP lookup failed", exc_info=exc)

	token = getattr(settings, "IPINFO_TOKEN", "")
	if token and ip and not ip.startswith("127."):
		try:
			resp = requests.get(f"https://ipinfo.io/{ip}/json", params={"token": token}, timeout=1.5)
			if resp.status_code == 200:
				data = resp.json()
				return {
					"country_code": (data.get("country") or "")[:2],
					"region": (data.get("region") or "")[:100],
					"city": (data.get("city") or "")[:100],
					"timezone": (data.get("timezone") or "")[:64],
				}
		except Exception as exc:  # pragma: no cover
			logging.getLogger(__name__).debug("ipinfo lookup failed", exc_info=exc)

	return {"country_code": "", "region": "", "city": "", "timezone": ""}


def _session_id_from_request(request: Any) -> str:
	if not request:
		return "auth-none"
	sid = getattr(getattr(request, "session", None), "session_key", None)
	if not sid and getattr(request, "session", None) is not None:
		request.session.create()
		sid = request.session.session_key
	return sid or "auth-none"


@receiver(user_logged_in)
def log_auth_success(sender, request, user, **kwargs):  # type: ignore
	ip = _client_ip(request)
	geo = _geolocate_ip(ip)
	AnalyticsEvent.objects.create(
		event_type=AnalyticsEventType.AUTH_SUCCESS,
		session_id=_session_id_from_request(request),
		path=(getattr(request, "path", "") or "")[:500],
		referrer=(request.META.get("HTTP_REFERER", "") if request else "")[:500],
		user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else "")[:1000],
		ip_hash=AnalyticsEvent.hash_ip(ip),
		label="login_success",
		is_authenticated=True,
		country_code=geo.get("country_code", ""),
		region=geo.get("region", ""),
		city=geo.get("city", ""),
		timezone=geo.get("timezone", ""),
	)


@receiver(user_login_failed)
def log_auth_failed(sender, credentials, request, **kwargs):  # type: ignore
	if not request:
		return
	ip = _client_ip(request)
	geo = _geolocate_ip(ip)
	AnalyticsEvent.objects.create(
		event_type=AnalyticsEventType.AUTH_FAILED,
		session_id=_session_id_from_request(request),
		path=(getattr(request, "path", "") or "")[:500],
		referrer=(request.META.get("HTTP_REFERER", "") if request else "")[:500],
		user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else "")[:1000],
		ip_hash=AnalyticsEvent.hash_ip(ip),
		label="login_failed",
		metadata={"has_username": bool(credentials.get("username"))} if isinstance(credentials, dict) else {},
		is_authenticated=False,
		country_code=geo.get("country_code", ""),
		region=geo.get("region", ""),
		city=geo.get("city", ""),
		timezone=geo.get("timezone", ""),
	)