"""Playwright browser automation for capturing page resources."""

import asyncio
from dataclasses import dataclass

from playwright.async_api import Page, Response, async_playwright

from .utils import should_skip_url


@dataclass
class CapturedResource:
    """A captured network resource."""

    url: str
    content_type: str
    body: bytes


async def capture_page_resources(
    url: str,
    wait_time: int = 0,
    on_status: callable = None,
) -> list[CapturedResource]:
    """Load a page and capture all network resources.

    Args:
        url: URL of the page to load.
        wait_time: Additional seconds to wait after page load for JS content.
        on_status: Optional callback for status updates (receives string message).

    Returns:
        List of captured resources with their content.

    Raises:
        Exception: If browser launch or page load fails.
    """
    captured: list[CapturedResource] = []
    pending_responses: list[Response] = []

    def _status(msg: str) -> None:
        if on_status:
            on_status(msg)

    async def handle_response(response: Response) -> None:
        """Collect successful responses for later processing."""
        # Skip non-successful responses
        if not response.ok:
            return

        # Skip URLs we can't/shouldn't download
        if should_skip_url(response.url):
            return

        pending_responses.append(response)

    async with async_playwright() as p:
        _status("Launching browser...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            # Accept all content types
            accept_downloads=True,
            # Bypass some security for resource capture
            bypass_csp=True,
        )
        page = await context.new_page()

        # Register response handler BEFORE navigation
        page.on("response", handle_response)

        _status(f"Navigating to {url}...")
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
        except Exception as e:
            await browser.close()
            raise RuntimeError(f"Failed to load page: {e}") from e

        # Additional wait time for SPAs/lazy-loaded content
        if wait_time > 0:
            _status(f"Waiting {wait_time}s for additional content...")
            await asyncio.sleep(wait_time)

        # Process all collected responses
        _status(f"Processing {len(pending_responses)} responses...")
        for response in pending_responses:
            try:
                body = await response.body()
                content_type = response.headers.get("content-type", "")
                captured.append(CapturedResource(
                    url=response.url,
                    content_type=content_type,
                    body=body,
                ))
            except Exception:
                # Response body may no longer be available (e.g., redirects)
                # Just skip it
                pass

        await browser.close()

    return captured
