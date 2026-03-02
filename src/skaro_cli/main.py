"""Skaro CLI — lightweight command-line interface for Spec-Guided Development.

All phase execution (clarify, plan, implement, review, etc.) is handled
through the web dashboard (``skaro ui``).  The CLI provides only:
  - project bootstrapping (init, config)
  - dashboard launcher (ui)
  - CI-friendly checks (validate, constitution validate, status)
"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

import click
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from skaro_core.artifacts import ArtifactManager, Phase, Status
from skaro_core.config import SkaroConfig, load_config, save_config, save_secret
from skaro_core.i18n import set_locale, t

console = Console()

# ── Banner ──────────────────────────────────────

LOGO = r"""
 ███████╗██╗  ██╗ █████╗ ██████╗  ██████╗
 ██╔════╝██║ ██╔╝██╔══██╗██╔══██╗██╔═══██╗
 ███████╗█████╔╝ ███████║██████╔╝██║   ██║
 ╚════██║██╔═██╗ ██╔══██║██╔══██╗██║   ██║
 ███████║██║  ██╗██║  ██║██║  ██║╚██████╔╝
 ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝"""


def _print_banner() -> None:
    """Print the branded welcome banner with quick-start instructions."""
    try:
        version = _get_version()
    except Exception:
        version = "dev"

    logo_text = Text(LOGO, style="bold cyan")
    tagline = Text(
        "  AI-powered SDLC orchestration platform", style="dim white"
    )
    ver = Text(f"  v{version}\n", style="dim")

    banner = Text()
    banner.append_text(logo_text)
    banner.append("\n")
    banner.append_text(tagline)
    banner.append("\n")
    banner.append_text(ver)

    console.print(banner)

    quick_start = (
        "[bold]Quick start:[/bold]\n"
        "\n"
        "  [cyan]skaro init[/cyan]                       Initialize project\n"
        "  [cyan]skaro config --provider groq[/cyan]     Configure LLM\n"
        "  [cyan]skaro ui[/cyan]                         Launch web dashboard\n"
        "\n"
        "[bold]Useful commands:[/bold]\n"
        "\n"
        "  [cyan]skaro status[/cyan]                     Project overview\n"
        "  [cyan]skaro constitution validate[/cyan]      Check constitution\n"
        "  [cyan]skaro --help[/cyan]                     All commands"
    )

    console.print(
        Panel(quick_start, border_style="dim", padding=(1, 2)),
    )


def _get_version() -> str:
    """Return the installed package version."""
    from importlib.metadata import version

    return version("skaro")


# ── Helpers ─────────────────────────────────────


def _find_free_port(start: int = 4700, max_attempts: int = 50) -> int:
    """Find a free port starting from *start*, incrementing on conflict."""
    import socket

    for offset in range(max_attempts):
        port = start + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start}–{start + max_attempts - 1}")


def _ensure_initialized() -> ArtifactManager:
    """Return ArtifactManager or exit if .skaro/ is missing."""
    am = ArtifactManager()
    if not am.is_initialized:
        console.print(f"[red]✗[/red] {t('errors.no_skaro')}")
        raise SystemExit(1)
    return am


# ── Root group ──────────────────────────────────


@click.group(invoke_without_command=True)
@click.option("--lang", default=None, help="Language: en, ru")
@click.version_option(package_name="skaro")
@click.pass_context
def cli(ctx: click.Context, lang: str | None) -> None:
    """Skaro — Spec-Guided Development toolkit."""
    config = load_config()
    set_locale(lang or config.lang)

    if ctx.invoked_subcommand is None:
        _print_banner()


# ── skaro init ──────────────────────────────────


@cli.command()
@click.option("--no-git", is_flag=True, help="Skip git detection")
@click.option("--name", default=None, help="Project name")
@click.option("--description", default="", help="Project description")
def init(no_git: bool, name: str | None, description: str) -> None:
    """Initialize Skaro in the current project."""
    am = ArtifactManager()
    if am.is_initialized:
        console.print(f"[yellow]⚠[/yellow]  {t('cli.init.already_exists')}")
        return

    if name is None:
        default_name = Path.cwd().name
        name = click.prompt("Project name", default=default_name)

    skaro_path = am.init_project()

    config = SkaroConfig(project_name=name, project_description=description)
    save_config(config)

    console.print(f"[green]✓[/green] {t('cli.init.success', path=str(skaro_path))}")
    console.print()
    console.print("  Created:")
    console.print("    📄 .skaro/constitution.md               — fill in your project principles")
    console.print("    📄 .skaro/architecture/architecture.md  — describe your architecture")
    console.print("    📄 .skaro/config.yaml                   — LLM and project settings")

    if not no_git:
        git_dir = am.root / ".git"
        if git_dir.is_dir():
            console.print(f"\n  {t('cli.init.git_detected')}")

    console.print()
    console.print("  [bold]Next steps:[/bold]")
    console.print("    1. Fill in constitution:  [cyan]nano .skaro/constitution.md[/cyan]")
    console.print("    2. Fill in architecture:  [cyan]nano .skaro/architecture/architecture.md[/cyan]")
    console.print("    3. Configure LLM:         [cyan]skaro config --provider groq[/cyan]")
    console.print("    4. Launch dashboard:       [cyan]skaro ui[/cyan]")


# ── skaro config ────────────────────────────────


@cli.command()
@click.option(
    "--provider",
    type=click.Choice(["anthropic", "openai", "groq", "ollama"]),
    help="LLM provider",
)
@click.option("--model", help="Model name")
@click.option("--api-key", help="API key for the LLM provider")
@click.option("--show", is_flag=True, help="Show current config")
def config(
    provider: str | None,
    model: str | None,
    api_key: str | None,
    show: bool,
) -> None:
    """Configure Skaro settings."""
    _ensure_initialized()
    cfg = load_config()

    if show or (not provider and not model and not api_key):
        _show_config(cfg)
        return

    if provider:
        cfg.llm.provider = provider
        from skaro_core.llm.base import PROVIDER_PRESETS

        preset = PROVIDER_PRESETS.get(provider)
        if preset and not model:
            cfg.llm.model = preset[0]

    if model:
        cfg.llm.model = model

    if api_key:
        from skaro_core.llm.base import PROVIDER_PRESETS

        preset = PROVIDER_PRESETS.get(cfg.llm.provider)
        env_name = preset[1] if preset and preset[1] else f"{cfg.llm.provider.upper()}_API_KEY"
        save_secret(env_name, api_key)
        cfg.llm.api_key_env = env_name
        console.print(
            f"[green]✓[/green] API key saved to [cyan].skaro/secrets.yaml[/cyan] as {env_name}"
        )

    path = save_config(cfg)
    console.print(f"[green]✓[/green] {t('cli.config.saved', path=str(path))}")
    _show_config(cfg)
    console.print("\n  Next step: [cyan]skaro ui[/cyan]")


def _show_config(cfg: SkaroConfig) -> None:
    table = Table(title=t("cli.config.current"), show_header=False)
    table.add_column("Key", style="cyan")
    table.add_column("Value")
    table.add_row("LLM Provider", cfg.llm.provider)
    table.add_row("Model", cfg.llm.model)
    table.add_row("API Key Env", cfg.llm.api_key_env or "(not set)")
    table.add_row("API Key Resolved", "✓" if cfg.llm.api_key else "✗")
    table.add_row("Language", cfg.lang)
    console.print(table)


# ── skaro ui ────────────────────────────────────


@cli.command()
@click.option("--port", type=int, default=None, help="Port (default: auto from 4700)")
@click.option("--no-browser", is_flag=True, help="Don't open browser")
def ui(port: int | None, no_browser: bool) -> None:
    """Start the Skaro web dashboard."""
    am = _ensure_initialized()
    cfg = load_config()

    if port is not None:
        actual_port = port
    else:
        try:
            actual_port = _find_free_port()
        except RuntimeError as e:
            console.print(f"[red]✗[/red] {e}")
            raise SystemExit(1)

    url = f"http://127.0.0.1:{actual_port}"

    console.print(f"\n🌐 {t('cli.ui.starting', port=actual_port)}")
    console.print(f"   {url}\n")

    if not no_browser and cfg.ui.auto_open_browser:
        webbrowser.open(url)

    try:
        import uvicorn
        from skaro_web.app import create_app

        app = create_app(project_root=am.root)
        uvicorn.run(app, host="127.0.0.1", port=actual_port, log_level="info")
    except KeyboardInterrupt:
        console.print(f"\n{t('cli.ui.stopped')}")
    except ImportError as e:
        console.print(f"[red]✗[/red] Web UI dependencies not installed: {e}")
        console.print("  Run: pip install skaro[web]")


# ── skaro status ────────────────────────────────


@cli.command()
def status() -> None:
    """Show project overview: milestones, tasks, and their progress."""
    am = _ensure_initialized()

    # Constitution
    c_icon = "[green]✓[/green]" if am.has_constitution else "[red]✗[/red]"
    console.print(f"  {c_icon} Constitution")

    # Architecture
    a_icon = "[green]✓[/green]" if am.has_architecture else "[red]✗[/red]"
    console.print(f"  {a_icon} Architecture")

    # Milestones & tasks
    milestones = am.list_milestones()
    if not milestones:
        console.print("\n  No milestones yet. Launch [cyan]skaro ui[/cyan] to get started.")
        return

    for ms in milestones:
        tasks = am.list_tasks(ms)
        console.print(f"\n  [bold]{escape(ms)}[/bold] ({len(tasks)} tasks)")
        for tname in tasks:
            state = am.get_task_state(ms, tname)
            pct = state.progress_percent
            icon = "●" if pct == 100 else "◐" if pct > 0 else "○"
            console.print(f"    {icon} {tname} ({pct}%)")


# ── skaro constitution validate ─────────────────


@cli.group()
def constitution() -> None:
    """Manage project constitution."""


@constitution.command("validate")
def constitution_validate() -> None:
    """Validate constitution completeness (useful in CI)."""
    am = _ensure_initialized()
    checks = am.validate_constitution()

    all_ok = True
    for section, present in checks.items():
        icon = "[green]✓[/green]" if present else "[red]✗[/red]"
        msg = (
            t("cli.constitution.section_ok", section=section)
            if present
            else t("cli.constitution.missing_section", section=section)
        )
        console.print(f"  {icon} {msg}")
        if not present:
            all_ok = False

    if all_ok:
        console.print(f"\n[green]✓[/green] {t('cli.constitution.valid')}")
    else:
        console.print(f"\n[red]✗[/red] {t('cli.constitution.invalid')}")
        raise SystemExit(1)


# ── skaro validate ──────────────────────────────


@cli.command()
@click.argument("task_name")
def validate(task_name: str) -> None:
    """Validate Definition-of-Done for current phase (useful in CI)."""
    am = _ensure_initialized()

    if not am.find_task_exists(task_name):
        console.print(f"[red]✗[/red] {t('cli.task.not_found', name=task_name)}")
        raise SystemExit(1)

    state = am.find_task_state(task_name)
    phase = state.current_phase

    console.print(f"\n{t('cli.validate.checking', feature=task_name, phase=phase.value)}\n")

    checks = _get_dod_checks(am, task_name, phase)
    failed = 0
    for label, passed in checks.items():
        icon = "[green]✓[/green]" if passed else "[red]✗[/red]"
        console.print(f"  {icon} {label}")
        if not passed:
            failed += 1

    if failed == 0:
        console.print(f"\n[green]✓[/green] {t('cli.validate.passed')}")
    else:
        console.print(f"\n[red]✗[/red] {t('cli.validate.failed', count=failed)}")
        raise SystemExit(1)


def _get_dod_checks(
    am: ArtifactManager, task_slug: str, phase: Phase
) -> dict[str, bool]:
    """Get DoD checks for a given phase."""
    fdir = am.find_task_dir(task_slug)

    if phase == Phase.CONSTITUTION:
        checks = am.validate_constitution()
        return {f"Section: {k}": v for k, v in checks.items()}

    if phase == Phase.CLARIFY:
        return {
            "spec.md exists": (fdir / "spec.md").exists(),
            "clarifications.md exists": (fdir / "clarifications.md").exists(),
            "No TODO/TBD in spec": "TODO"
            not in am.find_and_read_task_file(task_slug, "spec.md").upper(),
        }

    if phase == Phase.PLAN:
        plan_content = am.find_and_read_task_file(task_slug, "plan.md")
        return {
            "plan.md exists": (fdir / "plan.md").exists(),
            "tasks.md exists": (fdir / "tasks.md").exists(),
            "Plan has stages": bool(
                plan_content
                and ("stage" in plan_content.lower() or "этап" in plan_content.lower())
            ),
        }

    if phase == Phase.IMPLEMENT:
        completed = am.find_completed_stages(task_slug)
        return {
            "At least one stage completed": len(completed) > 0,
            "AI_NOTES.md for each stage": all(
                (am.find_stage_dir(task_slug, s) / "AI_NOTES.md").exists()
                for s in completed
            ),
        }

    return {"Phase check not implemented": False}


# ── Entrypoint ──────────────────────────────────


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
