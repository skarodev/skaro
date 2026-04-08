"""Tests for Skaro Web API endpoints using FastAPI TestClient.

Requires: pip install httpx (used by TestClient internally).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from skaro_core.artifacts import ArtifactManager
from skaro_web.app import create_app


@pytest.fixture
def uninit_project():
    """Temporary project directory, NOT initialized."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def init_project():
    """Temporary project directory, initialized with .skaro/."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        am = ArtifactManager(root)
        am.init_project()
        yield root


@pytest.fixture
def client(init_project) -> TestClient:
    """TestClient bound to an initialized project."""
    app = create_app(project_root=init_project)
    return TestClient(app)


@pytest.fixture
def uninit_client(uninit_project) -> TestClient:
    """TestClient bound to an uninitialized project."""
    app = create_app(project_root=uninit_project)
    return TestClient(app)


# ═══════════════════════════════════════════════════
# Status
# ═══════════════════════════════════════════════════

class TestStatusAPI:

    def test_status_uninitialized(self, uninit_client):
        resp = uninit_client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["initialized"] is False

    def test_status_initialized(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["initialized"] is True
        assert "tasks" in data
        assert "config" in data

    def test_tokens_endpoint(self, client):
        resp = client.get("/api/tokens")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_tokens" in data

    def test_stats_endpoint(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "tokens" in data
        assert "total_requests" in data

    def test_dashboard_endpoint(self, client):
        resp = client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "stats" in data


# ═══════════════════════════════════════════════════
# Constitution
# ═══════════════════════════════════════════════════

class TestConstitutionAPI:

    def test_get_empty_constitution(self, client):
        resp = client.get("/api/constitution")
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert data["has_constitution"] is False

    def test_save_and_read_constitution(self, client):
        content = "# Constitution\n\n## Stack\n- Python 3.12"
        resp = client.put("/api/constitution", json={"content": content})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        resp = client.get("/api/constitution")
        data = resp.json()
        assert data["has_constitution"] is True
        assert "Python 3.12" in data["content"]

    def test_validate_empty(self, client):
        resp = client.post("/api/constitution/validate")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════
# Architecture
# ═══════════════════════════════════════════════════

class TestArchitectureAPI:

    def test_get_architecture(self, client):
        resp = client.get("/api/architecture")
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert "adrs" in data

    def test_save_architecture(self, client):
        resp = client.put("/api/architecture", json={"content": "# Architecture\n\nMicroservices"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_get_adrs_empty(self, client):
        resp = client.get("/api/architecture/adrs")
        assert resp.status_code == 200
        assert resp.json()["adrs"] == []

    def test_create_adr(self, client):
        resp = client.post("/api/architecture/adrs", json={"title": "Use PostgreSQL"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["number"] == 1

        # Verify it appears in list
        resp = client.get("/api/architecture/adrs")
        assert len(resp.json()["adrs"]) == 1

    def test_approve_architecture_without_content(self, client):
        resp = client.post("/api/architecture/approve")
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_approve_architecture_with_content(self, client):
        client.put("/api/architecture", json={"content": "# Arch\nMono"})
        resp = client.post("/api/architecture/approve")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# ═══════════════════════════════════════════════════
# DevPlan
# ═══════════════════════════════════════════════════

class TestDevPlanAPI:

    def test_get_empty_devplan(self, client):
        resp = client.get("/api/devplan")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_devplan"] is False

    def test_save_devplan(self, client):
        resp = client.put("/api/devplan", json={"content": "# Plan\n\n## Milestone 1"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# ═══════════════════════════════════════════════════
# Tasks
# ═══════════════════════════════════════════════════

class TestTasksAPI:

    def _setup_milestone(self, client):
        """Create a milestone so we can create tasks."""
        # Directly init via AM since there's no milestone-create endpoint
        am = ArtifactManager(client.app.state.project_root)
        am.create_milestone("01-foundation", title="Foundation")

    def test_get_tasks_empty(self, client):
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        assert resp.json()["tasks"] == []

    def test_create_task(self, client):
        self._setup_milestone(client)
        resp = client.post("/api/tasks", json={
            "name": "auth-setup",
            "milestone": "01-foundation",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["name"] == "auth-setup"

    def test_create_task_then_list(self, client):
        self._setup_milestone(client)
        client.post("/api/tasks", json={"name": "auth", "milestone": "01-foundation"})
        resp = client.get("/api/tasks")
        assert len(resp.json()["tasks"]) == 1

    def test_get_task_detail(self, client):
        self._setup_milestone(client)
        client.post("/api/tasks", json={"name": "auth", "milestone": "01-foundation"})
        resp = client.get("/api/tasks/auth")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "auth"
        assert "files" in data
        assert "stages" in data
        assert "phases" in data["state"]

    def test_get_task_not_found(self, client):
        resp = client.get("/api/tasks/nonexistent")
        assert resp.status_code == 200  # returns {success: False}
        assert resp.json()["success"] is False

    def test_create_task_empty_name(self, client):
        resp = client.post("/api/tasks", json={"name": "", "milestone": "01-foundation"})
        assert resp.status_code == 422  # Pydantic validation

    def test_create_task_empty_milestone(self, client):
        resp = client.post("/api/tasks", json={"name": "auth", "milestone": ""})
        assert resp.status_code == 200
        assert resp.json()["success"] is False


# ═══════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════

class TestConfigAPI:

    def test_get_config(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm" in data
        assert "ui" in data
        assert "_provider_presets" in data
        assert "_role_phases" in data

    def test_update_config(self, client):
        resp = client.put("/api/config", json={
            "llm": {"provider": "openai", "model": "gpt-4o"},
            "lang": "ru",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify persistence
        resp = client.get("/api/config")
        data = resp.json()
        assert data["llm"]["provider"] == "openai"
        assert data["lang"] == "ru"


# ═══════════════════════════════════════════════════
# Validation / Error handling
# ═══════════════════════════════════════════════════

class TestValidationErrors:

    def test_file_apply_rejects_traversal(self, client, init_project):
        am = ArtifactManager(init_project)
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")

        resp = client.post("/api/tasks/auth/apply-file", json={
            "filepath": "../../../etc/passwd",
            "content": "hacked",
        })
        assert resp.status_code == 422  # Pydantic catches .. in validator

    def test_fix_apply_rejects_traversal(self, client, init_project):
        am = ArtifactManager(init_project)
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")

        resp = client.post("/api/tasks/auth/fix/apply", json={
            "filepath": "../../etc/shadow",
            "content": "hacked",
        })
        assert resp.status_code == 422

    def test_fix_rejects_empty_message(self, client):
        resp = client.post("/api/tasks/auth/fix", json={
            "message": "",
        })
        assert resp.status_code == 422

    def test_adr_status_rejects_invalid(self, client):
        resp = client.patch("/api/architecture/adrs/1/status", json={
            "status": "invalid_status",
        })
        assert resp.status_code == 422

    def test_config_rejects_bad_temperature(self, client):
        resp = client.put("/api/config", json={
            "llm": {"temperature": 99.0},
        })
        assert resp.status_code == 422


class TestFixConversationAPI:
    """Tests for fix conversation persistence endpoints."""

    def _setup_task(self, client):
        am = ArtifactManager(client.app.state.project_root)
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")

    def test_get_empty_conversation(self, client):
        self._setup_task(client)
        resp = client.get("/api/tasks/auth/fix/conversation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation"] == []
        assert "context_tokens" in data

    def test_get_fix_log_empty(self, client):
        self._setup_task(client)
        resp = client.get("/api/tasks/auth/fix/log")
        assert resp.status_code == 200
        assert resp.json()["content"] == ""

    def test_delete_conversation(self, client):
        self._setup_task(client)
        resp = client.delete("/api/tasks/auth/fix/conversation")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestAdrLifecycleAPI:
    """Full ADR lifecycle: create → update content → change status."""

    def test_full_adr_lifecycle(self, client):
        # Create
        resp = client.post("/api/architecture/adrs", json={"title": "Use PostgreSQL"})
        assert resp.json()["success"] is True
        num = resp.json()["number"]

        # Update content
        resp = client.put(f"/api/architecture/adrs/{num}", json={
            "content": "# ADR-001: Use PostgreSQL\n\n## Status: proposed\n\nWe choose PG.",
        })
        assert resp.json()["success"] is True

        # Change status
        resp = client.patch(f"/api/architecture/adrs/{num}/status", json={
            "status": "accepted",
        })
        assert resp.json()["success"] is True

        # Verify in list
        resp = client.get("/api/architecture/adrs")
        adrs = resp.json()["adrs"]
        assert len(adrs) == 1
        assert adrs[0]["number"] == num

    def test_update_nonexistent_adr(self, client):
        resp = client.put("/api/architecture/adrs/999", json={"content": "test"})
        assert resp.json()["success"] is False
