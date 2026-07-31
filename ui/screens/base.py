from abc import ABC, abstractmethod
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, Tuple, Dict
import threading
import time
from rich.layout import Layout
from rich.panel import Panel
from rich.padding import Padding
from rich.text import Text
from rich.align import Align

class TransitionType(Enum):
    NONE = auto()
    PUSH = auto()
    POP = auto()
    QUIT = auto()

@dataclass(frozen=True)
class TransitionSignal:
    type: TransitionType
    screen_key: Optional[str] = None

class Screen(ABC):
    def __init__(self, engine):
        self.engine = engine
        self.ctx = engine.ctx

    def on_enter(self, context: dict, from_pop: bool = False) -> None:
        pass

    def on_exit(self) -> dict:
        return {}

    def get_menu_hints(self) -> Dict[str, str]:
        return {"q": "Quit"}

    def get_title(self) -> str:
        return self.engine.current_key.upper()

    def get_header(self) -> Padding:
        #screen_title = self.get_title()
        screen_title = self.page_title
        header_text = Text()
        header_text.append(" CRUCIBLE ", style="bold primary")
        header_text.append(f"│ {screen_title} ", style="border_active")
        return Padding(header_text, (1, 0, 1, 0))

    def get_footer(self) -> Padding:
        footer_text = Text()
        hints = self.get_menu_hints()
        for i, (key, label) in enumerate(hints.items()):
            if i > 0:
                footer_text.append("    ")
            display_key = "Enter" if key == "enter" else ("←" if key in ("left", "back") else key)
            footer_text.append(f"[{display_key}]", style="bold primary")
            footer_text.append(f" {label}")
        return Padding(Align.center(footer_text), (1, 0, 1, 0))

    def assemble_layout(self, body_renderable) -> Layout:
        root_layout = Layout()
        root_layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=3)
        )
        root_layout["header"].update(self.get_header())
        root_layout["body"].update(body_renderable)
        root_layout["footer"].update(self.get_footer())
        return root_layout

    @abstractmethod
    def render(self):
        pass

    @abstractmethod
    def handle_input(self, key: str) -> Tuple[Optional[TransitionSignal], bool]:
        pass

class ThreadedWorkerScreen(Screen):
    def __init__(self, engine):
        super().__init__(engine)
        self.worker_thread: threading.Thread | None = None
        self._state_lock = threading.Lock()  # Protects local screen properties from rendering race conditions
        self.is_processing = False

    def start_worker(self, target_function, *args, **kwargs):
        with self._state_lock:
            if self.is_processing:
                return
            self.is_processing = True

        # def wrapper():
        #     try:
        #         last_update = 0.0
        #         def progress_bridge(current, total):
        #             nonlocal last_update
        #             now = time.time()
        #             if (now - last_update > 0.05) or (current == total):
        #                 self.engine.event_queue.put(("worker", {"type": "progress", "current": current, "total": total}))
        #                 self.engine.event_queue.put(("render_request", None))
        #                 last_update = now

        #         result = target_function(progress_bridge, *args, **kwargs)
        #         self.engine.event_queue.put(("worker", {"type": "success", "result": result}))
        #         self.engine.event_queue.put(("render_request", None))
        #     except Exception as e:
        #         self.engine.event_queue.put(("worker", {"type": "error", "message": str(e)}))
        #         self.engine.event_queue.put(("render_request", None))

        def wrapper():
            try:
                last_update = 0.0
                def progress_bridge(current, total):
                    nonlocal last_update
                    now = time.time()
                    if (now - last_update > 0.05) or (current == total):
                        self.engine.event_queue.put(("worker", {"type": "progress", "current": current, "total": total}))
                        self.engine.event_queue.put(("render_request", None))
                    last_update = now
                    
                # Run the real pipeline
                result = target_function(progress_bridge, *args, **kwargs)
                self.engine.event_queue.put(("worker", {"type": "success", "result": result}))
            except Exception as e:
                # Crucial: Push the error to the event queue so the UI unlocks and displays it!
                self.engine.event_queue.put(("worker", {"type": "error", "message": str(e)}))
            finally:
                self.engine.event_queue.put(("render_request", None))

        self.worker_thread = threading.Thread(target=wrapper, daemon=True)
        self.worker_thread.start()

    def handle_worker_event(self, event: dict) -> bool:
        return False