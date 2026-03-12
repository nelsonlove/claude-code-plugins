"""org-roam adapter — notes via emacsclient --eval.

Maps org-roam nodes to PIM notes in the working and scratch registers.
Uses emacsclient to query org-roam's database and manipulate files.
"""

import json
import subprocess
from typing import Any

from src.adapter import Adapter, Node, SyncResult
from src.uri import pim_uri


class OrgRoamAdapter(Adapter):
    """Adapter for org-roam notes.

    org-roam stores notes as .org files with metadata in a SQLite DB.
    This adapter uses emacsclient --eval to query and manipulate them
    through org-roam's Emacs Lisp API.
    """
    adapter_id = "org-roam"
    supported_types = ("note",)
    supported_operations = ("query", "create", "update")
    supported_registers = ("scratch", "working", "reference")

    def _eval(self, elisp: str) -> str:
        """Evaluate an Emacs Lisp expression via emacsclient.

        Returns the raw stdout from emacsclient.
        """
        result = subprocess.run(
            ["emacsclient", "--eval", elisp],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"emacsclient error: {result.stderr.strip()}")
        return result.stdout.strip()

    def _eval_json(self, elisp: str) -> Any:
        """Evaluate elisp that returns a JSON-encoded string."""
        # Wrap in json-encode so we get structured data back
        wrapped = f'(json-encode {elisp})'
        raw = self._eval(wrapped)
        # emacsclient wraps output in quotes — strip them
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]
        # Unescape the JSON string
        raw = raw.replace('\\"', '"').replace('\\\\', '\\')
        if not raw or raw == "null":
            return None
        return json.loads(raw)

    def _build_node(self, data: dict) -> Node:
        """Build a PIM Node from org-roam node data."""
        node_id = data.get("id", "")
        title = data.get("title", "")
        file_path = data.get("file", "")
        tags = data.get("tags", [])

        # Register heuristic: tagged "inbox" or no tags → scratch,
        # tagged "reference" → reference, otherwise → working
        register = "working"
        if isinstance(tags, list):
            tag_names = [t.lower() if isinstance(t, str) else "" for t in tags]
            if "inbox" in tag_names or "scratch" in tag_names:
                register = "scratch"
            elif "reference" in tag_names:
                register = "reference"

        return Node({
            "id": pim_uri("note", self.adapter_id, node_id),
            "type": "note",
            "adapter": self.adapter_id,
            "native_id": node_id,
            "register": register,
            "attributes": {
                "title": title,
                "file": file_path,
                "tags": tags if isinstance(tags, list) else [],
            },
        })

    def health_check(self) -> bool:
        try:
            result = self._eval("(org-roam-version)")
            return bool(result and result != "nil")
        except (RuntimeError, FileNotFoundError):
            return False

    def resolve(self, native_id: str) -> Node | None:
        data = self._eval_json(
            f'(org-roam-node-to-plist (org-roam-node-from-id "{native_id}"))'
        )
        if data is None:
            return None
        return self._build_node(data)

    def reverse_resolve(self, pim_uri_str: str) -> str | None:
        from src.uri import parse_uri
        parts = parse_uri(pim_uri_str)
        if parts["adapter"] != self.adapter_id:
            return None
        return parts["native_id"]

    def enumerate(self, obj_type: str, filters: dict | None = None,
                  limit: int = 100, offset: int = 0) -> list[Node]:
        if obj_type != "note":
            return []
        data = self._eval_json(
            f'(mapcar #\'org-roam-node-to-plist '
            f'(seq-take (seq-drop (org-roam-node-list) {offset}) {limit}))'
        )
        if not data or not isinstance(data, list):
            return []
        return [self._build_node(d) for d in data]

    def create_node(self, obj_type: str, attributes: dict,
                    body: str | None = None) -> Node:
        if obj_type != "note":
            raise ValueError(f"org-roam adapter only supports notes, got {obj_type}")

        title = attributes.get("title", "Untitled")
        tags = attributes.get("tags", [])

        # Use org-roam capture to create a new note
        result = self._eval(
            f'(progn '
            f'  (org-roam-capture- :node (org-roam-node-create :title "{title}") '
            f'    :templates \'(("d" "default" plain "%?" :target '
            f'      (file+head "%<%Y%m%d%H%M%S>-${{slug}}.org" '
            f'       "#+title: ${{title}}\\n"))) :finalize) '
            f'  (org-roam-node-id (org-roam-node-from-title-or-alias "{title}")))'
        )
        node_id = result.strip('"')

        if body:
            # Append body to the file
            file_result = self._eval(
                f'(org-roam-node-file (org-roam-node-from-id "{node_id}"))'
            )
            file_path = file_result.strip('"')
            self._eval(
                f'(with-current-buffer (find-file-noselect "{file_path}") '
                f'  (goto-char (point-max)) '
                f'  (insert "\\n{body}") '
                f'  (save-buffer))'
            )

        return Node({
            "id": pim_uri("note", self.adapter_id, node_id),
            "type": "note",
            "adapter": self.adapter_id,
            "native_id": node_id,
            "register": "scratch",
            "attributes": {
                "title": title,
                "tags": tags,
            },
        })

    def query_nodes(self, obj_type: str, filters: dict | None = None) -> list[Node]:
        if obj_type != "note":
            return []
        filters = filters or {}
        limit = filters.get("limit", 50)

        text_search = filters.get("text_search")
        if text_search:
            data = self._eval_json(
                f'(mapcar #\'org-roam-node-to-plist '
                f'  (seq-take (org-roam-node-find nil "{text_search}") {limit}))'
            )
        else:
            data = self._eval_json(
                f'(mapcar #\'org-roam-node-to-plist '
                f'  (seq-take (org-roam-node-list) {limit}))'
            )

        if not data or not isinstance(data, list):
            return []

        nodes = [self._build_node(d) for d in data]

        # Filter by register if requested
        register = filters.get("register")
        if register:
            nodes = [n for n in nodes if n["register"] == register]

        return nodes

    def update_node(self, native_id: str, changes: dict) -> Node:
        attrs = changes.get("attributes", {})
        new_title = attrs.get("title")

        if new_title:
            self._eval(
                f'(let ((node (org-roam-node-from-id "{native_id}"))) '
                f'  (when node '
                f'    (with-current-buffer (find-file-noselect (org-roam-node-file node)) '
                f'      (goto-char (point-min)) '
                f'      (when (re-search-forward "^#\\+title: .*$" nil t) '
                f'        (replace-match "#+title: {new_title}")) '
                f'      (save-buffer))))'
            )

        new_tags = attrs.get("tags")
        if new_tags is not None:
            tags_str = ":".join(new_tags)
            if tags_str:
                tags_str = f":{tags_str}:"
            self._eval(
                f'(let ((node (org-roam-node-from-id "{native_id}"))) '
                f'  (when node '
                f'    (with-current-buffer (find-file-noselect (org-roam-node-file node)) '
                f'      (goto-char (point-min)) '
                f'      (if (re-search-forward "^#\\+filetags: .*$" nil t) '
                f'        (replace-match "#+filetags: {tags_str}") '
                f'        (goto-char (point-min)) '
                f'        (forward-line 1) '
                f'        (insert "#+filetags: {tags_str}\\n")) '
                f'      (save-buffer))))'
            )

        node = self.resolve(native_id)
        if node is None:
            raise ValueError(f"Node not found after update: {native_id}")
        return node

    def close_node(self, native_id: str, mode: str) -> None:
        if mode == "delete":
            self._eval(
                f'(let ((node (org-roam-node-from-id "{native_id}"))) '
                f'  (when node '
                f'    (delete-file (org-roam-node-file node)) '
                f'    (org-roam-db-sync)))'
            )
        elif mode == "archive":
            self._eval(
                f'(let ((node (org-roam-node-from-id "{native_id}"))) '
                f'  (when node '
                f'    (with-current-buffer (find-file-noselect (org-roam-node-file node)) '
                f'      (goto-char (point-min)) '
                f'      (if (re-search-forward "^#\\+filetags: " nil t) '
                f'        (progn (end-of-line) (insert ":archive")) '
                f'        (forward-line 1) '
                f'        (insert "#+filetags: :archive:\\n")) '
                f'      (save-buffer))))'
            )
        # complete, cancel → no-op for notes

    def sync(self, since: str | None = None) -> SyncResult:
        self._eval("(org-roam-db-sync)")
        nodes = self.enumerate("note", limit=500)
        return SyncResult({
            "adapter": self.adapter_id,
            "synced": len(nodes),
            "nodes": [n["id"] for n in nodes],
        })

    def fetch_body(self, native_id: str) -> str | None:
        result = self._eval(
            f'(let ((node (org-roam-node-from-id "{native_id}"))) '
            f'  (when node '
            f'    (with-current-buffer (find-file-noselect (org-roam-node-file node)) '
            f'      (buffer-string))))'
        )
        if result and result != "nil":
            # Strip emacsclient quoting
            if result.startswith('"') and result.endswith('"'):
                result = result[1:-1]
            return result.replace('\\n', '\n').replace('\\"', '"')
        return None
