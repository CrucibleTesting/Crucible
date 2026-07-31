from rich.table import Table
from rich.panel import Panel
from rich.style import Style
from ui.screens.base import Screen, TransitionSignal, TransitionType
from ui.registry import register_screen


@register_screen("component_dashboard")
class ComponentDashboardScreen(Screen):
    def __init__(self, engine):
        super().__init__(engine)
        self.page_title = "COMPONENT MENU"
        self.selected_component = "None"
        self.options = [
            {"name": "Add Candidates", "status": "Ready"},
            {"name": "Run staging", "status": "Idle"},
            {"name": "Cluster Review", "status": "Available"},
        ]
        self.selected_index = 0

    def on_enter(self, context: dict, from_pop: bool = False) -> None:
        """Retrieves active component and resets selection when entering freshly."""
        if not from_pop:
            self.selected_index = 0
        self.selected_component = self.ctx.get("current_adapter", "UNKNOWN")

    def render(self):
        # Table configured identically to component_list.py
        table = Table(
            expand=True,
            border_style="border_muted",
            box=None,
            padding=(0, 2),
        )
        table.add_column("SELECT", width=6, justify="center")
        table.add_column("ACTION / WORKFLOW", ratio=1, justify="left")
        table.add_column("STATUS", width=20, justify="right")

        selected_style = Style(color="#00F0FF", bold=True, reverse=True)
        unselected_style = Style(color="#F5F5F7", dim=False)

        for idx, item in enumerate(self.options):
            if idx == self.selected_index:
                selector, row_style = "▶", selected_style
            else:
                selector, row_style = " ", unselected_style
            table.add_row(selector, item["name"], item["status"], style=row_style)

        return self.assemble_layout(
            Panel(
                table,
                title=f"[bold primary] {self.selected_component.upper()} ACTIONS [/bold primary]",
                title_align="center",
                border_style="border_active",
                padding=(2, 2)
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
            self.ctx.set("current_action", chosen_action)

            # Route based on the selected option
            if chosen_action == "Add Candidates":
                return TransitionSignal(TransitionType.PUSH, "add_candidates"), True

            return None, True

        if key == "q":
            return TransitionSignal(TransitionType.QUIT), True

        return None, False

    def get_menu_hints(self):
        return {"↑/↓": "Cycle Options", "Enter": "Select", "←": "Back", "q": "Quit"}