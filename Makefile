# `make ci` is the gate every change passes before it is reported done. There is no hosted CI:
# this target is the whole of it, so it has to fail on anything a reviewer would reject.

PKG := agent_tablet

.PHONY: ci venv lint test history fmt run clean

ci: lint test history

# --system-site-packages is not optional: PyGObject, GTK, libadwaita and VTE come from the system
# packages, and a venv without them imports nothing of the app.
venv: .venv/.stamp

.venv/.stamp: pyproject.toml uv.lock
	@command -v uv >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/"; exit 1; }
	@test -d .venv || uv venv -q --system-site-packages
	uv sync -q --locked
	@touch $@

lint: venv
	uv run --locked ruff check $(PKG)/ tests/

# In parallel from day one: a test that passes only because of the order it runs in, or of state
# another test left behind, shows up here instead of months later.
test: venv
	uv run --locked pytest -q -n auto

# Every line that left a decision document since HEAD is in its history (docs/history/README.md).
history:
	python3 docs/history/nothing_lost.py

# Formats only the paths given, never the whole tree: other sessions may have files half-written.
#   make fmt FILES="<package>/names.py tests/test_names.py"
fmt: venv
	@test -n "$(FILES)" || { echo 'usage: make fmt FILES="<paths>"'; exit 1; }
	uv run --locked ruff format $(FILES)
	uv run --locked ruff check --fix $(FILES)

run: venv
	uv run --locked python -m $(PKG)

clean:
	rm -rf .venv
