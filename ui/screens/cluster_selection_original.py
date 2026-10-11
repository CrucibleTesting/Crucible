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
        self.page_title = "CLUSTER SELECTION"
        self.selected_component = "UNKNOWN"
        self.clusters = []
        self.selected_index = 0

    def on_enter(self, context: dict, from_pop: bool = False) -> None:
        # Always fetch fresh clusters on enter or return (pop)
        raw_adapter = self.ctx.get("current_adapter", "UNKNOWN")
        self.selected_component = raw_adapter.lower().replace("_", "-")
        
        raw_clusters = self.engine.broker.get_cluster_table(
            self.selected_component
        )
        
        # Filter out promoted, accepted, or resolved clusters from active review queue
        self.clusters = [
            c for c in raw_clusters 
            if c.get("state", "pending") not in ("accepted", "promoted", "gold", "rejected")
        ]
        
        # Keep selected index within valid bounds
        if not from_pop or self.selected_index >= len(self.clusters):
            self.selected_index = 0

    def get_menu_hints(self):
        return {"↑/↓": "Cycle Clusters", "Enter": "Select", "←": "Back", "q": "Quit"}

    def render(self):
        table = Table(
            expand=True,
            border_style="dim white",
            box=None,
            padding=(0, 2),
            show_header=True,
            header_style="bold bright_white",
        )
        table.add_column("SELECT", width=8, justify="center")
        table.add_column("CLUSTER ID", ratio=3, justify="left")
        table.add_column("TOTAL CASES", ratio=1, justify="right")

        selected_style = Style(color="cyan", bold=True)
        unselected_style = Style(color="white", dim=True)

        if not self.clusters:
            table.add_row("", "No pending clusters found", "[dim]0[/dim]")
        else:
            for idx, item in enumerate(self.clusters):
                if idx == self.selected_index:
                    selector = Text("── ▶ ──", style="bold cyan")
                    cid = Text(str(item["cluster_id"]), style="bold bright_white")
                    badge = f"[bold black on cyan]  {item['count']} cases  [/bold black on cyan]"
                    row_style = selected_style
                else:
                    selector = Text("", style="dim")
                    cid = Text(str(item["cluster_id"]), style="dim white")
                    badge = f"[dim cyan][ {item['count']} cases ][/dim cyan]"
                    row_style = unselected_style

                table.add_row(
                    selector,
                    cid,
                    badge,
                    style=row_style,
                )

        total_clusters = len(self.clusters)
        total_cases = sum(c.get("count", 0) for c in self.clusters)
        subtitle = f"[dim] Pending Clusters: [bold white]{total_clusters}[/bold white]  │  Total Cases: [bold white]{total_cases}[/bold white] [/dim]"

        return self.assemble_layout(
            Panel(
                table,
                title=f"[bold cyan] {self.selected_component.upper()} CLUSTERS [/bold cyan]",
                subtitle=subtitle,
                subtitle_align="right",
                title_align="center",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    def handle_input(self, key: str):
        if key == "up":
            if self.clusters:
                self.selected_index = (self.selected_index - 1) % len(
                    self.clusters
                )
            return None, True
        if key == "down":
            if self.clusters:
                self.selected_index = (self.selected_index + 1) % len(
                    self.clusters
                )
            return None, True
        if key == "enter":
            if self.clusters:
                chosen_cluster = self.clusters[self.selected_index]
                self.ctx.set("current_cluster_id", chosen_cluster.get("cluster_id"))
                return TransitionSignal(TransitionType.PUSH, "cluster_review"), True
            return None, True
        if key in ("left", "escape", "b"):
            return TransitionSignal(TransitionType.POP), True
        if key == "q":
            return TransitionSignal(TransitionType.QUIT), True
        return None, False