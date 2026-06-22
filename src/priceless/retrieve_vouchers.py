"""Retrieve eMAG gift-card codes from Reward Cloud redemption pages."""

from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import pandas as pd
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
from proton_email.login import LibraVoucherDetail, parse_message_datetime


@dataclass(frozen=True)
class GiftCardVoucher:
    """One gift card shown on the Reward Cloud order-details page."""

    card_number: int
    product_label: str
    voucher_id: str
    voucher_code: str
    expiry_date: str


@dataclass(frozen=True)
class RetrievedVouchersResult:
    """Gift cards retrieved from a Libra e-voucher redemption link."""

    vouchers: list[GiftCardVoucher]
    status_message: str
    page_url: str
    source: LibraVoucherDetail


VOUCHER_EXCEL_COLUMNS = (
    "voucher ID",
    "voucher code",
    "expiry date",
    "value in RON",
    "Award date",
    "Folosit data",
    "Folosit",
)


def parse_ron_value(product_label: str) -> float:
    """Extract the numeric RON amount from a product label."""
    match = re.search(r"([\d]+(?:[.,]\d+)?)\s*RON", product_label, re.I)
    if not match:
        return 0.0
    return float(match.group(1).replace(",", "."))


def award_date_from_voucher(voucher: LibraVoucherDetail) -> str:
    """Format Libra email received time as YYYY-MM-DD."""
    if voucher.received_at_dt is not None:
        return voucher.received_at_dt.strftime("%Y-%m-%d")
    parsed = parse_message_datetime(voucher.received_at)
    if parsed is not None:
        return parsed.strftime("%Y-%m-%d")
    return ""


def vouchers_result_to_rows(result: RetrievedVouchersResult) -> list[dict[str, Union[str, float, int]]]:
    """Build Excel rows from a retrieval result."""
    award_date = award_date_from_voucher(result.source)
    rows: list[dict[str, Union[str, float, int]]] = []
    for card in result.vouchers:
        rows.append(
            {
                "voucher ID": card.voucher_id,
                "voucher code": card.voucher_code,
                "expiry date": card.expiry_date,
                "value in RON": parse_ron_value(card.product_label),
                "Award date": award_date,
                "Folosit data": ".",
                "Folosit": 0,
            }
        )
    return rows


def validate_voucher_count(result: RetrievedVouchersResult) -> None:
    """Raise if retrieved gift-card count does not match email `cantitate`."""
    expected_raw = result.source.cantitate.strip()
    if not expected_raw:
        return
    try:
        expected_count = int(expected_raw)
    except ValueError:
        return
    actual_count = len(result.vouchers)
    if actual_count != expected_count:
        raise ValueError(
            "Expected %s gift card(s) (cantitate=%s), got %s."
            % (expected_count, expected_raw, actual_count)
        )


def order_timestamp_from_voucher(voucher: LibraVoucherDetail) -> str:
    """Format Libra email received time as YYYY-MM-DD-HH-MM-SS."""
    if voucher.received_at_dt is not None:
        return voucher.received_at_dt.strftime("%Y-%m-%d-%H-%M-%S")
    parsed = parse_message_datetime(voucher.received_at)
    if parsed is not None:
        return parsed.strftime("%Y-%m-%d-%H-%M-%S")
    return "unknown-datetime"


def voucher_excel_filename(voucher: LibraVoucherDetail, prefix: str) -> str:
    """Build `{prefix}_{received_at}_{comanda_id}_{redemption_id}.xlsx`.

    One order (comanda) can have several redemptions; including both avoids
    overwriting Excel files when multiple line items share the same order number.
    """
    timestamp = order_timestamp_from_voucher(voucher)
    order_key = (
        (voucher.comanda_id or "").strip()
        or (voucher.comanda_nr or "").strip()
        or "unknown"
    )
    redemption_id = (voucher.redemption_id or "").strip()
    safe_prefix = re.sub(r"[^\w\-]+", "_", prefix).strip("_") or "vouchers"
    safe_order_key = order_key.replace("/", "-")
    if redemption_id:
        return "%s_%s_%s_%s.xlsx" % (
            safe_prefix,
            timestamp,
            safe_order_key,
            redemption_id,
        )
    return "%s_%s_%s.xlsx" % (safe_prefix, timestamp, safe_order_key)


def combined_voucher_excel_filename(
    prefix: str,
    results: list[RetrievedVouchersResult],
    *,
    run_at: Optional[datetime] = None,
) -> str:
    """Build `{prefix}_combined_{run_at}_{from}_to_{to}.xlsx`."""
    safe_prefix = re.sub(r"[^\w\-]+", "_", prefix).strip("_") or "vouchers"
    run_timestamp = (run_at or datetime.now()).strftime("%Y-%m-%d-%H-%M-%S")
    timestamps = sorted(order_timestamp_from_voucher(result.source) for result in results)
    if not timestamps:
        return "%s_combined_%s.xlsx" % (safe_prefix, run_timestamp)
    if timestamps[0] == timestamps[-1]:
        return "%s_combined_%s_%s.xlsx" % (safe_prefix, run_timestamp, timestamps[0])
    return "%s_combined_%s_%s_to_%s.xlsx" % (
        safe_prefix,
        run_timestamp,
        timestamps[0],
        timestamps[-1],
    )


def combined_voucher_excel_path(
    prefix: str,
    results: list[RetrievedVouchersResult],
    output_dir: Union[str, Path],
    *,
    run_at: Optional[datetime] = None,
) -> Path:
    """Return full path for a combined export of several retrieval results."""
    return Path(output_dir) / combined_voucher_excel_filename(
        prefix, results, run_at=run_at
    )


def voucher_excel_path(
    voucher: LibraVoucherDetail,
    prefix: str,
    output_dir: Union[str, Path],
) -> Path:
    """Return full path under `output_dir` for one voucher export."""
    return Path(output_dir) / voucher_excel_filename(voucher, prefix)


def default_voucher_output_dir() -> Path:
    workdir = Path(os.getenv("WORKDIR", Path.cwd()))
    return workdir / "data" / "priceless_folder"


def export_vouchers_to_excel(
    result: RetrievedVouchersResult,
    output_path: Optional[Union[str, Path]] = None,
    *,
    prefix: str = "vouchers",
    output_dir: Optional[Union[str, Path]] = None,
    validate_count: bool = True,
) -> Path:
    """Write retrieved gift cards to an Excel file."""
    if validate_count:
        validate_voucher_count(result)

    if output_path is None:
        base_dir = Path(output_dir) if output_dir is not None else default_voucher_output_dir()
        path = voucher_excel_path(result.source, prefix, base_dir)
    else:
        path = Path(output_path)

    path.parent.mkdir(parents=True, exist_ok=True)
    rows = vouchers_result_to_rows(result)
    dataframe = pd.DataFrame(rows, columns=list(VOUCHER_EXCEL_COLUMNS))
    dataframe.to_excel(path, index=False)
    return path


def export_combined_vouchers_to_excel(
    results: list[RetrievedVouchersResult],
    output_path: Optional[Union[str, Path]] = None,
    *,
    prefix: str = "vouchers",
    output_dir: Optional[Union[str, Path]] = None,
    run_at: Optional[datetime] = None,
) -> Path:
    """Write gift cards from several retrievals into one Excel file."""
    if not results:
        raise ValueError("No voucher results to export.")

    run_at = run_at or datetime.now()
    base_dir = Path(output_dir) if output_dir is not None else default_voucher_output_dir()
    if output_path is None:
        path = combined_voucher_excel_path(prefix, results, base_dir, run_at=run_at)
    else:
        path = Path(output_path)

    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Union[str, float, int]]] = []
    for result in results:
        rows.extend(vouchers_result_to_rows(result))
    dataframe = pd.DataFrame(rows, columns=list(VOUCHER_EXCEL_COLUMNS))
    dataframe.to_excel(path, index=False)
    return path


def parse_gift_cards_from_text(text: str) -> list[GiftCardVoucher]:
    """Parse gift-card rows from Reward Cloud page-3 body text."""
    normalized = re.sub(r"\s+", " ", text).strip()
    pattern = re.compile(
        r"Card (\d+) - (.+?) Voucher ID:\s*(\d+)\s+"
        r"Voucher Code:\s*([\d-]+)\s+Expiry Date:\s*(\d{4}-\d{2}-\d{2})",
        re.I,
    )
    cards: list[GiftCardVoucher] = []
    for match in pattern.finditer(normalized):
        cards.append(
            GiftCardVoucher(
                card_number=int(match.group(1)),
                product_label=match.group(2).strip(),
                voucher_id=match.group(3),
                voucher_code=match.group(4),
                expiry_date=match.group(5),
            )
        )
    return cards


def _status_message(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    match = re.search(
        r"(Detaliile comenzii au fost preluate|Cod de contesta.{1,3} aceptat)",
        normalized,
        re.I,
    )
    return match.group(1) if match else ""


class RetrieveVouchers:
    """Open a Reward Cloud link and read gift-card voucher codes."""

    PAGE_3_PATH = re.compile(r"/page-3", re.I)
    PAGE_2_PATH = re.compile(r"/page-2", re.I)
    CLAIM_READY_TIMEOUT_MS = 120_000
    PAGE_3_TIMEOUT_MS = 120_000

    def __init__(
        self,
        voucher: LibraVoucherDetail,
        *,
        prefix: str = "vouchers",
        output_dir: Optional[Union[str, Path]] = None,
        headless: bool = True,
        verbose: bool = True,
        debug: bool = False,
        screenshot_dir: Optional[str] = None,
        debug_version: str = "v01",
        slow_mo: int = 0,
    ) -> None:
        """Prepare browser settings for one Libra voucher redemption.

        Args:
            voucher: Email detail with `url` (Reward Cloud link) and `code`.
            prefix: Excel filename prefix, e.g.
                `adi` -> adi_2026-06-21-04-49-00_979182-1_1008541841.xlsx.
            output_dir: Folder for Excel output (default: data/priceless_folder).
            debug: Save step screenshots under `data/debug/priceless_retrieve_vouchers`.
            debug_version: Prefix for screenshots, e.g. v01 -> v01_01_code_page.png.
        """
        self.voucher = voucher
        self.prefix = prefix
        self.output_dir = (
            Path(output_dir) if output_dir is not None else default_voucher_output_dir()
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._last_excel_path: Optional[Path] = None
        self.headless = headless
        self.verbose = verbose
        self.debug = debug
        self.debug_version = debug_version
        self.slow_mo = 300 if debug and slow_mo == 0 else slow_mo
        workdir = Path(os.getenv("WORKDIR", Path.cwd()))
        self.screenshot_dir = (
            Path(screenshot_dir)
            if screenshot_dir
            else (
                workdir / "data" / "debug" / "priceless_retrieve_vouchers" if debug else None
            )
        )
        if self.screenshot_dir is not None:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._screenshot_step = 0

        if not voucher.url or not voucher.code:
            raise ValueError("LibraVoucherDetail must include url and code.")

    async def get_vouchers(self) -> RetrievedVouchersResult:
        """Submit the contestation code and return gift-card voucher details."""
        try:
            await self._launch_browser()
            result = await self._redeem_voucher(self._page)
            validate_voucher_count(result)
            await self._screenshot(self._page, "vouchers_retrieved")
            self._log("Retrieved %s gift card(s)." % len(result.vouchers))
            for card in result.vouchers:
                self._log(
                    "  card %s id=%s code=%s expires=%s (%s)"
                    % (
                        card.card_number,
                        card.voucher_id,
                        card.voucher_code,
                        card.expiry_date,
                        card.product_label,
                    )
                )
            excel_path = export_vouchers_to_excel(
                result,
                prefix=self.prefix,
                output_dir=self.output_dir,
                validate_count=False,
            )
            self._last_excel_path = excel_path
            self._log("Excel saved: %s" % excel_path)
            return result
        except Exception as exc:
            await self._handle_error(exc)
            raise

    def get_vouchers_sync(self) -> RetrievedVouchersResult:
        """Blocking version of `get_vouchers`."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.get_vouchers())
        raise RuntimeError(
            "Use `await retriever.get_vouchers()` in Jupyter/async contexts."
        )

    def excel_output_path(self) -> Path:
        """Resolved Excel path for this voucher (`prefix_date_comanda_id.xlsx`)."""
        return voucher_excel_path(self.voucher, self.prefix, self.output_dir)

    async def get_vouchers_and_export(self) -> tuple[RetrievedVouchersResult, Path]:
        """Retrieve gift cards and return `(result, excel_path)`."""
        result = await self.get_vouchers()
        if self._last_excel_path is None:
            raise RuntimeError("Excel export did not run.")
        return result, self._last_excel_path

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

    async def _launch_browser(self) -> None:
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

    async def _redeem_voucher(self, page: Page) -> RetrievedVouchersResult:
        self._log("Opening %s" % self.voucher.url)
        await page.goto(self.voucher.url, wait_until="domcontentloaded", timeout=60_000)
        await self._screenshot(page, "code_page")

        code_input = page.locator('input[name="code"]')
        await code_input.wait_for(state="visible", timeout=30_000)
        await code_input.fill(self.voucher.code)
        await self._screenshot(page, "code_filled")

        continue_button = page.locator('button:has-text("Continue")')
        await continue_button.click()
        await self._wait_for_post_continue(page)
        await self._screenshot(page, "after_continue")

        if self.PAGE_2_PATH.search(page.url):
            self._log("Code accepted on page-2; waiting to claim gift...")
            await self._wait_for_claim_ready(page)
            await self._screenshot(page, "claim_ready")
            claim_button = page.locator(
                'button:has-text("Claim your Gift"), button:has-text("Claim")'
            )
            await claim_button.first.click()
            self._log("Clicked Claim your Gift; waiting for voucher details...")
            await self._screenshot(page, "after_claim_click")

        body_text = await self._wait_for_gift_cards_page(page)
        await self._screenshot(page, "vouchers_loaded")

        vouchers = parse_gift_cards_from_text(body_text)
        if not vouchers:
            raise RuntimeError(
                "No gift cards found on page-3. Body preview: %s"
                % (body_text[:400] or "<empty>")
            )

        return RetrievedVouchersResult(
            vouchers=vouchers,
            status_message=_status_message(body_text),
            page_url=page.url,
            source=self.voucher,
        )

    async def _wait_for_post_continue(self, page: Page) -> None:
        """Wait until Reward Cloud shows page-2 or page-3 after code submit."""
        deadline = time.monotonic() + self.PAGE_3_TIMEOUT_MS / 1000
        while time.monotonic() < deadline:
            if self.PAGE_3_PATH.search(page.url):
                body_text = await page.locator("body").inner_text()
                if parse_gift_cards_from_text(body_text):
                    return
            if self.PAGE_2_PATH.search(page.url):
                return
            await page.wait_for_timeout(1000)
        raise RuntimeError(
            "Timed out waiting for Reward Cloud page-2/page-3 after Continue. url=%s"
            % page.url
        )

    async def _wait_for_claim_ready(self, page: Page) -> None:
        """Wait until page-2 spinner finishes and Claim is clickable."""
        claim_button = page.locator(
            'button:has-text("Claim your Gift"), button:has-text("Claim")'
        )
        await claim_button.first.wait_for(state="visible", timeout=30_000)
        deadline = time.monotonic() + self.CLAIM_READY_TIMEOUT_MS / 1000
        while time.monotonic() < deadline:
            enabled = await claim_button.first.is_enabled()
            spinner = page.locator(
                '[class*="spinner"], [class*="Spinner"], '
                '[class*="loading"], [class*="Loading"], '
                '[role="progressbar"]'
            )
            spinner_visible = False
            if await spinner.count() > 0:
                spinner_visible = await spinner.first.is_visible()
            if enabled and not spinner_visible:
                await page.wait_for_timeout(500)
                return
            await page.wait_for_timeout(1000)
        self._log("Claim button wait timed out; attempting click anyway.")

    async def _wait_for_gift_cards_page(self, page: Page) -> str:
        """Wait until voucher cards are visible on page-3."""
        deadline = time.monotonic() + self.PAGE_3_TIMEOUT_MS / 1000
        last_body = ""
        while time.monotonic() < deadline:
            last_body = await page.locator("body").inner_text()
            if parse_gift_cards_from_text(last_body):
                return last_body
            await page.wait_for_timeout(2000)
        raise RuntimeError(
            "Timed out waiting for gift-card details on page-3. "
            "url=%s body=%s" % (page.url, last_body[:300])
        )

    async def _handle_error(self, exc: Exception) -> None:
        if self._page is not None:
            path = await self._screenshot(self._page, "error")
            if path is not None:
                raise RuntimeError("%s (screenshot: %s)" % (exc, path)) from exc
        if not self.debug:
            await self.close()

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


EXAMPLE_LIBRA_VOUCHER = LibraVoucherDetail(
    url="https://rl.rewardcloud.io/index/676c450d-f1d5-4a33-9ff3-302dc6356c90",
    code="7714061d-cf10-4303-b6b2-516c1b831204",
    received_at="Sunday, 21 June 2026 at 4:49 AM",
    comanda_nr="979182",
    redemption_id="1008541841",
    comanda_id="979182-1",
    cantitate="3",
    puncte="1.290",
    subtotal="3.870",
    total="3.870",
    received_at_dt=datetime(2026, 6, 21, 4, 49),
)
