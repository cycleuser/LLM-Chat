"""Screenshot capture and OCR module with macOS support."""

from __future__ import annotations

import io
import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image
    from ..models.window import WindowInfo

logger = logging.getLogger(__name__)

IS_LINUX = sys.platform == "linux"
IS_MACOS = sys.platform == "darwin"


class ScreenshotReader:
    """Captures screenshots and performs OCR text extraction.

    Platform-specific backends:
    - macOS: Quartz framework or screencapture CLI
    - Windows: pyautogui (Win32 API)
    - Linux: Wayland ScreenCast or xwininfo/wmctrl
    """

    def __init__(self):
        self._pyautogui = None
        self._pil_image = None
        self._ocr_reader = None
        self._ocr_type: str | None = None
        self._macos_screenshot = None
        print(f"ScreenshotReader 初始化 - macOS: {IS_MACOS}")
        self._load_deps()

    def _load_deps(self):
        """Load dependencies."""
        # Load pyautogui for Windows/Linux
        if not IS_MACOS:
            try:
                import pyautogui

                self._pyautogui = pyautogui
            except Exception as e:
                logger.warning(f"pyautogui not available: {e}")

        # Load PIL
        try:
            from PIL import Image

            self._pil_image = Image
        except ImportError:
            logger.warning("Pillow not available")

        # macOS: Use Quartz/screencapture
        if IS_MACOS:
            try:
                from .macos_screenshot import MacOSScreenshot

                self._macos_screenshot = MacOSScreenshot()
                logger.info("Using macOS Quartz for screenshots")
            except Exception as e:
                logger.warning(f"macOS screenshot failed: {e}")

        # Initialize OCR
        self._init_ocr()

    def _init_ocr(self):
        """Initialize OCR engine."""
        # Try EasyOCR first
        try:
            import easyocr

            self._ocr_reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
            self._ocr_type = "easyocr"
            logger.info("Using EasyOCR")
            return
        except Exception:
            pass

        # Try RapidOCR
        try:
            from rapidocr_onnxruntime import RapidOCR

            self._ocr_reader = RapidOCR()
            self._ocr_type = "rapidocr"
            logger.info("Using RapidOCR")
            return
        except Exception:
            pass

        # Try pytesseract
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            self._ocr_reader = pytesseract
            self._ocr_type = "pytesseract"
            logger.info("Using pytesseract")
        except Exception:
            logger.warning("No OCR engine available")

    def is_available(self) -> bool:
        """Check if screenshot capture is available."""
        if IS_MACOS:
            return self._macos_screenshot is not None or self._pyautogui is not None
        return self._pyautogui is not None

    def has_ocr(self) -> bool:
        """Check if OCR is available."""
        return self._ocr_reader is not None

    def get_ocr_status(self) -> str:
        """Get OCR engine status."""
        return f"OCR: {self._ocr_type}" if self._ocr_type else "OCR unavailable"

    def capture_window(self, window_info: WindowInfo) -> Image | None:
        """Capture screenshot of a window.

        Args:
            window_info: Window to capture

        Returns:
            PIL Image or None
        """
        if not self.is_available():
            return None

        try:
            left, top, right, bottom = window_info.rect
            width = right - left
            height = bottom - top

            if IS_MACOS and self._macos_screenshot:
                return self._macos_screenshot.capture_window(window_info)
            elif self._pyautogui:
                return self._pyautogui.screenshot(region=(left, top, width, height))
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")

        return None

    def capture_region(
        self, window_info: WindowInfo, region_rect: tuple[int, int, int, int]
    ) -> Image | None:
        """Capture specific region (screen coordinates).

        Args:
            window_info: Window reference (unused, for API compatibility)
            region_rect: (left, top, right, bottom) in screen coords

        Returns:
            PIL Image or None
        """
        if not self.is_available():
            logger.error("Screenshot not available")
            return None

        try:
            left, top, right, bottom = region_rect
            width = right - left
            height = bottom - top

            if width <= 0 or height <= 0:
                logger.error(f"Invalid region dimensions: {width}x{height}")
                return None

            logger.debug(f"Capturing region: ({left}, {top}) {width}x{height}")
            print(f"    截图区域: ({left}, {top}) 到 ({right}, {bottom}), 尺寸 {width}x{height}")

            if IS_MACOS and self._macos_screenshot:
                return self._macos_screenshot.capture_region(left, top, width, height)
            elif self._pyautogui:
                return self._pyautogui.screenshot(region=(left, top, width, height))
        except Exception as e:
            logger.error(f"Region capture failed: {e}")
            print(f"    ❌ 截图失败: {e}")

        return None

    def extract_text(self, image: Image) -> str:
        """Extract text from image using OCR.

        Args:
            image: PIL Image

        Returns:
            Extracted text
        """
        if not self._ocr_reader:
            return ""

        try:
            if self._ocr_type == "easyocr":
                import numpy as np

                results = self._ocr_reader.readtext(np.array(image))
                return "\n".join(text for (_, text, prob) in results if prob > 0.3)
            elif self._ocr_type == "rapidocr":
                import numpy as np

                result, _ = self._ocr_reader(np.array(image))
                return "\n".join(item[1] for item in result) if result else ""
            elif self._ocr_type == "pytesseract":
                return self._ocr_reader.image_to_string(image, lang="chi_sim+eng")
        except Exception as e:
            logger.error(f"OCR failed: {e}")

        return ""

    def extract_with_bboxes(self, image: Image) -> list[tuple[list, str, float]]:
        """Extract text with bounding boxes.

        Args:
            image: PIL Image

        Returns:
            List of (bbox, text, confidence) tuples
        """
        if not self._ocr_reader:
            return []

        try:
            if self._ocr_type == "easyocr":
                import numpy as np

                results = self._ocr_reader.readtext(np.array(image))
                return [(bbox, text, prob) for (bbox, text, prob) in results if prob > 0.3]
            elif self._ocr_type == "rapidocr":
                import numpy as np

                result, _ = self._ocr_reader(np.array(image))
                if result:
                    return [(item[0], item[1], item[2]) for item in result]
                return []
            elif self._ocr_type == "pytesseract":
                text = self._ocr_reader.image_to_string(image, lang="chi_sim+eng")
                w, h = image.size
                if text.strip():
                    return [([[0, 0], [w, 0], [w, h], [0, h]], text.strip(), 0.5)]
                return []
        except Exception as e:
            logger.error(f"OCR bbox failed: {e}")

        return []

    def capture_and_extract(self, window_info: WindowInfo) -> tuple[Image | None, str]:
        """Capture window and extract text.

        Args:
            window_info: Window to capture

        Returns:
            Tuple of (PIL Image, extracted text)
        """
        screenshot = self.capture_window(window_info)
        if not screenshot:
            return None, ""

        text = self.extract_text(screenshot) if self.has_ocr() else ""
        return screenshot, text

    @staticmethod
    def image_to_bytes(image: Image, fmt: str = "PNG") -> bytes:
        """Convert PIL Image to bytes."""
        buf = io.BytesIO()
        image.save(buf, format=fmt)
        return buf.getvalue()

    @staticmethod
    def bytes_to_image(data: bytes) -> Image | None:
        """Convert bytes to PIL Image."""
        try:
            from PIL import Image

            return Image.open(io.BytesIO(data))
        except Exception:
            return None
