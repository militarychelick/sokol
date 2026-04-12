"""Browser automation - DOM-based browser automation using Playwright."""

from typing import Optional, Dict, Any
import asyncio

from sokol.observability.logging import get_logger

logger = get_logger("sokol.action.browser_automation")


class BrowserExecutor:
    """
    Browser automation using Playwright.

    Primary method for browser tasks - uses DOM, not mouse/OCR.
    """

    def __init__(self) -> None:
        self._available = self._check_availability()
        self._browser: Optional[Any] = None
        self._page: Optional[Any] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        logger.info_data(
            "Browser executor initialized",
            {"available": self._available},
        )

    def _check_availability(self) -> bool:
        """Check if Playwright is available."""
        try:
            from playwright.async_api import async_playwright
            return True
        except ImportError:
            return False

    def is_available(self) -> bool:
        """Check if browser executor is available."""
        return self._available

    async def _ensure_browser(self) -> None:
        """Ensure browser is started."""
        if self._browser is None:
            from playwright.async_api import async_playwright

            playwright = await async_playwright().start()
            self._browser = await playwright.chromium.launch(headless=False)
            self._page = await self._browser.new_page()

    async def _close_browser(self) -> None:
        """Close browser."""
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._page = None

    def execute(
        self,
        action_type: str,
        target: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute browser action.

        Args:
            action_type: Type of action (click, type, select, etc.)
            target: Target selector or URL
            params: Additional parameters

        Returns:
            Dict with success status and result data
        """
        params = params or {}

        # Run async action in event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                self._execute_async(action_type, target, params)
            )
            return result
        except Exception as e:
            logger.error_data(
                "Browser execution failed",
                {"action": action_type, "target": target, "error": str(e)},
            )
            return {
                "success": False,
                "error": str(e),
            }

    async def _execute_async(
        self,
        action_type: str,
        target: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute browser action asynchronously."""
        await self._ensure_browser()

        try:
            if action_type == "navigate":
                return await self._navigate(target, params)
            elif action_type == "click":
                return await self._click(target, params)
            elif action_type == "type":
                return await self._type(target, params)
            elif action_type == "select":
                return await self._select(target, params)
            elif action_type == "get_text":
                return await self._get_text(target, params)
            elif action_type == "wait":
                return await self._wait(target, params)
            elif action_type == "screenshot":
                return await self._screenshot(target, params)
            else:
                return {
                    "success": False,
                    "error": f"Unknown action type: {action_type}",
                }
        except Exception as e:
            logger.error_data(
                "Browser async execution failed",
                {"action": action_type, "target": target, "error": str(e)},
            )
            return {
                "success": False,
                "error": str(e),
            }

    async def _navigate(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Navigate to URL."""
        await self._page.goto(url)
        return {"success": True, "url": url}

    async def _click(self, selector: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Click on element by selector."""
        await self._page.click(selector)
        return {"success": True, "selector": selector}

    async def _type(self, selector: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Type text into element by selector."""
        text = params.get("text", "")
        await self._page.fill(selector, text)
        return {"success": True, "selector": selector, "text": text}

    async def _select(self, selector: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Select option from dropdown."""
        value = params.get("value", "")
        await self._page.select_option(selector, value)
        return {"success": True, "selector": selector, "value": value}

    async def _get_text(self, selector: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get text from element by selector."""
        text = await self._page.inner_text(selector)
        return {"success": True, "text": text, "selector": selector}

    async def _wait(self, selector: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Wait for element to appear."""
        timeout = params.get("timeout", 10000)
        await self._page.wait_for_selector(selector, timeout=timeout)
        return {"success": True, "selector": selector}

    async def _screenshot(self, target: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Take screenshot."""
        path = params.get("path", "screenshot.png")
        await self._page.screenshot(path=path)
        return {"success": True, "path": path}

    def shutdown(self) -> None:
        """Shutdown browser executor."""
        if self._loop and self._browser:
            self._loop.run_until_complete(self._close_browser())
