"""Adapter base class — the contract every adapter implements."""

from abc import ABC, abstractmethod
from typing import Any


class Node(dict):
    """A node returned by an adapter. Dict-like with convenience accessors."""
    @property
    def id(self): return self["id"]
    @property
    def type(self): return self["type"]


class Edge(dict):
    """An edge returned by an adapter."""
    @property
    def id(self): return self["id"]


class SyncResult(dict):
    """Result of a sync operation."""
    pass


def escape_applescript(s: str) -> str:
    """Escape a string for safe inclusion in an AppleScript double-quoted string."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def escape_shell_arg(s: str) -> str:
    """Escape a string for safe use as a shell argument (single-quote wrapping)."""
    return "'" + s.replace("'", "'\"'\"'") + "'"


class Adapter(ABC):
    """
    Base class for PIM adapters.

    Every adapter covers one or more object types. The orchestrator routes
    operations to adapters based on the routing table.

    See docs/architecture.md "Adapter Contract" for the full specification.
    """

    adapter_id: str = "base"
    supported_types: tuple[str, ...] = ()
    supported_operations: tuple[str, ...] = ()
    supported_registers: tuple[str, ...] = ()

    @abstractmethod
    def resolve(self, native_id: str) -> Node | None:
        """Given a native ID, return the node with attributes."""
        ...

    @abstractmethod
    def reverse_resolve(self, pim_uri: str) -> str | None:
        """Given a PIM URI, return the native ID."""
        ...

    @abstractmethod
    def enumerate(self, obj_type: str, filters: dict | None = None, limit: int = 100, offset: int = 0) -> list[Node]:
        """List all nodes of a type, with optional filters and pagination."""
        ...

    @abstractmethod
    def create_node(self, obj_type: str, attributes: dict, body: str | None = None) -> Node:
        """Create a new node. Returns the created node with its native_id."""
        ...

    @abstractmethod
    def query_nodes(self, obj_type: str, filters: dict | None = None) -> list[Node]:
        """Find nodes by type and filters (attributes, text search, etc.)."""
        ...

    @abstractmethod
    def update_node(self, native_id: str, changes: dict) -> Node:
        """Update a node's attributes or body."""
        ...

    @abstractmethod
    def close_node(self, native_id: str, mode: str) -> None:
        """Close a node (complete, archive, cancel, delete)."""
        ...

    @abstractmethod
    def sync(self, since: str | None = None) -> SyncResult:
        """Return changed nodes since the given timestamp. For index building."""
        ...

    @abstractmethod
    def fetch_body(self, native_id: str) -> str | None:
        """Fetch the full content body for an unstructured node."""
        ...

    # Optional — not all adapters support these
    def create_edge(self, source: str, target: str, edge_type: str, metadata: dict | None = None) -> Edge | None:
        return None

    def query_edges(self, node_id: str, direction: str = "both", edge_type: str | None = None) -> list[Edge]:
        return []

    def update_edge(self, edge_id: str, changes: dict) -> Edge | None:
        return None

    def close_edge(self, edge_id: str) -> None:
        pass

    def dispatch(self, native_id: str, method: str | None = None, params: dict | None = None) -> Any:
        raise NotImplementedError(f"{self.adapter_id} does not support dispatch")

    def health_check(self) -> bool:
        """Return True if the adapter is operational."""
        return True
