import json
import sys
import os
import queue
import threading
import time
import re
from rich.layout import Layout
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
from rich.syntax import Syntax
from ui.screens.base import Screen, TransitionSignal, TransitionType
from ui.registry import register_screen

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
            "\t": "tab",
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
                                continue
                            
                            for ch in token:
                                if ch in self._key_map:
                                    self.out_queue.put(("input", self._key_map[ch]))
                                elif ch.isalnum():
                                    self.out_queue.put(("input", ch.lower()))
                except Exception:
                    pass
                time.sleep(0.005)


@register_screen("cluster_review")
class ClusterReviewScreen(Screen):
    def __init__(self, engine):
        super().__init__(engine)
        self.page_title = "CLUSTER SAMPLE INSPECTION"
        self.cluster_id = None
        self.samples = []
        self.selected_index = 0
        self.json_scroll_offset = 0
        self.json_expansion_depth = 1  # Collapsed initially, adjustable via ←/→

    def on_enter(self, context: dict, from_pop: bool = False) -> None:
        if not from_pop:
            self.selected_index = 0
            self.json_scroll_offset = 0
            self.json_expansion_depth = 1
            self.cluster_id = self.ctx.get("current_cluster_id", "Unassigned")
            self.page_title = f"CLUSTER REVIEW - {self.cluster_id}"
            
            raw_adapter = self.ctx.get("current_adapter", "UNKNOWN")
            self.component = raw_adapter.lower().replace("_", "-")
            
            try:
                result = self.engine.broker.get_cluster_samples(self.component, self.cluster_id)
                if isinstance(result, dict):
                    self.samples = result.get("samples", result.get("cases", []))
                elif isinstance(result, list):
                    self.samples = result
                else:
                    self.samples = []
            except Exception as e:
                self.samples = []
                if hasattr(self.engine, "_log_error"):
                    self.engine._log_error(f"Failed to fetch cluster samples for {self.component}/{self.cluster_id}: {e}")

    def get_menu_hints(self):
        return {
            "p": "Promote",
            "r": "Reject",
            "Esc": "Back",
            "q": "Quit"
        }

    def _format_compact_json(self, obj, max_depth, indent=4, current_depth=0, current_indent=0):
        """Recursively formats JSON with inline primitive lists and depth limits."""
        space = " " * current_indent
        next_space = " " * (current_indent + indent)
        
        if current_depth >= max_depth:
            if isinstance(obj, dict):
                return "{...}"
            elif isinstance(obj, list):
                return "[...]"
            return json.dumps(obj)

        if isinstance(obj, dict):
            if not obj:
                return "{}"
            items = []
            for k, v in obj.items():
                formatted_val = self._format_compact_json(v, max_depth, indent, current_depth + 1, current_indent + indent)
                items.append(f'{next_space}"{k}": {formatted_val.lstrip()}')
            return "{\n" + ",\n".join(items) + f"\n{space}}}"
        
        elif isinstance(obj, list):
            if not obj:
                return "[]"
            if all(not isinstance(item, (dict, list)) for item in obj):
                inline_str = json.dumps(obj)
                if len(inline_str) < 60:
                    return inline_str
            
            items = []
            for item in obj:
                formatted_val = self._format_compact_json(item, max_depth, indent, current_depth + 1, current_indent + indent)
                items.append(f'{next_space}{formatted_val.lstrip()}')
            return "[\n" + ",\n".join(items) + f"\n{space}]"
        
        else:
            return json.dumps(obj)

    def render(self):
        # Left Panel: Sample Tray Table with clean highlighting
        left_table = Table(
            expand=True,
            box=None,
            padding=(0, 1),
            show_header=True,
            header_style="bold bright_white",
        )
        left_table.add_column("", width=2)
        left_table.add_column("", ratio=1)

        selected_style = Style(color="cyan", bold=True)
        unselected_style = Style(color="white")

        if not self.samples:
            left_table.add_row(" ", "[dim]No samples[/dim]", style="dim")
        else:
            for idx, sample in enumerate(self.samples):
                is_sel = (idx == self.selected_index)
                row_style = selected_style if is_sel else unselected_style
                
                # Standardized enumerated test case naming
                s_id = f"Case {idx + 1}"
                
                if is_sel:
                    pointer_text = Text("▶ ", style="bold cyan")
                else:
                    pointer_text = Text("  ", style="dim")
                    
                left_table.add_row(pointer_text, s_id, style=row_style)

        # Left Panel: Dynamic count title and white cycle subtitle
        left_panel = Panel(
            left_table,
            title=f"[bold cyan]{len(self.samples)} Samples[/bold cyan]",
            subtitle="[white][Space] Cycle[/white]",
            subtitle_align="center",
            border_style="cyan",
            padding=(1, 1)
        )

        # Right Panel: Filtered Specimen Inspector
        if self.samples and 0 <= self.selected_index < len(self.samples):
            current_sample = self.samples[self.selected_index]
            payload = current_sample.get("semantic_root", current_sample.get("payload", current_sample))
            
            if isinstance(payload, dict):
                filtered_payload = {
                    k: v for k, v in payload.items() 
                    if k.lower() in ("input", "snapshot")
                }
                if not filtered_payload:
                    filtered_payload = payload
            else:
                filtered_payload = payload

            json_str = self._format_compact_json(filtered_payload, self.json_expansion_depth)
            json_lines = json_str.splitlines()
            total_lines = len(json_lines)
            
            max_offset = max(0, total_lines - 15)
            self.json_scroll_offset = max(0, min(self.json_scroll_offset, max_offset))
            
            visible_lines = json_lines[self.json_scroll_offset : self.json_scroll_offset + 22]
            visible_json_str = "\n".join(visible_lines)
            
            right_content = Syntax(visible_json_str, "json", theme="monokai", background_color="default")
        else:
            right_content = Text("No sample selected or tray is empty.", style="dim")

        # Right Panel: Electric blue title and border with white nav subtitle
        right_subtitle = f"[white] ↑/↓ Scroll │ ←/→ Depth[/white]"
        right_panel = Panel(
            right_content,
            title="[bold cyan]Semantic Root Inspector[/bold cyan]",
            subtitle=right_subtitle,
            subtitle_align="right",
            border_style="cyan",
            padding=(1, 2)
        )

        main_layout = Layout()
        main_layout.split_row(
            Layout(left_panel, size=32),
            Layout(right_panel, ratio=1)
        )

        return self.assemble_layout(main_layout)

    def handle_input(self, key: str):
        # Right panel navigation / scrolling / depth controls
        if key == "up":
            self.json_scroll_offset = max(0, self.json_scroll_offset - 1)
            return None, True

        if key == "down":
            self.json_scroll_offset += 1
            return None, True

        if key == "right":
            self.json_expansion_depth += 1
            self.json_scroll_offset = 0
            return None, True

        if key == "left":
            self.json_expansion_depth = max(1, self.json_expansion_depth - 1)
            self.json_scroll_offset = 0
            return None, True

        # Left panel interaction: Space cycles through sample items
        if key == " ":
            if self.samples:
                self.selected_index = (self.selected_index + 1) % len(self.samples)
                self.json_scroll_offset = 0
            return None, True

        if key == "p":
            if self.cluster_id and self.cluster_id != "Unassigned":
                try:
                    if hasattr(self.engine.broker, "promote_cluster"):
                        self.engine.broker.promote_cluster(self.component, self.cluster_id)
                    return TransitionSignal(TransitionType.POP), True
                except Exception as e:
                    if hasattr(self.engine, "_log_error"):
                        self.engine._log_error(f"Failed to promote cluster {self.cluster_id}: {e}")
            return None, True

        if key == "r":
            if self.cluster_id and self.cluster_id != "Unassigned":
                try:
                    if hasattr(self.engine.broker, "reject_cluster"):
                        self.engine.broker.reject_cluster(self.component, self.cluster_id)
                    return TransitionSignal(TransitionType.POP), True
                except Exception as e:
                    if hasattr(self.engine, "_log_error"):
                        self.engine._log_error(f"Failed to reject cluster {self.cluster_id}: {e}")
                    return None, True
            return None, True

        # Back and Quit
        if key == "escape":
            return TransitionSignal(TransitionType.POP), True

        if key == "q":
            return TransitionSignal(TransitionType.QUIT), True

        return None, False