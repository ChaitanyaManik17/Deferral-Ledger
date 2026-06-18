# Deferral Ledger — Makefile
# Usage: make setup | make test | make run

.PHONY: setup test lint run clean

# ── Environment setup ─────────────────────────────────────────────────────────
setup:
	@echo "→ Creating virtual environment and installing dependencies..."
	python3.11 -m venv .venv 2>/dev/null || python3 -m venv .venv
	.venv/bin/pip install --upgrade pip -q
	.venv/bin/pip install -e ".[dev]" -q
	@echo "✓ Setup complete. Activate with: source .venv/bin/activate"

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	@echo "→ Running tests..."
	.venv/bin/pytest tests/ -v --tb=short || python -m pytest tests/ -v --tb=short
	@echo "✓ Tests done."

# ── Lint ──────────────────────────────────────────────────────────────────────
lint:
	.venv/bin/ruff check . || ruff check .

# ── Run (Streamlit dashboard — Day 3+) ───────────────────────────────────────
run:
	@echo "→ Starting Streamlit dashboard..."
	@if [ -f app/dashboard.py ]; then \
		.venv/bin/streamlit run app/dashboard.py; \
	else \
		echo "Dashboard not yet built (Day 3+). Running catalog validation instead."; \
		.venv/bin/python -c "from catalog import load_edges, default_enabled_edges; \
			edges = load_edges(); print(f'Loaded {len(edges)} edges.'); \
			enabled = default_enabled_edges(); print(f'Default enabled: {len(enabled)} edges.')"; \
	fi

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	rm -rf .venv __pycache__ .pytest_cache dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
