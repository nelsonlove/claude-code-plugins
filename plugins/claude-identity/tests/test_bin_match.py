"""Test the standalone bin/match CLI used by shell consumers."""
import subprocess
from pathlib import Path

BIN = Path(__file__).parent.parent / "bin" / "match"


def run_cli(*args):
    return subprocess.run([str(BIN), *args], capture_output=True, text=True)


def test_match_exits_0_when_match():
    """bin/match returns exit 0 if any subscriber pattern matches any scope tag."""
    result = run_cli("--subscriber", "02.*", "--scope", "02.14")
    assert result.returncode == 0


def test_match_exits_1_when_no_match():
    result = run_cli("--subscriber", "03.*", "--scope", "02.14")
    assert result.returncode == 1


def test_multiple_tags_csv():
    """Tags can be CSV-separated (one --subscriber arg, one --scope arg)."""
    result = run_cli("--subscriber", "xx,02.*", "--scope", "yy,02.14")
    assert result.returncode == 0


def test_path_prefix():
    result = run_cli("--subscriber", "path:/repos/foo/**", "--scope", "path:/repos/foo/src")
    assert result.returncode == 0
