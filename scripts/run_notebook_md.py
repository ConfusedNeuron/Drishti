"""
run_notebook_md.py — execute [CODE] cells from a Drishti findings notebook (.md).

Usage:
    python scripts/run_notebook_md.py <notebook.md>

Extracts every ``## Cell N [CODE]`` section in order, runs the first fenced
```python / ```py block from each section in a single shared namespace, and
exits non-zero on the first error (reporting the real Cell N, not an index).

Rules enforced by design:
- ``[MARKDOWN]`` cells are never executed, even if they contain ```python blocks.
- A non-empty notebook with zero CODE cells is treated as a harness error.
- CRLF line endings are normalised before parsing.
- matplotlib is forced to the Agg backend before any cell runs.
"""

import os
import re
import sys
import traceback
from pathlib import Path

# Must be set before any import that could pull matplotlib.
os.environ.setdefault("MPLBACKEND", "Agg")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# Matches a cell header line:  ## Cell 3 [CODE]  or  ## Cell 3 [MARKDOWN]
_HEADER_RE = re.compile(
    r"(?m)^##\s*Cell\s*(\d+)\s*\[(MARKDOWN|CODE)\]\s*$"
)

# Matches the FIRST fenced python/py block within a cell body.
_FENCE_RE = re.compile(
    r"```(?:python|py)?[^\S\n]*\n(.*?)```",
    re.S | re.I,
)


def parse_code_cells(text: str) -> list[tuple[int, str]]:
    """Return [(cell_number, code_str), ...] for every [CODE] cell in *text*."""
    # Split into segments: [before_first_header, n1, type1, body1, n2, type2, body2, ...]
    parts = _HEADER_RE.split(text)
    # parts[0] is text before the first header (preamble — ignore)
    # parts[1], parts[2], parts[3] are: cell_num, cell_type, cell_body (first cell)
    # parts[4], parts[5], parts[6] are: cell_num, cell_type, cell_body (second cell), …
    cells: list[tuple[int, str]] = []
    i = 1
    while i + 2 <= len(parts):
        cell_num = int(parts[i])
        cell_type = parts[i + 1].upper()
        cell_body = parts[i + 2]
        if cell_type == "CODE":
            m = _FENCE_RE.search(cell_body)
            if m:
                cells.append((cell_num, m.group(1)))
        i += 3
    return cells


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def run_notebook(path: Path) -> None:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")

    code_cells = parse_code_cells(text)

    if not code_cells and text.strip():
        print(
            f"[run_notebook_md] ERROR: no [CODE] cells found in {path.name}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Shared execution namespace
    ns: dict = {"__name__": "__notebook__"}

    # Seed headless matplotlib BEFORE any user cell can import it.
    # The MPLBACKEND env var (set at module load) handles the common case;
    # this exec() pre-imports matplotlib so that use('Agg') is already called
    # even if a notebook does a bare ``import matplotlib.pyplot``.
    # Guard with try/except so the harness works when matplotlib is absent.
    try:
        exec("import matplotlib; matplotlib.use('Agg')", ns)  # noqa: S102
    except ModuleNotFoundError:
        pass

    for cell_num, code in code_cells:
        filename = f"{path.name}::Cell{cell_num}"
        try:
            exec(compile(code, filename, "exec"), ns)  # noqa: S102
        except Exception:  # noqa: BLE001
            print(
                f"[run_notebook_md] FAILED at Cell {cell_num} in {path.name}",
                file=sys.stderr,
            )
            traceback.print_exc()
            sys.exit(1)

    print(f"[run_notebook_md] OK: {path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <notebook.md>", file=sys.stderr)
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"[run_notebook_md] ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    run_notebook(path)


if __name__ == "__main__":
    main()
