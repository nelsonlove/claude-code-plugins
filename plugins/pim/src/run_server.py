"""Entry point for MCP runner — adds plugin root to sys.path and runs the server."""
import sys
from pathlib import Path

# Add plugin root to path so src.* imports work
plugin_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(plugin_root))

from src.server import mcp

if __name__ == "__main__":
    mcp.run()
