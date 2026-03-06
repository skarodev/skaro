<div align="center">

# Skaro — AI-powered Software Development orchestration platform

<br />

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/skarodev/skaro/3e2cd385d4e49d4375ff14b7391903931652b62b/assets/logo-dark.svg" />
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/skarodev/skaro/3e2cd385d4e49d4375ff14b7391903931652b62b/assets/logo-light.svg" />
  <img src="https://raw.githubusercontent.com/skarodev/skaro/3e2cd385d4e49d4375ff14b7391903931652b62b/assets/logo-dark.svg" alt="Skaro" width="200" />
</picture>

<br />
<br />

![PyPI - Version](https://img.shields.io/pypi/v/skaro?style=for-the-badge)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/skaro?style=for-the-badge)
![GitHub License](https://img.shields.io/github/license/skarodev/skaro?style=for-the-badge)

<br />

[Documentation](https://docs.skaro.dev) · [PyPI](https://pypi.org/project/skaro/) · [Telegram](https://t.me/skarodev) · [Discord](https://discord.gg/zUv6AHuJwD)

</div>

---

Developer is the architect, the AI is the executor.
<br />
Specifications live in the repository next to code. Context never gets lost.

## Install

Python 3.11+ required. Everything included: CLI, web dashboard, LLM adapters, templates.

**Linux / macOS:**

```sh
curl -fsSL https://raw.githubusercontent.com/skarodev/skaro/main/install.sh | sh
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/skarodev/skaro/main/install.ps1 | iex
```

**Alternative (if you have pipx or uv):**

```
pipx install skaro
# or
uv tool install skaro
```

## Quick start

```
cd my-project
skaro init
skaro ui
```

`skaro init` creates a `.skaro/` directory with constitution, architecture template, and config.

`skaro ui` starts the web dashboard at `http://localhost:4700`. LLM provider is configured from the UI.

## Update

Check for a new version:

```
skaro update
```

Use `--force` to bypass the 24-hour cache:

```
skaro update --force
```

**Upgrade — install script (venv):**

| OS | Command |
|---|---|
| Windows | `& "$env:USERPROFILE\.skaro\venv\Scripts\pip.exe" install --upgrade skaro` |
| macOS / Linux | `~/.skaro/venv/bin/pip install --upgrade skaro` |

Or simply re-run the install script — it detects the existing venv and upgrades in place.

**Upgrade — pipx:**

```
pipx upgrade skaro
```

Verify after upgrade:

```
skaro --version
```

## From source (development)

```
git clone https://github.com/skarodev/skaro.git
cd skaro
python3 -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Frontend (requires Node.js 18+):

```
cd frontend
npm install
npm run build
```

Run tests:

```
pytest
```

## License

AGPL-3.0 — see [LICENSE](LICENSE).

---

From Russia with love ❤️

