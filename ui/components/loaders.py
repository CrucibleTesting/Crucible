from rich.panel import Panel
from rich.align import Align
from rich.console import Group
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from ui.theme import console


def create_cold_boot_progress():
    """Instantiates a single persistent Progress instance to preserve spinner frame ticks."""
    progress = Progress(
        SpinnerColumn(spinner_name="dots2", style="bold #66FCF1"),
        TextColumn("[#66FCF1]{task.description}[/#66FCF1]"),
        BarColumn(bar_width=40, style="dim #66FCF1", complete_style="bold #66FCF1"),
        console=console,
        transient=False
    )
    task_id = progress.add_task("Hydrating adapter layers...", total=100)
    return progress, task_id


def render_cold_boot_frame(progress_renderable):
    """Renders the full-screen height cold boot panel."""
    content = Group(
        "\n[bold #66FCF1]CRUCIBLE COMPONENT HYDRATION[/bold #66FCF1]\n",
        "[dim]Creating new component folder structures[/dim]\n\n",
        progress_renderable
    )
    return Panel(
        Align.center(content, vertical="middle"),
        title="[bold #66FCF1] INITIALIZING SYSTEM [/bold #66FCF1]",
        title_align="center",
        border_style="#66FCF1",
        expand=True,
        height=console.height
    )