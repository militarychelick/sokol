"""OCR fallback - OCR as last resort when UIA and DOM fail."""

from typing import Optional, Dict, Any
from pathlib import Path

from sokol.observability.logging import get_logger

logger = get_logger("sokol.action.ocr_fallback")


class OCRFallback:
    """
    OCR-based automation as fallback when UIA and DOM fail.

    Uses OCR to find elements by text and mouse to interact.
    """

    def __init__(self) -> None:
        self._available = self._check_availability()
        logger.info_data(
            "OCR fallback initialized",
            {"available": self._available},
        )

    def _check_availability(self) -> bool:
        """Check if OCR is available."""
        try:
            import pytesseract
            from PIL import ImageGrab
            return True
        except ImportError:
            return False

    def is_available(self) -> bool:
        """Check if OCR fallback is available."""
        return self._available

    def execute(
        self,
        action_type: str,
        target: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute action using OCR.

        Args:
            action_type: Type of action (click, type, etc.)
            target: Target text to find via OCR
            params: Additional parameters

        Returns:
            Dict with success status and result data
        """
        params = params or {}

        try:
            if action_type == "click":
                return self._click_by_text(target, params)
            elif action_type == "find_text":
                return self._find_text(target, params)
            elif action_type == "screenshot":
                return self._screenshot(target, params)
            else:
                return {
                    "success": False,
                    "error": f"Unknown action type for OCR: {action_type}",
                }
        except Exception as e:
            logger.error_data(
                "OCR execution failed",
                {"action": action_type, "target": target, "error": str(e)},
            )
            return {
                "success": False,
                "error": str(e),
            }

    def _click_by_text(self, text: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Click on element found by text using OCR.

        This is a fallback method and should be avoided if possible.
        """
        # Capture screen
        from PIL import ImageGrab

        screenshot = ImageGrab.grab()

        # Use OCR to find text location
        location = self._find_text_location(screenshot, text)

        if location:
            # Click using pyautogui
            try:
                import pyautogui

                x, y = location
                pyautogui.click(x, y)
                return {
                    "success": True,
                    "location": location,
                    "method": "ocr_click",
                }
            except ImportError:
                return {
                    "success": False,
                    "error": "pyautogui not available for mouse control",
                }
        else:
            return {
                "success": False,
                "error": f"Text not found via OCR: {text}",
            }

    def _find_text(self, text: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find text on screen using OCR."""
        from PIL import ImageGrab

        screenshot = ImageGrab.grab()
        location = self._find_text_location(screenshot, text)

        if location:
            return {
                "success": True,
                "location": location,
                "method": "ocr_find",
            }
        else:
            return {
                "success": False,
                "error": f"Text not found via OCR: {text}",
            }

    def _find_text_location(
        self, image, text: str
    ) -> Optional[tuple[int, int]]:
        """
        Find text location in image using OCR.

        Returns (x, y) coordinates or None if not found.
        """
        try:
            import pytesseract
            from PIL import Image

            # Get OCR data with bounding boxes
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

            # Search for text
            for i, detected_text in enumerate(data["text"]):
                if text.lower() in detected_text.lower():
                    x = data["left"][i]
                    y = data["top"][i]
                    w = data["width"][i]
                    h = data["height"][i]
                    # Return center of bounding box
                    return (x + w // 2, y + h // 2)

            return None

        except Exception as e:
            logger.error_data("OCR text location failed", {"error": str(e)})
            return None

    def _screenshot(self, target: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Take screenshot."""
        from PIL import ImageGrab

        path = params.get("path", "screenshot.png")
        screenshot = ImageGrab.grab()
        screenshot.save(path)

        return {
            "success": True,
            "path": path,
        }

    def get_all_text(self) -> Dict[str, Any]:
        """Get all text from screen using OCR."""
        from PIL import ImageGrab
        import pytesseract

        try:
            screenshot = ImageGrab.grab()
            text = pytesseract.image_to_string(screenshot)

            return {
                "success": True,
                "text": text.strip(),
            }
        except Exception as e:
            logger.error_data("OCR get all text failed", {"error": str(e)})
            return {
                "success": False,
                "error": str(e),
            }
