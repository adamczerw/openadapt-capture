"""Utility functions for openadapt-capture.

Copied from legacy OpenAdapt utils.py — timestamp management, screenshot capture,
and multiprocessing helpers. Only import paths are changed.
"""

import sys
import threading
import time
from functools import wraps
from typing import Any, Callable

import mss
import mss.base
from loguru import logger
from PIL import Image

if sys.platform == "win32":
    import mss.windows

    # fix cursor flicker on windows; see:
    # https://github.com/BoboTiG/python-mss/issues/179#issuecomment-673292002
    mss.windows.CAPTUREBLT = 0


# TODO: move to constants.py
DEFAULT_DOUBLE_CLICK_INTERVAL_SECONDS = 0.5
DEFAULT_DOUBLE_CLICK_DISTANCE_PIXELS = 5

_logger_lock = threading.Lock()
_start_time = None
_start_perf_counter = None

# Process-local storage for MSS instances
# Use threading.local() as a simpler alternative to multiprocessing_utils.local()
_process_local = threading.local()


def get_process_local_sct() -> mss.mss:
    """Retrieve or create the `mss` instance for the current thread."""
    if not hasattr(_process_local, "sct"):
        _process_local.sct = mss.mss()
    return _process_local.sct


def list_monitors() -> list[dict]:
    """Return all mss monitor dicts.

    monitors[0] is the virtual bounding box of all monitors combined.
    monitors[1] is the primary monitor, monitors[2] the secondary, etc.
    """
    return list(get_process_local_sct().monitors)


def get_monitor_info(monitor_index: int | None = None) -> dict:
    """Return the mss monitor dict for the given index.

    Args:
        monitor_index: mss index (0=all combined, 1=primary, 2=secondary, …).
            Defaults to config.MONITOR_INDEX.
    """
    from openadapt_capture.config import config as _config
    idx = monitor_index if monitor_index is not None else _config.MONITOR_INDEX
    monitors = get_process_local_sct().monitors
    if 0 <= idx < len(monitors):
        return monitors[idx]
    logger.warning(f"Monitor index {idx} out of range (have {len(monitors)}), using 0")
    return monitors[0]


def get_monitor_dims(monitor_index: int | None = None) -> tuple[int, int]:
    """Get the dimensions of the selected monitor.

    Args:
        monitor_index: mss index. Defaults to config.MONITOR_INDEX.

    Returns:
        tuple[int, int]: The width and height of the monitor.
    """
    monitor = get_monitor_info(monitor_index)
    return monitor["width"], monitor["height"]


def set_start_time(value: float = None) -> float:
    """Set the start time for recordings. Required for accurate process-wide timestamps.

    Args:
        value (float): The start time value. Defaults to the current time.

    Returns:
        float: The start time.
    """
    global _start_time
    global _start_perf_counter
    _start_time = value or time.time()
    _start_perf_counter = time.perf_counter()
    logger.debug(f"{_start_time=} {_start_perf_counter=}")
    return _start_time


def get_timestamp() -> float:
    """Get the current timestamp, synchronized between processes.

    Before calling this function from any process, set_start_time must have been called.

    Returns:
        float: The current timestamp.
    """
    global _start_time
    global _start_perf_counter

    msg = "set_start_time must be called before get_timestamp"
    assert _start_time, f"{_start_time=}; {msg}"
    assert _start_perf_counter, f"{_start_perf_counter=}; {msg}"

    perf_duration = time.perf_counter() - _start_perf_counter
    return _start_time + perf_duration


def take_screenshot(monitor_index: int | None = None) -> Image.Image:
    """Take a screenshot of the selected monitor.

    Args:
        monitor_index: mss index. Defaults to config.MONITOR_INDEX.

    Returns:
        PIL.Image: The screenshot image.
    """
    sct = get_process_local_sct()
    monitor = get_monitor_info(monitor_index)
    sct_img = sct.grab(monitor)
    return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")


def get_double_click_interval_seconds() -> float:
    """Get the double click interval in seconds.

    Returns:
        float: The double click interval in seconds.
    """
    if sys.platform == "darwin":
        try:
            from AppKit import NSEvent
            return NSEvent.doubleClickInterval()
        except ImportError:
            return DEFAULT_DOUBLE_CLICK_INTERVAL_SECONDS
    elif sys.platform == "win32":
        try:
            from ctypes import windll
            return windll.user32.GetDoubleClickTime() / 1000
        except Exception:
            return DEFAULT_DOUBLE_CLICK_INTERVAL_SECONDS
    else:
        return DEFAULT_DOUBLE_CLICK_INTERVAL_SECONDS


def get_double_click_distance_pixels() -> int:
    """Get the double click distance in pixels.

    Returns:
        int: The double click distance in pixels.
    """
    if sys.platform == "darwin":
        try:
            from AppKit import NSPressGestureRecognizer
            return NSPressGestureRecognizer.new().allowableMovement()
        except ImportError:
            return DEFAULT_DOUBLE_CLICK_DISTANCE_PIXELS
    elif sys.platform == "win32":
        try:
            import win32api
            import win32con
            x = win32api.GetSystemMetrics(win32con.SM_CXDOUBLECLK)
            y = win32api.GetSystemMetrics(win32con.SM_CYDOUBLECLK)
            return max(x, y)
        except ImportError:
            return DEFAULT_DOUBLE_CLICK_DISTANCE_PIXELS
    else:
        return DEFAULT_DOUBLE_CLICK_DISTANCE_PIXELS


class WrapStdout:
    """Wrapper for multiprocessing process targets.

    Ensures that stdout/stderr are properly redirected in child processes.
    Copied from legacy OpenAdapt utils.py.
    """

    def __init__(self, fn: Callable) -> None:
        """Initialize with the function to wrap."""
        self.fn = fn

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Call the wrapped function."""
        return self.fn(*args, **kwargs)


def trace(logger: Any) -> Callable:
    """Decorator to trace function entry and exit.

    Args:
        logger: The logger to use.

    Returns:
        Callable: The decorator.
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.info(f"Starting {fn.__name__}")
            try:
                result = fn(*args, **kwargs)
                logger.info(f"Finished {fn.__name__}")
                return result
            except Exception as e:
                logger.error(f"Error in {fn.__name__}: {e}")
                raise
        return wrapper
    return decorator
