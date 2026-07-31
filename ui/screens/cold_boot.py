import time
from rich.panel import Panel
from rich.align import Align
from ui.registry import register_screen
from ui.screens.base import ThreadedWorkerScreen, TransitionSignal, TransitionType
from ui.components.loaders import create_cold_boot_progress, render_cold_boot_frame


@register_screen("cold_boot")
class ColdBootScreen(ThreadedWorkerScreen):
    """Clean screen wrapper for background system hydration with smoothed progress rendering."""

    def __init__(self, engine):
        super().__init__(engine)
        self.page_title = "SYSTEM BOOT"
        self._hydration_started = False
        self.current_progress = 0.0
        self.target_progress = 0.0
        self.worker_finished = False
        self.error_message = None
        self.progress, self.task_id = create_cold_boot_progress()

    def on_enter(self, context: dict, from_pop: bool = False) -> None:
        if not self._hydration_started:
            self._hydration_started = True
            self.current_progress = 0.0
            self.target_progress = 5.0  # Initial nudge to show immediate feedback
            self.worker_finished = False
            self.start_worker(self.engine.broker.hydrate_system)

    def handle_worker_event(self, event: dict) -> bool:
        ev_type = event.get("type")

        if ev_type == "progress":
            current = event.get("current", 0)
            total = event.get("total", 100)
            calculated = (current / total) * 100.0 if total > 0 else 0.0
            self.target_progress = max(self.target_progress, calculated)
            return True

        elif ev_type == "success":
            warnings = event.get("result", [])
            if warnings and any("failed" in str(w).lower() for w in warnings):
                self.error_message = "\n".join(warnings)
                return True
            self.target_progress = 100.0
            self.worker_finished = True
            return True

        elif ev_type == "error":
            self.error_message = event.get("message", "Unknown boot error")
            self.engine._log_error(f"Cold boot worker failed: {self.error_message}")
            return True

        return False

    def handle_input(self, key: str):
        if key == "q":
            return TransitionSignal(TransitionType.QUIT), True
        return None, False

    def render(self):
        if self.error_message:
            return Panel(
                Align.center(f"[bold red]Hydration Error:[/bold red]\n{self.error_message}"),
                title="[bold red] BOOT FAILURE [/bold red]",
                border_style="red"
            )

        if self.current_progress < self.target_progress:
            diff = self.target_progress - self.current_progress
            step = max(0.5, diff * 0.15)  # Ease-out progression curve
            self.current_progress = min(self.target_progress, self.current_progress + step)

        if self.worker_finished and self.current_progress >= 99.5:
            self.current_progress = 100.0
            self.progress.update(self.task_id, completed=100)
            time.sleep(0.25)  # Brief pause so the complete bar state is visible
            self.engine._apply_transition(
                TransitionSignal(TransitionType.PUSH, "component_list")
            )

        self.progress.update(self.task_id, completed=int(self.current_progress))
        return render_cold_boot_frame(self.progress)