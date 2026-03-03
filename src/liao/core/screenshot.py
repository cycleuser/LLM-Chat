"""Screenshot capture and OCR module."""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PIL.Image import Image
    from ..models.window import WindowInfo

logger = logging.getLogger(__name__)


class ScreenshotReader:
    """Captures screenshots and performs OCR text extraction.
    
    Supports multiple OCR backends with automatic fallback:
    - EasyOCR (recommended)
    - RapidOCR
    - pytesseract
    
    Example:
        reader = ScreenshotReader()
        screenshot = reader.capture_window(window_info)
        text = reader.extract_text(screenshot)
    """

    def __init__(self):
        self._pyautogui = None
        self._pil_image = None
        self._ocr_reader = None
        self._ocr_type: str | None = None
        self._load_deps()

    def _load_deps(self):
        """Load dependencies."""
        try:
            import pyautogui
            self._pyautogui = pyautogui
        except Exception as e:
            logger.warning(f"pyautogui not available - screenshot disabled: {e}")
        
        try:
            from PIL import Image
            self._pil_image = Image
        except ImportError:
            logger.warning("Pillow not available - image processing disabled")
        
        self._init_ocr()

    def _init_ocr(self):
        """Initialize OCR engine with fallback chain."""
        # Try EasyOCR first (best quality)
        try:
            import easyocr
            self._ocr_reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
            self._ocr_type = "easyocr"
            logger.info("Using EasyOCR")
            return
        except (ImportError, Exception) as e:
            logger.debug(f"EasyOCR not available: {e}")
        
        # Try RapidOCR
        try:
            from rapidocr_onnxruntime import RapidOCR
            self._ocr_reader = RapidOCR()
            self._ocr_type = "rapidocr"
            logger.info("Using RapidOCR")
            return
        except (ImportError, Exception) as e:
            logger.debug(f"RapidOCR not available: {e}")
        
        # Try pytesseract
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            self._ocr_reader = pytesseract
            self._ocr_type = "pytesseract"
            logger.info("Using pytesseract")
            return
        except (ImportError, Exception) as e:
            logger.debug(f"pytesseract not available: {e}")
        
        logger.warning("No OCR engine available. Install: pip install easyocr")

    def is_available(self) -> bool:
        """Check if screenshot capture is available."""
        return self._pyautogui is not None and self._pil_image is not None

    def has_ocr(self) -> bool:
        """Check if OCR is available."""
        return self._ocr_reader is not None

    def get_ocr_status(self) -> str:
        """Get OCR engine status string."""
        if self._ocr_type:
            return f"OCR: {self._ocr_type}"
        return "OCR unavailable"

    def capture_window(self, window_info: "WindowInfo") -> "Image | None":
        """Capture screenshot of a window.
        
        Args:
            window_info: Window to capture
            
        Returns:
            PIL Image or None if failed
        """
        if not self.is_available():
            return None
        try:
            left, top, right, bottom = window_info.rect
            w, h = right - left, bottom - top
            if w <= 0 or h <= 0:
                return None
            return self._pyautogui.screenshot(region=(left, top, w, h))
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None

    def capture_region(
        self,
        window_info: "WindowInfo",
        region_rect: tuple[int, int, int, int]
    ) -> "Image | None":
        """Capture screenshot of a specific region.
        
        Args:
            window_info: Window for reference (unused but kept for API consistency)
            region_rect: Region to capture (left, top, right, bottom) in screen coords
            
        Returns:
            PIL Image or None if failed
        """
        if not self.is_available():
            return None
        try:
            left, top, right, bottom = region_rect
            w, h = right - left, bottom - top
            if w <= 0 or h <= 0:
                return None
            return self._pyautogui.screenshot(region=(left, top, w, h))
        except Exception as e:
            logger.error(f"Region capture failed: {e}")
            return None

    def extract_text(self, image: "Image") -> str:
        """Extract text from image using OCR.
        
        Args:
            image: PIL Image to process
            
        Returns:
            Extracted text or empty string
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

    def extract_with_bboxes(self, image: "Image") -> list[tuple[list, str, float]]:
        """Extract text with bounding boxes from image.
        
        Args:
            image: PIL Image to process
            
        Returns:
            List of (bbox, text, confidence) tuples
            where bbox is [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
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

    def capture_and_extract(
        self,
        window_info: "WindowInfo"
    ) -> tuple["Image | None", str]:
        """Capture window screenshot and extract text.
        
        Args:
            window_info: Window to capture
            
        Returns:
            Tuple of (PIL Image or None, extracted text)
        """
        screenshot = self.capture_window(window_info)
        if not screenshot:
            return None, ""
        text = self.extract_text(screenshot) if self.has_ocr() else ""
        return screenshot, text

    @staticmethod
    def image_to_bytes(image: "Image", fmt: str = "PNG") -> bytes:
        """Convert PIL Image to bytes.
        
        Args:
            image: PIL Image
            fmt: Image format (PNG, JPEG, etc.)
            
        Returns:
            Image bytes
        """
        buf = io.BytesIO()
        image.save(buf, format=fmt)
        return buf.getvalue()

    @staticmethod
    def bytes_to_image(data: bytes) -> "Image | None":
        """Convert bytes to PIL Image.
        
        Args:
            data: Image bytes
            
        Returns:
            PIL Image or None
        """
        try:
            from PIL import Image
            return Image.open(io.BytesIO(data))
        except Exception:
            return None
