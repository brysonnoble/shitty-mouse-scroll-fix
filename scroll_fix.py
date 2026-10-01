"""
shitty-mouse-scroll-fix

Runs in the background and filters out spurious scroll-wheel reversals.

Once you've scrolled N ticks in one direction (default 5) and keep scrolling
without pausing, any tick in the opposite direction is treated as a glitch:
it's swallowed and replaced with a tick in the direction you were already
scrolling. Pause for longer than the timeout and the next tick is accepted
as-is, so you can still change direction normally.

Windows only. No third-party dependencies.
"""

import argparse
import ctypes
import logging
import os
import queue
import sys
import threading
from ctypes import wintypes

# --------------------------------------------------------------------------- #
# Filter logic (platform independent, unit tested)
# --------------------------------------------------------------------------- #

UP = 1
DOWN = -1


class ScrollFilter:
    """Decides which direction each wheel tick should actually go.

    threshold:  consecutive ticks in one direction before reversals get blocked
    timeout_ms: a gap longer than this between ticks ends the scroll "session"
    confirm:    if > 0, this many opposite ticks in a row are accepted as a
                genuine change of direction (0 = never, you must pause)
    """

    def __init__(self, threshold=5, timeout_ms=400, confirm=0):
        self.threshold = threshold
        self.timeout_ms = timeout_ms
        self.confirm = confirm
        self.direction = None
        self.streak = 0
        self.opposite = 0
        self.last_time = None

    def process(self, direction, now_ms):
        """Return the direction this tick should scroll in."""
        expired = (
            self.last_time is None
            # Tick counts are 32-bit and wrap, so compare modulo 2**32.
            or ((now_ms - self.last_time) & 0xFFFFFFFF) > self.timeout_ms
        )
        self.last_time = now_ms

        if expired or direction == self.direction:
            if expired or self.direction is None:
                self.streak = 0
            self.direction = direction
            self.streak += 1
            self.opposite = 0
            return direction

        # Opposite direction mid-scroll.
        if self.streak < self.threshold:
            self.direction = direction
            self.streak = 1
            self.opposite = 0
            return direction

        self.opposite += 1
        if self.confirm and self.opposite >= self.confirm:
            self.direction = direction
            self.streak = self.opposite
            self.opposite = 0
            return direction

        return self.direction


# --------------------------------------------------------------------------- #
# Win32 plumbing
# --------------------------------------------------------------------------- #

WH_MOUSE_LL = 14
WM_MOUSEWHEEL = 0x020A
WM_QUIT = 0x0012
HC_ACTION = 0
LLMHF_INJECTED = 0x01
INPUT_MOUSE = 0
MOUSEEVENTF_WHEEL = 0x0800
PM_REMOVE = 0x0001
QS_ALLINPUT = 0x04FF
ERROR_ALREADY_EXISTS = 183
WHEEL_DELTA = 120

# Tag on our own injected events so they're recognizable in a debugger/log.
INJECT_TAG = 0x5C401F1C

LRESULT = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.LONG),  # DWORD in the SDK; signed for wheel deltas
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


def _load_win32():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
    user32.SetWindowsHookExW.restype = wintypes.HHOOK
    user32.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
    user32.CallNextHookEx.restype = LRESULT
    user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
    user32.UnhookWindowsHookEx.restype = wintypes.BOOL
    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.SendInput.restype = wintypes.UINT
    user32.PeekMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT)
    user32.PeekMessageW.restype = wintypes.BOOL
    user32.TranslateMessage.argtypes = (ctypes.POINTER(wintypes.MSG),)
    user32.DispatchMessageW.argtypes = (ctypes.POINTER(wintypes.MSG),)
    user32.MsgWaitForMultipleObjects.argtypes = (wintypes.DWORD, ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD, wintypes.DWORD)
    user32.MsgWaitForMultipleObjects.restype = wintypes.DWORD

    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    return user32, kernel32


class ScrollFixer:
    def __init__(self, scroll_filter):
        self.filter = scroll_filter
        self.user32, self.kernel32 = _load_win32()
        self.hook = None
        self.corrected = 0
        # SendInput runs on a worker thread so the hook callback returns fast
        # (Windows silently drops low-level hooks that take too long).
        self.inject_queue = queue.Queue()
        self._proc = HOOKPROC(self._hook_proc)  # keep a reference alive

    def _hook_proc(self, n_code, w_param, l_param):
        try:
            if n_code == HC_ACTION and w_param == WM_MOUSEWHEEL:
                info = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                if not info.flags & LLMHF_INJECTED:
                    delta = ctypes.c_short(info.mouseData >> 16).value
                    if delta:
                        actual = UP if delta > 0 else DOWN
                        wanted = self.filter.process(actual, info.time)
                        if wanted != actual:
                            self.corrected += 1
                            logging.debug("corrected %s -> %s (total %d)",
                                          _name(actual), _name(wanted), self.corrected)
                            self.inject_queue.put(abs(delta) * wanted)
                            return 1  # swallow the bogus tick
        except Exception:
            logging.exception("error in hook callback")
        return self.user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _injector(self):
        while True:
            delta = self.inject_queue.get()
            if delta is None:
                return
            inp = INPUT(type=INPUT_MOUSE)
            inp.mi = MOUSEINPUT(0, 0, delta, MOUSEEVENTF_WHEEL, 0, INJECT_TAG)
            if not self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)):
                logging.warning("SendInput failed (error %d)", ctypes.get_last_error())

    def run(self):
        injector = threading.Thread(target=self._injector, daemon=True)
        injector.start()

        self.hook = self.user32.SetWindowsHookExW(
            WH_MOUSE_LL, self._proc, self.kernel32.GetModuleHandleW(None), 0)
        if not self.hook:
            raise ctypes.WinError(ctypes.get_last_error())
        logging.info("scroll fix running (threshold=%d, timeout=%dms, confirm=%d)",
                     self.filter.threshold, self.filter.timeout_ms, self.filter.confirm)

        msg = wintypes.MSG()
        try:
            # Pump messages (needed for the hook to be called), waking up
            # periodically so Ctrl+C works when run from a console.
            while True:
                self.user32.MsgWaitForMultipleObjects(0, None, False, 250, QS_ALLINPUT)
                while self.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                    if msg.message == WM_QUIT:
                        return
                    self.user32.TranslateMessage(ctypes.byref(msg))
                    self.user32.DispatchMessageW(ctypes.byref(msg))
        except KeyboardInterrupt:
            pass
        finally:
            self.user32.UnhookWindowsHookEx(self.hook)
            self.inject_queue.put(None)
            logging.info("scroll fix stopped (%d ticks corrected)", self.corrected)


def _name(direction):
    return "up" if direction == UP else "down"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Block spurious scroll-wheel reversals.")
    parser.add_argument("--threshold", type=int, default=5,
                        help="ticks in one direction before reversals are blocked (default: 5)")
    parser.add_argument("--timeout", type=int, default=400,
                        help="ms without scrolling that ends a scroll and resets (default: 400)")
    parser.add_argument("--confirm", type=int, default=0,
                        help="accept a reversal after this many opposite ticks in a row; "
                             "0 = only after pausing (default: 0)")
    parser.add_argument("--log", metavar="FILE", help="write log output to FILE")
    parser.add_argument("-v", "--verbose", action="store_true", help="log every corrected tick")
    args = parser.parse_args(argv)

    if sys.platform != "win32":
        parser.error("this program only runs on Windows")

    handlers = []
    if args.log:
        handlers.append(logging.FileHandler(args.log, encoding="utf-8"))
    if sys.stderr is not None:  # None under pythonw.exe
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s",
                        handlers=handlers or [logging.NullHandler()])

    _, kernel32 = _load_win32()
    mutex = kernel32.CreateMutexW(None, False, "Local\\ShittyMouseScrollFix")
    if mutex and ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        logging.info("already running, exiting")
        return 0

    ScrollFixer(ScrollFilter(args.threshold, args.timeout, args.confirm)).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
