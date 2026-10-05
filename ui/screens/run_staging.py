import time
from rich.panel import Panel
from rich.align import Align
from rich.console import Group
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.table import Table

from ui.registry import register_screen
from ui.screens.base import ThreadedWorkerScreen, TransitionSignal, TransitionType
from ui.theme import console


@register_screen("run_staging")
class RunStagingScreen(ThreadedWorkerScreen):
    """Executes the pipeline runner with real-time feedback and results display."""

    def __init__(self, engine):
        super().__init__(engine)
        self.page_title = "STAGING RUNNER"
        self.selected_component = "UNKNOWN"
        self.is_running = False
        self.is_complete = False
        self.error_message = None
        self.results = None

        self.progress = Progress(
            SpinnerColumn(spinner_name="dots2", style="primary"),
            TextColumn("[primary]{task.description}[/primary]"),
            BarColumn(bar_width=40, style="border_muted", complete_style="primary"),
            TextColumn("[bold body]{task.completed}%[/bold body]"),
            console=console,
            transient=False,
        )
        self.task_id = self.progress.add_task("Running staging pipeline...", total=100)

    def on_enter(self, context: dict, from_pop: bool = False) -> None:
        if not from_pop:
            self.selected_component = self.ctx.get("current_adapter", "UNKNOWN")
            self.is_running = True
            self.is_complete = False
            self.error_message = None
            self.results = None
            self.progress.reset(self.task_id, completed=0, total=100)

            def pipeline_runner(progress_callback):
                return self.engine.broker.run_pipeline(
                    component_id=self.selected_component,
                    progress_callback=progress_callback,
                )

            self.start_worker(pipeline_runner)

    def handle_worker_event(self, event: dict) -> bool:
        ev_type = event.get("type")

        if ev_type == "progress":
            current = event.get("current", 0)
            total = event.get("total", 100)
            pct = int((current / total) * 100) if total > 0 else 0
            self.progress.update(self.task_id, completed=pct)
            return True

        elif ev_type == "success":
            self.is_running = False
            self.is_complete = True
            self.results = event.get("result", {})
            self.progress.update(self.task_id, completed=100)
            return True

        elif ev_type == "error":
            self.is_running = False
            self.error_message = event.get("message", "Unknown execution pipeline error.")
            self.engine._log_error(f"Run staging pipeline failed: {self.error_message}")
            return True

        return False

    def render_summary_table(self):
        table = Table(expand=True, border_style="border_muted", box=None, padding=(0, 2))
        table.add_column("METRIC / RESULT", ratio=1, justify="left", style="primary")
        table.add_column("VALUE", ratio=1, justify="right", style="body")

        if isinstance(self.results, dict):
            for k, v in self.results.items():
                table.add_row(str(k).upper(), str(v))

        return Panel(
            table,
            title="[bold success] STAGING SUMMARY [/bold success]",
            border_style="success",
            padding=(1, 2),
        )

    def render(self):
        # 1. Error View
        if self.error_message:
            content = Group(
                Align.center(f"[bold error]Execution Error:[/bold error]\n\n{self.error_message}"),
                "\n",
                Align.center("[dim]Press [b]Enter[/b] or [b]←[/b] to return.[/dim]"),
            )
            return self.assemble_layout(
                Panel(content, title="[bold error] STAGING FAILED [/bold error]", border_style="error")
            )

        # 2. Completion View
        if self.is_complete:
            return self.assemble_layout(self.render_summary_table())

        # 3. Active Running View (Loader)
        content = Group(
            Align.center(f"\n[bold primary]GENERATING SNAPSHOTS[/bold primary]"),
            Align.center(f"[dim]Component: {self.selected_component}[/dim]\n\n"),
            Align.center(self.progress),
        )
        return self.assemble_layout(
            Panel(
                content,
                title="[bold primary] PIPELINE RUNNING [/bold primary]",
                border_style="border_active",
            )
        )

    def handle_input(self, key: str):
        if key in ("left", "escape", "b", "enter") and not self.is_running:
            return TransitionSignal(TransitionType.POP), True
        if key == "q":
            return TransitionSignal(TransitionType.QUIT), True
        return None, False

    def get_menu_hints(self):
        if self.is_running:
            return {"q": "Quit"}
        return {"←": "Back", "q": "Quit"}