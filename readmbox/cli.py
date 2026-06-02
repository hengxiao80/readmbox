import sys
from pathlib import Path

import click

from .exporter import export
from .indexer import index as run_index
from .searcher import search


@click.group()
def cli() -> None:
    """Search and export messages from large .mbox files."""


@cli.command()
@click.argument("mbox_file", type=click.Path(exists=True, path_type=Path))
@click.option("--rebuild", is_flag=True, default=False, help="Recreate the index even if it exists.")
def index(mbox_file: Path, rebuild: bool) -> None:
    """Build a search index for MBOX_FILE."""
    run_index(mbox_file, rebuild=rebuild)


@cli.command()
@click.argument("query")
@click.option("--mbox", "mbox_file", required=True, type=click.Path(exists=True, path_type=Path), help="Path to the .mbox file.")
@click.option("--from-date", default=None, metavar="YYYY-MM-DD", help="Start of date range (inclusive).")
@click.option("--to-date", default=None, metavar="YYYY-MM-DD", help="End of date range (inclusive).")
@click.option("--limit", default=50, show_default=True, help="Maximum number of results.")
@click.option("--save", "save_dir", default=None, type=click.Path(path_type=Path), help="Directory to save matched messages as HTML.")
def search_cmd(
    query: str,
    mbox_file: Path,
    from_date: str | None,
    to_date: str | None,
    limit: int,
    save_dir: Path | None,
) -> None:
    """Search QUERY in the index for MBOX_FILE."""
    try:
        results = search(mbox_file, query, from_date=from_date, to_date=to_date, limit=limit)
    except FileNotFoundError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    if not results:
        click.echo("No results found.")
        return

    click.echo(f"\nFound {len(results)} result(s):\n")
    click.echo(f"  {'#':<5} {'Date':<12} {'From':<30} Subject")
    click.echo(f"  {'-'*5} {'-'*12} {'-'*30} {'-'*40}")
    for i, r in enumerate(results, 1):
        date = r.date[:10] if r.date else "unknown"
        from_ = r.from_[:28] + ".." if len(r.from_) > 30 else r.from_
        subject = r.subject or "(no subject)"
        click.echo(f"  [{i:<3}] {date:<12} {from_:<30} {subject}")

    if save_dir:
        saved = export(results, mbox_file, save_dir)
        click.echo(f"Saved {len(saved)} file(s) to {save_dir}/")
    else:
        _prompt_save(results, mbox_file)


def _prompt_save(results, mbox_file: Path) -> None:
    click.echo()
    raw = click.prompt(
        "Save messages as HTML? Enter numbers (e.g. 1 3 5), 'all', or press Enter to skip",
        default="",
        show_default=False,
    ).strip()

    if not raw:
        return

    if raw.lower() == "all":
        selected = results
    else:
        indices = []
        for token in raw.replace(",", " ").split():
            try:
                n = int(token)
                if 1 <= n <= len(results):
                    indices.append(n - 1)
                else:
                    click.echo(f"  Skipping {n}: out of range.", err=True)
            except ValueError:
                click.echo(f"  Skipping '{token}': not a number.", err=True)
        selected = [results[i] for i in indices]

    if not selected:
        return

    save_dir = Path(click.prompt("Save to directory", default="./saved_messages"))
    saved = export(selected, mbox_file, save_dir)
    click.echo(f"Saved {len(saved)} file(s) to {save_dir}/")


# register the search command under the name 'search'
cli.add_command(search_cmd, name="search")
