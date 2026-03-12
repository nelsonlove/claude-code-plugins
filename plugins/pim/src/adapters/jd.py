"""Johnny Decimal adapter — JD tree navigation via the jd CLI."""

import json
import subprocess
from typing import Any

from src.adapter import Adapter, Node, SyncResult
from src.uri import pim_uri


class JDAdapter(Adapter):
    """Adapter for the Johnny Decimal filing system.

    Maps JD areas, categories, and IDs to PIM topics and resources.
    Uses the `jd` CLI for all operations.
    """
    adapter_id = "jd"
    supported_types = ("topic", "resource")
    supported_operations = ("query",)
    supported_registers = ("reference", "working")

    def _run_jd(self, *args: str) -> subprocess.CompletedProcess:
        cmd = ["jd", *args]
        return subprocess.run(cmd, capture_output=True, text=True)

    def _parse_json(self, result: subprocess.CompletedProcess) -> Any:
        if result.returncode != 0:
            raise RuntimeError(f"jd error: {result.stderr}")
        output = result.stdout.strip()
        if not output:
            return None
        return json.loads(output)

    # --- JD level detection ---

    def _jd_level(self, jd_id: str) -> str:
        """Determine if a JD identifier is an area, category, or ID."""
        if "-" in jd_id:
            return "area"
        if "." in jd_id:
            return "id"
        return "category"

    # --- Node builders ---

    def _area_to_node(self, data: dict) -> Node:
        area_id = data.get("id", "")
        name = data.get("name", "")

        return Node({
            "id": pim_uri("topic", "jd", area_id),
            "type": "topic",
            "register": "reference",
            "adapter": "jd",
            "native_id": area_id,
            "attributes": {
                "title": name,
                "description": f"JD Area: {area_id}",
                "status": "active",
                "taxonomy_id": area_id,
                "jd_level": "area",
            },
            "body": None,
            "body_path": None,
            "source_op": None,
            "created_at": None,
            "modified_at": None,
        })

    def _category_to_node(self, data: dict) -> Node:
        cat_id = data.get("id", "")
        name = data.get("name", "")

        return Node({
            "id": pim_uri("topic", "jd", cat_id),
            "type": "topic",
            "register": "reference",
            "adapter": "jd",
            "native_id": cat_id,
            "attributes": {
                "title": name,
                "description": f"JD Category: {cat_id}",
                "status": "active",
                "taxonomy_id": cat_id,
                "jd_level": "category",
            },
            "body": None,
            "body_path": None,
            "source_op": None,
            "created_at": None,
            "modified_at": None,
        })

    def _id_to_node(self, data: dict) -> Node:
        jd_id = data.get("id", "")
        name = data.get("name", "")
        path = data.get("path", "")

        return Node({
            "id": pim_uri("topic", "jd", jd_id),
            "type": "topic",
            "register": "working",
            "adapter": "jd",
            "native_id": jd_id,
            "attributes": {
                "title": name,
                "description": f"JD ID: {jd_id}",
                "status": "active",
                "taxonomy_id": jd_id,
                "jd_level": "id",
                "path": path,
            },
            "body": None,
            "body_path": None,
            "source_op": None,
            "created_at": None,
            "modified_at": None,
        })

    def _file_to_node(self, data: dict) -> Node:
        file_path = data.get("path", "")
        name = data.get("name", "")
        jd_id = data.get("jd_id", "")

        return Node({
            "id": pim_uri("resource", "jd", file_path),
            "type": "resource",
            "register": "reference",
            "adapter": "jd",
            "native_id": file_path,
            "attributes": {
                "uri": file_path,
                "title": name,
                "description": f"File in JD ID: {jd_id}",
            },
            "body": None,
            "body_path": None,
            "source_op": None,
            "created_at": None,
            "modified_at": None,
        })

    # --- Adapter interface ---

    def health_check(self) -> bool:
        result = self._run_jd("--version")
        return result.returncode == 0

    def resolve(self, native_id: str) -> Node | None:
        level = self._jd_level(native_id)

        if level == "area":
            result = self._run_jd("ls", native_id, "--json")
            if result.returncode != 0:
                return None
            data = self._parse_json(result)
            if data is None:
                return None
            return self._area_to_node({"id": native_id, "name": data.get("name", native_id)})

        if level == "category":
            result = self._run_jd("ls", native_id, "--json")
            if result.returncode != 0:
                return None
            data = self._parse_json(result)
            if data is None:
                return None
            return self._category_to_node({"id": native_id, "name": data.get("name", native_id)})

        # ID level — resolve path
        result = self._run_jd("which", native_id)
        if result.returncode != 0:
            return None
        path = result.stdout.strip()
        result_ls = self._run_jd("ls", native_id, "--json")
        name = native_id
        if result_ls.returncode == 0:
            data = self._parse_json(result_ls)
            if data:
                name = data.get("name", native_id)
        return self._id_to_node({"id": native_id, "name": name, "path": path})

    def reverse_resolve(self, uri: str) -> str | None:
        if "jd" not in uri:
            return None
        parts = uri.replace("pim://", "").split("/")
        if len(parts) >= 3:
            return "/".join(parts[2:])
        return None

    def enumerate(self, obj_type: str, filters: dict | None = None,
                  limit: int = 100, offset: int = 0) -> list[Node]:
        if obj_type == "topic":
            return self._enumerate_topics(limit, offset)
        if obj_type == "resource":
            return self._enumerate_resources(limit, offset)
        return []

    def _enumerate_topics(self, limit: int, offset: int) -> list[Node]:
        result = self._run_jd("index", "--json")
        if result.returncode != 0:
            return []
        data = self._parse_json(result)
        if not data or not isinstance(data, list):
            return []
        nodes = []
        for item in data:
            level = self._jd_level(item.get("id", ""))
            if level == "area":
                nodes.append(self._area_to_node(item))
            elif level == "category":
                nodes.append(self._category_to_node(item))
            else:
                nodes.append(self._id_to_node(item))
        return nodes[offset:offset + limit]

    def _enumerate_resources(self, limit: int, offset: int) -> list[Node]:
        # Resources are files within JD IDs; not directly enumerable without scanning
        return []

    def create_node(self, obj_type: str, attributes: dict, body: str | None = None) -> Node:
        if obj_type == "topic":
            return self._create_jd_entry(attributes)
        raise ValueError(f"Unsupported type for JD adapter: {obj_type}")

    def _create_jd_entry(self, attributes: dict) -> Node:
        title = attributes.get("title", "")
        parent = attributes.get("taxonomy_id", "")

        if parent:
            result = self._run_jd("new-id", parent, title)
        else:
            result = self._run_jd("new-category", title)

        if result.returncode != 0:
            raise RuntimeError(f"Failed to create JD entry: {result.stderr}")

        jd_id = result.stdout.strip()
        return self._id_to_node({"id": jd_id, "name": title, "path": ""})

    def query_nodes(self, obj_type: str, filters: dict | None = None) -> list[Node]:
        if obj_type not in ("topic", "resource"):
            return []
        filters = filters or {}

        text_search = filters.get("text_search")
        limit = filters.get("limit", 100)

        if text_search:
            result = self._run_jd("search", text_search, "--json")
            if result.returncode != 0:
                return []
            data = self._parse_json(result)
            if not data or not isinstance(data, list):
                return []
            nodes = []
            for item in data:
                if obj_type == "topic":
                    level = self._jd_level(item.get("id", ""))
                    if level == "area":
                        nodes.append(self._area_to_node(item))
                    elif level == "category":
                        nodes.append(self._category_to_node(item))
                    else:
                        nodes.append(self._id_to_node(item))
                else:
                    nodes.append(self._file_to_node(item))
            return nodes[:limit]

        return self.enumerate(obj_type, filters, limit)

    def update_node(self, native_id: str, changes: dict) -> Node:
        # JD structure is largely immutable; renaming is the main operation
        attrs = changes.get("attributes", {})
        if "title" in attrs:
            result = self._run_jd("mv", native_id, attrs["title"])
            if result.returncode != 0:
                raise RuntimeError(f"Failed to rename JD entry: {result.stderr}")
        node = self.resolve(native_id)
        if node is None:
            raise ValueError(f"JD entry not found after update: {native_id}")
        return node

    def close_node(self, native_id: str, mode: str) -> None:
        if mode == "archive":
            # Move to archive area (90-99)
            pass
        elif mode == "delete":
            raise ValueError("JD entries should not be deleted. Use archive instead.")
        else:
            pass

    def sync(self, since: str | None = None) -> SyncResult:
        result = self._run_jd("index", "--json")
        if result.returncode != 0:
            return SyncResult({"changed_nodes": [], "changed_edges": []})
        data = self._parse_json(result)
        if not data or not isinstance(data, list):
            return SyncResult({"changed_nodes": [], "changed_edges": []})
        nodes = []
        for item in data:
            level = self._jd_level(item.get("id", ""))
            if level == "area":
                nodes.append(self._area_to_node(item))
            elif level == "category":
                nodes.append(self._category_to_node(item))
            else:
                nodes.append(self._id_to_node(item))
        return SyncResult({"changed_nodes": nodes, "changed_edges": []})

    def fetch_body(self, native_id: str) -> str | None:
        # For JD IDs, the body could be the README.md content
        result = self._run_jd("which", native_id)
        if result.returncode != 0:
            return None
        path = result.stdout.strip()
        readme_path = f"{path}/README.md"
        try:
            with open(readme_path) as f:
                return f.read()
        except (FileNotFoundError, PermissionError):
            return None
