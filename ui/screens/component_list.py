from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich.style import Style
from ui.screens.base import Screen, TransitionSignal, TransitionType
from ui.registry import register_screen


@register_screen("component_list")
class WorkspaceSelectorScreen(Screen):
    def __init__(self, engine):
        super().__init__(engine)
        self.workspaces = []
        self.selected_index = 0
        self.page_title = 'SELECT COMPONENT'

    def on_enter(self, context: dict, from_pop: bool = False) -> None:
        """Dynamically fetches component states through the UI Broker."""
        if not from_pop:
            self.workspaces = self.engine.broker.get_components()
            self.selected_index = 0

    def get_title(self) -> str:
        return self.page_title

    def render(self):
        if not self.workspaces:
            content = "[bold error]No active adapters discovered inside crucible.json![/bold error]"
            return self.assemble_layout(
                Panel(Align.center(content, vertical="middle"), border_style="border_active")
            )

        table = Table(
            expand=True,
            border_style="border_muted",
            box=None,
            padding=(0, 2),
        )
        table.add_column("SELECT", width=6, justify="center")
        table.add_column("TEST COMPONENT", ratio=1, justify="left")
        table.add_column("STATUS", width=20, justify="right")

        selected_style = Style(color="#00F0FF", bold=True, reverse=True)
        unselected_style = Style(color="#F5F5F7", dim=False)

        for idx, item in enumerate(self.workspaces):
            if idx == self.selected_index:
                selector, row_style = "▶", selected_style
            else:
                selector, row_style = " ", unselected_style
            table.add_row(selector, item["name"], item["status"], style=row_style)

        return self.assemble_layout(
            Panel(
                table,
                title="[bold primary] AVAILABLE TEST COMPONENTS [/bold primary]",
                title_align="center",
                border_style="border_active",
                padding=(2, 2)
            )
        )

    def handle_input(self, key: str):
        if key == "up":
            if self.workspaces:
                self.selected_index = (self.selected_index - 1) % len(self.workspaces)
            return None, True
        if key == "down":
            if self.workspaces:
                self.selected_index = (self.selected_index + 1) % len(self.workspaces)
            return None, True
        # if key == "enter":
        #     if self.workspaces:
        #         chosen_adapter = self.workspaces[self.selected_index]["name"]
        #         self.ctx.set("current_adapter", chosen_adapter)
        #         return TransitionSignal(TransitionType.PUSH, "page2"), True
        if key == "enter":
            if self.workspaces:
                chosen_adapter = self.workspaces[self.selected_index]["name"]
                self.ctx.set("current_adapter", chosen_adapter)
                # Change "page2" to "component_dashboard"
                return TransitionSignal(TransitionType.PUSH, "component_dashboard"), True
        if key == "q":
            return TransitionSignal(TransitionType.QUIT), True
        return None, False

    def get_menu_hints(self):
        return {"↑/↓": "Cycle Components", "Enter": "Select", "q": "Quit"}