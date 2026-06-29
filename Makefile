.PHONY: lint test

UV_CACHE_DIR := $(CURDIR)/.cache/uv

lint:
	mkdir -p "$(UV_CACHE_DIR)"
	UV_CACHE_DIR="$(UV_CACHE_DIR)" uv run ruff check .

test:
	mkdir -p "$(UV_CACHE_DIR)"
	UV_CACHE_DIR="$(UV_CACHE_DIR)" uv run python -m unittest discover -s tests
