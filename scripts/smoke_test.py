"""
Post-deployment smoke test (standard library only). Verifies the things that broke or could silently break in production:
the SPA is served with security headers, SPA routes resolve, API errors are NOT rewritten to index.html, the API refuses
anonymous callers both through CloudFront and directly, and (optionally) an authenticated call works.

Usage:
    python scripts/smoke_test.py --site https://dxxxx.cloudfront.net --api https://abc.execute-api.af-south-1.amazonaws.com/staging
Optional: set SMOKE_ID_TOKEN to a valid Cognito ID token to also verify an authenticated, tenant-scoped read.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

REQUIRED_HEADERS = ["strict-transport-security", "content-security-policy", "x-frame-options", "x-content-type-options", "referrer-policy"]


def fetch(url: str, headers: dict | None = None):
    request = urllib.request.Request(url, headers=headers or {})  # noqa: S310 - https URLs supplied by CI
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:  # noqa: S310
            return resp.status, dict((k.lower(), v) for k, v in resp.headers.items()), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        return err.code, dict((k.lower(), v) for k, v in err.headers.items()), err.read().decode("utf-8", "replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--api", required=True)
    args = parser.parse_args()
    site, api = args.site.rstrip("/"), args.api.rstrip("/")
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'}  {name}{(' - ' + detail) if detail and not ok else ''}")
        if not ok:
            failures.append(name)

    status, headers, body = fetch(f"{site}/")
    check("site root serves the SPA", status == 200 and '<div id="root">' in body, f"status={status}")
    missing = [h for h in REQUIRED_HEADERS if h not in headers]
    check("security headers present", not missing, f"missing={missing}")

    status, _, body = fetch(f"{site}/vehicles")
    check("SPA deep link resolves to index.html", status == 200 and '<div id="root">' in body, f"status={status}")

    status, headers, body = fetch(f"{site}/api/vehicles")
    check("anonymous /api call is rejected with 401 JSON (not index.html)", status == 401 and "<html" not in body.lower(), f"status={status}")

    status, _, _ = fetch(f"{api}/vehicles")
    check("direct API refuses anonymous callers", status == 401, f"status={status}")

    status, _, body = fetch(f"{site}/api/not-a-route", {"Authorization": "Bearer invalid"})
    check("invalid token is refused through CloudFront", status in (401, 403) and "<html" not in body.lower(), f"status={status}")

    token = os.environ.get("SMOKE_ID_TOKEN")
    if token:
        status, _, body = fetch(f"{site}/api/vehicles?limit=1", {"Authorization": f"Bearer {token}"})
        ok = status == 200
        if ok:
            payload = json.loads(body)
            ok = isinstance(payload.get("items"), list) and "nextToken" in payload
        check("authenticated tenant-scoped read works", ok, f"status={status}")
    else:
        print("SKIP  authenticated read (set SMOKE_ID_TOKEN to enable)")

    print(f"\n{'ALL CHECKS PASSED' if not failures else 'FAILED: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
