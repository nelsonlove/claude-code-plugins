"""OmniFocus adapter — tasks and topics (projects) via JXA."""

import json
import subprocess
from typing import Any

from src.adapter import Adapter, Node, Edge, SyncResult
from src.uri import pim_uri

# --- JXA script templates ---

JXA_HEALTH = """\
const app = Application("OmniFocus");
app.name();
"""

JXA_GET_TASK = """\
const doc = Application("OmniFocus").defaultDocument;
const tasks = doc.flattenedTasks.whose({id: "%TASK_ID%"})();
if (tasks.length === 0) { JSON.stringify(null); }
else {
    const t = tasks[0];
    JSON.stringify({
        id: t.id(),
        name: t.name(),
        note: t.note(),
        completed: t.completed(),
        flagged: t.flagged(),
        deferDate: t.deferDate() ? t.deferDate().toISOString() : null,
        dueDate: t.dueDate() ? t.dueDate().toISOString() : null,
        tags: t.tags().map(tag => tag.name()),
        containingProject: t.containingProject() ? {
            id: t.containingProject().id(),
            name: t.containingProject().name()
        } : null,
        inInbox: t.inInbox(),
    });
}
"""

JXA_LIST_TASKS = """\
const doc = Application("OmniFocus").defaultDocument;
const tasks = doc.flattenedTasks();
const result = tasks.map(t => ({
    id: t.id(),
    name: t.name(),
    completed: t.completed(),
    flagged: t.flagged(),
    deferDate: t.deferDate() ? t.deferDate().toISOString() : null,
    dueDate: t.dueDate() ? t.dueDate().toISOString() : null,
    tags: t.tags().map(tag => tag.name()),
    inInbox: t.inInbox(),
}));
JSON.stringify(result);
"""

JXA_LIST_INBOX = """\
const doc = Application("OmniFocus").defaultDocument;
const tasks = doc.inboxTasks();
const result = tasks.map(t => ({
    id: t.id(),
    name: t.name(),
    completed: t.completed(),
    flagged: t.flagged(),
    deferDate: t.deferDate() ? t.deferDate().toISOString() : null,
    dueDate: t.dueDate() ? t.dueDate().toISOString() : null,
    tags: t.tags().map(tag => tag.name()),
    inInbox: true,
}));
JSON.stringify(result);
"""

JXA_CREATE_INBOX_TASK = """\
const app = Application("OmniFocus");
const doc = app.defaultDocument;
const task = app.Task({name: %NAME%, note: %NOTE%, flagged: %FLAGGED%});
doc.inboxTasks.push(task);
JSON.stringify({
    id: task.id(),
    name: task.name(),
    completed: task.completed(),
});
"""

JXA_CREATE_PROJECT_TASK = """\
const app = Application("OmniFocus");
const doc = app.defaultDocument;
const projects = doc.flattenedProjects.whose({id: "%PROJECT_ID%"})();
if (projects.length === 0) throw new Error("Project not found: %PROJECT_ID%");
const proj = projects[0];
const task = app.Task({name: %NAME%, note: %NOTE%, flagged: %FLAGGED%});
proj.tasks.push(task);
JSON.stringify({
    id: task.id(),
    name: task.name(),
    completed: task.completed(),
});
"""

JXA_UPDATE_TASK = """\
const doc = Application("OmniFocus").defaultDocument;
const tasks = doc.flattenedTasks.whose({id: "%TASK_ID%"})();
if (tasks.length === 0) throw new Error("Task not found");
const t = tasks[0];
%UPDATES%
JSON.stringify({
    id: t.id(),
    name: t.name(),
    completed: t.completed(),
});
"""

JXA_COMPLETE_TASK = """\
const app = Application("OmniFocus");
const doc = app.defaultDocument;
const tasks = doc.flattenedTasks.whose({id: "%TASK_ID%"})();
if (tasks.length === 0) throw new Error("Task not found");
tasks[0].markComplete();
"""

JXA_DELETE_TASK = """\
const app = Application("OmniFocus");
const doc = app.defaultDocument;
const tasks = doc.flattenedTasks.whose({id: "%TASK_ID%"})();
if (tasks.length === 0) throw new Error("Task not found");
app.delete(tasks[0]);
"""

# --- Project (topic) JXA ---

JXA_GET_PROJECT = """\
const doc = Application("OmniFocus").defaultDocument;
const projects = doc.flattenedProjects.whose({id: "%PROJECT_ID%"})();
if (projects.length === 0) { JSON.stringify(null); }
else {
    const p = projects[0];
    JSON.stringify({
        id: p.id(),
        name: p.name(),
        note: p.note(),
        status: p.status(),
        sequential: p.sequential(),
        reviewInterval: p.reviewInterval() ? p.reviewInterval().toString() : null,
        folder: p.folder() ? { id: p.folder().id(), name: p.folder().name() } : null,
    });
}
"""

JXA_LIST_PROJECTS = """\
const doc = Application("OmniFocus").defaultDocument;
const projects = doc.flattenedProjects();
const result = projects.map(p => ({
    id: p.id(),
    name: p.name(),
    status: p.status(),
    sequential: p.sequential(),
}));
JSON.stringify(result);
"""

JXA_CREATE_PROJECT = """\
const app = Application("OmniFocus");
const doc = app.defaultDocument;
const proj = app.Project({name: %NAME%, note: %NOTE%});
doc.projects.push(proj);
JSON.stringify({
    id: proj.id(),
    name: proj.name(),
});
"""

JXA_UPDATE_PROJECT = """\
const doc = Application("OmniFocus").defaultDocument;
const projects = doc.flattenedProjects.whose({id: "%PROJECT_ID%"})();
if (projects.length === 0) throw new Error("Project not found");
const p = projects[0];
%UPDATES%
JSON.stringify({
    id: p.id(),
    name: p.name(),
});
"""

JXA_COMPLETE_PROJECT = """\
const app = Application("OmniFocus");
const doc = app.defaultDocument;
const projects = doc.flattenedProjects.whose({id: "%PROJECT_ID%"})();
if (projects.length === 0) throw new Error("Project not found");
projects[0].markComplete();
"""

JXA_DELETE_PROJECT = """\
const app = Application("OmniFocus");
const doc = app.defaultDocument;
const projects = doc.flattenedProjects.whose({id: "%PROJECT_ID%"})();
if (projects.length === 0) throw new Error("Project not found");
app.delete(projects[0]);
"""

JXA_SYNC = """\
const doc = Application("OmniFocus").defaultDocument;
const tasks = doc.flattenedTasks();
const cutoff = %SINCE% ? new Date(%SINCE%) : new Date(0);
const changed = tasks.filter(t => {
    const mod = t.modificationDate();
    return mod && mod >= cutoff;
}).map(t => ({
    id: t.id(),
    name: t.name(),
    completed: t.completed(),
    flagged: t.flagged(),
    inInbox: t.inInbox(),
}));
JSON.stringify(changed);
"""


class OmniFocusAdapter(Adapter):
    adapter_id = "omnifocus"
    supported_types = ("task", "topic")
    supported_operations = ("create", "query", "update", "close")
    supported_registers = ("scratch", "working", "log")

    def _run_jxa(self, script: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True,
            text=True,
        )

    def _parse_json(self, result: subprocess.CompletedProcess) -> Any:
        if result.returncode != 0:
            raise RuntimeError(f"JXA error: {result.stderr}")
        output = result.stdout.strip()
        if not output:
            return None
        return json.loads(output)

    # --- Register mapping ---

    def _register_for_task(self, data: dict) -> str:
        if data.get("completed"):
            return "log"
        if data.get("inInbox"):
            return "scratch"
        return "working"

    def _register_for_project(self, data: dict) -> str:
        status = data.get("status")
        if status in ("done", "dropped"):
            return "log"
        return "working"

    # --- Node builders ---

    def _task_to_node(self, data: dict) -> Node:
        return Node({
            "id": pim_uri("task", "omnifocus", data["id"]),
            "type": "task",
            "register": self._register_for_task(data),
            "adapter": "omnifocus",
            "native_id": data["id"],
            "attributes": {
                "title": data.get("name", ""),
                "status": "completed" if data.get("completed") else "open",
                "flagged": data.get("flagged", False),
                "defer_date": data.get("deferDate"),
                "due_date": data.get("dueDate"),
                "tags": data.get("tags", []),
            },
            "body": data.get("note"),
            "body_path": None,
            "source_op": None,
            "created_at": None,
            "modified_at": None,
        })

    def _project_to_node(self, data: dict) -> Node:
        return Node({
            "id": pim_uri("topic", "omnifocus", data["id"]),
            "type": "topic",
            "register": self._register_for_project(data),
            "adapter": "omnifocus",
            "native_id": data["id"],
            "attributes": {
                "title": data.get("name", ""),
                "status": data.get("status", "active"),
                "sequential": data.get("sequential", False),
                "review_interval": data.get("reviewInterval"),
                "folder": data.get("folder"),
            },
            "body": data.get("note"),
            "body_path": None,
            "source_op": None,
            "created_at": None,
            "modified_at": None,
        })

    # --- Adapter interface ---

    def health_check(self) -> bool:
        result = self._run_jxa(JXA_HEALTH)
        return result.returncode == 0

    def resolve(self, native_id: str) -> Node | None:
        # Try task first, then project
        script = JXA_GET_TASK.replace("%TASK_ID%", native_id)
        result = self._run_jxa(script)
        data = self._parse_json(result)
        if data is not None:
            return self._task_to_node(data)

        script = JXA_GET_PROJECT.replace("%PROJECT_ID%", native_id)
        result = self._run_jxa(script)
        data = self._parse_json(result)
        if data is not None:
            return self._project_to_node(data)

        return None

    def reverse_resolve(self, uri: str) -> str | None:
        if "omnifocus" not in uri:
            return None
        parts = uri.replace("pim://", "").split("/")
        if len(parts) == 3:
            return parts[2]
        return None

    def enumerate(self, obj_type: str, filters: dict | None = None, limit: int = 100, offset: int = 0) -> list[Node]:
        if obj_type == "task":
            result = self._run_jxa(JXA_LIST_TASKS)
            items = self._parse_json(result) or []
            nodes = [self._task_to_node(t) for t in items]
        elif obj_type == "topic":
            result = self._run_jxa(JXA_LIST_PROJECTS)
            items = self._parse_json(result) or []
            nodes = [self._project_to_node(p) for p in items]
        else:
            return []
        return nodes[offset:offset + limit]

    def create_node(self, obj_type: str, attributes: dict, body: str | None = None) -> Node:
        if obj_type == "task":
            return self._create_task(attributes, body)
        elif obj_type == "topic":
            return self._create_project(attributes, body)
        else:
            raise ValueError(f"Unsupported type for OmniFocus: {obj_type}")

    def _create_task(self, attributes: dict, body: str | None = None) -> Node:
        name = json.dumps(attributes.get("title", "Untitled"))
        note = json.dumps(body or "")
        flagged = "true" if attributes.get("flagged") else "false"
        project_id = attributes.get("project_id")

        if project_id:
            script = JXA_CREATE_PROJECT_TASK
            script = script.replace("%PROJECT_ID%", project_id)
        else:
            script = JXA_CREATE_INBOX_TASK

        script = script.replace("%NAME%", name)
        script = script.replace("%NOTE%", note)
        script = script.replace("%FLAGGED%", flagged)

        result = self._run_jxa(script)
        data = self._parse_json(result)
        return self._task_to_node(data)

    def _create_project(self, attributes: dict, body: str | None = None) -> Node:
        name = json.dumps(attributes.get("title", "Untitled"))
        note = json.dumps(body or "")
        script = JXA_CREATE_PROJECT.replace("%NAME%", name).replace("%NOTE%", note)
        result = self._run_jxa(script)
        data = self._parse_json(result)
        return self._project_to_node(data)

    def query_nodes(self, obj_type: str, filters: dict | None = None) -> list[Node]:
        filters = filters or {}
        register = filters.get("register")

        if obj_type == "task":
            if register == "scratch":
                result = self._run_jxa(JXA_LIST_INBOX)
            else:
                result = self._run_jxa(JXA_LIST_TASKS)
            items = self._parse_json(result) or []
            nodes = [self._task_to_node(t) for t in items]

            if register and register != "scratch":
                nodes = [n for n in nodes if n["register"] == register]

            if "attributes" in filters:
                for key, value in filters["attributes"].items():
                    nodes = [n for n in nodes if n["attributes"].get(key) == value]

        elif obj_type == "topic":
            result = self._run_jxa(JXA_LIST_PROJECTS)
            items = self._parse_json(result) or []
            nodes = [self._project_to_node(p) for p in items]

            if register:
                nodes = [n for n in nodes if n["register"] == register]
        else:
            return []

        return nodes

    def update_node(self, native_id: str, changes: dict) -> Node:
        attrs = changes.get("attributes", {})

        # Determine if this is a task or project by trying to resolve
        updates_lines = []
        is_project = False

        if "title" in attrs:
            updates_lines.append(f't.name = {json.dumps(attrs["title"])};')
        if "flagged" in attrs:
            updates_lines.append(f't.flagged = {"true" if attrs["flagged"] else "false"};')
        if "note" in changes:
            updates_lines.append(f't.note = {json.dumps(changes["note"])};')

        updates_str = "\n".join(updates_lines) if updates_lines else ""

        # Try task first
        script = JXA_UPDATE_TASK.replace("%TASK_ID%", native_id).replace("%UPDATES%", updates_str)
        result = self._run_jxa(script)
        if result.returncode == 0:
            data = self._parse_json(result)
            return self._task_to_node(data)

        # Try project
        project_updates = updates_str.replace("t.", "p.")
        script = JXA_UPDATE_PROJECT.replace("%PROJECT_ID%", native_id).replace("%UPDATES%", project_updates)
        result = self._run_jxa(script)
        data = self._parse_json(result)
        return self._project_to_node(data)

    def close_node(self, native_id: str, mode: str) -> None:
        if mode == "complete":
            # Try task
            script = JXA_COMPLETE_TASK.replace("%TASK_ID%", native_id)
            result = self._run_jxa(script)
            if result.returncode != 0:
                # Try project
                script = JXA_COMPLETE_PROJECT.replace("%PROJECT_ID%", native_id)
                result = self._run_jxa(script)
                if result.returncode != 0:
                    raise RuntimeError(f"Failed to complete: {result.stderr}")
        elif mode == "delete":
            script = JXA_DELETE_TASK.replace("%TASK_ID%", native_id)
            result = self._run_jxa(script)
            if result.returncode != 0:
                script = JXA_DELETE_PROJECT.replace("%PROJECT_ID%", native_id)
                result = self._run_jxa(script)
                if result.returncode != 0:
                    raise RuntimeError(f"Failed to delete: {result.stderr}")
        else:
            raise ValueError(f"OmniFocus adapter supports close modes: complete, delete. Got: {mode}")

    def sync(self, since: str | None = None) -> SyncResult:
        since_val = f'"{since}"' if since else "null"
        script = JXA_SYNC.replace("%SINCE%", since_val)
        result = self._run_jxa(script)
        items = self._parse_json(result) or []
        changed = [self._task_to_node(t) for t in items]
        return SyncResult({"changed_nodes": changed, "changed_edges": []})

    def fetch_body(self, native_id: str) -> str | None:
        node = self.resolve(native_id)
        if node is None:
            return None
        return node.get("body")

    def create_edge(self, source: str, target: str, edge_type: str, metadata: dict | None = None) -> Edge | None:
        # OmniFocus has native belongs-to (task in project) but we don't create those externally
        return None

    def query_edges(self, node_id: str, direction: str = "both", edge_type: str | None = None) -> list[Edge]:
        return []

    def dispatch(self, native_id: str, method: str | None = None, params: dict | None = None) -> Any:
        raise NotImplementedError("OmniFocus adapter does not support dispatch")
