# Skaro

AI-powered SDLC orchestration platform.

Developer is the architect. LLM is the amplifier.
Specifications live in the repository next to code. Context never gets lost.

## Install

```
pip install skaro
```

Python 3.11+ required. Everything included: CLI, web dashboard, LLM adapters, templates.

## Quick start

```
cd my-project
skaro init
skaro ui
```

`skaro init` creates a `.skaro/` directory with constitution, architecture template, and config.

`skaro ui` starts the web dashboard at `http://localhost:4700`. LLM provider is configured from the UI.

## From source (development)

```
git clone https://github.com/skarodev/skaro.git
cd skaro
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