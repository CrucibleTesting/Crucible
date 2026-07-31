# crucible/core/reporting.py

from rich.console import Console
from rich.table import Table

def print_diff_summary(diffs):
    console = Console()
    table = Table(title="Staging Diff Summary")

    table.add_column("ID")
    table.add_column("Signature")
    table.add_column("Fields Changed")

    for d in diffs:
        fields = ", ".join(fd.field for fd in d.field_diffs)
        table.add_row(d.id, d.signature, fields)

    console.print(table)
