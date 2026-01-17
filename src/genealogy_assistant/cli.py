"""
Command-line interface for the Genealogy Research Assistant.

Provides GPS-compliant genealogy research tools with AI assistance.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from genealogy_assistant.api.assistant import GenealogyAssistant, AssistantConfig
from genealogy_assistant.core.gedcom import GedcomManager
from genealogy_assistant.core.models import ConfidenceLevel
from genealogy_assistant.search.unified import UnifiedSearch, UnifiedSearchConfig

console = Console()


def async_command(f):
    """Decorator to run async commands."""
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


@click.group()
@click.version_option(version="0.1.0", prog_name="genealogy-assistant")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx, verbose):
    """
    GPS-compliant Genealogy Research Assistant.

    AI-powered genealogical research following BCG certification standards
    and the Genealogical Proof Standard (GPS).
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


# =============================================================================
# Research Commands
# =============================================================================

@cli.group()
def research():
    """AI-assisted genealogical research commands."""
    pass


@research.command("ask")
@click.argument("question")
@click.option("--context", "-c", help="Additional context (JSON string)")
@click.option("--model", default="claude-sonnet-4-20250514", help="Claude model to use")
@async_command
async def research_ask(question: str, context: Optional[str], model: str):
    """
    Ask a genealogical research question.

    Uses AI to provide GPS-compliant research guidance.
    """
    config = AssistantConfig(model=model)

    context_dict = None
    if context:
        try:
            context_dict = json.loads(context)
        except json.JSONDecodeError:
            console.print("[red]Error: Invalid JSON context[/red]")
            sys.exit(1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Researching...", total=None)

        async with GenealogyAssistant(config) as assistant:
            response = await assistant.research(question, context_dict)

    # Display response
    console.print(Panel(
        Markdown(response.message),
        title="Research Response",
        subtitle=f"Confidence: {response.confidence.value}",
    ))

    if response.next_actions:
        console.print("\n[bold]Recommended Next Actions:[/bold]")
        for i, action in enumerate(response.next_actions, 1):
            console.print(f"  {i}. {action}")


@research.command("plan")
@click.option("--surname", "-s", required=True, help="Target person's surname")
@click.option("--given", "-g", help="Target person's given name")
@click.option("--birth-year", "-b", type=int, help="Approximate birth year")
@click.option("--birth-place", "-p", help="Birth place")
@click.argument("goal")
@async_command
async def research_plan(surname: str, given: Optional[str], birth_year: Optional[int],
                        birth_place: Optional[str], goal: str):
    """
    Create a GPS-compliant research plan.

    Generates systematic research steps prioritizing primary sources.
    """
    from genealogy_assistant.core.models import Person, PersonName, Event, GenealogyDate, Place

    # Build target person
    target = Person(id="target")
    target.primary_name = PersonName(surname=surname, given=given or "")

    if birth_year or birth_place:
        target.birth = Event(event_type="BIRT")
        if birth_year:
            target.birth.date = GenealogyDate(year=birth_year)
        if birth_place:
            target.birth.place = Place(name=birth_place)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Creating research plan...", total=None)

        async with GenealogyAssistant() as assistant:
            response = await assistant.create_research_plan(target, goal)

    console.print(Panel(
        Markdown(response.message),
        title=f"Research Plan: {given or ''} {surname}",
        subtitle=f"Goal: {goal}",
    ))


@research.command("verify")
@click.argument("conclusion")
@click.option("--evidence", "-e", multiple=True, required=True, help="Evidence supporting conclusion")
@async_command
async def research_verify(conclusion: str, evidence: tuple):
    """
    Verify a genealogical conclusion against GPS standards.

    Evaluates whether evidence supports the conclusion.
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Verifying conclusion...", total=None)

        async with GenealogyAssistant() as assistant:
            response = await assistant.verify_conclusion(conclusion, list(evidence))

    # Determine status color
    confidence_colors = {
        ConfidenceLevel.GPS_COMPLETE: "green",
        ConfidenceLevel.STRONG: "blue",
        ConfidenceLevel.REASONABLE: "yellow",
        ConfidenceLevel.WEAK: "orange",
        ConfidenceLevel.SPECULATIVE: "red",
    }
    color = confidence_colors.get(response.confidence, "white")

    console.print(Panel(
        Markdown(response.message),
        title="GPS Verification",
        subtitle=f"[{color}]Confidence: {response.confidence.value}[/{color}]",
    ))


# =============================================================================
# Search Commands
# =============================================================================

@cli.group()
def search():
    """Search genealogy databases."""
    pass


@search.command("person")
@click.option("--surname", "-s", required=True, help="Surname to search")
@click.option("--given", "-g", help="Given name")
@click.option("--birth-year", "-b", type=int, help="Birth year (+/- 2 years)")
@click.option("--birth-place", "-p", help="Birth place")
@click.option("--provider", "-P", multiple=True,
              help="Specific provider(s): familysearch, geneanet, belgian_archives, findagrave")
@click.option("--analyze/--no-analyze", default=True, help="AI analysis of results")
@async_command
async def search_person(surname: str, given: Optional[str], birth_year: Optional[int],
                       birth_place: Optional[str], provider: tuple, analyze: bool):
    """
    Search for a person across genealogy databases.

    Searches FamilySearch, Geneanet, Belgian Archives, and FindAGrave.
    """
    providers = list(provider) if provider else None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Searching databases...", total=None)

        if analyze:
            async with GenealogyAssistant() as assistant:
                response = await assistant.search_and_analyze(
                    surname=surname,
                    given_name=given,
                    birth_year=birth_year,
                    birth_place=birth_place,
                    providers=providers,
                )
        else:
            async with UnifiedSearch() as search_engine:
                search_response = await search_engine.search_person(
                    surname=surname,
                    given_name=given,
                    birth_year=birth_year,
                    birth_place=birth_place,
                    providers=providers,
                )
                response = None

    # Display results table
    if analyze:
        results = response.search_results
    else:
        results = search_response.results

    if results:
        table = Table(title=f"Search Results for {given or ''} {surname}")
        table.add_column("#", style="dim")
        table.add_column("Name")
        table.add_column("Birth")
        table.add_column("Death")
        table.add_column("Place")
        table.add_column("Provider")
        table.add_column("Source Level")

        for i, result in enumerate(results[:20], 1):
            birth = result.birth_date.to_gedcom() if result.birth_date else "-"
            death = result.death_date.to_gedcom() if result.death_date else "-"
            place = result.birth_place.name if result.birth_place else "-"

            # Color code source level
            level_colors = {
                "PRIMARY": "green",
                "SECONDARY": "yellow",
                "TERTIARY": "red",
            }
            level_color = level_colors.get(result.source_level.value, "white")

            table.add_row(
                str(i),
                f"{result.given_name} {result.surname}",
                birth,
                death,
                place[:30] + "..." if len(place) > 30 else place,
                result.provider,
                f"[{level_color}]{result.source_level.value}[/{level_color}]",
            )

        console.print(table)
    else:
        console.print("[yellow]No results found[/yellow]")

    # Display AI analysis if enabled
    if analyze and response:
        console.print()
        console.print(Panel(
            Markdown(response.message),
            title="AI Analysis",
            subtitle=f"Confidence: {response.confidence.value}",
        ))


# =============================================================================
# GEDCOM Commands
# =============================================================================

@cli.group()
def gedcom():
    """GEDCOM file management."""
    pass


@gedcom.command("info")
@click.argument("file", type=click.Path(exists=True))
def gedcom_info(file: str):
    """Display GEDCOM file statistics."""
    manager = GedcomManager()

    try:
        manager.load(file)
    except Exception as e:
        console.print(f"[red]Error loading GEDCOM: {e}[/red]")
        sys.exit(1)

    stats = manager.stats()

    table = Table(title=f"GEDCOM: {Path(file).name}")
    table.add_column("Metric", style="bold")
    table.add_column("Count", justify="right")

    table.add_row("Individuals", str(stats.get("individuals", 0)))
    table.add_row("Families", str(stats.get("families", 0)))
    table.add_row("Sources", str(stats.get("sources", 0)))
    table.add_row("Notes", str(stats.get("notes", 0)))

    console.print(table)

    if "version" in stats:
        console.print(f"\nGEDCOM Version: {stats['version']}")


@gedcom.command("validate")
@click.argument("file", type=click.Path(exists=True))
@click.option("--fix/--no-fix", default=False, help="Attempt to fix issues")
def gedcom_validate(file: str, fix: bool):
    """Validate GEDCOM file for GPS compliance."""
    manager = GedcomManager()

    try:
        manager.load(file)
    except Exception as e:
        console.print(f"[red]Error loading GEDCOM: {e}[/red]")
        sys.exit(1)

    issues = manager.validate()

    if not issues:
        console.print("[green]GEDCOM file is valid![/green]")
        return

    # Group issues by severity
    errors = [i for i in issues if i.startswith("ERROR")]
    warnings = [i for i in issues if i.startswith("WARNING")]

    if errors:
        console.print(f"\n[red]Errors ({len(errors)}):[/red]")
        for error in errors[:20]:
            console.print(f"  {error}")
        if len(errors) > 20:
            console.print(f"  ... and {len(errors) - 20} more")

    if warnings:
        console.print(f"\n[yellow]Warnings ({len(warnings)}):[/yellow]")
        for warning in warnings[:20]:
            console.print(f"  {warning}")
        if len(warnings) > 20:
            console.print(f"  ... and {len(warnings) - 20} more")


@gedcom.command("search")
@click.argument("file", type=click.Path(exists=True))
@click.option("--surname", "-s", help="Surname to search")
@click.option("--given", "-g", help="Given name to search")
def gedcom_search(file: str, surname: Optional[str], given: Optional[str]):
    """Search for persons in a GEDCOM file."""
    if not surname and not given:
        console.print("[red]Please provide --surname or --given[/red]")
        sys.exit(1)

    manager = GedcomManager()
    manager.load(file)

    results = manager.find_persons(surname=surname, given_name=given)

    if not results:
        console.print("[yellow]No matches found[/yellow]")
        return

    table = Table(title=f"Matches in {Path(file).name}")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Birth")
    table.add_column("Death")

    for person in results[:50]:
        name = person.primary_name.full_name() if person.primary_name else "Unknown"
        birth = ""
        if person.birth and person.birth.date:
            birth = person.birth.date.to_gedcom()
        death = ""
        if person.death and person.death.date:
            death = person.death.date.to_gedcom()

        table.add_row(person.id, name, birth, death)

    console.print(table)

    if len(results) > 50:
        console.print(f"\n[dim]Showing 50 of {len(results)} matches[/dim]")


# =============================================================================
# Gramps Commands
# =============================================================================

@cli.group()
def gramps():
    """Gramps database integration."""
    pass


@gramps.command("connect")
@click.option("--url", envvar="GRAMPS_WEB_URL", help="Gramps Web URL")
@click.option("--user", envvar="GRAMPS_WEB_USER", help="Username")
@click.option("--password", envvar="GRAMPS_WEB_PASS", help="Password")
@async_command
async def gramps_connect(url: Optional[str], user: Optional[str], password: Optional[str]):
    """Test connection to Gramps Web."""
    from genealogy_assistant.gramps.web_api import GrampsWebClient, GrampsWebConfig

    if not url:
        url = "http://localhost:5000"

    config = GrampsWebConfig(
        base_url=url,
        username=user,
        password=password,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Connecting to Gramps Web...", total=None)

        async with GrampsWebClient(config) as client:
            try:
                await client.authenticate()
                metadata = await client.get_metadata()
                console.print("[green]Connected successfully![/green]")
                console.print(f"Database: {metadata.get('database', {}).get('name', 'Unknown')}")
            except Exception as e:
                console.print(f"[red]Connection failed: {e}[/red]")
                sys.exit(1)


@gramps.command("search")
@click.option("--url", envvar="GRAMPS_WEB_URL", default="http://localhost:5000")
@click.option("--user", envvar="GRAMPS_WEB_USER")
@click.option("--password", envvar="GRAMPS_WEB_PASS")
@click.argument("query")
@async_command
async def gramps_search(url: str, user: Optional[str], password: Optional[str], query: str):
    """Search Gramps Web database."""
    from genealogy_assistant.gramps.web_api import GrampsWebClient, GrampsWebConfig

    config = GrampsWebConfig(
        base_url=url,
        username=user,
        password=password,
    )

    async with GrampsWebClient(config) as client:
        await client.authenticate()
        results = await client.search(query)

    if not results:
        console.print("[yellow]No results found[/yellow]")
        return

    for category, items in results.items():
        if items:
            console.print(f"\n[bold]{category.title()}[/bold] ({len(items)})")
            for item in items[:10]:
                console.print(f"  - {item.get('name', item.get('handle', 'Unknown'))}")


# =============================================================================
# Letter Generation
# =============================================================================

@cli.command("letter")
@click.option("--archive", "-a", required=True, help="Target archive/repository")
@click.option("--person", "-p", required=True, help="Person being researched")
@click.option("--record", "-r", multiple=True, required=True, help="Records needed")
@click.option("--fact", "-f", multiple=True, help="Known facts about the person")
@click.option("--output", "-o", type=click.Path(), help="Output file")
@async_command
async def generate_letter(archive: str, person: str, record: tuple, fact: tuple,
                         output: Optional[str]):
    """
    Generate a professional archive request letter.

    Creates a formal letter requesting genealogical records.
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating letter...", total=None)

        async with GenealogyAssistant() as assistant:
            letter = await assistant.generate_archive_letter(
                archive=archive,
                person_name=person,
                records_needed=list(record),
                known_facts=list(fact),
            )

    if output:
        Path(output).write_text(letter)
        console.print(f"[green]Letter saved to {output}[/green]")
    else:
        console.print(Panel(letter, title=f"Letter to {archive}"))


# =============================================================================
# Interactive Mode
# =============================================================================

@cli.command("interactive")
@click.option("--model", default="claude-sonnet-4-20250514", help="Claude model to use")
@async_command
async def interactive(model: str):
    """
    Start interactive research session.

    Provides a conversational interface for genealogy research.
    """
    console.print(Panel(
        "[bold]GPS-Compliant Genealogy Research Assistant[/bold]\n\n"
        "Type your research questions. The assistant follows BCG certification standards.\n\n"
        "Commands:\n"
        "  /reset  - Clear conversation history\n"
        "  /exit   - Exit interactive mode\n"
        "  /help   - Show help",
        title="Interactive Mode",
    ))

    config = AssistantConfig(model=model)

    async with GenealogyAssistant(config) as assistant:
        while True:
            try:
                user_input = console.input("\n[bold blue]You:[/bold blue] ")
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Goodbye![/dim]")
                break

            if not user_input.strip():
                continue

            # Handle commands
            if user_input.startswith("/"):
                cmd = user_input.lower().strip()
                if cmd == "/exit":
                    console.print("[dim]Goodbye![/dim]")
                    break
                elif cmd == "/reset":
                    assistant.reset_conversation()
                    console.print("[dim]Conversation cleared.[/dim]")
                    continue
                elif cmd == "/help":
                    console.print(
                        "Ask genealogy research questions. The assistant:\n"
                        "- Follows GPS (Genealogical Proof Standard)\n"
                        "- Prioritizes primary sources\n"
                        "- Identifies conflicts in evidence\n"
                        "- Provides confidence ratings (1-5)\n"
                    )
                    continue

            # Process research question
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("Thinking...", total=None)
                response = await assistant.research(user_input)

            console.print(f"\n[bold green]Assistant[/bold green] [dim](Confidence: {response.confidence.value})[/dim]")
            console.print(Markdown(response.message))

            if response.next_actions:
                console.print("\n[dim]Suggested next steps:[/dim]")
                for action in response.next_actions[:5]:
                    console.print(f"  [dim]- {action}[/dim]")


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
