"""CLI entry point for pagesource."""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from . import __version__
from .browser import capture_page_resources
from .downloader import save_resources
from .utils import parse_url

app = typer.Typer(
    name="pagesource",
    help="Capture all resources from a webpage like browser DevTools Sources tab.",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"pagesource {__version__}")
        raise typer.Exit()


@app.command()
def capture(
    url: str = typer.Argument(
        ...,
        help="URL of the webpage to capture resources from.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Output directory for saved resources. Defaults to ./pagesource_output",
    ),
    wait: int = typer.Option(
        0,
        "--wait", "-w",
        help="Additional seconds to wait after page load for JS content.",
    ),
    include_external: bool = typer.Option(
        False,
        "--include-external", "-e",
        help="Include external resources (CDN assets, third-party scripts).",
    ),
    version: bool = typer.Option(
        False,
        "--version", "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Capture all resources loaded by a webpage and save them locally."""
    # Validate URL
    try:
        parsed = parse_url(url)
        full_url = parsed.geturl()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Set default output directory
    if output is None:
        output = Path("./pagesource_output")

    # Create output directory
    output.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Capturing resources from:[/bold] {full_url}")
    console.print(f"[bold]Output directory:[/bold] {output.absolute()}")

    if include_external:
        console.print("[dim]Including external resources[/dim]")

    # Capture resources
    try:
        with console.status("[bold blue]Loading page and capturing resources...") as status:
            def on_status(msg: str) -> None:
                status.update(f"[bold blue]{msg}")

            resources = asyncio.run(
                capture_page_resources(full_url, wait_time=wait, on_status=on_status)
            )
    except RuntimeError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[dim]Hint: Make sure you've run 'playwright install chromium'[/dim]")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user[/yellow]")
        raise typer.Exit(130)

    console.print(f"[green]OK[/green] Captured {len(resources)} resources")

    # Save resources
    if resources:
        with console.status("[bold blue]Saving resources to disk..."):
            saved, skipped = save_resources(
                resources,
                output,
                full_url,
                include_external=include_external,
            )

        console.print(f"[green]OK[/green] Saved {saved} resources")
        if skipped > 0:
            console.print(f"[dim]Skipped {skipped} external resources (use --include-external to include)[/dim]")
    else:
        console.print("[yellow]No resources captured[/yellow]")

    console.print(f"\n[bold green]Done![/bold green] Resources saved to: {output.absolute()}")


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
