# `make ci` is the gate every change passes before it is reported done. There is no hosted CI:
# this target is the whole of it, so it has to fail on anything a reviewer would reject.

PKG := agent_tablet

.PHONY: ci venv lint format-check types test test-midnight coverage history fmt run ui ui-watch ui-check clean

ci: lint format-check types test history

# --system-site-packages is not optional: PyGObject, GTK, libadwaita and VTE come from the system
# packages, and a venv without them imports nothing of the app.
venv: .venv/.stamp

.venv/.stamp: pyproject.toml uv.lock
	@command -v uv >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/"; exit 1; }
	@test -d .venv || uv venv -q --system-site-packages
	uv sync -q --locked
	@touch $@

lint: venv
	uv run --locked ruff check .

format-check: venv
	uv run --locked ruff format --check .

types: venv
	uv run --locked pyright

# In parallel from day one: a test that passes only because of the order it runs in, or of state
# another test left behind, shows up here instead of months later.
test: venv
	uv run --locked pytest -q -n auto

# The whole suite as if it were 23:30 today, in UTC: finds the tests that pass only away from
# midnight (tests/clock_plugin.py).
test-midnight: venv
	AT_TEST_CLOCK_AT=$(shell date +%Y-%m-%dT23:30:00%:z) TZ=UTC uv run --locked pytest -q -n auto

# A report to read, never a threshold.
coverage: venv
	uv run --locked pytest -q -n auto --cov=agent_tablet --cov-report=term-missing:skip-covered

# Every line that left a decision document since HEAD is in its history (docs/history/README.md).
history:
	python3 docs/history/nothing_lost.py

# Formats only the paths given, never the whole tree: other sessions may have files half-written.
#   make fmt FILES="<package>/names.py tests/test_names.py"
fmt: venv
	@test -n "$(FILES)" || { echo 'usage: make fmt FILES="<paths>"'; exit 1; }
	uv run --locked ruff format $(FILES)
	uv run --locked ruff check --fix $(FILES)

# Looks at the UI of an isolated instance (docs/ui-verification.md). Not part of `ci`: it needs
# Google Chrome and gtk4-broadwayd, and the block that changes the UI runs it.
#   make ui-check [THEME=light] [DEMO=empty] [OUT=<dir>]
ui-check: venv
	uv run --locked python -m tools.ui.check $(if $(THEME),--theme $(THEME)) $(if $(DEMO),--demo $(DEMO)) $(if $(OUT),--out $(OUT))

# An isolated instance at a URL, until Ctrl+C; ui-watch restarts it on every source change.
ui: venv
	uv run --locked python -m tools.ui.serve $(if $(THEME),--theme $(THEME))

ui-watch: venv
	uv run --locked python -m tools.ui.serve --watch $(if $(THEME),--theme $(THEME))

run: venv
	uv run --locked python -m $(PKG)

clean:
	rm -rf .venv
