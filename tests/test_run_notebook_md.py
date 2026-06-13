"""Tests for scripts/run_notebook_md.py — notebook [CODE]-cell execution harness."""
import subprocess
import sys
import textwrap
from pathlib import Path


def _run(nb: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/run_notebook_md.py", str(nb)],
        capture_output=True,
        text=True,
    )


def _write_nb(tmp_path: Path, content: str, name: str = "test_nb.md") -> Path:
    nb = tmp_path / name
    nb.write_text(textwrap.dedent(content))
    return nb


# ---------------------------------------------------------------------------
# 1. Happy path: shared namespace across cells
# ---------------------------------------------------------------------------
def test_runs_code_cells_and_passes(tmp_path):
    nb = _write_nb(tmp_path, """\
        ## Cell 1 [CODE]
        ```python
        x = 40
        ```

        ## Cell 2 [CODE]
        ```python
        assert x + 2 == 42
        ```
    """)
    result = _run(nb)
    assert result.returncode == 0, (
        f"Expected exit 0.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# 2. Error propagation — exit non-zero, error text visible, cell number visible
# ---------------------------------------------------------------------------
def test_propagates_cell_error(tmp_path):
    nb = _write_nb(tmp_path, """\
        ## Cell 1 [CODE]
        ```python
        raise ValueError('boom')
        ```
    """)
    result = _run(nb)
    assert result.returncode != 0, "Expected non-zero exit on cell error"
    combined = result.stdout + result.stderr
    assert "boom" in combined, f"Expected 'boom' in output.\ncombined: {combined}"
    assert "Cell 1" in combined, f"Expected 'Cell 1' in output.\ncombined: {combined}"


# ---------------------------------------------------------------------------
# 3. Real cell number reported (not enumeration index)
# ---------------------------------------------------------------------------
def test_reports_real_cell_number(tmp_path):
    nb = _write_nb(tmp_path, """\
        ## Cell 1 [MARKDOWN]
        Some prose here.

        ## Cell 2 [MARKDOWN]
        More prose.

        ## Cell 3 [CODE]
        ```python
        raise ValueError('x')
        ```
    """)
    result = _run(nb)
    assert result.returncode != 0, "Expected non-zero exit"
    combined = result.stdout + result.stderr
    assert "Cell 3" in combined, (
        f"Expected 'Cell 3' in output (real cell number).\ncombined: {combined}"
    )
    assert "Cell 1" not in combined or "Cell 3" in combined, (
        "Should report real cell number 3, not enumeration index"
    )


# ---------------------------------------------------------------------------
# 4. Markdown cells with python blocks are NOT executed
# ---------------------------------------------------------------------------
def test_markdown_python_block_not_executed(tmp_path):
    nb = _write_nb(tmp_path, """\
        ## Cell 1 [MARKDOWN]
        Example code shown in docs:

        ```python
        raise RuntimeError('should-not-run')
        ```

        ## Cell 2 [CODE]
        ```python
        y = 1
        ```
    """)
    result = _run(nb)
    assert result.returncode == 0, (
        f"Expected exit 0 — markdown python block must not execute.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# 5. A non-empty notebook with zero CODE cells must fail
# ---------------------------------------------------------------------------
def test_zero_code_cells_fails(tmp_path):
    nb = _write_nb(tmp_path, """\
        ## Cell 1 [MARKDOWN]
        Just some text, no code cells at all.
    """)
    result = _run(nb)
    assert result.returncode != 0, (
        "Expected non-zero exit when no CODE cells are found in a non-empty notebook"
    )


# ---------------------------------------------------------------------------
# 6. CRLF line endings are normalized — cell still found and runs
# ---------------------------------------------------------------------------
def test_crlf_notebook_runs(tmp_path):
    nb = tmp_path / "crlf_nb.md"
    # Build content with \r\n explicitly
    lines = [
        "## Cell 1 [CODE]",
        "```python",
        "z = 5",
        "```",
        "",
    ]
    nb.write_bytes("\r\n".join(lines).encode("utf-8"))
    result = _run(nb)
    assert result.returncode == 0, (
        f"Expected exit 0 with CRLF notebook.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
