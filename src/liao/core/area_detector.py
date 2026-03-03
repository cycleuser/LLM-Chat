"""Chat area detection module."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..models.detection import AreaDetectionResult

if TYPE_CHECKING:
    from ..models.window import WindowInfo
    from .screenshot import ScreenshotReader

logger = logging.getLogger(__name__)


class ChatAreaDetector:
    """Detects chat message area and input box in chat application windows.
    
    Uses OCR-based detection with heuristic fallback.
    
    Example:
        detector = ChatAreaDetector(screenshot_reader)
        result = detector.detect_areas(window_info)
        print(f"Chat area: {result.chat_area_rect}")
        print(f"Input area: {result.input_area_rect}")
    """

    def __init__(self, screenshot_reader: "ScreenshotReader"):
        self._reader = screenshot_reader

    def detect_areas(self, window_info: "WindowInfo") -> AreaDetectionResult:
        """Detect chat and input areas in a window.
        
        Args:
            window_info: Window to analyze
            
        Returns:
            AreaDetectionResult with detected regions
        """
        if self._reader.has_ocr():
            result = self._detect_via_ocr(window_info)
            if result is not None:
                # Validate: detected area must be reasonably large
                cr = result.chat_area_rect
                cw = cr[2] - cr[0]
                ch = cr[3] - cr[1]
                ww = window_info.rect[2] - window_info.rect[0]
                wh = window_info.rect[3] - window_info.rect[1]
                if cw >= ww * 0.25 and ch >= wh * 0.30:
                    return result
                logger.info(
                    "OCR-detected area too small (%dx%d for %dx%d window), "
                    "using heuristic",
                    cw, ch, ww, wh,
                )
        return self._detect_via_heuristic(window_info)

    def _detect_via_ocr(self, window_info: "WindowInfo") -> AreaDetectionResult | None:
        """Detect areas using OCR analysis."""
        screenshot = self._reader.capture_window(window_info)
        if screenshot is None:
            return None
        
        bboxes = self._reader.extract_with_bboxes(screenshot)
        if len(bboxes) < 3:
            return None
        
        win_left, win_top, win_right, win_bottom = window_info.rect
        win_w, win_h = win_right - win_left, win_bottom - win_top
        if win_w <= 0 or win_h <= 0:
            return None

        # Collect bbox data
        bbox_data = []
        for bbox, text, _conf in bboxes:
            cx = sum(p[0] for p in bbox) / 4
            cy = sum(p[1] for p in bbox) / 4
            left_x = min(p[0] for p in bbox)
            right_x = max(p[0] for p in bbox)
            top_y = min(p[1] for p in bbox)
            bottom_y = max(p[1] for p in bbox)
            bbox_data.append({
                "cx": cx, "cy": cy,
                "left_x": left_x, "right_x": right_x,
                "top_y": top_y, "bottom_y": bottom_y
            })

        # Find columns by gap detection
        sorted_xs = sorted(b["cx"] for b in bbox_data)
        min_gap = win_w * 0.05
        boundaries = [0]
        for i in range(len(sorted_xs) - 1):
            if sorted_xs[i + 1] - sorted_xs[i] > min_gap:
                boundaries.append((sorted_xs[i] + sorted_xs[i + 1]) / 2)
        boundaries.append(win_w)
        columns = [(boundaries[i], boundaries[i + 1]) for i in range(len(boundaries) - 1)]

        # Score columns to find the chat column
        best_score, best_col = -1, None
        for cl, cr in columns:
            cw = cr - cl
            if cw < win_w * 0.15:
                continue
            col_bboxes = [b for b in bbox_data if cl < b["cx"] < cr]
            if len(col_bboxes) < 3:
                continue
            
            score = 0
            xs = [b["cx"] - cl for b in col_bboxes]
            x_spread = (max(xs) - min(xs)) / cw if cw > 0 else 0
            if x_spread > 0.30:
                score += 40
            elif x_spread > 0.20:
                score += 20
            score += min(len(col_bboxes) * 2, 30)
            score += int(((cl + cr) / 2 / win_w) * 25)
            width_ratio = cw / win_w
            if 0.25 <= width_ratio <= 0.60:
                score += 15
            ys = [b["cy"] for b in col_bboxes]
            if (max(ys) - min(ys)) / win_h > 0.50:
                score += 15
            
            if score > best_score:
                best_score, best_col = score, (cl, cr)

        if best_col is None:
            return None

        col_left, col_right = best_col
        col_bboxes = [b for b in bbox_data if col_left <= b["cx"] <= col_right]
        if not col_bboxes:
            return None
        col_ys = [b["cy"] for b in col_bboxes]

        # Find input boundary using band density analysis
        num_bands = 10
        band_h = win_h / num_bands
        bands = [0] * num_bands
        for y in col_ys:
            bands[min(int(y / band_h), num_bands - 1)] += 1
        
        input_top_y = win_h * 0.85
        for i in range(num_bands * 6 // 10, num_bands):
            upper_avg = sum(bands[:i]) / max(i, 1)
            if upper_avg > 0 and bands[i] < upper_avg * 0.3:
                input_top_y = i * band_h
                break

        chat_bboxes = [b for b in col_bboxes if b["cy"] < input_top_y] or col_bboxes
        header = win_h * 0.05
        chat_left_x = max(col_left, min(b["left_x"] for b in chat_bboxes) - win_w * 0.02)
        chat_right_x = min(col_right, max(b["right_x"] for b in chat_bboxes) + win_w * 0.02)
        chat_top_y = max(header, min(b["top_y"] for b in chat_bboxes) - win_h * 0.02)

        return AreaDetectionResult(
            chat_area_rect=(
                win_left + int(chat_left_x),
                win_top + int(chat_top_y),
                win_left + int(chat_right_x),
                win_top + int(input_top_y)
            ),
            input_area_rect=(
                win_left + int(chat_left_x),
                win_top + int(input_top_y),
                win_left + int(chat_right_x),
                win_bottom
            ),
            method="ocr",
            confidence=0.8,
        )

    @staticmethod
    def _detect_via_heuristic(window_info: "WindowInfo") -> AreaDetectionResult:
        """Detect areas using heuristic estimation.
        
        Uses app-specific layout assumptions when the app type is known,
        otherwise falls back to generic chat layout.
        """
        wl, wt, wr, wb = window_info.rect
        ww, wh = wr - wl, wb - wt
        
        # App-specific layouts
        app = window_info.app_type
        if app in ("wechat", "wecom"):
            # WeChat / WeCom: left sidebar ~22%, right chat area
            sidebar = 0.22
            header = 0.06
            input_h = 0.13
        elif app == "qq":
            # QQ: left sidebar ~25%, right chat area
            sidebar = 0.25
            header = 0.06
            input_h = 0.15
        elif app == "telegram":
            # Telegram: left sidebar ~30%, right chat area
            sidebar = 0.30
            header = 0.05
            input_h = 0.08
        elif app in ("dingtalk", "feishu"):
            # DingTalk / Feishu: left sidebar ~22%
            sidebar = 0.22
            header = 0.06
            input_h = 0.12
        elif app in ("slack", "discord", "teams"):
            # Slack / Discord / Teams: left sidebar ~20%
            sidebar = 0.20
            header = 0.05
            input_h = 0.10
        else:
            # Generic: assume sidebar on left ~45%
            sidebar = 0.45
            header = 0.05
            input_h = 0.15
        
        chat_left = wl + int(ww * sidebar)
        chat_top = wt + int(wh * header)
        chat_right = wr - int(ww * 0.01)
        input_top = wb - int(wh * input_h)
        
        return AreaDetectionResult(
            chat_area_rect=(chat_left, chat_top, chat_right, input_top),
            input_area_rect=(chat_left, input_top, chat_right, wb),
            method="heuristic",
            confidence=0.5 if app != "other" else 0.3,
        )
