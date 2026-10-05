import os
import time
from rich.layout import Layout
from rich.table import Table
from rich.panel import Panel
from rich.style import Style
from rich.text import Text
from rich.align import Align
from ui.screens.base import Screen, TransitionSignal, TransitionType
from ui.registry import register_screen


@register_screen("component_dashboard")
class ComponentDashboardScreen(Screen):
    def __init__(self, engine):
        super().__init__(engine)
        self.page_title = "COMPONENT MENU"
        self.selected_component = "None"
        self.status_message = ""
        self.status_type = "info"  # "info", "success", "warning", "error"
        self.options = [
            {"name": "Open Candidate Pool File", "status": "External Editor"},
            {"name": "Run Staging", "status": "Idle"},
            {"name": "Cluster Review", "status": "Available"},
        ]
        self.selected_index = 0
        self._last_mtime = None
        self._last_sync_time = 0.0  # Debounce timestamp tracker
        self._watched_file = None

    def on_enter(self, context: dict, from_pop: bool = False) -> None:
        if not from_pop:
            self.selected_index = 0
            self.status_message = ""
            self.selected_component = self.ctx.get("current_adapter", "UNKNOWN")
            self._last_mtime = None
            self._last_sync_time = 0.0
            self._watched_file = None

    def set_status(self, message: str, msg_type: str = "success") -> None:
        """Standardized helper to set flash messages."""
        self.status_message = message
        self.status_type = msg_type

    def _check_auto_sync(self):
        """
        Polls watched file for disk modification events with a 0.5s debounce guard.
        Handles empty or malformed files gracefully with warning banners.
        """
        if not self._watched_file or not self._watched_file.exists():
            return

        now = time.time()
        # Debounce: Ensure at least 0.5s between auto-sync runs
        if now - self._last_sync_time < 0.5:
            return

        try:
            current_mtime = self._watched_file.stat().st_mtime
            if self._last_mtime is not None and current_mtime > self._last_mtime:
                self._last_mtime = current_mtime
                self._last_sync_time = now

                stats = self.engine.broker.sync_candidate_pool(self.selected_component)
                
                if stats["unique_count"] == 0:
                    self.set_status(
                        "⚠️ File saved, but candidate pool is empty!", 
                        msg_type="warning"
                    )
                else:
                    self.set_status(
                        f"⚡ Auto-Synced on Save! {stats['unique_count']} entries "
                        f"({stats['removed_duplicates']} duplicate(s) merged).",
                        msg_type="success"
                    )
        except Exception as e:
            self.set_status(f"❌ Read Error during auto-sync: {e}", msg_type="error")

    def _render_flash_message(self):
        """Standardised bottom-centered flash message component."""
        if not self.status_message:
            return Text("")

        style_map = {
            "info": "bold #00F0FF",
            "success": "bold green",
            "warning": "bold yellow",
            "error": "bold red",
        }
        style = style_map.get(self.status_type, "bold green")
        return Align.center(Text(f" {self.status_message} ", style=style))

    def render(self):
        self._check_auto_sync()

        # 1. Action items table
        options_table = Table(
            expand=True,
            border_style="border_muted",
            box=None,
            padding=(0, 2),
        )
        options_table.add_column("SELECT", width=6, justify="center")
        options_table.add_column("ACTION / WORKFLOW", ratio=1, justify="left")
        options_table.add_column("STATUS", width=20, justify="right")

        selected_style = Style(color="#00F0FF", bold=True, reverse=True)
        unselected_style = Style(color="#F5F5F7", dim=False)

        for idx, item in enumerate(self.options):
            selector, row_style = ("▶", selected_style) if idx == self.selected_index else (" ", unselected_style)
            options_table.add_row(selector, item["name"], item["status"], style=row_style)

        # 2. Split vertical space cleanly using Layout
        content_layout = Layout()
        content_layout.split_column(
            Layout(name="menu", ratio=1),
            Layout(name="status", size=1)
        )

        # Disable all region borders/titles
        content_layout["menu"].show_border = False
        content_layout["status"].show_border = False

        # Assign renderables explicitly
        content_layout["menu"].update(options_table)
        content_layout["status"].update(self._render_flash_message())

        return self.assemble_layout(
            Panel(
                content_layout,
                title=f"[bold primary] {self.selected_component.upper()} ACTIONS [/bold primary]",
                title_align="center",
                border_style="border_active",
                padding=(1, 2)
            )
        )

    def handle_input(self, key: str):
        if key == "up":
            self.selected_index = (self.selected_index - 1) % len(self.options)
            return None, True

        if key == "down":
            self.selected_index = (self.selected_index + 1) % len(self.options)
            return None, True

        if key in ("left", "escape", "b"):
            return TransitionSignal(TransitionType.POP), True

        if key == "enter":
            chosen_action = self.options[self.selected_index]["name"]

            if "Open Candidate Pool" in chosen_action:
                pool_path = self.engine.broker.open_candidate_pool_in_editor(self.selected_component)
                self._watched_file = pool_path
                self._last_mtime = pool_path.stat().st_mtime if pool_path.exists() else 0
                self.set_status(f"📂 Opened {pool_path.name}. Auto-sync active on save.", msg_type="info")
                return None, True

            if chosen_action == "Run Staging":
                return TransitionSignal(TransitionType.PUSH, "run_staging"), True

            # ADD THIS DISPATCH FOR CLUSTER REVIEW: CHANGE TO REVERT TO NON TEST VERSION
            if chosen_action == "Cluster Review":
                return TransitionSignal(TransitionType.PUSH, "cluster_selection"), True

            return None, True

        if key == "q":
            return TransitionSignal(TransitionType.QUIT), True

        return None, False

    def get_menu_hints(self):
        return {"↑/↓": "Cycle", "Enter": "Select", "←": "Back", "q": "Quit"}