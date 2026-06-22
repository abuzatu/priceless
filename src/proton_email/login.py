"""Log in to Proton Mail with Playwright and read inbox messages."""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
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
        """
        load_dotenv()

        self.email_address = email_address or os.getenv("PROTON_EMAIL_ADDRESS_01", "")
        self.password = password or os.getenv("PROTON_EMAIL_PASSWORD_01", "")
        self.headless = headless
        self.verbose = verbose
        self.debug = debug
        self.debug_version = debug_version
        self.slow_mo = 300 if debug and slow_mo == 0 else slow_mo
        workdir = Path(os.getenv("WORKDIR", Path.cwd()))
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
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
        )
        self._page = await self._context.new_page()
        await self._page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        self._log("Signing in to Proton...")
        await self._authenticate(self._page)
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

        try:
            await page.wait_for_url(self.LOGGED_IN_URL, timeout=120_000)
        except Exception as exc:
            await self._screenshot(page, "login_timeout")
            if await self._two_factor_prompt_visible(page):
                raise RuntimeError(
                    "Proton Mail requested 2FA. Disable 2FA for this account or "
                    "complete a manual browser login once and reuse storage state."
                ) from exc
            if await self._login_error_visible(page):
                raise RuntimeError(
                    "Proton Mail login failed. Check PROTON_EMAIL_ADDRESS_01 and "
                    "PROTON_EMAIL_PASSWORD_01 in .env."
                ) from exc
            raise RuntimeError(
                "Proton Mail login timed out at %s. "
                "Approve the sign-in alert on your phone if prompted."
                % page.url
            ) from exc

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
        await page.wait_for_selector(
            '[data-testid="message-view:body"], .message-content, article, iframe',
            timeout=60_000,
        )

        texts: list[str] = []

        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                frame_text = (await frame.locator("body").inner_text()).strip()
                if frame_text:
                    texts.append(frame_text)
            except Exception:
                continue

        for selector in (
            '[data-testid="message-view:body"] iframe',
            ".message-content iframe",
            "article iframe",
        ):
            iframe = page.frame_locator(selector).first
            try:
                frame_text = (await iframe.locator("body").inner_text()).strip()
                if frame_text:
                    texts.append(frame_text)
            except Exception:
                continue

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
                if outer_text:
                    texts.append(outer_text)

        combined = "\n".join(dict.fromkeys(texts))
        if combined.strip():
            self._log("Email body preview: %s..." % combined.strip()[:120])
            return combined.strip()

        raise RuntimeError("Could not read email body.")

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
