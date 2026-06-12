# Agent Instructions for `vot-py` Maintenance & Development

You are an AI Agent tasked with maintaining, extending, or debugging `vot-py`, a modern, high-quality Python library for interacting with the Yandex Video Translation API.

The initial port from the TypeScript `vot.js` library has been completed. These instructions outline the established architecture, technology stack, and best practices. **Always refer to these guidelines when making modifications.**

---

## 1. Project Overview & Tech Stack

`vot-py` is a fully typed, asynchronous Python package targeting desktop and server environments.

### Established Tech Stack
- **Python Version**: 3.10+ (Modern typing and language features).
- **Dependency Management**: `uv` (Use `uv run`, `uv add`, etc.).
- **HTTP Client**: `httpx` (Asynchronous and synchronous clients).
- **Protobuf**: `protobuf` (Google's official Python implementation).
- **Data Validation/Models**: `pydantic` (v2).
- **Testing**: `pytest` + `pytest-asyncio`.
- **Linting & Formatting**: `ruff`.
- **Type Checking**: `mypy`.

---

## 2. Python Library Best Practices

All agents contributing to `vot-py` MUST adhere to the following Python library best practices:

1. **Strict Type Hinting**: Every function signature and class must have proper type hints. Use `typing` features extensively (e.g., `Optional`, `Union`, `Literal`, or new syntax `X | Y`).
2. **Docstrings**: Use Google-style or NumPy-style docstrings for all public modules, classes, and functions.
3. **Async First, Sync Optional**: The core client uses `httpx.AsyncClient`. A synchronous wrapper (`VOTClientSync`) is provided.
4. **Exception Handling**: Do not use bare `except:` clauses. Define custom exceptions (e.g., `VOTError`, `VOTAPIError`, `VideoDataError`) inheriting from Python's standard `Exception`.
5. **Clean Imports**: Use absolute imports (`from vot.client import VOTClient`) or explicit relative imports (`from . import utils`).
6. **No Global State**: Ensure that instances of the client do not leak state globally. Sessions and configurations should be bound to the client instance.

---

## 3. Project Architecture

The repository is structured as a standard Python package:

```text
vot-py/
├── pyproject.toml         # Project metadata, dependencies, and tool configs
├── README.md              # English documentation
├── README.ru.md           # Russian documentation
├── docs/                  # API documentation (English & Russian)
├── scripts/
│   └── generate_proto.sh  # Script to recompile protobuf bindings
├── src/
│   └── vot/
│       ├── __init__.py    # Exposes main clients and models
│       ├── cli.py         # CLI implementation & argument parsing
│       ├── client.py      # Core clients (MinimalClient, VOTClient, VOTClientSync, VOTWorkerClient)
│       ├── config.py      # Global configurations and constants
│       ├── exceptions.py  # Custom exception hierarchy
│       ├── models.py      # Pydantic data models
│       ├── helpers/       # Domain-specific extractors (e.g., youtube.py)
│       ├── protobuf/      # Yandex Protobuf schemas and compiled python files
│       └── utils/         # Crypto, URL parsing, subtitles conversion, and language normalization
├── tests/                 # Comprehensive pytest suite
└── vot-cli                # Bash wrapper for local CLI testing
```

---

## 4. Agent Workflow Rules

1. **Test Before Commit**: You must successfully run `uv run pytest`, `uv run mypy src tests`, and `uv run ruff check src tests` before claiming a task is complete or committing changes.
2. **Modifying Protobufs**: If you update `src/vot/protobuf/yandex.proto`, you MUST execute `./scripts/generate_proto.sh` to regenerate `yandex_pb2.py`.
3. **CLI Updates**: If you add new functionality to the CLI (`src/vot/cli.py`), make sure to write corresponding tests in `tests/test_cli.py` and update the READMEs.
4. **Small, Descriptive Commits**: Keep changes atomic and commit messages clear (e.g., `feat: add support for new video host`, `fix: resolve mypy typing error in client`).
5. **Bilingual Documentation**: User-facing documentation (`README.md`, `docs/api.md`) must be maintained in both English and Russian (`README.ru.md`, `docs/api.ru.md`).
