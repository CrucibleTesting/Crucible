import sys
import os
import queue
import threading
import time
import re

class CommercialInputDriver:
    """Enterprise-Grade Native Input Driver with comprehensive ANSI token parsing."""
    def __init__(self, out_queue: queue.Queue):
        self.out_queue = out_queue
        self._running = False
        self._thread = None
        self._is_win = sys.platform.startswith("win")
        self._key_map = {
            "enter": "enter",
            "\r": "enter",
            "\n": "enter",
            "q": "q",
            " ": " ",
            "\x1b": "escape"
        }
        self._orig_win_mode = None
        self._win_lock = threading.Lock()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen, daemon=True, name="CrucibleInputDriver")
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._restore_win_console_mode()

    def _restore_win_console_mode(self):
        """Safely restores the original Windows console flags exactly once."""
        if self._is_win:
            with self._win_lock:
                if self._orig_win_mode is not None:
                    try:
                        import ctypes
                        kernel32 = ctypes.windll.kernel32
                        h_input = kernel32.GetStdHandle(-10)
                        kernel32.SetConsoleMode(h_input, self._orig_win_mode)
                    except Exception:
                        pass
                    self._orig_win_mode = None

    def _listen(self):
        if self._is_win:
            import msvcrt
            import ctypes
            
            try:
                kernel32 = ctypes.windll.kernel32
                h_input = kernel32.GetStdHandle(-10)
                mode = ctypes.c_ulong()
                kernel32.GetConsoleMode(h_input, ctypes.byref(mode))
                with self._win_lock:
                    self._orig_win_mode = mode.value
                kernel32.SetConsoleMode(h_input, mode.value & ~0x0002 & ~0x0004)
            except Exception:
                pass

            try:
                while self._running:
                    if msvcrt.kbhit():
                        ch = msvcrt.getch()
                        if ch in (b"\x00", b"\xe0"):
                            arr = msvcrt.getch()
                            maps = {b"H": "up", b"P": "down", b"K": "left", b"M": "right"}
                            if arr in maps:
                                self.out_queue.put(("input", maps[arr]))
                        else:
                            try:
                                key_str = ch.decode("utf-8")
                                if key_str in self._key_map:
                                    self.out_queue.put(("input", self._key_map[key_str]))
                                elif key_str.isalnum():
                                    self.out_queue.put(("input", key_str.lower()))
                            except Exception:
                                pass
                    time.sleep(0.01)
            finally:
                self._restore_win_console_mode()
        else:
            import select
            
            fd = sys.stdin.fileno()
            # Captures any ANSI CSI escape sequences (\x1b[...] up to any terminal command character A-Z, a-z)
            ansi_splitter = re.compile(r"(\x1b\[[\d;]*[A-Za-z])")
            ansi_maps = {"\x1b[A": "up", "\x1b[B": "down", "\x1b[D": "left", "\x1b[C": "right"}

            while self._running:
                try:
                    rlist, _, _ = select.select([fd], [], [], 0.02)
                    if rlist:
                        raw_bytes = os.read(fd, 1024)
                        if not raw_bytes:
                            continue
                        
                        data = raw_bytes.decode("utf-8", errors="ignore")
                        tokens = [t for t in ansi_splitter.split(data) if t]
                        
                        for token in tokens:
                            if token.startswith("\x1b["):
                                if token in ansi_maps:
                                    self.out_queue.put(("input", ansi_maps[token]))
                                # Unmapped macro codes are discarded to stop ghost escape triggers
                                continue
                            
                            for ch in token:
                                if ch in self._key_map:
                                    self.out_queue.put(("input", self._key_map[ch]))
                                elif ch.isalnum():
                                    self.out_queue.put(("input", ch.lower()))
                except Exception:
                    pass
                time.sleep(0.005)