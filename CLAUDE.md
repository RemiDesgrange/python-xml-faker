# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

python-xml-faker is a Python library for generating fake XML data. The project is in early development.

## Development Commands

This project uses [uv](https://docs.astral.sh/uv/) for package management.

```bash
# Install dependencies
uv sync

# Run the project
uv run python -m python_xml_faker

# Run tests (when added)
uv run pytest

# Run a single test
uv run pytest path/to/test.py::test_function_name
```

## Architecture

- `src/python_xml_faker/` - Main package source code
- Uses Python 3.12+
- Uses `uv_build` as the build backend
