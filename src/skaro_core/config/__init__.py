"""Skaro configuration package.

Public API (backward-compatible):
    from skaro_core.config import SkaroConfig, LLMConfig, load_config, save_config, ...
"""

from skaro_core.config._io import find_project_root, load_config, save_config, skaro_path
from skaro_core.config._models import (
    CONFIG_FILENAME,
    GLOBAL_CONFIG_DIR,
    ROLE_PHASES,
    SECRETS_FILENAME,
    SKARO_DIR,
    TOKENS_FILENAME,
    USAGE_LOG_FILENAME,
    LLMConfig,
    RoleConfig,
    SkaroConfig,
    UIConfig,
)
from skaro_core.config._secrets import load_secrets, save_secret
from skaro_core.config._token_tracking import add_token_usage, load_token_usage, load_usage_log

__all__ = [
    # Constants
    "CONFIG_FILENAME",
    "GLOBAL_CONFIG_DIR",
    "ROLE_PHASES",
    "SECRETS_FILENAME",
    "SKARO_DIR",
    "TOKENS_FILENAME",
    "USAGE_LOG_FILENAME",
    # Dataclasses
    "LLMConfig",
    "RoleConfig",
    "SkaroConfig",
    "UIConfig",
    # Config I/O
    "find_project_root",
    "load_config",
    "save_config",
    "skaro_path",
    # Secrets
    "load_secrets",
    "save_secret",
    # Token tracking
    "add_token_usage",
    "load_token_usage",
    "load_usage_log",
]
