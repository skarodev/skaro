"""Configuration dataclasses and constants."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SKARO_DIR = ".skaro"
CONFIG_FILENAME = "config.yaml"
SECRETS_FILENAME = "secrets.yaml"
TOKENS_FILENAME = "token_usage.yaml"
USAGE_LOG_FILENAME = "usage_log.jsonl"
GLOBAL_CONFIG_DIR = Path.home() / ".skaro"

# Roles and which phases they cover
ROLE_PHASES: dict[str, list[str]] = {
    "architect": ["architecture", "devplan", "plan", "import_analyze"],
    "coder": ["implement", "fix"],
    "reviewer": ["tests", "clarify"],
}


@dataclass
class LLMConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    api_key_env: str = ""
    base_url: str | None = None
    max_tokens: int = 16384
    temperature: float = 0.3

    @property
    def api_key(self) -> str | None:
        """Resolve API key: env var -> secrets.yaml -> provider preset env -> None."""
        env_name = self.api_key_env
        if not env_name:
            from skaro_core.llm.base import PROVIDER_PRESETS

            preset = PROVIDER_PRESETS.get(self.provider)
            if preset and preset[1]:
                env_name = preset[1]

        if env_name:
            value = os.environ.get(env_name)
            if value:
                return value

            from skaro_core.config._secrets import load_secrets

            value = load_secrets().get(env_name)
            if value:
                return value

        return None

    @property
    def api_key_value(self) -> str:
        """Deprecated alias."""
        return self.api_key_env


@dataclass
class RoleConfig:
    """Override LLM settings for a specific role. None means use default."""

    provider: str | None = None
    model: str | None = None
    api_key_env: str | None = None
    base_url: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None

    @property
    def is_active(self) -> bool:
        return self.provider is not None and self.model is not None

    @property
    def api_key_value(self) -> str | None:
        """Deprecated alias."""
        return self.api_key_env


@dataclass
class UIConfig:
    auto_open_browser: bool = True


@dataclass
class VerifyCommand:
    """A single verification command to run during the Tests phase."""

    name: str = ""
    command: str = ""


@dataclass
class ImportConfig:
    """Settings for the 'skaro init' existing-project analysis flow."""

    token_limit: int = 200_000
    """Maximum estimated tokens to send to LLM. Triggers smart sampling above this."""

    max_file_size: int = 100_000
    """Skip individual files larger than this many bytes."""


@dataclass
class SkaroConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    import_config: ImportConfig = field(default_factory=ImportConfig)
    lang: str = "en"
    theme: str = "dark"
    project_name: str = ""
    project_description: str = ""
    roles: dict[str, RoleConfig] = field(
        default_factory=lambda: {
            "architect": RoleConfig(),
            "coder": RoleConfig(),
            "reviewer": RoleConfig(),
        }
    )
    verify_commands: list[VerifyCommand] = field(default_factory=list)

    def llm_for_role(self, role: str | None) -> LLMConfig:
        """Return LLM config for a specific role, falling back to default."""
        if role and role in self.roles:
            rc = self.roles[role]
            if rc.is_active:
                api_key_env = rc.api_key_env
                if not api_key_env and rc.provider == self.llm.provider:
                    api_key_env = self.llm.api_key_env

                base_url = rc.base_url
                if base_url is None and rc.provider == self.llm.provider:
                    base_url = self.llm.base_url

                return LLMConfig(
                    provider=rc.provider,
                    model=rc.model,
                    api_key_env=api_key_env or "",
                    base_url=base_url,
                    max_tokens=rc.max_tokens if rc.max_tokens is not None else self.llm.max_tokens,
                    temperature=rc.temperature if rc.temperature is not None else self.llm.temperature,
                )
        return self.llm

    def role_for_phase(self, phase_name: str) -> str | None:
        """Determine which role covers a given phase."""
        for role, phases in ROLE_PHASES.items():
            if phase_name in phases:
                return role
        return None

    def llm_for_phase(self, phase_name: str) -> LLMConfig:
        """Return LLM config for a phase (resolves role automatically)."""
        return self.llm_for_role(self.role_for_phase(phase_name))

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "llm": {
                "provider": self.llm.provider,
                "model": self.llm.model,
                "api_key_env": self.llm.api_key_env,
                "base_url": self.llm.base_url,
                "max_tokens": self.llm.max_tokens,
                "temperature": self.llm.temperature,
            },
            "ui": {
                "auto_open_browser": self.ui.auto_open_browser,
            },
            "import": {
                "token_limit": self.import_config.token_limit,
                "max_file_size": self.import_config.max_file_size,
            },
            "lang": self.lang,
            "theme": self.theme,
            "project_name": self.project_name,
            "project_description": self.project_description,
        }
        roles_dict: dict[str, Any] = {}
        for rname, rc in self.roles.items():
            if rc.is_active:
                roles_dict[rname] = {
                    "provider": rc.provider,
                    "model": rc.model,
                    "api_key_env": rc.api_key_env,
                    "base_url": rc.base_url,
                    "max_tokens": rc.max_tokens,
                    "temperature": rc.temperature,
                }
            else:
                roles_dict[rname] = None
        d["roles"] = roles_dict

        if self.verify_commands:
            d["verify_commands"] = [
                {"name": vc.name, "command": vc.command}
                for vc in self.verify_commands
            ]

        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkaroConfig:
        llm_data = data.get("llm", {})
        ui_data = data.get("ui", {})
        import_data = data.get("import", {})
        roles_data = data.get("roles", {})

        roles: dict[str, RoleConfig] = {}
        for rname in ("architect", "coder", "reviewer"):
            rd = roles_data.get(rname)
            if rd and isinstance(rd, dict):
                roles[rname] = RoleConfig(
                    provider=rd.get("provider"),
                    model=rd.get("model"),
                    api_key_env=rd.get("api_key_env") or rd.get("api_key") or None,
                    base_url=rd.get("base_url"),
                    max_tokens=rd.get("max_tokens"),
                    temperature=rd.get("temperature"),
                )
            else:
                roles[rname] = RoleConfig()

        # Parse verify_commands
        vc_data = data.get("verify_commands", [])
        verify_commands: list[VerifyCommand] = []
        if isinstance(vc_data, list):
            for item in vc_data:
                if isinstance(item, dict):
                    verify_commands.append(
                        VerifyCommand(
                            name=item.get("name", ""),
                            command=item.get("command", ""),
                        )
                    )

        return cls(
            llm=LLMConfig(
                provider=llm_data.get("provider", "anthropic"),
                model=llm_data.get("model", "claude-sonnet-4-6"),
                api_key_env=llm_data.get("api_key_env") or llm_data.get("api_key", ""),
                base_url=llm_data.get("base_url"),
                max_tokens=llm_data.get("max_tokens", 16384),
                temperature=llm_data.get("temperature", 0.3),
            ),
            ui=UIConfig(
                auto_open_browser=ui_data.get("auto_open_browser", True),
            ),
            import_config=ImportConfig(
                token_limit=import_data.get("token_limit", 200_000),
                max_file_size=import_data.get("max_file_size", 100_000),
            ),
            lang=data.get("lang", "en"),
            theme=data.get("theme", "dark"),
            project_name=data.get("project_name", ""),
            project_description=data.get("project_description", ""),
            roles=roles,
            verify_commands=verify_commands,
        )
