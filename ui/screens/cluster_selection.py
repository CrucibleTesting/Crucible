from rich.table import Table
from rich.panel import Panel
from rich.style import Style
from rich.text import Text
from ui.screens.base import Screen, TransitionSignal, TransitionType
from ui.registry import register_screen

@register_screen("cluster_selection")
class ClusterSelectionScreen(Screen):
    def __init__(self, engine):
        super().__init__(engine)
        self.selected_component = "UNKNOWN"
        self.clusters = []
        self.selected_index = 0
        self.show_suppressed = False
        self.active_count = 0
        self.suppressed_count = 0

    def on_enter(self, context: dict, from_pop: bool = False) -> None:
        raw_adapter = self.ctx.get("current_adapter", "UNKNOWN")
        self.selected_component = raw_adapter.lower().replace("_", "-")
        self.page_title = f"{self.selected_component.upper()} - CLUSTER SELECTION"
        self._load_data()
        if not from_pop or self.selected_index >= len(self.clusters):
            self.selected_index = 0

    def _load_data(self):
        raw_clusters = self.engine.broker.get_cluster_table(self.selected_component)
        self.active_count = len([
            c for c in raw_clusters
            if c.get("state", "pending") not in ("accepted", "promoted", "gold", "rejected")
        ])
        self.suppressed_count = self.engine.broker.get_suppressed_cluster_count(self.selected_component)

        if self.show_suppressed:
            self.clusters = self.engine.broker.get_suppressed_cluster_table(self.selected_component)
        else:
            self.clusters = [
                c for c in raw_clusters
                if c.get("state", "pending") not in ("accepted", "promoted", "gold", "rejected")
            ]

    def get_menu_hints(self):
        if self.show_suppressed:
            return {"↑/↓": "Cycle", "Enter": "Unsuppress", "←": "Back", "q": "Quit"}
        return {"↑/↓": "Cycle", "Enter": "Select", "←": "Back", "q": "Quit"}

    def render(self):
        mode_label = "[red]SUPPRESSED CLUSTERS[/red]" if self.show_suppressed else "[green]ACTIVE CLUSTERS[/green]"
        border_color = "red" if self.show_suppressed else "green"

        table = Table(
            expand=True,
            border_style="dim white",
            box=None,
            padding=(0, 1),
            show_header=True,
            header_style="bold bright_white",
        )
        table.add_column("", width=2, justify="center")
        table.add_column("CLUSTER ID", ratio=3, justify="left")
        table.add_column("TOTAL CASES", ratio=1, justify="right")

        selected_style = Style(color="cyan", bold=True)
        unselected_style = Style(color="white")

        if not self.clusters:
            msg = "No suppressed clusters found" if self.show_suppressed else "No pending clusters found"
            table.add_row("", msg, "[dim]0[/dim]", style="dim")
        else:
            for idx, item in enumerate(self.clusters):
                is_sel = (idx == self.selected_index)
                row_style = selected_style if is_sel else unselected_style
                
                pointer = Text("▶ ", style="bold cyan") if is_sel else Text("  ", style="dim")
                cid = str(item["cluster_id"])
                cases_str = f"{item['count']} cases"
                
                table.add_row(pointer, cid, cases_str, style=row_style)

        view_toggle_label = "Active View" if self.show_suppressed else "Suppressed View"
        subtitle = f"[dim][green]Active:[/green] [bold white]{self.active_count}[/bold white]  │  [red]Suppressed:[/red] [bold white]{self.suppressed_count}[/bold white][/dim]  │  [bold white][S] - {view_toggle_label}[/bold white]"
        
        return self.assemble_layout(
            Panel(
                table,
                title=mode_label,
                subtitle=subtitle,
                subtitle_align="center",
                title_align="center",
                border_style=border_color,
                padding=(1, 2),
            )
        )

    def handle_input(self, key: str):
        if key == "up":
            if self.clusters:
                self.selected_index = (self.selected_index - 1) % len(self.clusters)
            return None, True
        if key == "down":
            if self.clusters:
                self.selected_index = (self.selected_index + 1) % len(self.clusters)
            return None, True
        if key == "s":
            self.show_suppressed = not self.show_suppressed
            self.selected_index = 0
            self._load_data()
            return None, True
        if key == "enter":
            if self.clusters:
                chosen_cluster = self.clusters[self.selected_index]
                cluster_id = chosen_cluster.get("cluster_id")
                if self.show_suppressed:
                    self.engine.broker.unreject_cluster(self.selected_component, cluster_id)
                    self._load_data()
                    self.selected_index = min(self.selected_index, max(0, len(self.clusters) - 1))
                else:
                    self.ctx.set("current_cluster_id", cluster_id)
                    return TransitionSignal(TransitionType.PUSH, "cluster_review"), True
            return None, True
        if key in ("left", "escape", "b"):
            return TransitionSignal(TransitionType.POP), True
        if key == "q":
            return TransitionSignal(TransitionType.QUIT), True
        return None, False