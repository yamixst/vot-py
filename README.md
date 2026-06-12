# vot-py

A Python port of the TS-based `vot.js` library for interacting with the Yandex Video Translation API.

## Installation

```bash
uv pip install -e .
```

## Usage

```python
import asyncio
from vot import VOTClient

async def main():
    client = VOTClient()
    # Use client...

if __name__ == "__main__":
    asyncio.run(main())
```
