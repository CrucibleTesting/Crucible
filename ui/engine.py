import sys
import os
import time
import traceback
import queue
import signal
import atexit
import threading
from pathlib import Path
from typing import Any
from rich.live import Live
from rich.panel import Panel
from rich.align import Align
from ui.theme import console
from ui.context import AppContext
from ui.io.keyboard import CommercialInputDriver
from ui.screens.base import TransitionType
from ui.registry import SCREEN_REGISTRY, SCREEN_CACHE
import ui.screens


class SimpleEngine:
    def __init__(self, broker: Any, initial_screen: str = "component_list", max_crashes=3):
        self.broker = broker
        self.running = True
        self._engine_lock = threading.RLock()
        self._stack = []
        self._keys = []
        self.initial_screen = initial_screen
        self._last_key = None
        self._crashes = 0
        self._max_crashes = max_crashes
        self._log_path = Path("ui_runtime.log")
        self.ctx = AppContext()
        self.event_queue = queue.Queue()
        self.input_driver = CommercialInputDriver(self.event_queue)
        self.last_size = console.size
        self._debounce = 0.1
        self._last_resize_time = 0.0
        self._is_win = sys.platform.startswith("win")
        self._fps_cap = 0.033  # ~30 FPS frame loop
        self._last_frame_time = 0.0
        self._saved_termios_settings = None
        self._restored = False
        self._initialize_terminal_environment()
        atexit.register(self._force_terminal_restore)
        self._setup_signal_traps()

    def _initialize_terminal_environment(self):
        """Configures standard inputs/outputs for raw character tracking."""
        if not self._is_win:
            import termios
            try:
                fd = sys.stdin.fileno()
                self._saved_termios_settings = termios.tcgetattr(fd)
                new_settings = termios.tcgetattr(fd)
                new_settings[3] = new_settings[3] & ~termios.ICANON & ~termios.ECHO
                termios.tcsetattr(fd, termios.TCSANOW, new_settings)
            except Exception:
                pass
        else:
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            except Exception:
                pass

    def _main_frame_loop(self):
        """The core full-screen interactive loop handling views, updates, and key reads."""
        self._push(self.initial_screen, {})
        self.input_driver.start()

        with Live(console=console, screen=True, auto_refresh=False) as live:
            while self.running:
                needs_render = False
                now = time.time()

                # Always trigger a render tick if enough time has passed for an animation frame
                if (now - self._last_frame_time) >= self._fps_cap:
                    needs_render = True

                try:
                    event_packet = self.event_queue.get(timeout=0.01)
                    ev_type, payload = event_packet
                    if ev_type == "input":
                        self._last_key = payload
                        active_screen = self.active
                        if active_screen:
                            try:
                                sig, dirty = active_screen.handle_input(payload)
                                if self._apply_transition(sig) or dirty:
                                    needs_render = True
                            except RuntimeError as e:
                                self._log_error(f"Atomic mutation error captured: {str(e)}")
                                needs_render = True
                    elif ev_type in ("resize", "render_request"):
                        needs_render = True
                    elif ev_type == "worker":
                        active_screen = self.active
                        if active_screen and hasattr(active_screen, "handle_worker_event"):
                            if active_screen.handle_worker_event(payload):
                                needs_render = True
                except queue.Empty:
                    if self._check_resize():
                        needs_render = True
                except Exception:
                    self._crashes += 1
                    self._log_error("Captured internal frame execution failure")
                    if self._crashes >= self._max_crashes:
                        self.running = False

                active_view = self.active
                if needs_render and self.running and active_view:
                    if self.last_size.height < 12 or self.last_size.width < 50:
                        live.update(
                            Panel(Align.center("[red]Terminal viewport too small![/red]", vertical="middle")),
                            refresh=True
                        )
                    else:
                        live.update(active_view.render(), refresh=True)
                    self._last_frame_time = time.time()

    def run(self):
        """Orchestrates initialization steps and boots the interactive interface."""
        try:
            self._main_frame_loop()
        except Exception as e:
            self._log_error(f"Fatal Engine Breakdown: {str(e)}")
            raise

    @property
    def active(self):
        with self._engine_lock:
            return self._stack[-1] if self._stack else None

    @property
    def current_key(self):
        with self._engine_lock:
            return self._keys[-1] if self._keys else "UNINITIALIZED"

    def _setup_signal_traps(self):
        def handle_signal(signum, frame):
            self.running = False
            self._force_terminal_restore()
            sys.exit(0)

        if not self._is_win:
            signal.signal(signal.SIGINT, handle_signal)
            signal.signal(signal.SIGTERM, handle_signal)

    def _force_terminal_restore(self):
        with self._engine_lock:
            if self._restored:
                return
            self._restored = True
            if hasattr(self, 'input_driver') and self.input_driver:
                self.input_driver.stop()
            if not self._is_win and self._saved_termios_settings:
                import termios
                try:
                    termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, self._saved_termios_settings)
                except Exception:
                    pass
            sys.stdout.write("\x1b[?25h")
            sys.stdout.flush()

    def _log_error(self, message):
        entry = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\nActive: {self.current_key}\n{traceback.format_exc()}\n" + ("=" * 60) + "\n"
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass

    def _check_resize(self) -> bool:
        now = time.time()
        size = console.size
        if (size.width, size.height) != (self.last_size.width, self.last_size.height):
            if (now - self._last_resize_time) > self._debounce:
                self.last_size = size
                self._last_resize_time = now
                return True
        return False

    def _push(self, key, context):
        with self._engine_lock:
            if key not in SCREEN_REGISTRY:
                raise RuntimeError(
                    f"Screen '{key}' not found in SCREEN_REGISTRY. "
                    f"Registered keys: {list(SCREEN_REGISTRY.keys())}"
                )
            if key not in SCREEN_CACHE:
                SCREEN_CACHE[key] = SCREEN_REGISTRY[key](self)
            screen = SCREEN_CACHE[key]
            self._stack.append(screen)
            self._keys.append(key)
            screen.on_enter(context, from_pop=False)

    def _pop(self):
        with self._engine_lock:
            if len(self._stack) <= 1:
                self.running = False
                return {}
            old = self._stack.pop()
            popped_key = self._keys.pop()
            if popped_key in SCREEN_CACHE:
                del SCREEN_CACHE[popped_key]
            ctx = old.on_exit() or {}
            if self.active:
                self.active.on_enter(ctx, from_pop=True)
            return ctx

    def _apply_transition(self, signal_obj):
        if not signal_obj:
            return False
        match signal_obj.type:
            case TransitionType.QUIT:
                self.running = False
                return True
            case TransitionType.POP:
                self._pop()
                return True
            case TransitionType.PUSH:
                self._push(signal_obj.screen_key, {})
                return True
        return False