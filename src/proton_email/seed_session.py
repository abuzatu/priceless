"""Save a Proton Mail Playwright session by connecting to Chrome on your Mac.

Use this when Proton shows the Human Verification puzzle and the Jupyter notebook
(running in Docker) cannot display a browser window for you to solve it.

Workflow:
1. Start Chrome on your Mac with remote debugging (see bin/dev/proton-seed-session.sh).
2. Log in to Proton in that Chrome window and complete the puzzle.
3. Run this script from Docker; it copies cookies into the per-email session file.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import socket
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

from proton_email.login import proton_session_path_for_email

DEFAULT_CDP_PORT = 9222
INBOX_URL = "https://mail.proton.me/u/0/inbox"
LOGGED_IN = re.compile(r"(mail\.proton\.me|account\.proton\.me/(apps|mail|u/))")


def _docker_host_cdp_urls(port: int = DEFAULT_CDP_PORT) -> list[str]:
    """Build CDP URLs that can reach Chrome on the Mac host from inside Docker."""
    hosts: list[str] = []

    # Docker Desktop (Mac/Windows) host IP — works when host.docker.internal uses IPv6.
    hosts.append("192.168.65.254")

    try:
        for info in socket.getaddrinfo(
            "host.docker.internal", port, type=socket.SOCK_STREAM
        ):
            ip = info[4][0]
            if ":" not in ip and ip not in hosts:
                hosts.append(ip)
    except OSError:
        pass

    try:
        with open("/proc/net/route", encoding="utf-8") as route_file:
            for line in route_file:
                parts = line.strip().split()
                if len(parts) >= 3 and parts[1] == "00000000":
                    gateway_hex = parts[2]
                    gateway = socket.inet_ntoa(bytes.fromhex(gateway_hex)[::-1])
                    if gateway not in hosts:
                        hosts.append(gateway)
                    break
    except OSError:
        pass

    hosts.extend(["host.docker.internal", "127.0.0.1"])

    seen: set[str] = set()
    urls: list[str] = []
    for host in hosts:
        if host in seen:
            continue
        seen.add(host)
        urls.append("http://%s:%d" % (host, port))
    return urls


async def save_session_from_cdp(
    *,
    cdp_url: str,
    email_address: str,
    output_path: Path,
    timeout_ms: int = 120_000,
) -> Path:
    """Connect to Chrome over CDP and export Proton cookies to storage_state JSON."""
    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.connect_over_cdp(cdp_url)
    except Exception as exc:
        raise RuntimeError(
            "Could not connect to Chrome at %s. Start Chrome with remote debugging "
            "first (see bin/dev/proton-seed-session.sh)." % cdp_url
        ) from exc

    try:
        if not browser.contexts:
            raise RuntimeError("Chrome has no browser context. Restart Chrome and retry.")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()

        print("Opening Proton inbox in Chrome...", flush=True)
        await page.goto(INBOX_URL, wait_until="domcontentloaded", timeout=timeout_ms)

        if "login" in page.url:
            raise RuntimeError(
                "Chrome is not logged in to Proton yet. In the Chrome window:\n"
                "  1. Go to https://account.proton.me/login\n"
                "  2. Sign in as %s\n"
                "  3. Complete Human Verification if shown\n"
                "  4. Re-run this script"
                % email_address
            )

        if not LOGGED_IN.search(page.url):
            raise RuntimeError(
                "Unexpected page after login: %s. Open the Proton inbox in Chrome "
                "and re-run this script." % page.url
            )

        try:
            await page.wait_for_selector(
                '[data-testid="message-list-loaded"], .item-container, '
                '[data-testid="conversation-header"]',
                timeout=30_000,
            )
        except Exception:
            print(
                "Warning: inbox UI not fully loaded, saving session anyway.",
                flush=True,
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(output_path))
        print("Saved Proton session to %s" % output_path, flush=True)
        return output_path
    finally:
        await browser.close()
        await playwright.stop()


async def _main_async(args: argparse.Namespace) -> int:
    load_dotenv()
    email = args.email or os.getenv("PROTON_EMAIL_ADDRESS_01", "")
    if not email:
        print("Set PROTON_EMAIL_ADDRESS_01 in .env or pass --email.", file=sys.stderr)
        return 1

    workdir = Path(os.getenv("WORKDIR", Path.cwd()))
    output_path = (
        Path(args.output)
        if args.output
        else proton_session_path_for_email(email, workdir)
    )

    cdp_urls = (
        [args.cdp_url]
        if args.cdp_url
        else (
            [os.getenv("PROTON_CDP_URL")]
            if os.getenv("PROTON_CDP_URL")
            else _docker_host_cdp_urls()
        )
    )
    last_error: Exception | None = None
    for cdp_url in cdp_urls:
        print("Trying Chrome at %s ..." % cdp_url, flush=True)
        try:
            await save_session_from_cdp(
                cdp_url=cdp_url,
                email_address=email,
                output_path=output_path,
            )
            print(
                "Done. Re-run the notebook with headless=True (default); "
                "it will reuse this session for %s." % email,
                flush=True,
            )
            return 0
        except RuntimeError as exc:
            last_error = exc
            print(str(exc), flush=True)
            if args.cdp_url:
                return 1

    if last_error is not None:
        print(str(last_error), file=sys.stderr, flush=True)
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Save Proton session from Chrome on your Mac (CDP)."
    )
    parser.add_argument(
        "--email",
        help="Proton address (default: PROTON_EMAIL_ADDRESS_01 from .env).",
    )
    parser.add_argument(
        "--cdp-url",
        help="Chrome remote debugging URL (default: host.docker.internal:9222).",
    )
    parser.add_argument(
        "--output",
        help="Override session JSON path (default: per-email path under data/).",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_main_async(args)))


if __name__ == "__main__":
    main()
