"""macOS-specific chat area detection using OCR."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.window import WindowInfo

logger = logging.getLogger(__name__)

IS_MACOS = sys.platform == "darwin"


@dataclass
class MacOSDetectedAreas:
    """Detected UI areas on macOS."""

    chat_rect: tuple[int, int, int, int]
    input_rect: tuple[int, int, int, int]
    send_button: tuple[int, int] | None = None
    method: str = "heuristic"
    confidence: float = 0.5


class MacOSAreaDetector:
    """macOS-specific area detection using pyautogui and OCR."""

    def __init__(self):
        self._ocr_reader = None
        logger.info("MacOSAreaDetector initialized")

    def _init_ocr(self) -> bool:
        """Initialize OCR reader lazily."""
        if self._ocr_reader is not None:
            return True
        try:
            import easyocr

            self._ocr_reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
            logger.info("EasyOCR reader initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize OCR: {e}")
            return False

    def detect_areas(self, window: WindowInfo) -> MacOSDetectedAreas | None:
        """Detect chat and input areas in a window using pyautogui."""
        import pyautogui

        # 使用pyautogui获取截图
        screen = pyautogui.screenshot()
        screen_w, screen_h = screen.size

        print(f"\n=== macOS Area Detection (pyautogui) ===")
        print(f"屏幕尺寸: {screen_w}x{screen_h}")

        # Quartz窗口坐标
        q_x, q_y, q_right, q_bottom = window.rect
        q_w = q_right - q_x
        q_h = q_bottom - q_y
        print(f"Quartz窗口: ({q_x}, {q_y}) {q_w}x{q_h}")

        # 计算DPI缩放
        logical_size = pyautogui.size()
        dpr_x = screen_w / logical_size.width
        dpr_y = screen_h / logical_size.height
        print(f"DPI缩放: {dpr_x:.2f}x{dpr_y:.2f}")

        # 转换窗口坐标到pyautogui坐标系
        win_x = int(q_x * dpr_x)
        win_y = int(q_y * dpr_y)
        win_w = int(q_w * dpr_x)
        win_h = int(q_h * dpr_y)
        print(f"窗口(pyautogui坐标): ({win_x}, {win_y}) {win_w}x{win_h}")

        # 裁剪窗口
        win_img = screen.crop((win_x, win_y, win_x + win_w, win_y + win_h))
        print(f"窗口截图尺寸: {win_img.size}")

        if self._init_ocr():
            result = self._detect_via_ocr(window, win_img, dpr_x, dpr_y)
            if result:
                return result

        return self._detect_via_heuristic(window, dpr_x, dpr_y)

    def _detect_via_ocr(self, window: WindowInfo, win_img, dpr_x: float, dpr_y: float):
        """Detect areas using OCR."""
        try:
            import numpy as np

            results = self._ocr_reader.readtext(np.array(win_img), low_text=0.2, text_threshold=0.3)

            if not results:
                logger.warning("OCR returned no text")
                return None

            print(f"    OCR识别到 {len(results)} 个文字区域")

            for bbox, text, conf in results:
                if conf < 0.3:
                    continue
                xs = [p[0] for p in bbox]
                ys = [p[1] for p in bbox]
                cx = (min(xs) + max(xs)) / 2
                cy = (min(ys) + max(ys)) / 2
                print(f'      [{int(cx):4d},{int(cy):4d}] "{text[:30]}"')

            # 聊天区域：窗口右侧部分，扩展范围
            # 从 45% 开始（能识别到昵称）
            # 到 97% 结束
            q_x, q_y, q_right, q_bottom = window.rect
            q_w = q_right - q_x
            q_h = q_bottom - q_y

            chat_rect = (
                int(q_x + q_w * 0.45),
                int(q_y + q_h * 0.08),
                int(q_x + q_w * 0.97),
                int(q_y + q_h * 0.82),
            )

            input_rect = (
                int(q_x + q_w * 0.45),
                int(q_y + q_h * 0.82),
                int(q_x + q_w * 0.97),
                int(q_bottom - 5),
            )

            print(f"\n    聊天区域: {chat_rect}")
            print(f"    输入区域: {input_rect}")

            return MacOSDetectedAreas(
                chat_rect=chat_rect,
                input_rect=input_rect,
                send_button=(input_rect[2] - 50, (input_rect[1] + input_rect[3]) // 2),
                method="ocr",
                confidence=0.8,
            )

        except Exception as e:
            logger.error(f"OCR detection error: {e}")
            import traceback

            traceback.print_exc()
            return None

    def _detect_via_heuristic(self, window: WindowInfo, dpr_x: float, dpr_y: float):
        """Detect areas using heuristics."""
        rect = window.rect
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]
        wl, wt, wr, wb = rect

        chat_left = int(wl + w * 0.5)
        chat_top = int(wt + h * 0.12)
        chat_right = int(wr - 5)
        input_top = int(wb - h * 0.15)

        return MacOSDetectedAreas(
            chat_rect=(chat_left, chat_top, chat_right, input_top),
            input_rect=(chat_left, input_top, chat_right, wb),
            send_button=(chat_right - 50, wb - int(h * 0.075)),
            method="heuristic",
            confidence=0.5,
        )
