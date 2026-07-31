import csv
import json
from pathlib import Path
from rich.table import Table
from rich.panel import Panel
from rich.style import Style
from rich.console import Group
from rich.text import Text
from ui.screens.base import Screen, TransitionSignal, TransitionType
from ui.registry import register_screen


@register_screen("add_candidates")
class AddCandidatesScreen(Screen):
    def __init__(self, engine):
        super().__init__(engine)
        self.page_title = "SELECT CANDIDATE FILE"
        self.sut_root = Path.cwd()
        self.current_dir = self.sut_root
        self.items = []
        self.selected_index = 0
        self.status_message = ""
        self.is_error = False

    def on_enter(self, context: dict, from_pop: bool = False) -> None:
        if not from_pop:
            self.selected_index = 0
            self.status_message = ""
            
            # Start directly in .crucible/suites/<component_name>/Bronze/
            active_component = self.ctx.get("current_adapter", "UNKNOWN")
            bronze_dir = self.sut_root / ".crucible" / "suites" / active_component / "Bronze"
            bronze_dir.mkdir(parents=True, exist_ok=True)
            
            self.current_dir = bronze_dir
            self._refresh_dir_contents()

    def _refresh_dir_contents(self):
        """Lists folders and files in current view."""
        dirs = []
        files = []

        try:
            if self.current_dir.parent != self.current_dir:
                dirs.append({
                    "name": ".. (Parent Directory)",
                    "path": self.current_dir.parent,
                    "is_dir": True
                })

            for p in sorted(self.current_dir.iterdir()):
                if p.name.startswith(".") or p.name == "__pycache__":
                    continue

                if p.is_dir():
                    dirs.append({"name": f"📁 {p.name}/", "path": p, "is_dir": True})
                else:
                    files.append({"name": f"📄 {p.name}", "path": p, "is_dir": False})

            self.items = dirs + files
            self.selected_index = min(self.selected_index, max(0, len(self.items) - 1))
        except PermissionError:
            self.status_message = "❌ Permission denied accessing folder."
            self.is_error = True

    def _parse_incoming_file(self, file_path: Path) -> list[str]:
        """Parses TXT, CSV, or JSON input into clean candidate strings."""
        incoming = []
        suffix = file_path.suffix.lower()

        if suffix == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            incoming.append(str(item.get("name") or item.get("id") or ""))
                        elif isinstance(item, str):
                            incoming.append(item)
        elif suffix == ".csv":
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    if row:
                        incoming.append(row[0].strip())
        else:  # TXT / Fallback
            with open(file_path, "r", encoding="utf-8") as f:
                incoming = [line.strip() for line in f if line.strip()]

        return [c.strip() for c in incoming if c and c.strip()]

    def _append_to_candidate_pool(self, new_candidates: list[str]) -> tuple[int, int]:
        """Appends candidates to candidate_pool.txt in the active component's Bronze folder."""
        active_component = self.ctx.get("current_adapter", "UNKNOWN")
        pool_file = self.sut_root / ".crucible" / "suites" / active_component / "Bronze" / "candidate_pool.txt"
        
        # Ensure target directory exists
        pool_file.parent.mkdir(parents=True, exist_ok=True)

        existing_lines = []
        existing_set = set()

        # 1. Read existing candidates to prevent duplicates
        if pool_file.exists():
            try:
                with open(pool_file, "r", encoding="utf-8") as f:
                    for line in f:
                        clean_line = line.strip()
                        if clean_line:
                            existing_lines.append(clean_line)
                            existing_set.add(clean_line.lower())
            except Exception:
                existing_lines = []
                existing_set = set()

        # 2. Filter new candidates
        added_count = 0
        skipped_count = 0

        for candidate in new_candidates:
            if candidate.lower() in existing_set:
                skipped_count += 1
            else:
                existing_set.add(candidate.lower())
                existing_lines.append(candidate)
                added_count += 1

        # 3. Write back to candidate_pool.txt
        with open(pool_file, "w", encoding="utf-8") as f:
            for item in existing_lines:
                f.write(f"{item}\n")

        # 4. Sync context
        self.ctx.set(f"candidate_pool_{active_component}", existing_lines)

        return added_count, skipped_count

    def _import_file(self, file_path: Path):
        try:
            incoming_items = self._parse_incoming_file(file_path)
            if not incoming_items:
                self.status_message = f"❌ File '{file_path.name}' contained no valid entries."
                self.is_error = True
                return

            added, skipped = self._append_to_candidate_pool(incoming_items)
            
            msg = f"✓ Added {added} candidate(s) to candidate_pool.txt!"
            if skipped > 0:
                msg += f" ({skipped} duplicate(s) skipped)"
                
            self.status_message = msg
            self.is_error = False
            self._refresh_dir_contents()

        except Exception as e:
            self.status_message = f"❌ Error saving candidates: {str(e)}"
            self.is_error = True

    def render(self):
        active_component = self.ctx.get("current_adapter", "UNKNOWN")

        table = Table(
            expand=True,
            border_style="border_muted",
            box=None,
            padding=(0, 2),
        )
        table.add_column("SELECT", width=6, justify="center")
        table.add_column("FILE / DIRECTORY", ratio=1, justify="left")
        table.add_column("TYPE", width=15, justify="right")

        selected_style = Style(color="#00F0FF", bold=True, reverse=True)
        unselected_style = Style(color="#F5F5F7", dim=False)

        for idx, item in enumerate(self.items):
            if idx == self.selected_index:
                selector, row_style = "▶", selected_style
            else:
                selector, row_style = " ", unselected_style

            item_type = "DIR" if item["is_dir"] else (item["path"].suffix.upper() or "FILE")
            table.add_row(selector, item["name"], item_type, style=row_style)

        path_info = Text()
        path_info.append("Target Component: ", style="dim")
        path_info.append(f"{active_component}\n", style="bold primary")
        path_info.append("Target Pool File: ", style="dim")
        path_info.append(f".crucible/suites/{active_component}/Bronze/candidate_pool.txt\n", style="bold white")
        path_info.append("Current Location: ", style="dim")
        path_info.append(f"{self.current_dir.resolve()}\n\n", style="bold dim")

        body_elements = [path_info, table]

        if self.status_message:
            msg_style = "error" if self.is_error else "success"
            body_elements.append(Text(f"\n{self.status_message}", style=msg_style))

        return self.assemble_layout(
            Panel(
                Group(*body_elements),
                title="[bold primary] BROWSE CANDIDATE FILES [/bold primary]",
                title_align="center",
                border_style="border_active",
                padding=(2, 2),
            )
        )

    def handle_input(self, key: str):
        if key == "up" and self.items:
            self.selected_index = (self.selected_index - 1) % len(self.items)
            return None, True

        if key == "down" and self.items:
            self.selected_index = (self.selected_index + 1) % len(self.items)
            return None, True

        if key == "enter" and self.items:
            selected_item = self.items[self.selected_index]
            if selected_item["is_dir"]:
                self.current_dir = selected_item["path"]
                self.selected_index = 0
                self._refresh_dir_contents()
            else:
                self._import_file(selected_item["path"])
            return None, True

        if key in ("left", "escape", "b"):
            return TransitionSignal(TransitionType.POP), True

        if key == "q":
            return TransitionSignal(TransitionType.QUIT), True

        return None, False

    def get_menu_hints(self):
        return {"↑/↓": "Navigate", "Enter": "Append to candidate_pool.txt", "← / Esc": "Back", "q": "Quit"}