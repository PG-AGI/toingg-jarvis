# -*- coding: utf-8 -*-
"""Window and monitor configuration helper for Playwright browser."""
import os
import re
from typing import Dict, Any, Tuple, Optional, List

class WindowConfig:
    def __init__(
        self,
        window_size: Optional[str] = None,
        position: Optional[str] = None,
        monitor: Optional[str] = None,
    ):
        self.raw_size = window_size or os.getenv("JARVIS_WINDOW_SIZE")
        self.raw_pos = position or os.getenv("JARVIS_WINDOW_POSITION")
        self.raw_monitor = monitor or os.getenv("JARVIS_MONITOR", "primary")

    def parse_size(self) -> Tuple[int, int]:
        """Parses width and height from format '1600x900' or returns default (1366, 768)."""
        if not self.raw_size:
            return (1366, 768)
        m = re.match(r"^(\d+)[xX,](\d+)$", str(self.raw_size).strip())
        if m:
            w, h = int(m.group(1)), int(m.group(2))
            if w > 0 and h > 0:
                return (w, h)
        return (1366, 768)

    def parse_position(self, width: int = 1366, height: int = 768) -> Optional[Tuple[int, int]]:
        """Parses position string: 'center', 'top-left', 'top-right', 'x=100,y=200', or '100,200'."""
        if not self.raw_pos:
            return None
        pos_str = str(self.raw_pos).strip().lower()

        # Monitor offset calculation
        x_offset = 0
        if self.raw_monitor and self.raw_monitor.startswith("monitor-"):
            try:
                mon_idx = int(self.raw_monitor.split("-")[1])
                if mon_idx > 1:
                    x_offset = (mon_idx - 1) * 1920
            except ValueError:
                pass

        if pos_str == "top-left":
            return (x_offset + 0, 0)
        elif pos_str == "top-right":
            return (x_offset + max(0, 1920 - width), 0)
        elif pos_str in ("center", "active"):
            x = max(0, (1920 - width) // 2)
            y = max(0, (1080 - height) // 2)
            return (x_offset + x, y)

        m = re.match(r"^(?:x=)?(\d+)[,;:\s]+(?:y=)?(\d+)$", pos_str)
        if m:
            return (x_offset + int(m.group(1)), int(m.group(2)))
        return None

    def get_chromium_args(self) -> List[str]:
        """Returns Chromium CLI flags for window size and positioning."""
        w, h = self.parse_size()
        args = [f"--window-size={w},{h}"]
        pos = self.parse_position(w, h)
        if pos:
            args.append(f"--window-position={pos[0]},{pos[1]}")
        return args

    def get_viewport(self) -> Dict[str, int]:
        """Returns viewport dictionary for Playwright browser context."""
        w, h = self.parse_size()
        return {"width": w, "height": h}
