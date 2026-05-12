"""
management command: remove_urls
Usage::

    python manage.py remove_urls [--file dead_urls.txt] [--base-url http://localhost:8000]

Reads URLs from a file (one per line, blank lines and # comments ignored) and
POSTs them in batches to the /api/url-removal/ endpoint.

Environment variables required on the calling machine:
    URL_REMOVAL_TOKEN – must match the value configured on the server.

Example::

    URL_REMOVAL_TOKEN=secret python manage.py remove_urls --file dead_urls.txt
"""

from __future__ import annotations

import os
import urllib.request
import urllib.error
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Submit a list of dead URLs to /api/url-removal/ for Google Search Console removal."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default="dead_urls.txt",
            help="Path to a text file containing one URL per line (default: dead_urls.txt).",
        )
        parser.add_argument(
            "--base-url",
            default="http://localhost:8000",
            dest="base_url",
            help="Base URL of the Django site running locally or remotely (default: http://localhost:8000).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            dest="batch_size",
            help="Number of URLs to send per request (default: 50).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Print what would be sent without actually making any API calls.",
        )

    def handle(self, *args, **options):
        token = os.environ.get("URL_REMOVAL_TOKEN", "")
        if not token and not options["dry_run"]:
            raise CommandError(
                "URL_REMOVAL_TOKEN environment variable is not set.  "
                "Export it before running this command."
            )

        file_path = Path(options["file"])
        if not file_path.is_file():
            raise CommandError(f"File not found: {file_path}")

        raw_lines = file_path.read_text(encoding="utf-8").splitlines()
        urls = [
            line.strip()
            for line in raw_lines
            if line.strip() and not line.strip().startswith("#")
        ]

        if not urls:
            self.stdout.write(self.style.WARNING("No URLs found in file — nothing to do."))
            return

        self.stdout.write(f"Found {len(urls)} URL(s) in {file_path}")

        if options["dry_run"]:
            for url in urls:
                self.stdout.write(f"  [dry-run] would remove: {url}")
            return

        base_url = options["base_url"].rstrip("/")
        endpoint = f"{base_url}/api/url-removal/"
        batch_size: int = options["batch_size"]

        total_success = 0
        total_failure = 0

        for i in range(0, len(urls), batch_size):
            batch = urls[i : i + batch_size]
            self.stdout.write(
                f"Submitting batch {i // batch_size + 1} ({len(batch)} URLs)…"
            )

            payload = json.dumps({"urls": batch}).encode("utf-8")
            req = urllib.request.Request(
                endpoint,
                data=payload,
                headers={
                    "X-Removal-Token": token,
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    body: dict = json.loads(resp.read().decode())
            except urllib.error.HTTPError as exc:
                error_body = exc.read().decode() if exc.fp else str(exc)
                raise CommandError(
                    f"HTTP {exc.code} from {endpoint}: {error_body}"
                ) from exc
            except Exception as exc:
                raise CommandError(f"Request to {endpoint} failed: {exc}") from exc

            results: list[dict] = body.get("results", [])
            for result in results:
                url_str = result.get("url", "?")
                if result.get("success"):
                    total_success += 1
                    self.stdout.write(f"  {self.style.SUCCESS('OK')}  {url_str}")
                else:
                    total_failure += 1
                    error = result.get("error", "unknown error")
                    self.stdout.write(
                        f"  {self.style.ERROR('FAIL')} {url_str} — {error}"
                    )

        self.stdout.write("")
        self.stdout.write(
            f"Done.  {total_success} submitted successfully, {total_failure} failed."
        )
        if total_failure:
            raise CommandError(f"{total_failure} URL removal(s) failed.")
