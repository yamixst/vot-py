# Agent Instructions for Porting `vot.js` to `vot-py`

You are an AI Agent tasked with helping the USER rewrite `vot.js` (an unofficial library for interacting with the Yandex VOT API) into a modern, high-quality Python library (`vot-py`).

These instructions outline the architecture, tech stack, and step-by-step implementation plan. **Always refer to these guidelines when making architectural decisions or generating code.**

---

## 1. Project Overview & Tech Stack

The goal is to port the TypeScript-based `vot.js` (which consists of `core`, `node`, `ext`, `shared` packages) into a cohesive Python package. Unlike JavaScript which has distinct Node and Browser Extension environments, the Python library will primarily target standard desktop/server environments.

### Recommended Tech Stack
- **Python Version**: 3.10+ (Modern typing and language features).
- **Dependency Management**: `uv`
- **HTTP Client**: `httpx` (Provides both synchronous and asynchronous clients, similar to Node's `fetch` but more Pythonic).
- **Protobuf**: `protobuf` (Google's official Python implementation) or `betterproto` for cleaner dataclass generation.
- **Data Validation/Models**: `pydantic` or standard `dataclasses`.
- **Testing**: `pytest` + `pytest-asyncio`.
- **Linting & Formatting**: `ruff` (replaces Black, Flake8, and isort).
- **Type Checking**: `mypy` or `pyright`.

---

## 2. Python Library Best Practices

All agents contributing to `vot-py` MUST adhere to the following Python library best practices:

1. **Strict Type Hinting**: Every function signature and class must have proper type hints. Use `typing` features extensively (e.g., `Optional`, `Union`, `Literal`, or new syntax `X | Y`).
2. **Docstrings**: Use Google-style or NumPy-style docstrings for all public modules, classes, and functions. This makes it easy to generate documentation later (e.g., using Sphinx or MkDocs).
3. **Async First, Sync Optional**: The Yandex VOT API relies on network requests. Implement the core client asynchronously using `httpx.AsyncClient`. You can provide a synchronous wrapper if necessary, but network-bound libraries in Python should support `asyncio`.
4. **Exception Handling**: Do not use bare `except:` clauses. Define custom exceptions (e.g., `VOTError`, `VOTAPIError`, `VideoNotFoundError`) inheriting from Python's standard `Exception` to make error handling intuitive for library users.
5. **Clean Imports**: Use absolute imports (`from vot.core import client`) or explicit relative imports (`from . import utils`).
6. **No Global State**: Ensure that instances of the client do not leak state globally. Sessions and configurations should be bound to the client instance.

---

## 3. Project Architecture (Proposed)

We should flatten the TypeScript monorepo into a single structured Python package:

```text
vot-py/
├── pyproject.toml         # Project metadata and dependencies
├── README.md              # Project documentation
├── src/
│   └── vot/
│       ├── __init__.py    # Expose the main VOTClient / VOTWorkerClient
│       ├── client.py      # Core client implementation (sync/async)
│       ├── worker.py      # VOTWorkerClient implementation
│       ├── models.py      # Pydantic models / Dataclasses for request/response payloads
│       ├── protobuf/      # Generated protobuf files
│       │   ├── __init__.py
│       │   └── video_translation_pb2.py
│       ├── utils/
│       │   ├── __init__.py
│       │   ├── crypto.py  # Request signing / HMAC logic
│       │   └── url.py     # Video URL parsing and data extraction
│       └── exceptions.py  # Custom exceptions
├── tests/
│   ├── conftest.py
│   ├── test_client.py
│   └── test_utils.py
└── scripts/               # Scripts for protoc generation, etc.
```

---

## 4. Implementation Phases

Agents should tackle the porting process in these sequential phases:

### Phase 1: Project Initialization & Tooling
- Initialize the Python project using `uv init --lib`.
- Setup `pyproject.toml` with `ruff`, `pytest`, `httpx`, and `protobuf`.
- Configure linting and formatting rules.

### Phase 2: Protobuf Generation
- Locate the `.proto` files from `vot.js` or write a script to fetch them.
- Use `protoc` to generate Python bindings into `src/vot/protobuf/`.
- Ensure the generated code can be cleanly imported without path issues.

### Phase 3: Core Utilities & Data Models
- Port the URL parsing logic (`utils/url.py`) to extract video IDs and domains from various platforms (YouTube, etc.).
- Port any cryptographic or signing mechanisms needed for the Yandex API (`utils/crypto.py`).
- Define Pydantic models or standard Dataclasses for inputs/outputs (`models.py`).

### Phase 4: The Core Client
- Implement the base `VOTClient` in `client.py` using `httpx.AsyncClient`.
- Implement `translateVideo` and `getVideoData` methods.
- Handle protobuf serialization (requests) and deserialization (responses).
- Implement the `VOTWorkerClient` proxy logic.

### Phase 5: Testing & CI
- Write unit tests in `tests/` mocking the HTTP responses.
- Ensure all logic (URL parsing, crypto, protobuf packing) has 100% coverage.
- Add GitHub Actions for Python CI (similar to `build.yml` in the JS project).

---

## 5. Agent Workflow Tips

- **Read Before Writing**: Use `view_file` on `../vot.js/packages/core/src/...` to understand the original TypeScript implementation before writing the Python equivalent.
- **Small Commits / Edits**: When making changes, modify one module at a time and write tests alongside the implementation.
- **Run Type Checks**: Continuously run `mypy src/vot` or `ruff check` to ensure code quality throughout the session.
