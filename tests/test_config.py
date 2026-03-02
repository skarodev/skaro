"""Tests for config management: round-trip, save/load, defaults."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from skaro_core.config import (
    LLMConfig,
    RoleConfig,
    SkaroConfig,
    UIConfig,
    load_config,
    save_config,
)


class TestConfigDefaults:

    def test_default_llm_config(self):
        cfg = SkaroConfig()
        assert cfg.llm.provider == "anthropic"
        assert cfg.llm.temperature == 0.3
        assert cfg.llm.max_tokens == 16384

    def test_default_ui_config(self):
        cfg = SkaroConfig()
        assert cfg.ui.auto_open_browser is True

    def test_default_roles(self):
        cfg = SkaroConfig()
        assert "architect" in cfg.roles
        assert "coder" in cfg.roles
        assert "reviewer" in cfg.roles
        # All inactive by default
        for rc in cfg.roles.values():
            assert not rc.is_active

    def test_role_is_active(self):
        rc = RoleConfig(provider="openai", model="gpt-4o")
        assert rc.is_active

    def test_role_is_inactive(self):
        rc = RoleConfig()
        assert not rc.is_active
        rc2 = RoleConfig(provider="openai")
        assert not rc2.is_active  # needs both provider AND model


class TestConfigRoundTrip:

    def test_to_dict_from_dict(self):
        original = SkaroConfig(
            llm=LLMConfig(provider="openai", model="gpt-4o", temperature=0.7),
            ui=UIConfig(),
            lang="ru",
            theme="light",
            project_name="MyProject",
            project_description="Test project",
        )
        d = original.to_dict()
        restored = SkaroConfig.from_dict(d)

        assert restored.llm.provider == "openai"
        assert restored.llm.model == "gpt-4o"
        assert restored.llm.temperature == 0.7
        assert restored.lang == "ru"
        assert restored.theme == "light"
        assert restored.project_name == "MyProject"

    def test_round_trip_with_roles(self):
        original = SkaroConfig(
            roles={
                "architect": RoleConfig(provider="anthropic", model="claude-opus-4-6"),
                "coder": RoleConfig(),
                "reviewer": RoleConfig(provider="openai", model="gpt-4o"),
            },
        )
        d = original.to_dict()
        restored = SkaroConfig.from_dict(d)

        assert restored.roles["architect"].is_active
        assert restored.roles["architect"].provider == "anthropic"
        assert not restored.roles["coder"].is_active
        assert restored.roles["reviewer"].model == "gpt-4o"

    def test_from_dict_with_minimal_data(self):
        cfg = SkaroConfig.from_dict({})
        assert cfg.llm.provider == "anthropic"
        assert cfg.lang == "en"

    def test_from_dict_preserves_api_key_env(self):
        cfg = SkaroConfig.from_dict({
            "llm": {"api_key_env": "ANTHROPIC_API_KEY"},
        })
        assert cfg.llm.api_key_env == "ANTHROPIC_API_KEY"

    def test_from_dict_handles_legacy_api_key_field(self):
        """Legacy config files may use 'api_key' instead of 'api_key_env'."""
        cfg = SkaroConfig.from_dict({
            "llm": {"api_key": "MY_ENV_KEY"},
        })
        assert cfg.llm.api_key_env == "MY_ENV_KEY"


class TestConfigSaveLoad:

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".skaro").mkdir()

            original = SkaroConfig(
                llm=LLMConfig(provider="openai", model="gpt-4o"),
                lang="de",
                project_name="TestProject",
            )
            save_config(original, root)
            loaded = load_config(root)

            assert loaded.llm.provider == "openai"
            assert loaded.llm.model == "gpt-4o"
            assert loaded.lang == "de"
            assert loaded.project_name == "TestProject"

    def test_load_missing_config_returns_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".skaro").mkdir()
            cfg = load_config(root)
            assert cfg.llm.provider == "anthropic"

    def test_llm_for_role_fallback(self):
        cfg = SkaroConfig(
            llm=LLMConfig(provider="anthropic", model="claude-sonnet-4-6"),
            roles={
                "architect": RoleConfig(provider="openai", model="gpt-4o"),
                "coder": RoleConfig(),
                "reviewer": RoleConfig(),
            },
        )
        # Active role → uses role config
        arch_llm = cfg.llm_for_role("architect")
        assert arch_llm.provider == "openai"
        assert arch_llm.model == "gpt-4o"

        # Inactive role → falls back to default
        coder_llm = cfg.llm_for_role("coder")
        assert coder_llm.provider == "anthropic"

        # Unknown role → falls back to default
        unknown_llm = cfg.llm_for_role("unknown")
        assert unknown_llm.provider == "anthropic"

        # None → default
        none_llm = cfg.llm_for_role(None)
        assert none_llm.provider == "anthropic"


class TestTokenUsageTracking:

    def test_add_token_usage_with_task_param(self):
        """New `task=` parameter works correctly."""
        from skaro_core.config import add_token_usage, load_token_usage, load_usage_log

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".skaro").mkdir()

            usage = {"input_tokens": 100, "output_tokens": 50}
            add_token_usage(usage, root, phase="implement", task="auth")

            # Cumulative totals
            totals = load_token_usage(root)
            assert totals["prompt_tokens"] == 100
            assert totals["completion_tokens"] == 50

            # Log entry has both task and feature fields
            log = load_usage_log(root)
            assert len(log) == 1
            assert log[0]["task"] == "auth"
            assert log[0]["feature"] == "auth"  # backward compat
            assert log[0]["phase"] == "implement"

    def test_add_token_usage_with_legacy_feature_param(self):
        """Deprecated `feature=` parameter still works."""
        from skaro_core.config import add_token_usage, load_usage_log

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".skaro").mkdir()

            usage = {"input_tokens": 200, "output_tokens": 100}
            add_token_usage(usage, root, phase="plan", feature="auth")

            log = load_usage_log(root)
            assert len(log) == 1
            assert log[0]["task"] == "auth"
            assert log[0]["feature"] == "auth"

    def test_add_token_usage_task_takes_precedence(self):
        """When both task= and feature= are given, task= wins."""
        from skaro_core.config import add_token_usage, load_usage_log

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".skaro").mkdir()

            usage = {"input_tokens": 50, "output_tokens": 25}
            add_token_usage(usage, root, task="new-name", feature="old-name")

            log = load_usage_log(root)
            assert log[0]["task"] == "new-name"

    def test_cumulative_token_totals(self):
        """Multiple calls accumulate token totals."""
        from skaro_core.config import add_token_usage, load_token_usage

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".skaro").mkdir()

            add_token_usage({"input_tokens": 100, "output_tokens": 50}, root)
            add_token_usage({"input_tokens": 200, "output_tokens": 100}, root)

            totals = load_token_usage(root)
            assert totals["prompt_tokens"] == 300
            assert totals["completion_tokens"] == 150
            assert totals["total_tokens"] == 450


class TestSecrets:

    def test_save_and_load_secret(self):
        from skaro_core.config import save_secret, load_secrets

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".skaro").mkdir()

            save_secret("ANTHROPIC_API_KEY", "sk-ant-test123", root)

            secrets = load_secrets(root)
            assert secrets["ANTHROPIC_API_KEY"] == "sk-ant-test123"

    def test_save_multiple_secrets(self):
        from skaro_core.config import save_secret, load_secrets

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".skaro").mkdir()

            save_secret("ANTHROPIC_API_KEY", "sk-ant-111", root)
            save_secret("OPENAI_API_KEY", "sk-222", root)

            secrets = load_secrets(root)
            assert len(secrets) == 2
            assert secrets["ANTHROPIC_API_KEY"] == "sk-ant-111"
            assert secrets["OPENAI_API_KEY"] == "sk-222"

    def test_save_secret_overwrites(self):
        from skaro_core.config import save_secret, load_secrets

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".skaro").mkdir()

            save_secret("KEY", "old_value", root)
            save_secret("KEY", "new_value", root)

            secrets = load_secrets(root)
            assert secrets["KEY"] == "new_value"

    def test_load_secrets_missing_file(self):
        from skaro_core.config import load_secrets

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".skaro").mkdir()
            assert load_secrets(root) == {}

    def test_api_key_resolves_from_env(self, monkeypatch):
        monkeypatch.setenv("TEST_API_KEY", "sk-from-env")
        cfg = LLMConfig(provider="anthropic", api_key_env="TEST_API_KEY")
        assert cfg.api_key == "sk-from-env"

    def test_api_key_resolves_from_secrets(self):
        from skaro_core.config import save_secret

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".skaro").mkdir()
            save_secret("MY_KEY", "sk-from-secrets", root)

            # Temporarily override find_project_root to return our tmpdir
            import skaro_core.config as cfg_mod
            original = cfg_mod.find_project_root

            cfg_mod.find_project_root = lambda start=None: root
            try:
                cfg = LLMConfig(provider="anthropic", api_key_env="MY_KEY")
                assert cfg.api_key == "sk-from-secrets"
            finally:
                cfg_mod.find_project_root = original

    def test_api_key_env_takes_precedence_over_secrets(self, monkeypatch):
        """Env var wins over secrets.yaml."""
        from skaro_core.config import save_secret

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".skaro").mkdir()
            save_secret("MY_KEY", "sk-from-secrets", root)
            monkeypatch.setenv("MY_KEY", "sk-from-env")

            cfg = LLMConfig(provider="anthropic", api_key_env="MY_KEY")
            assert cfg.api_key == "sk-from-env"

    def test_to_dict_never_contains_actual_key(self, monkeypatch):
        """Config serialization must never leak real API key values."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-real-secret")

        config = SkaroConfig(
            llm=LLMConfig(provider="anthropic", api_key_env="ANTHROPIC_API_KEY"),
        )
        d = config.to_dict()

        # Must contain env var name, not the actual key
        assert d["llm"]["api_key_env"] == "ANTHROPIC_API_KEY"
        assert "sk-ant-real-secret" not in str(d)
