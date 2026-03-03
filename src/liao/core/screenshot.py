"""Screenshot capture and OCR module.

Uses pyautogui on Windows/X11, and xdg-desktop-portal ScreenCast
with PipeWire/GStreamer on Wayland (Linux). Falls back to gnome-screenshot
or grim subprocess calls when PyGObject is not available.
"""

from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PIL.Image import Image
    from ..models.window import WindowInfo

logger = logging.getLogger(__name__)

IS_LINUX = sys.platform == "linux"


def _detect_screenshot_tool() -> str | None:
    """Detect available screenshot tool on Linux.

    Returns:
        Tool name ('gnome-screenshot', 'grim') or None.
    """
    if not IS_LINUX:
        return None
    for tool in ("gnome-screenshot", "grim"):
        if shutil.which(tool):
            return tool
    return None


class ScreenshotReader:
    """Captures screenshots and performs OCR text extraction.

    Supports multiple capture backends:
    - pyautogui (Windows, X11)
    - Wayland ScreenCast portal + PipeWire/GStreamer (Linux/Wayland)

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
        self._wayland_capturer = None
        self._wayland_checked = False
        self._screenshot_tool: str | None = None
        self._load_deps()

    def _load_deps(self):
        """Load dependencies."""
        try:
            import pyautogui
            self._pyautogui = pyautogui
        except Exception as e:
            logger.warning(f"pyautogui not available: {e}")

        try:
            from PIL import Image
            self._pil_image = Image
        except ImportError:
            logger.warning("Pillow not available - image processing disabled")

        # Detect Linux screenshot tool fallback
        if IS_LINUX:
            self._screenshot_tool = _detect_screenshot_tool()
            if self._screenshot_tool:
                logger.info(f"Using {self._screenshot_tool} for screenshots")

        self._init_ocr()

    def _init_wayland_capture(self) -> bool:
        """Lazily initialize Wayland capture if needed and available.

        Returns:
            True if Wayland capture is ready.
        """
        if self._wayland_checked:
            return self._wayland_capturer is not None and self._wayland_capturer.is_active

        self._wayland_checked = True

        if not IS_LINUX:
            return False

        try:
            from .wayland_capture import WaylandScreenCapturer, _check_deps
            if not _check_deps():
                logger.debug("Wayland capture dependencies not available")
                return False

            capturer = WaylandScreenCapturer()
            if capturer.create_session():
                self._wayland_capturer = capturer
                logger.info("Wayland ScreenCast capture initialized")
                return True
            else:
                logger.warning(
                    "Wayland ScreenCast session not established "
                    "(user may have cancelled)"
                )
                return False
        except Exception as e:
            logger.warning(f"Wayland capture init failed: {e}")
            return False

    def request_screen_permission(self) -> bool:
        """Request screen capture permission (Linux/Wayland only).

        On Wayland, this triggers the desktop portal consent dialog or
        runs gnome-screenshot to trigger its permission prompt.
        Should be called early in the application lifecycle before
        any screenshot capture is attempted.

        Returns:
            True if screen capture is available.
        """
        if not IS_LINUX:
            # On Windows/X11, no permission dialog is needed
            return self._pyautogui is not None

        # Try Wayland portal first
        self._wayland_checked = False
        if self._init_wayland_capture():
            return True

        # Try gnome-screenshot (triggers permission dialog on first run)
        if self._screenshot_tool == "gnome-screenshot":
            logger.info("Triggering gnome-screenshot for permission request")
            fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="liao_perm_")
            os.close(fd)
            try:
                result = subprocess.run(
                    ["gnome-screenshot", "-f", tmp_path],
                    capture_output=True,
                    timeout=30,  # Give user time to grant permission
                )
                if result.returncode == 0 and os.path.exists(tmp_path):
                    logger.info("gnome-screenshot permission granted")
                    return True
                else:
                    logger.warning(f"gnome-screenshot failed: {result.stderr.decode()}")
            except subprocess.TimeoutExpired:
                logger.warning("gnome-screenshot timed out waiting for permission")
            except Exception as e:
                logger.warning(f"gnome-screenshot permission request failed: {e}")
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        # Try grim (usually doesn't need permission dialog)
        if self._screenshot_tool == "grim":
            return True

        return False

    def has_screen_permission(self) -> bool:
        """Check if screen capture permission has been granted.

        Returns:
            True if screenshots can be taken.
        """
        if not IS_LINUX:
            return self._pyautogui is not None
        if self._wayland_capturer is not None and self._wayland_capturer.is_active:
            return True
        # Subprocess tools are available
        if self._screenshot_tool:
            return True
        return False

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
        if self._pyautogui is not None and self._pil_image is not None:
            return True
        # On Linux, Wayland capture may be available even without pyautogui
        if IS_LINUX and self._pil_image is not None:
            return True
        return False

    def has_ocr(self) -> bool:
        """Check if OCR is available."""
        return self._ocr_reader is not None

    def get_ocr_status(self) -> str:
        """Get OCR engine status string."""
        if self._ocr_type:
            return f"OCR: {self._ocr_type}"
        return "OCR unavailable"

    def _capture_screenshot(
        self, left: int, top: int, width: int, height: int
    ) -> "Image | None":
        """Capture a screen region using the best available backend.

        Tries Wayland ScreenCast on Linux first, then subprocess tools,
        finally falls back to pyautogui.

        Args:
            left: Region left x.
            top: Region top y.
            width: Region width.
            height: Region height.

        Returns:
            PIL Image or None.
        """
        if width <= 0 or height <= 0:
            return None

        # On Linux, try Wayland capture first
        if IS_LINUX:
            # Try Wayland capture (lazy init on first use)
            if self._wayland_capturer and self._wayland_capturer.is_active:
                img = self._wayland_capturer.capture_region(left, top, width, height)
                if img is not None:
                    return img
            elif not self._wayland_checked:
                if self._init_wayland_capture():
                    img = self._wayland_capturer.capture_region(left, top, width, height)
                    if img is not None:
                        return img

            # Fallback to subprocess-based tools (gnome-screenshot, grim)
            if self._screenshot_tool:
                img = self._capture_via_subprocess(left, top, width, height)
                if img is not None:
                    return img

        # Fallback to pyautogui
        if self._pyautogui:
            try:
                return self._pyautogui.screenshot(region=(left, top, width, height))
            except Exception as e:
                logger.error(f"pyautogui screenshot failed: {e}")

        return None

    def _capture_via_subprocess(
        self, left: int, top: int, width: int, height: int
    ) -> "Image | None":
        """Capture screenshot using subprocess (gnome-screenshot or grim).

        Args:
            left: Region left x.
            top: Region top y.
            width: Region width.
            height: Region height.

        Returns:
            PIL Image or None.
        """
        if not self._screenshot_tool or not self._pil_image:
            return None

        fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="liao_")
        os.close(fd)

        try:
            if self._screenshot_tool == "gnome-screenshot":
                # gnome-screenshot captures full screen, we crop after
                result = subprocess.run(
                    ["gnome-screenshot", "-f", tmp_path],
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    logger.error(f"gnome-screenshot failed: {result.stderr.decode()}")
                    return None

            elif self._screenshot_tool == "grim":
                # grim can capture a region directly
                geometry = f"{left},{top} {width}x{height}"
                result = subprocess.run(
                    ["grim", "-g", geometry, tmp_path],
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    logger.error(f"grim failed: {result.stderr.decode()}")
                    return None

            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                img = self._pil_image.open(tmp_path)
                # gnome-screenshot captures full screen, need to crop
                if self._screenshot_tool == "gnome-screenshot":
                    img = img.crop((left, top, left + width, top + height))
                return img.copy()  # Copy to release file handle

        except subprocess.TimeoutExpired:
            logger.error(f"{self._screenshot_tool} timed out")
        except Exception as e:
            logger.error(f"Subprocess screenshot failed: {e}")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return None

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
            return self._capture_screenshot(left, top, w, h)
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
            return self._capture_screenshot(left, top, w, h)
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
            logger.warning("extract_with_bboxes called but no OCR engine available")
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
