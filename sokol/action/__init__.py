"""Action layer - UIA, browser, and OCR automation."""

from sokol.action.executor import ActionExecutor
from sokol.action.uia_automation import UIAExecutor
from sokol.action.browser_automation import BrowserExecutor
from sokol.action.ocr_fallback import OCRFallback

__all__ = ["ActionExecutor", "UIAExecutor", "BrowserExecutor", "OCRFallback"]
