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
import questionary
from prompt_toolkit.styles import Style as PTStyle
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from skaro_core.artifacts import ArtifactManager, Phase, Status
from skaro_core.config import SkaroConfig, load_config, save_config, save_secret
from skaro_core.i18n import set_locale, t
from skaro_core.providers import get_model_choices, get_provider, get_provider_keys

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


# ── Questionary style ───────────────────────────

SKARO_STYLE = PTStyle(
    [
        ("qmark", "fg:cyan bold"),
        ("question", "fg:white bold"),
        ("answer", "fg:cyan bold"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "fg:cyan bold"),
        ("selected", "fg:green"),
        ("instruction", "fg:#888888"),
    ]
)

_CUSTOM_MODEL_LABEL = "✎ Custom (enter manually)"


# ── Init wizard helpers ─────────────────────────


def _print_init_banner() -> None:
    """Print the branded init banner with description and repo link."""
    try:
        version = _get_version()
    except Exception:
        version = "dev"

    logo_text = Text(LOGO, style="bold cyan")
    tagline = Text(
        "  AI-powered SDLC orchestration platform", style="dim white"
    )
    ver = Text(f"  v{version}", style="dim")
    repo = Text(
        "  https://github.com/skarodev/skaro", style="dim cyan"
    )

    banner = Text()
    banner.append_text(logo_text)
    banner.append("\n")
    banner.append_text(tagline)
    banner.append("\n")
    banner.append_text(ver)
    banner.append("\n")
    banner.append_text(repo)
    banner.append("\n")

    console.print(banner)


def _select_language() -> str:
    """Prompt for language via interactive select, apply immediately."""
    lang = questionary.select(
        "Language / Язык",
        choices=[
            questionary.Choice("English", value="en"),
            questionary.Choice("Русский", value="ru"),
        ],
        default="en",
        style=SKARO_STYLE,
    ).ask()

    if lang is None:  # Ctrl+C
        raise SystemExit(0)

    set_locale(lang)
    return lang


def _show_license_and_confirm() -> None:
    """Display license info and ask for confirmation to continue."""
    console.print()
    console.print(
        Panel(
            f"  {t('cli.init.license_type')}: [bold]AGPL-3.0[/bold]\n"
            f"  {t('cli.init.license_url')}: "
            "[cyan]https://github.com/skarodev/skaro/blob/main/LICENSE[/cyan]",
            title=t("cli.init.license_title"),
            border_style="dim",
            padding=(1, 2),
        )
    )

    accepted = questionary.confirm(
        t("cli.init.license_confirm"),
        default=True,
        style=SKARO_STYLE,
    ).ask()

    if not accepted:
        raise SystemExit(0)


def _setup_llm_interactive(cfg: SkaroConfig) -> SkaroConfig:
    """Interactive LLM configuration wizard for option B. Returns updated config."""
    console.print()
    console.print(
        Panel(
            t("cli.init.llm_setup_intro"),
            border_style="yellow",
            padding=(1, 2),
        )
    )

    # 1. Provider ─────────────────────────────────────────────────────────────
    provider_keys = get_provider_keys()
    provider_choices = []
    for key in provider_keys:
        info = get_provider(key)
        label = info.name if info else key
        provider_choices.append(questionary.Choice(label, value=key))

    default_provider = cfg.llm.provider if cfg.llm.provider in provider_keys else "groq"

    provider = questionary.select(
        t("cli.init.llm_provider_prompt"),
        choices=provider_choices,
        default=default_provider,
        style=SKARO_STYLE,
    ).ask()

    if provider is None:
        raise SystemExit(0)

    cfg.llm.provider = provider
    provider_info = get_provider(provider)

    # 2. Console URL ──────────────────────────────────────────────────────────
    if provider_info and provider_info.console_url:
        console.print(f"\n  {t('cli.init.llm_console_hint')}")
        console.print(f"  [cyan]{provider_info.console_url}[/cyan]")

    # 3. API Key ──────────────────────────────────────────────────────────────
    needs_key = provider_info.needs_key if provider_info else True
    if needs_key:
        api_key = questionary.password(
            t("cli.init.llm_api_key_prompt"),
            style=SKARO_STYLE,
        ).ask()

        if api_key is None:
            raise SystemExit(0)

        env_name = (
            provider_info.api_key_env
            if provider_info and provider_info.api_key_env
            else f"{provider.upper()}_API_KEY"
        )
        save_secret(env_name, api_key)
        cfg.llm.api_key_env = env_name
    else:
        console.print(f"\n  [dim]{t('cli.init.llm_no_key_needed')}[/dim]")

    # 4. Model ────────────────────────────────────────────────────────────────
    model_choices_raw = get_model_choices(provider)
    default_model = provider_info.default_model if provider_info else ""

    model_choices = [
        questionary.Choice(f"{display}  [dim]({mid})[/dim]" if display != mid else mid, value=mid)
        for display, mid in model_choices_raw
    ]
    model_choices.append(questionary.Choice(_CUSTOM_MODEL_LABEL, value="__custom__"))

    model = questionary.select(
        t("cli.init.llm_model_prompt"),
        choices=model_choices,
        default=default_model,
        style=SKARO_STYLE,
    ).ask()

    if model is None:
        raise SystemExit(0)

    if model == "__custom__":
        model = questionary.text(
            t("cli.init.llm_model_custom_prompt"),
            default=default_model,
            style=SKARO_STYLE,
        ).ask()
        if not model:
            raise SystemExit(0)

    cfg.llm.model = model

    # 5. Max tokens for import ────────────────────────────────────────────────
    token_limit_str = questionary.text(
        t("cli.init.llm_token_limit_prompt"),
        default=str(cfg.import_config.token_limit),
        style=SKARO_STYLE,
    ).ask()

    if token_limit_str is None:
        raise SystemExit(0)

    try:
        cfg.import_config.token_limit = int(token_limit_str)
    except ValueError:
        pass  # keep default

    # Save ────────────────────────────────────────────────────────────────────
    save_config(cfg)

    console.print(
        f"\n  [green]✓[/green] "
        f"{t('cli.init.llm_configured', provider=provider, model=model)}"
    )
    return cfg


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
    import asyncio

    am = ArtifactManager()

    # ── Re-initialization guard ──────────────────────────────────────────────
    if am.is_initialized:
        console.print(f"[yellow]⚠[/yellow]  {t('cli.init.already_exists')}")
        if not click.confirm(t("cli.init.reinit_confirm"), default=False):
            return
        am.clear_import_flags()
        console.print(f"[dim]{t('cli.init.reinit_notice')}[/dim]")

    # ── Init wizard: banner → language → license → confirm ───────────────────
    _print_init_banner()

    lang = _select_language()

    _show_license_and_confirm()

    # ── Project name ─────────────────────────────────────────────────────────
    cwd = Path.cwd()
    if name is None:
        default_name = cwd.name
        name = questionary.text(
            t("cli.init.name_prompt"),
            default=default_name,
            style=SKARO_STYLE,
        ).ask()
        if name is None:
            raise SystemExit(0)

    # ── Detect existing project ──────────────────────────────────────────────
    is_existing = _detect_existing_project(cwd, no_git=no_git)

    # ── Bootstrap .skaro/ structure ─────────────────────────────────────────
    skaro_path = am.init_project()

    # Save language + project name to config
    cfg = load_config()
    changed = False
    if lang and cfg.lang != lang:
        cfg.lang = lang
        changed = True
    if name and cfg.project_name != name:
        cfg.project_name = name
        changed = True
    if description and cfg.project_description != description:
        cfg.project_description = description
        changed = True
    if not cfg.project_name:
        cfg.project_name = name or cwd.name
        changed = True
    if changed:
        save_config(cfg)

    if not is_existing:
        # ── New project: standard flow ───────────────────────────────────────
        _print_init_success_new(skaro_path, no_git, am)
        return

    # ── Existing project: A/B choice ─────────────────────────────────────────
    console.print()
    console.print(
        Panel(
            t("cli.init.existing_detected", name=name, path=str(cwd)),
            border_style="cyan",
            padding=(1, 2),
        )
    )

    choice = questionary.select(
        t("cli.init.existing_choice_prompt"),
        choices=[
            questionary.Choice(
                t("cli.init.choice_a_label"),
                value="A",
            ),
            questionary.Choice(
                t("cli.init.choice_b_label"),
                value="B",
            ),
        ],
        default="A",
        style=SKARO_STYLE,
    ).ask()

    if choice is None:
        raise SystemExit(0)

    if choice == "A":
        _print_init_success_manual(skaro_path)
        am.mark_imported(mode="manual", source_commit=_get_git_head(cwd))
        return

    # ── Option B: inline LLM setup + automatic analysis ──────────────────────
    cfg = load_config()
    cfg = _setup_llm_interactive(cfg)

    asyncio.run(_run_import_analyze(am, cfg, name, cwd, no_git))


def _detect_existing_project(cwd: Path, *, no_git: bool) -> bool:
    """Return True if the directory looks like an existing project."""
    if not no_git and (cwd / ".git").is_dir():
        return True
    code_extensions = {".py", ".ts", ".js", ".go", ".rs", ".java", ".rb", ".cs", ".php"}
    count = sum(
        1
        for p in cwd.rglob("*")
        if p.is_file()
        and p.suffix.lower() in code_extensions
        and ".skaro" not in str(p)
        and "node_modules" not in str(p)
        and ".venv" not in str(p)
    )
    return count >= 3


def _get_git_head(cwd: Path) -> str:
    """Return the current HEAD commit hash or empty string."""
    try:
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


async def _run_import_analyze(
    am: ArtifactManager,
    cfg: "SkaroConfig",
    name: str,
    cwd: Path,
    no_git: bool,
) -> None:
    """Run the full automatic import flow (option B)."""
    from skaro_core.phases.repo_scan import RepoScanner, estimate_tokens
    from skaro_core.phases.import_analyze import ImportAnalyzePhase

    # ── Scan & estimate ──────────────────────────────────────────────────────
    console.print(f"\n  {t('cli.init.scanning')}  ", end="")
    scanner = RepoScanner(
        cwd,
        token_limit=cfg.import_config.token_limit,
        max_file_size=cfg.import_config.max_file_size,
    )

    import asyncio as _asyncio

    scan = await _asyncio.to_thread(scanner.scan)

    console.print(f"[green]✓[/green]")
    console.print(
        f"  {t('cli.init.scan_summary', files=len(scan.files), tokens=scan.estimated_tokens)}"
    )

    if scan.sampled:
        console.print(f"  [yellow]⚡[/yellow] {t('cli.init.smart_sampling_applied', skipped=len(scan.skipped_paths))}")

    # ── Show .skaroignore exclusions ─────────────────────────────────────────
    skaroignored = scanner.skaroignored_files()
    if skaroignored:
        console.print(f"\n  [dim]{t('cli.init.skaroignored', count=len(skaroignored))}[/dim]")
        for p in skaroignored[:5]:
            console.print(f"    [dim]  · {p}[/dim]")
        if len(skaroignored) > 5:
            console.print(f"    [dim]  … and {len(skaroignored) - 5} more[/dim]")

    # ── Privacy warning + confirmation ───────────────────────────────────────
    console.print()
    console.print(
        Panel(
            t("cli.init.privacy_warning", provider=cfg.llm.provider),
            border_style="yellow",
            padding=(1, 2),
        )
    )

    if not click.confirm(t("cli.init.confirm_send"), default=False):
        console.print(f"  [dim]{t('cli.init.cancelled')}[/dim]")
        raise SystemExit(0)

    # ── Run phase ────────────────────────────────────────────────────────────
    console.print(f"\n  {t('cli.init.analyzing')}  ")

    phase = ImportAnalyzePhase(project_root=cwd, config=cfg)
    source_commit = _get_git_head(cwd)

    def _on_chunk(text: str) -> None:
        console.print(text, end="", highlight=False)

    phase.on_stream_chunk = lambda text: _asyncio.get_event_loop().call_soon_threadsafe(
        _on_chunk, text
    )

    try:
        result = await phase.run(project_name=name, source_commit=source_commit)
    except Exception as exc:
        from skaro_core.llm.base import LLMError

        console.print()
        if isinstance(exc, LLMError):
            if exc.retriable:
                console.print(f"\n[yellow]⚠[/yellow]  {t('cli.init.llm_rate_limit')}")
                console.print(f"  [dim]{t('cli.init.llm_rate_limit_hint')}[/dim]")
            else:
                console.print(f"\n[red]✗[/red]  {t('cli.init.llm_error', error=str(exc)[:300])}")
        else:
            console.print(f"\n[red]✗[/red]  {t('cli.init.import_failed', reason=str(exc)[:300])}")
        raise SystemExit(1)

    console.print()

    if not result.success:
        console.print(f"\n[red]✗[/red]  {t('cli.init.import_failed', reason=result.message[:200])}")
        raise SystemExit(1)

    # ── Success summary ──────────────────────────────────────────────────────
    data = result.data
    scan_info = data.get("scan", {})

    console.print(f"\n[green]✓[/green]  {t('cli.init.import_success')}")
    console.print()
    console.print(f"  {t('cli.init.created_artifacts')}")
    for path in result.artifacts_created[:8]:
        short = Path(path).relative_to(cwd) if Path(path).is_absolute() else Path(path)
        console.print(f"    📄 {short}")
    if len(result.artifacts_created) > 8:
        console.print(f"    … {len(result.artifacts_created) - 8} more")

    console.print()
    console.print(f"  [bold]{t('cli.init.import_next_steps')}[/bold]")
    console.print(f"    1. {t('cli.init.review_constitution')}")
    console.print(f"    2. {t('cli.init.review_architecture')}")
    console.print(f"    3. {t('cli.init.review_devplan')}")
    console.print(f"    4. [cyan]skaro ui[/cyan]")


def _print_init_success_new(skaro_path: Path, no_git: bool, am: ArtifactManager) -> None:
    console.print(f"[green]✓[/green] {t('cli.init.success', path=str(skaro_path))}")
    console.print()
    console.print("  Created:")
    console.print("    📄 .skaro/constitution.md               — fill in your project principles")
    console.print("    📄 .skaro/architecture/architecture.md  — describe your architecture")
    console.print("    📄 .skaro/config.yaml                   — LLM and project settings")
    console.print("    📄 .skaroignore                         — files excluded from LLM analysis")

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


def _print_init_success_manual(skaro_path: Path) -> None:
    console.print(f"\n[green]✓[/green] {t('cli.init.success', path=str(skaro_path))}")
    console.print()
    console.print(f"  {t('cli.init.manual_mode_hint')}")
    console.print()
    console.print("  [bold]Next steps:[/bold]")
    console.print("    1. Configure LLM:         [cyan]skaro config --provider groq[/cyan]")
    console.print("    2. Fill in constitution:  [cyan]nano .skaro/constitution.md[/cyan]")
    console.print("    3. Fill in architecture:  [cyan]nano .skaro/architecture/architecture.md[/cyan]")
    console.print("    4. Launch dashboard:       [cyan]skaro ui[/cyan]")
    console.print("    5. Generate dev plan:      [cyan]Dashboard → Dev Plan[/cyan]")


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
        uvicorn.run(app, host="0.0.0.0", port=actual_port, log_level="info")
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


# ── skaro update ─────────────────────────────────


@cli.command()
@click.option("--force", is_flag=True, help="Bypass 24 h cache and check PyPI now")
def update(force: bool) -> None:
    """Check for a newer version of Skaro and show upgrade instructions."""
    from skaro_core.update_check import check_for_update

    console.print(f"\n  {t('cli.update.checking')}")

    result = check_for_update(force=force)

    console.print(f"  {t('cli.update.current')}: [cyan]{result.current_version}[/cyan]")

    if result.error:
        console.print(f"  [yellow]⚠[/yellow] {result.error}")
        console.print(f"  {t('cli.update.docs_hint')}: [cyan]{result.docs_url}[/cyan]\n")
        return

    console.print(f"  {t('cli.update.latest')}:  [cyan]{result.latest_version}[/cyan]")

    if not result.has_update:
        console.print(f"\n  [green]✓[/green] {t('cli.update.up_to_date')}\n")
        return

    console.print(
        Panel(
            f"  {t('cli.update.available', version=result.latest_version)}\n\n"
            f"  {t('cli.update.method')}: [dim]{result.install_method}[/dim]\n"
            f"  {t('cli.update.run')}:\n\n"
            f"    [cyan]{result.update_instruction}[/cyan]\n\n"
            f"  {t('cli.update.docs_hint')}: [cyan]{result.docs_url}[/cyan]",
            border_style="yellow",
            padding=(1, 2),
        )
    )


# ── skaro skills ──────────────────────────────────


@cli.group()
def skills() -> None:
    """Manage project skills (LLM instruction packs)."""


@skills.command("list")
def skills_list() -> None:
    """List all available skills and their status."""
    _ensure_initialized()
    config = load_config()

    from skaro_core.skills import list_all_with_status

    items = list_all_with_status(config.skills, project_root=None)

    if not items:
        console.print("  [dim]No skills available.[/dim]")
        if not config.skills.preset:
            console.print(
                "  [dim]Hint: apply a constitution preset to get built-in skills.[/dim]"
            )
        return

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Skill", style="cyan")
    table.add_column("Source")
    table.add_column("Status")
    table.add_column("Phases", style="dim")

    status_styles = {
        "active": "[green]active[/green]",
        "disabled": "[yellow]disabled[/yellow]",
        "available": "[dim]available[/dim]",
        "missing": "[red]missing[/red]",
    }

    for item in items:
        table.add_row(
            item["name"],
            item["source"],
            status_styles.get(item["status"], item["status"]),
            ", ".join(item["phases"]) if item["phases"] else "all",
        )

    if config.skills.preset:
        console.print(f"\n  Preset: [cyan]{config.skills.preset}[/cyan]\n")
    console.print(table)
    console.print()


@skills.command("info")
@click.argument("skill_name")
def skills_info(skill_name: str) -> None:
    """Show details of a specific skill."""
    _ensure_initialized()
    config = load_config()

    from skaro_core.skills.loader import discover_all_skills

    all_skills = discover_all_skills(config.skills, project_root=None)
    skill = all_skills.get(skill_name)
    if not skill:
        console.print(f"  [red]✗[/red] Skill '{skill_name}' not found.")
        raise SystemExit(1)

    console.print(f"\n  [bold cyan]{skill.name}[/bold cyan]")
    if skill.description:
        console.print(f"  {skill.description}")
    console.print(f"  Source: {skill.source}")
    if skill.phases:
        console.print(f"  Phases: {', '.join(skill.phases)}")
    if skill.roles:
        console.print(f"  Roles: {', '.join(skill.roles)}")
    console.print()
    if skill.instructions:
        console.print(Panel(skill.instructions.strip(), border_style="dim", padding=(1, 2)))


@skills.command("enable")
@click.argument("skill_name")
def skills_enable(skill_name: str) -> None:
    """Activate a skill."""
    _ensure_initialized()
    config = load_config()

    # Remove from disabled if present
    if skill_name in config.skills.disabled:
        config.skills.disabled.remove(skill_name)

    # Add to active if not a preset skill (preset skills are active by default)
    from skaro_core.skills.loader import discover_all_skills

    all_skills = discover_all_skills(config.skills, project_root=None)
    skill = all_skills.get(skill_name)

    if skill and skill.source == "preset":
        # Preset skill — just removing from disabled is enough
        pass
    elif skill_name not in config.skills.active:
        config.skills.active.append(skill_name)

    save_config(config)
    console.print(f"  [green]✓[/green] Skill '{skill_name}' enabled.")


@skills.command("disable")
@click.argument("skill_name")
def skills_disable(skill_name: str) -> None:
    """Deactivate a skill."""
    _ensure_initialized()
    config = load_config()

    # Remove from active if present
    if skill_name in config.skills.active:
        config.skills.active.remove(skill_name)

    # Add to disabled
    if skill_name not in config.skills.disabled:
        config.skills.disabled.append(skill_name)

    save_config(config)
    console.print(f"  [yellow]✓[/yellow] Skill '{skill_name}' disabled.")


@skills.command("create")
@click.argument("skill_name")
def skills_create(skill_name: str) -> None:
    """Create a new user skill from template in .skaro/skills/."""
    am = _ensure_initialized()
    skills_dir = am.skaro / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    target = skills_dir / f"{skill_name}.yaml"
    if target.exists():
        console.print(f"  [yellow]⚠[/yellow] Skill '{skill_name}' already exists: {target}")
        raise SystemExit(1)

    template = (
        f"name: {skill_name}\n"
        f'description: ""\n'
        f'version: "1.0"\n'
        f"\n"
        f"# Uncomment to limit to specific phases/roles:\n"
        f"# phases:\n"
        f"#   - implement\n"
        f"#   - plan\n"
        f"#   - tests\n"
        f"# roles:\n"
        f"#   - coder\n"
        f"#   - reviewer\n"
        f"\n"
        f"instructions: |\n"
        f"  ## {skill_name}\n"
        f"  Add your instructions here.\n"
    )
    target.write_text(template, encoding="utf-8")
    console.print(f"  [green]✓[/green] Created: {target}")
    console.print(f"  [dim]Enable with: skaro skills enable {skill_name}[/dim]")


# ── Entrypoint ──────────────────────────────────


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
