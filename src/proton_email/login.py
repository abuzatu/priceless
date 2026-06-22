"""Log in to Proton Mail with Playwright and read inbox messages."""

from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from playwright.async_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    Playwright,
    async_playwright,
)


@dataclass(frozen=True)
class ProtonEmailMessage:
    """Summary of a single Proton Mail message."""

    sender: str
    subject: str
    received_at: str
    snippet: str


@dataclass(frozen=True)
class LibraOneTimeCode:
    """One-time login code from a Libra X Priceless email."""

    code: str
    subject: str
    received_at: str


@dataclass(frozen=True)
class LibraVoucherDetail:
    """Claim URL, code, and order summary from a Libra e-voucher email."""

    url: str
    code: str
    received_at: str
    comanda_nr: str = ""
    redemption_id: str = ""
    comanda_id: str = ""
    cantitate: str = ""
    puncte: str = ""
    subtotal: str = ""
    total: str = ""
    received_at_dt: Optional[datetime] = None


def extract_one_time_code(body: str) -> str:
    """Parse a numeric one-time code from Libra email body text."""
    patterns = (
        re.compile(
            r"Your one-time code for Libra X Priceless is:\s*([0-9]{4,8})",
            re.I,
        ),
        re.compile(r"one[- ]time code[^0-9]*([0-9]{4,8})", re.I),
        re.compile(r"verification code[^0-9]*([0-9]{4,8})", re.I),
        re.compile(r"your code[^0-9]*([0-9]{4,8})", re.I),
        re.compile(r"\b(\d{6})\b"),
    )
    normalized = re.sub(r"\s+", " ", body).strip()
    for pattern in patterns:
        match = pattern.search(normalized)
        if match:
            return match.group(1)
    raise ValueError(
        "Could not find a one-time code in the email body. Body preview: %s"
        % (normalized[:200] or "<empty>")
    )


def _normalize_voucher_text(text: str) -> str:
    """Collapse whitespace and strip invisible chars from email body text."""
    cleaned = text.replace("\u200b", "").replace("\ufeff", "")
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_voucher_order_fields(text: str, html: str = "") -> dict[str, str]:
    """Parse order summary fields from a Libra e-voucher email body."""
    combined = _normalize_voucher_text(
        text + " " + re.sub(r"\s+", " ", html or "")
    )

    def grab(pattern: str) -> str:
        match = re.search(pattern, combined, re.I)
        return match.group(1).strip() if match else ""

    return {
        "comanda_nr": grab(r"Comanda #:\s*(\d+)"),
        "redemption_id": grab(r"Redemption ID:\s*(\d+)"),
        "comanda_id": grab(r"Comanda ID\s*(\d+-\d+)"),
        "cantitate": grab(r"Cantitate\s*(\d+)"),
        "puncte": grab(r"Puncte\s*([\d.,]+)"),
        "subtotal": grab(r"Subtotal\s*([\d.,]+)"),
        "total": grab(r"Total\s*:\s*([\d.,]+)"),
    }


def extract_all_voucher_url_and_code_pairs(text: str, html: str = "") -> list[tuple[str, str]]:
    """Parse all (url, code) pairs from a Libra e-voucher email body."""
    combined_html = html or ""
    normalized = re.sub(r"\s+", " ", text).strip()
    combined = normalized + " " + re.sub(r"\s+", " ", combined_html)

    urls: list[str] = []
    for match in re.finditer(
        r'href=["\'](https?://[^"\']+)["\'][^>]*>([^<]*)<',
        combined_html,
        re.I,
    ):
        link_text = match.group(2)
        if re.search(r"vizualiza|click aici", link_text, re.I):
            urls.append(match.group(1))

    if not urls:
        for candidate in re.findall(r"https?://[^\s<>\"']+", combined):
            lowered = candidate.lower()
            if any(
                token in lowered
                for token in (
                    "rewardcloud",
                    "voucher",
                    "priceless",
                    "evoucher",
                    "e-voucher",
                    "gift",
                    "emag",
                )
            ):
                urls.append(candidate.rstrip(".,;)"))

    # "." matches Romanian "ț" in contestație (t-comma) and plain ASCII variants.
    codes = re.findall(
        r"Cod de contesta.{1,3}:\s*([a-f0-9\-]{36})",
        combined,
        re.I,
    )
    if not codes:
        codes = re.findall(
            r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}",
            combined,
            re.I,
        )

    pairs: list[tuple[str, str]] = []
    if urls and codes:
        for index, code in enumerate(codes):
            url = urls[index] if index < len(urls) else urls[-1]
            pairs.append((url, code))
    return pairs


def extract_voucher_url_and_code(text: str, html: str = "") -> tuple[str, str]:
    """Parse the first claim URL and code from a Libra e-voucher email."""
    pairs = extract_all_voucher_url_and_code_pairs(text, html)
    if not pairs:
        normalized = re.sub(r"\s+", " ", text).strip()
        raise ValueError(
            "Could not find voucher url/code. Body preview: %s"
            % (normalized[:300] or "<empty>")
        )
    return pairs[0]


def parse_message_datetime(raw: str) -> Optional[datetime]:
    """Parse a Proton message time (ISO `datetime` attr or human-readable label)."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        pass

    for fmt in (
        "%A, %d %B %Y at %I:%M %p",
        "%d %B %Y at %I:%M %p",
    ):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def proton_session_path_for_email(
    email_address: str,
    workdir: Optional[Path] = None,
) -> Path:
    """Return per-account Playwright storage state path for one Proton address."""
    root = workdir or Path(os.getenv("WORKDIR", Path.cwd()))
    sessions_dir = root / "data" / "proton_email" / "sessions"
    safe = email_address.strip().lower()
    safe = safe.replace("@", "_at_").replace("+", "_plus_")
    safe = re.sub(r"[^\w.\-]+", "_", safe)
    return sessions_dir / ("%s.json" % safe)


class ProtonEmailLogin:
    """Browser-based Proton Mail client (no IMAP/API; E2E encryption)."""

    LOGIN_URL = "https://account.proton.me/login"
    INBOX_URL = "https://mail.proton.me/u/0/inbox"
    LOGGED_IN_URL = re.compile(
        r"(mail\.proton\.me|account\.proton\.me/(apps|mail|u/))"
    )
    LIBRA_ONE_TIME_CODE_SUBJECT = re.compile(
        r"One-time code for Libra X Priceless", re.I
    )
    # "." matches any character so we do not depend on typing Romanian "ă".
    LIBRA_VOUCHER_SUBJECT = re.compile(r"Detalii comand. e-voucher", re.I)

    def __init__(
        self,
        email_address: Optional[str] = None,
        password: Optional[str] = None,
        *,
        headless: bool = True,
        verbose: bool = True,
        debug: bool = False,
        screenshot_dir: Optional[str] = None,
        debug_version: str = "v01",
        slow_mo: int = 0,
        storage_state_path: Optional[str] = None,
        login_timeout_ms: int = 120_000,
        human_verification_timeout_ms: int = 600_000,
    ) -> None:
        """Load credentials from `.env` and prepare browser settings.

        Args:
            headless: Run Chromium without a visible window. Inside Docker there is
                no display on your Mac unless you add noVNC/X11 forwarding.
            debug: Save a PNG after each step under `screenshot_dir` and slow actions
                so you can follow progress from the notebook (like Selenium screenshots).
            screenshot_dir: Folder for step screenshots (default when debug=True:
                data/debug/proton_email).
            debug_version: Prefix for screenshot files, e.g. v01 -> v01_01_login_page.png.
            slow_mo: Milliseconds to pause between Playwright actions.
            storage_state_path: Playwright cookies/localStorage JSON used to skip login.
                Defaults to data/proton_email/sessions/<email>.json for the current
                PROTON_EMAIL_ADDRESS_01 value.
            login_timeout_ms: Max wait for login to finish under normal conditions.
            human_verification_timeout_ms: Extra wait when Proton shows a CAPTCHA puzzle.
        """
        load_dotenv()

        self.email_address = email_address or os.getenv("PROTON_EMAIL_ADDRESS_01", "")
        self.password = password or os.getenv("PROTON_EMAIL_PASSWORD_01", "")
        self.headless = headless
        self.verbose = verbose
        self.debug = debug
        self.debug_version = debug_version
        self.slow_mo = 300 if debug and slow_mo == 0 else slow_mo
        self.login_timeout_ms = login_timeout_ms
        self.human_verification_timeout_ms = human_verification_timeout_ms
        workdir = Path(os.getenv("WORKDIR", Path.cwd()))
        self.storage_state_path = (
            Path(storage_state_path)
            if storage_state_path
            else proton_session_path_for_email(self.email_address, workdir)
        )
        self.screenshot_dir = (
            Path(screenshot_dir)
            if screenshot_dir
            else (workdir / "data" / "debug" / "proton_email" if debug else None)
        )
        if self.screenshot_dir is not None:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._screenshot_step = 0

        if not self.email_address or not self.password:
            raise ValueError(
                "Set PROTON_EMAIL_ADDRESS_01 and PROTON_EMAIL_PASSWORD_01 in .env"
            )

    async def login(self) -> ProtonEmailMessage:
        """Sign in to Proton Mail and return the most recent inbox message."""
        try:
            await self._connect_to_inbox()
            self._log("Reading most recent email...")
            message = await self._read_last_email(self._page)
            await self._screenshot(self._page, "last_email_open")
            return message
        except Exception as exc:
            await self._handle_error(exc)
            raise

    async def get_libra_one_time_code(self) -> LibraOneTimeCode:
        """Open the latest Libra one-time-code email and return the code."""
        try:
            await self._connect_to_inbox()
            self._log('Looking for "One-time code for Libra X Priceless"...')
            result = await self._read_libra_one_time_code(self._page)
            await self._screenshot(self._page, "libra_one_time_code")
            self._log("Found code: %s" % result.code)
            return result
        except Exception as exc:
            await self._handle_error(exc)
            raise

    async def get_libra_voucher_details(
        self,
        since: Optional[datetime] = None,
    ) -> list[LibraVoucherDetail]:
        """Return voucher details for each e-voucher message in the latest matching thread.

        Args:
            since: If set, only include messages received strictly after this time.
        """
        try:
            await self._connect_to_inbox()
            self._log('Looking for "Detalii comand* e-voucher" thread...')
            details = await self._read_libra_voucher_thread(self._page, since=since)
            await self._screenshot(self._page, "libra_voucher_details")
            self._log("Found %s voucher message(s)." % len(details))
            for index, detail in enumerate(details, start=1):
                self._log(
                    "  %s. comanda#=%s redemption_id=%s comanda_id=%s "
                    "cantitate=%s puncte=%s subtotal=%s total=%s code=%s"
                    % (
                        index,
                        detail.comanda_nr,
                        detail.redemption_id,
                        detail.comanda_id,
                        detail.cantitate,
                        detail.puncte,
                        detail.subtotal,
                        detail.total,
                        detail.code,
                    )
                )
            return details
        except Exception as exc:
            await self._handle_error(exc)
            raise

    def login_sync(self) -> ProtonEmailMessage:
        """Blocking login for scripts outside an asyncio event loop (e.g. CLI)."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.login())
        raise RuntimeError(
            "Use `await client.login()` in Jupyter/async contexts, "
            "or `client.login_sync()` only from a plain script."
        )

    def get_libra_one_time_code_sync(self) -> LibraOneTimeCode:
        """Blocking version of `get_libra_one_time_code`."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.get_libra_one_time_code())
        raise RuntimeError(
            "Use `await client.get_libra_one_time_code()` in Jupyter/async contexts."
        )

    def get_libra_voucher_details_sync(
        self,
        since: Optional[datetime] = None,
    ) -> list[LibraVoucherDetail]:
        """Blocking version of `get_libra_voucher_details`."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.get_libra_voucher_details(since=since))
        raise RuntimeError(
            "Use `await client.get_libra_voucher_details()` in Jupyter/async contexts."
        )

    async def _connect_to_inbox(self) -> None:
        """Launch browser, sign in, and open the inbox."""
        self._log(
            "Launching browser (headless=%s, debug=%s)..." % (self.headless, self.debug)
        )
        if self.debug and self.screenshot_dir is not None:
            self._log("Screenshots -> %s" % self.screenshot_dir)

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context_kwargs = {
            "user_agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1440, "height": 900},
        }
        if self.storage_state_path.exists():
            context_kwargs["storage_state"] = str(self.storage_state_path)
            self._log("Loading saved Proton session from %s" % self.storage_state_path)
        self._context = await self._browser.new_context(**context_kwargs)
        self._page = await self._context.new_page()
        await self._page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        if await self._try_restore_session(self._page):
            self._log("Reused saved Proton session.")
            await self._screenshot(self._page, "authenticated")
        else:
            self._log("Signing in to Proton...")
            await self._authenticate(self._page)
            await self._save_storage_state()
            await self._screenshot(self._page, "authenticated")
            self._log("Authenticated at %s" % self._page.url)

        self._log("Opening inbox...")
        await self._open_inbox(self._page)
        await self._screenshot(self._page, "inbox")

    async def _handle_error(self, exc: Exception) -> None:
        if self._page is not None:
            path = await self._screenshot(self._page, "error")
            if path is not None:
                raise RuntimeError("%s (screenshot: %s)" % (exc, path)) from exc
        if not self.debug:
            await self.close()

    async def close(self) -> None:
        """Shut down the browser session."""
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        self._page = None

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message, flush=True)

    async def _screenshot(self, page: Page, label: str) -> Optional[Path]:
        if self.screenshot_dir is None:
            return None
        self._screenshot_step += 1
        path = self.screenshot_dir / (
            "%s_%02d_%s.png" % (self.debug_version, self._screenshot_step, label)
        )
        await page.screenshot(path=str(path), full_page=True)
        self._log("Screenshot: %s" % path)
        return path

    async def _authenticate(self, page: Page) -> None:
        await page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
        await self._screenshot(page, "login_page")
        self._log("Login page loaded.")

        username = page.locator("#username")
        await username.wait_for(state="visible", timeout=60_000)
        await username.fill(self.email_address)

        password = page.locator("#password")
        if not await password.is_visible():
            self._log("Submitting email, waiting for password field...")
            await page.locator('button[type="submit"]').click()
            await password.wait_for(state="visible", timeout=60_000)

        await password.fill(self.password)
        self._log("Submitting password...")
        await page.locator('button[type="submit"]').click()

        await self._wait_for_login_complete(page)

    async def _wait_for_login_complete(self, page: Page) -> None:
        deadline = time.monotonic() + self.login_timeout_ms / 1000
        human_verification_logged = False
        while time.monotonic() < deadline:
            if self.LOGGED_IN_URL.search(page.url):
                return
            if await self._human_verification_visible(page):
                if not human_verification_logged:
                    await self._screenshot(page, "human_verification")
                    if self.headless:
                        self._log(
                            "Human verification puzzle detected. The Docker notebook "
                            "cannot show this window. Run ./bin/dev/proton-seed-session.sh "
                            "on your Mac, then re-run with default headless=True."
                        )
                    else:
                        self._log(
                            "Human verification puzzle detected. Complete the puzzle "
                            "in the browser window, then click Next."
                        )
                    human_verification_logged = True
                    deadline = max(
                        deadline,
                        time.monotonic() + self.human_verification_timeout_ms / 1000,
                    )
                await page.wait_for_timeout(2000)
                continue
            if await self._two_factor_prompt_visible(page):
                raise RuntimeError(
                    "Proton Mail requested 2FA. Disable 2FA for this account or "
                    "complete a manual browser login once and reuse storage state."
                )
            if await self._login_error_visible(page):
                raise RuntimeError(
                    "Proton Mail login failed. Check PROTON_EMAIL_ADDRESS_01 and "
                    "PROTON_EMAIL_PASSWORD_01 in .env."
                )
            await page.wait_for_timeout(1000)

        await self._screenshot(page, "login_timeout")
        raise RuntimeError(
            "Proton Mail login timed out at %s. "
            "Human Verification (CAPTCHA) cannot be solved from the Docker notebook. "
            "Run once on your Mac: ./bin/dev/proton-seed-session.sh "
            "(see README_Proton.md), then re-run this notebook with default headless=True."
            % page.url
        )

    async def _try_restore_session(self, page: Page) -> bool:
        if not self.storage_state_path.exists():
            return False
        try:
            await page.goto(self.INBOX_URL, wait_until="domcontentloaded", timeout=60_000)
            if "login" in page.url:
                return False
            await page.wait_for_selector(
                '[data-testid="message-list-loaded"], .item-container, '
                '[data-testid="conversation-header"]',
                timeout=30_000,
            )
            self._log("Inbox URL: %s" % page.url)
            return True
        except Exception:
            return False

    async def _save_storage_state(self) -> None:
        if self._context is None:
            return
        self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
        await self._context.storage_state(path=str(self.storage_state_path))
        self._log("Saved Proton session to %s" % self.storage_state_path)

    async def _open_inbox(self, page: Page) -> None:
        if "account.proton.me/apps" in page.url:
            self._log("On Proton apps page, opening Mail...")
            mail_entry = page.locator(
                'a[href*="mail.proton.me"], button:has-text("Mail"), '
                '[data-testid*="mail"], [title*="Mail"]'
            )
            if await mail_entry.count() > 0:
                await mail_entry.first.click()
                await page.wait_for_url(re.compile(r"mail\.proton\.me"), timeout=120_000)
            else:
                await page.goto(self.INBOX_URL, wait_until="domcontentloaded")
        else:
            await page.goto(self.INBOX_URL, wait_until="domcontentloaded")

        try:
            await page.wait_for_load_state("networkidle", timeout=60_000)
        except Exception:
            self._log("Network still settling; continuing...")

        await self._dismiss_overlays(page)
        self._log("Inbox URL: %s" % page.url)

    async def _dismiss_overlays(self, page: Page) -> None:
        await self._dismiss_welcome_modal(page)
        await self._dismiss_upgrade_banner(page)

    async def _dismiss_welcome_modal(self, page: Page) -> None:
        """Step through the first-login 'Welcome to Proton Mail' carousel."""
        for step in range(8):
            modal = page.locator(".modal-two")
            if await modal.count() == 0 or not await modal.first.is_visible():
                return

            self._log("Dismissing welcome modal (step %s)..." % (step + 1))
            clicked = False
            for label in (
                r"let'?s get started",
                r"get started",
                r"continue",
                r"next",
                r"skip",
                r"maybe later",
                r"not now",
                r"got it",
                r"done",
            ):
                btn = modal.first.get_by_role("button", name=re.compile(label, re.I))
                if await btn.count() > 0:
                    await btn.first.click(timeout=10_000)
                    clicked = True
                    await page.wait_for_timeout(1000)
                    break

            if not clicked:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)

    async def _dismiss_upgrade_banner(self, page: Page) -> None:
        """Close the optional 'Upgrade to use auto-reply' top banner."""
        modal = page.locator(".modal-two")
        if await modal.count() > 0 and await modal.first.is_visible():
            return

        banner = page.get_by_text(re.compile(r"Upgrade to use auto-reply", re.I))
        if await banner.count() == 0:
            return

        self._log("Dismissing upgrade banner...")
        close_btn = page.locator(
            'button[title="Close"].button-for-icon.button-small'
        ).first
        if await close_btn.count() > 0 and await close_btn.is_visible():
            try:
                await close_btn.click(timeout=5_000)
            except Exception:
                await close_btn.click(force=True, timeout=5_000)
            await page.wait_for_timeout(300)

    async def _two_factor_prompt_visible(self, page: Page) -> bool:
        two_factor = page.get_by_text(re.compile(r"two.?factor|authentication code", re.I))
        return await two_factor.count() > 0

    async def _human_verification_visible(self, page: Page) -> bool:
        captcha = page.get_by_text(
            re.compile(r"human verification|verify you are human", re.I)
        )
        return await captcha.count() > 0

    async def _login_error_visible(self, page: Page) -> bool:
        error = page.locator('[role="alert"], .notification--danger, .alert-block--danger')
        return await error.count() > 0

    async def _wait_for_message_list(self, page: Page) -> None:
        self._log("Waiting for message list...")
        loading = page.locator('[data-testid="message-list-loading"]')
        loaded = page.locator('[data-testid="message-list-loaded"]')
        try:
            if await loading.count() > 0:
                await loading.first.wait_for(state="detached", timeout=120_000)
            await loaded.first.wait_for(state="attached", timeout=120_000)
        except Exception:
            self._log("message-list test ids not found; trying fallback selectors...")

        for selector in (
            ".item-container:not(.item-is-loading)",
            '[data-shortcut-target]',
            '[data-testid="message-column:subject"]',
        ):
            loc = page.locator(selector).first
            try:
                await loc.wait_for(state="visible", timeout=30_000)
                self._log("Message list ready via %s" % selector)
                return
            except Exception:
                continue

        empty = page.get_by_text(
            re.compile(r"no messages|inbox is empty|your inbox is empty", re.I)
        )
        if await empty.count() > 0:
            raise RuntimeError("Inbox is empty — no emails to read.")

        raise RuntimeError(
            "Message list did not appear at %s (title: %s)." % (page.url, await page.title())
        )

    async def _first_message_subject(self, page: Page) -> Locator:
        for selector in (
            '[data-testid="message-column:subject"]',
            '.item-subject [role="heading"][data-testid="message-column:subject"]',
            '.item-subject [role="heading"]',
            '.item-container [role="heading"]',
        ):
            loc = page.locator(selector).first
            try:
                await loc.wait_for(state="visible", timeout=20_000)
                self._log("Found first message via %s" % selector)
                return loc
            except Exception:
                continue
        raise RuntimeError(
            "No visible email rows found. Inbox may be empty or the UI changed."
        )

    async def _find_message_by_subject(self, page: Page, pattern: re.Pattern[str]) -> Locator:
        """Return the first (most recent) inbox row whose subject matches."""
        await self._wait_for_message_list(page)
        rows = page.locator(".item-container:not(.item-is-loading)")
        count = await rows.count()
        self._log("Scanning %s inbox rows for subject match..." % count)

        for index in range(count):
            row = rows.nth(index)
            subject_el = row.locator(
                '[data-testid="message-column:subject"], .item-subject [role="heading"]'
            ).first
            candidates: list[str] = []
            if await subject_el.count() > 0:
                title = await subject_el.get_attribute("title")
                if title:
                    candidates.append(title)
                candidates.append(await subject_el.inner_text())
            candidates.append(await row.inner_text())

            for text in candidates:
                if pattern.search(text):
                    self._log("Matched email: %s" % text.strip().split("\n")[0])
                    return row

        raise RuntimeError('No email found with subject matching "%s".' % pattern.pattern)

    async def _row_subject(self, row: Locator) -> str:
        subject_el = row.locator(
            '[data-testid="message-column:subject"], .item-subject [role="heading"]'
        ).first
        if await subject_el.count() > 0:
            return (
                await subject_el.get_attribute("title")
                or await subject_el.inner_text()
            ).strip()
        return (await row.inner_text()).strip().split("\n")[0]

    async def _row_received_at(self, row: Locator) -> str:
        time_locator = row.locator("time")
        if await time_locator.count() > 0:
            return (
                await time_locator.first.get_attribute("datetime")
                or await time_locator.first.inner_text()
            ).strip()
        return ""

    async def _read_message_body(self, page: Page) -> str:
        """Read the full visible body of the currently open message."""
        text, _html = await self._read_message_body_parts(page)
        return text

    async def _conversation_iframes(self, page: Page) -> Locator:
        """Return iframe locators for email bodies in the open conversation."""
        for selector in (
            '[data-testid="conversation-view"] iframe',
            '[data-shortcut-target="conversation-body"] iframe',
        ):
            iframes = page.locator(selector)
            if await iframes.count() > 0:
                return iframes
        iframes = page.locator("iframe")
        if await iframes.count() > 0:
            return iframes
        raise RuntimeError("No message iframes found in conversation.")

    async def _iframe_for_message(
        self, page: Page, headers: Locator, index: int
    ) -> Locator:
        """Click a thread message header and return its email iframe."""
        header = headers.nth(index)
        await header.scroll_into_view_if_needed(timeout=10_000)
        await header.click(timeout=10_000)
        await page.wait_for_timeout(1000)

        relative_selectors = (
            'xpath=ancestor::*[@data-shortcut-target="message-view"][1]//iframe',
            'xpath=ancestor::*[contains(@class, "message-container")][1]//iframe',
            "xpath=ancestor::article[1]//iframe",
            'xpath=ancestor::*[@data-testid="message-view:body"][1]//iframe',
            "xpath=following::iframe[1]",
        )
        for selector in relative_selectors:
            iframe = header.locator(selector).first
            if await iframe.count() > 0:
                await iframe.scroll_into_view_if_needed(timeout=10_000)
                await self._align_iframe_in_conversation(page, iframe)
                return iframe

        iframes = await self._conversation_iframes(page)
        count = await iframes.count()
        if count == 0:
            raise RuntimeError("No iframes in conversation for message %s." % (index + 1))
        iframe = iframes.nth(min(index, count - 1))
        await iframe.scroll_into_view_if_needed(timeout=10_000)
        await self._align_iframe_in_conversation(page, iframe)
        return iframe

    async def _iframe_parts_from_message_view(
        self, message_view: Locator
    ) -> tuple[str, str]:
        result = await message_view.evaluate(
            """el => {
              const iframe = el.querySelector('iframe');
              if (!iframe || !iframe.contentDocument) {
                return {text: '', html: ''};
              }
              const body = iframe.contentDocument.body;
              return {
                text: (body.textContent || '').trim(),
                html: (body.innerHTML || '').trim()
              };
            }"""
        )
        return result.get("text", ""), result.get("html", "")

    async def _align_iframe_in_conversation(
        self, page: Page, iframe_loc: Locator
    ) -> None:
        conversation = page.locator('[data-testid="conversation-view"]').first
        if await conversation.count() == 0:
            return
        iframe_box = await iframe_loc.bounding_box()
        conv_box = await conversation.bounding_box()
        if not iframe_box or not conv_box:
            return
        current_scroll = await conversation.evaluate("el => el.scrollTop")
        delta = iframe_box["y"] - conv_box["y"]
        await conversation.evaluate(
            "(el, top) => { el.scrollTop = Math.max(0, top); }",
            current_scroll + delta - 60,
        )
        await page.wait_for_timeout(200)

    async def _wheel_scroll_locator(self, page: Page, target: Locator, steps: int) -> None:
        box = await target.bounding_box()
        if not box:
            return
        x = box["x"] + box["width"] / 2
        y = box["y"] + min(box["height"] / 2, box["height"] - 10)
        await page.mouse.move(x, y)
        for _ in range(steps):
            await page.mouse.wheel(0, 700)
            await page.wait_for_timeout(150)

    async def _scroll_iframe_until_voucher(
        self, page: Page, iframe_loc: Locator
    ) -> tuple[str, str]:
        """Scroll one email iframe until voucher fields are in the DOM."""
        await iframe_loc.scroll_into_view_if_needed(timeout=10_000)
        await self._align_iframe_in_conversation(page, iframe_loc)
        await page.wait_for_timeout(300)

        handle = await iframe_loc.element_handle()
        if handle is None:
            raise RuntimeError("Email iframe handle not available.")
        frame = await handle.content_frame()
        if frame is None:
            raise RuntimeError("Email iframe content not loaded.")

        best_text = ""
        best_html = ""
        body = frame.locator("body")

        scroll_iframe_js = """() => {
          const nodes = [document.documentElement, document.body,
            ...document.body.querySelectorAll('*')];
          for (const node of nodes) {
            try {
              if (node.scrollHeight > node.clientHeight + 5) {
                node.scrollTop = Math.min(node.scrollTop + 450, node.scrollHeight);
              }
            } catch (e) {}
          }
        }"""

        scroll_to_bottom_js = """() => {
          const nodes = [document.documentElement, document.body,
            ...document.body.querySelectorAll('*')];
          for (const node of nodes) {
            try {
              if (node.scrollHeight > node.clientHeight + 5) {
                node.scrollTop = node.scrollHeight;
              }
            } catch (e) {}
          }
        }"""

        conversation = page.locator('[data-testid="conversation-view"]').first

        for _ in range(60):
            if await conversation.count() > 0:
                await conversation.evaluate(
                    """el => {
                      el.scrollTop = Math.min(el.scrollTop + 400, el.scrollHeight);
                    }"""
                )
            await body.evaluate(scroll_iframe_js)
            await self._wheel_scroll_locator(page, iframe_loc, 2)
            await page.wait_for_timeout(200)

            frame_text = (await body.evaluate("el => (el.textContent || '').trim()")).strip()
            frame_html = (await body.inner_html()).strip()
            if len(frame_text) > len(best_text):
                best_text = frame_text
                best_html = frame_html
            if re.search(r"Cod de contesta.{1,3}:", frame_text, re.I) and re.search(
                r"rewardcloud|vizualiza|Redemption ID", frame_text + " " + frame_html, re.I
            ):
                return frame_text, frame_html

        await self._wheel_scroll_locator(page, iframe_loc, 30)
        for _ in range(5):
            if await conversation.count() > 0:
                await conversation.evaluate("el => { el.scrollTop = el.scrollHeight; }")
            await body.evaluate(scroll_to_bottom_js)
            await page.wait_for_timeout(300)

        frame_text = (await body.evaluate("el => (el.textContent || '').trim()")).strip()
        frame_html = (await body.inner_html()).strip()
        return frame_text or best_text, frame_html or best_html

    async def _scroll_message_view_until_voucher(
        self, page: Page, iframe_loc: Locator
    ) -> tuple[str, str]:
        """Backward-compatible alias for iframe scrolling."""
        return await self._scroll_iframe_until_voucher(page, iframe_loc)

    async def _scroll_frame_until_voucher(self, page: Page, frame) -> tuple[str, str]:
        """Scroll an email iframe until voucher fields appear, then return text + HTML."""
        body = frame.locator("body")
        best_text = ""
        best_html = ""
        for _ in range(60):
            frame_text = (await body.evaluate("el => (el.textContent || '').trim()")).strip()
            frame_html = (await body.inner_html()).strip()
            if len(frame_text) > len(best_text):
                best_text = frame_text
                best_html = frame_html
            if re.search(r"Cod de contesta.{1,3}:", frame_text, re.I) and re.search(
                r"rewardcloud|vizualiza|Redemption ID", frame_text + frame_html, re.I
            ):
                return frame_text, frame_html
            await body.evaluate(
                """el => {
                    const nodes = [el, ...el.querySelectorAll('*')];
                    for (const node of nodes) {
                      try {
                        if (node.scrollHeight > node.clientHeight + 5) {
                          node.scrollTop = Math.min(
                            node.scrollTop + 450,
                            node.scrollHeight
                          );
                        }
                      } catch (e) {}
                    }
                    document.documentElement.scrollTop += 450;
                }"""
            )
            await page.wait_for_timeout(200)

        return await self._scroll_frame_body(page, frame)

    async def _scroll_frame_body(self, page: Page, frame) -> tuple[str, str]:
        """Scroll an email iframe to the bottom and return full text + HTML."""
        body = frame.locator("body")
        for _ in range(10):
            await body.evaluate(
                """el => {
                    el.scrollTop = el.scrollHeight;
                    document.documentElement.scrollTop =
                        document.documentElement.scrollHeight;
                    el.querySelectorAll('*').forEach(node => {
                        if (node.scrollHeight > node.clientHeight + 5) {
                            node.scrollTop = node.scrollHeight;
                        }
                    });
                }"""
            )
            await page.wait_for_timeout(300)
        frame_text = (await body.evaluate("el => (el.textContent || '').trim()")).strip()
        frame_html = (await body.inner_html()).strip()
        return frame_text, frame_html

    async def _read_body_parts_from_message_view(
        self, page: Page, body_loc: Locator
    ) -> tuple[str, str]:
        """Read scrolled iframe content from one message-view body block."""
        if await body_loc.count() == 0:
            raise RuntimeError("Message body block not found.")

        await body_loc.scroll_into_view_if_needed(timeout=10_000)
        iframe = body_loc.locator("iframe").first
        if await iframe.count() > 0:
            handle = await iframe.element_handle()
            if handle is not None:
                frame = await handle.content_frame()
                if frame is not None:
                    return await self._scroll_frame_body(page, frame)

        raise RuntimeError("No iframe found inside message body block.")

    async def _email_iframe_frames(self, page: Page) -> list:
        """Return email content frames from the open conversation."""
        frames = []
        iframes = page.locator(
            '[data-testid="conversation-view"] [data-testid="message-view:body"] iframe, '
            '[data-testid="message-view:body"] iframe, iframe'
        )
        count = await iframes.count()
        for index in range(count):
            try:
                handle = await iframes.nth(index).element_handle()
                if handle is None:
                    continue
                frame = await handle.content_frame()
                if frame is not None:
                    frames.append(frame)
            except Exception:
                continue

        if frames:
            return frames

        for frame in page.frames:
            if frame != page.main_frame:
                frames.append(frame)
        return frames

    async def _read_active_iframe_parts(self, page: Page) -> tuple[str, str]:
        """Read the currently visible email iframe after scrolling to the voucher."""
        frames = await self._email_iframe_frames(page)
        if not frames:
            raise RuntimeError("No email iframe found.")

        best_text = ""
        best_html = ""
        for frame in frames:
            try:
                frame_text, frame_html = await self._scroll_frame_until_voucher(page, frame)
                if len(frame_text) > len(best_text):
                    best_text = frame_text
                    best_html = frame_html
            except Exception:
                continue

        if best_text or best_html:
            self._log("Email body preview: %s..." % (best_text[:120] or best_html[:120]))
            return best_text, best_html

        raise RuntimeError("Could not read email iframe content.")

    def _redemption_id(self, text: str) -> str:
        return extract_voucher_order_fields(text).get("redemption_id", "")

    async def _expand_conversation_headers(self, page: Page, headers: Locator) -> None:
        header_count = await headers.count()
        for index in range(header_count):
            try:
                header = headers.nth(index)
                await header.scroll_into_view_if_needed(timeout=10_000)
                await header.click(timeout=10_000)
                await page.wait_for_timeout(600)
            except Exception:
                continue

    async def _read_libra_voucher_thread(
        self,
        page: Page,
        since: Optional[datetime] = None,
    ) -> list[LibraVoucherDetail]:
        row = await self._find_message_by_subject(page, self.LIBRA_VOUCHER_SUBJECT)
        subject = await self._row_subject(row)
        await row.click()
        await page.wait_for_selector(
            '[data-testid="conversation-header"], [data-testid="message-header"], iframe',
            timeout=60_000,
        )
        self._log("Opened voucher thread: %s" % subject)

        headers = await self._conversation_headers(page)
        header_count = await headers.count()
        self._log("Reading %s message(s) one by one..." % header_count)

        self._log("Expanding all messages in thread...")
        await self._expand_conversation_headers(page, headers)
        await page.wait_for_timeout(1200)
        try:
            iframe_count = await (await self._conversation_iframes(page)).count()
            self._log("Found %s message iframe(s)." % iframe_count)
        except RuntimeError:
            iframe_count = 0
            self._log("No message iframes visible yet.")

        details: list[LibraVoucherDetail] = []
        seen: set[tuple[str, str]] = set()
        seen_redemption_ids: set[str] = set()

        for index in range(header_count):
            header = headers.nth(index)
            try:
                iframe_loc = await self._iframe_for_message(page, headers, index)
                await page.wait_for_selector("iframe", timeout=30_000)
            except Exception as exc:
                self._log("Could not open message %s: %s" % (index + 1, exc))
                await self._screenshot(page, "voucher_msg_%02d_open_fail" % (index + 1))
                continue

            received_at, received_at_dt = await self._header_received_at(header)
            if since is not None and received_at_dt is not None and received_at_dt <= since:
                self._log(
                    "Skipping message %s at %s (not newer than %s)"
                    % (index + 1, received_at_dt, since)
                )
                continue

            try:
                text, html = await self._scroll_iframe_until_voucher(page, iframe_loc)
                redemption_id = self._redemption_id(text)
                if redemption_id and redemption_id in seen_redemption_ids:
                    self._log(
                        "Message %s still shows Redemption ID %s; retrying scroll..."
                        % (index + 1, redemption_id)
                    )
                    iframe_loc = await self._iframe_for_message(page, headers, index)
                    text, html = await self._scroll_iframe_until_voucher(page, iframe_loc)
                    redemption_id = self._redemption_id(text)

                pairs = extract_all_voucher_url_and_code_pairs(text, html)
                if not pairs:
                    raise ValueError("No voucher url/code in message %s." % (index + 1))
                order = extract_voucher_order_fields(text, html)
            except (RuntimeError, ValueError) as exc:
                await self._screenshot(page, "voucher_msg_%02d_missing" % (index + 1))
                self._log("Message %s had no url/code: %s" % (index + 1, exc))
                continue

            await self._screenshot(page, "voucher_msg_%02d" % (index + 1))
            added = False
            for url, code in pairs:
                pair = (url, code)
                if pair in seen:
                    self._log("Skipping duplicate pair in message %s" % (index + 1))
                    continue
                seen.add(pair)
                if redemption_id:
                    seen_redemption_ids.add(redemption_id)
                added = True
                details.append(
                    LibraVoucherDetail(
                        url=url,
                        code=code,
                        received_at=received_at,
                        comanda_nr=order.get("comanda_nr", ""),
                        redemption_id=order.get("redemption_id", "") or redemption_id,
                        comanda_id=order.get("comanda_id", ""),
                        cantitate=order.get("cantitate", ""),
                        puncte=order.get("puncte", ""),
                        subtotal=order.get("subtotal", ""),
                        total=order.get("total", ""),
                        received_at_dt=received_at_dt,
                    )
                )
                self._log(
                    "  extracted comanda#=%s redemption_id=%s code=%s"
                    % (
                        order.get("comanda_nr", "") or "?",
                        order.get("redemption_id", "") or redemption_id or "?",
                        code,
                    )
                )
            if not added:
                self._log("Message %s did not add new voucher pairs." % (index + 1))

        if not details:
            raise RuntimeError(
                "No voucher url/code pairs found in thread %s." % subject
            )
        return details

    async def _read_message_body_parts(self, page: Page) -> tuple[str, str]:
        """Read message body text and HTML from the open message view."""
        await page.wait_for_selector(
            '[data-testid="message-view:body"], .message-content, article, iframe',
            timeout=60_000,
        )

        best_text = ""
        best_html = ""
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                frame_text, frame_html = await self._scroll_frame_body(page, frame)
                if len(frame_text) > len(best_text):
                    best_text = frame_text
                    best_html = frame_html
            except Exception:
                continue

        texts: list[str] = [best_text] if best_text else []
        htmls: list[str] = [best_html] if best_html else []

        for selector in (
            '[data-testid="message-view:body"]',
            ".message-content",
            "article",
        ):
            body = page.locator(selector)
            if await body.count() > 0:
                target = body.first
                await target.scroll_into_view_if_needed()
                outer_text = (await target.inner_text()).strip()
                if outer_text and outer_text not in texts:
                    texts.append(outer_text)

        text = "\n".join(dict.fromkeys(texts)).strip()
        html = "\n".join(dict.fromkeys(htmls)).strip()
        if text or html:
            self._log("Email body preview: %s..." % (text[:120] or html[:120]))
            return text, html

        raise RuntimeError("Could not read email body.")

    async def _conversation_headers(self, page: Page) -> Locator:
        """Return locators for message headers in the open conversation."""
        for selector in (
            '[data-testid="message-header"]',
            '[data-shortcut-target="message-header"]',
            ".message-header",
        ):
            headers = page.locator(selector)
            if await headers.count() > 0:
                return headers
        raise RuntimeError("No conversation message headers found.")

    async def _header_received_at(self, header: Locator) -> tuple[str, Optional[datetime]]:
        time_locator = header.locator("time")
        if await time_locator.count() == 0:
            time_locator = header.locator("xpath=ancestor::*[1]//time")
        if await time_locator.count() == 0:
            return "", None

        raw = (
            await time_locator.first.get_attribute("datetime")
            or await time_locator.first.inner_text()
        ).strip()
        return raw, parse_message_datetime(raw)

    async def _read_libra_one_time_code(self, page: Page) -> LibraOneTimeCode:
        row = await self._find_message_by_subject(page, self.LIBRA_ONE_TIME_CODE_SUBJECT)
        subject = await self._row_subject(row)
        received_at = await self._row_received_at(row)

        await row.click()
        body = await self._read_message_body(page)
        code = extract_one_time_code(body)

        return LibraOneTimeCode(
            code=code,
            subject=subject,
            received_at=received_at,
        )

    async def _read_last_email(self, page: Page) -> ProtonEmailMessage:
        await self._wait_for_message_list(page)
        await self._screenshot(page, "message_list")

        subject_locator = await self._first_message_subject(page)

        sender = ""
        for sender_selector in (
            '[data-testid="message-column:sender-address"]',
            ".item-senders [data-testid='message-column:sender-address']",
            ".item-senders",
        ):
            sender_locator = page.locator(sender_selector).first
            if await sender_locator.count() > 0:
                sender = (
                    await sender_locator.get_attribute("title")
                    or await sender_locator.inner_text()
                )
                if sender.strip():
                    break

        subject = (
            await subject_locator.get_attribute("title")
            or await subject_locator.inner_text()
        )

        received_at = ""
        time_locator = subject_locator.locator(
            "xpath=ancestor::*[contains(@class, 'item')][1]//time"
        )
        if await time_locator.count() > 0:
            received_at = (
                await time_locator.first.get_attribute("datetime")
                or await time_locator.first.inner_text()
            )

        await subject_locator.click()
        snippet = await self._read_message_body(page)

        return ProtonEmailMessage(
            sender=sender.strip(),
            subject=subject.strip(),
            received_at=received_at.strip(),
            snippet=snippet[:500],
        )
