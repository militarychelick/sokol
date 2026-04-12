"""Screen input adapter - screen capture and vision integration."""

from typing import Optional
from dataclasses import dataclass
import io

from sokol.observability.logging import get_logger

logger = get_logger("sokol.perception.screen_input")


@dataclass
class ScreenElement:
    """Screen element data structure."""
    text: str
    location: tuple[int, int, int, int]  # x, y, width, height
    element_type: str = "unknown"


@dataclass
class ScreenSnapshot:
    """Screen snapshot data structure."""
    elements: list[ScreenElement]
    active_window: str = ""
    image_bytes: Optional[bytes] = None


class ScreenInputAdapter:
    """
    Screen input adapter with screen capture functionality.

    Provides screen capture and basic screen understanding.
    """

    def __init__(self) -> None:
        """Initialize screen input adapter."""
        self._available = self._check_availability()
        logger.info_data(
            "Screen input adapter initialized",
            {"available": self._available},
        )

    def _check_availability(self) -> bool:
        """Check if screen capture is available."""
        try:
            from PIL import ImageGrab
            return True
        except ImportError:
            logger.warning("PIL not available, install with: pip install pillow")
            return False

    def is_available(self) -> bool:
        """Check if screen input is available."""
        return self._available

    def capture(self) -> ScreenSnapshot:
        """
        Capture current screen state.

        Returns:
            ScreenSnapshot with captured image.
        """
        if not self._available:
            logger.warning("Screen capture not available")
            return ScreenSnapshot(elements=[], active_window="")

        try:
            from PIL import ImageGrab

            # Capture screen
            screenshot = ImageGrab.grab()

            # Convert to bytes
            img_bytes = io.BytesIO()
            screenshot.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            image_data = img_bytes.read()

            # Get active window (simplified - would use UIA for accurate detection)
            try:
                import pywinauto
                from pywinauto import Desktop
                desktop = Desktop(backend="uia")
                active_window = desktop.window().window_text()
            except:
                active_window = "Unknown"

            logger.info_data(
                "Screen captured successfully",
                {"size": screenshot.size, "active_window": active_window},
            )

            return ScreenSnapshot(
                elements=[],  # Would be populated by vision/OCR
                active_window=active_window,
                image_bytes=image_data,
            )

        except Exception as e:
            logger.error_data("Screen capture failed", {"error": str(e)})
            return ScreenSnapshot(elements=[], active_window="")

    def capture_region(self, x: int, y: int, width: int, height: int) -> ScreenSnapshot:
        """
        Capture specific region of screen.

        Args:
            x: X coordinate
            y: Y coordinate
            width: Width of region
            height: Height of region

        Returns:
            ScreenSnapshot with captured region.
        """
        if not self._available:
            logger.warning("Screen capture not available")
            return ScreenSnapshot(elements=[], active_window="")

        try:
            from PIL import ImageGrab

            # Capture region
            bbox = (x, y, x + width, y + height)
            screenshot = ImageGrab.grab(bbox=bbox)

            # Convert to bytes
            img_bytes = io.BytesIO()
            screenshot.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            image_data = img_bytes.read()

            logger.info_data(
                "Screen region captured successfully",
                {"bbox": bbox, "size": screenshot.size},
            )

            return ScreenSnapshot(
                elements=[],
                active_window="",
                image_bytes=image_data,
            )

        except Exception as e:
            logger.error_data("Screen region capture failed", {"error": str(e)})
            return ScreenSnapshot(elements=[], active_window="")

    def find_element(self, text: str) -> Optional[ScreenElement]:
        """
        Find screen element by text (OCR-based).

        Args:
            text: Text to search for

        Returns:
            ScreenElement if found, None otherwise.
        """
        if not self._available:
            logger.warning("Screen capture not available")
            return None

        try:
            from sokol.action.ocr_fallback import OCRFallback

            ocr = OCRFallback()
            if not ocr.is_available():
                logger.warning("OCR not available")
                return None

            result = ocr._find_text_location(None, text)  # Simplified call
            if result:
                x, y = result
                return ScreenElement(
                    text=text,
                    location=(x, y, 0, 0),  # OCR returns center point
                    element_type="text",
                )

            return None

        except Exception as e:
            logger.error_data("Element finding failed", {"error": str(e)})
            return None

    def get_description(self) -> str:
        """
        Get text description of current screen state.

        Returns:
            String description of screen (empty if not available).
        """
        snapshot = self.capture()
        if not snapshot.elements and not snapshot.active_window:
            return ""

        descriptions = []
        if snapshot.active_window:
            descriptions.append(f"Active window: {snapshot.active_window}")

        # OCR-based description would go here
        # For now, return basic window info
        return " | ".join(descriptions) if descriptions else "Screen captured, no description available"
