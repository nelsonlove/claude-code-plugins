# PIM Architecture Alignment Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close all gaps between the 10 architecture docs and the current plugin implementation, limited to what's achievable within Tier 1 (no embedding models, no LLM-in-the-loop).

**Architecture:** Wire existing backing logic (agents.py, enrichment.py, identity.py, profile.py) to the MCP surface. Create Claude Code agent definitions with system prompts from doc 10. Fix skill documentation to match actual tool signatures.

**Tech Stack:** Python (FastMCP), Claude Code plugin system (agent .md files, skill .md files)

---

### Task 1: Expose `pim_discover` as MCP tool

The `RelationDiscovery` class in enrichment.py has `discover_for_node()` and `auto_enrich()` but neither is accessible via MCP. The linking skill references `pim_discover` which doesn't exist.

**Files:**
- Modify: `plugins/pim/src/server.py` (add tool after convenience tools section)
- Modify: `plugins/pim/src/server.py` (add enrichment imports to `create_server`)

**Step 1: Add enrichment imports and initialization to `create_server()`**

In server.py, after `orch = Orchestrator(...)`, initialize the enrichment components:

```python
from src.enrichment import RelationDiscovery, EnrichmentPolicy
discovery = RelationDiscovery(orch=orch)
```

**Step 2: Add `pim_discover` tool**

After the `pim_review` tool, add:

```python
@mcp.tool()
def pim_discover(
    node_id: str,
    auto_create: bool = False,
) -> dict:
    """Discover potential relations for a node.

    Analyzes attributes and content to suggest edges. With auto_create=True,
    automatically creates low-risk relations (references, related-to, belongs-to)
    that meet the confidence threshold.

    Args:
        node_id: PIM URI of the node to analyze
        auto_create: If True, auto-create low-risk suggestions (default: False)
    """
    if auto_create:
        created = discovery.auto_enrich(node_id)
        return {"auto_created": created}
    suggestions = discovery.discover_for_node(node_id)
    return {"suggestions": suggestions}
```

**Step 3: Verify server loads**

Run: `cd plugins/pim && python3 -c "from src.server import mcp; import asyncio; tools = asyncio.run(mcp.list_tools()); print(f'{len(tools)} tools OK')"`
Expected: `20 tools OK`

**Step 4: Commit**

```bash
git add plugins/pim/src/server.py
git commit -m "feat(pim): expose pim_discover tool for relation discovery"
```

---

### Task 2: Expose config tools (`pim_stats`, `pim_adapter_list`, `pim_routing`)

ConfigAgent has `get_stats()`, `list_adapters()`, `get_routing()`/`set_routing()` but none are MCP tools. The status command currently has to manually query every type.

**Files:**
- Modify: `plugins/pim/src/server.py` (add 3 tools)

**Step 1: Initialize ConfigAgent in `create_server()`**

```python
from src.agents import ConfigAgent
config_agent = ConfigAgent(orch=orch, conn=conn)
```

**Step 2: Add config tools after `pim_decision_log`**

```python
@mcp.tool()
def pim_stats() -> dict:
    """Get PIM system statistics — node/edge counts by type and register."""
    return config_agent.get_stats()

@mcp.tool()
def pim_adapter_list() -> list[dict]:
    """List all registered adapters with capabilities and health status."""
    return config_agent.list_adapters()

@mcp.tool()
def pim_routing(
    updates: dict | None = None,
) -> dict:
    """Read or update the adapter routing table.

    Without arguments, returns the current routing. With updates dict,
    merges changes (e.g. {"task": "omnifocus"}).

    Args:
        updates: Optional partial routing changes to merge
    """
    if updates:
        current = config_agent.get_routing()
        current.update(updates)
        return config_agent.set_routing(current)
    return config_agent.get_routing()
```

**Step 3: Verify**

Run: `cd plugins/pim && python3 -c "from src.server import mcp; import asyncio; tools = asyncio.run(mcp.list_tools()); print(f'{len(tools)} tools OK')"`
Expected: `23 tools OK`

**Step 4: Commit**

```bash
git add plugins/pim/src/server.py
git commit -m "feat(pim): expose config tools — pim_stats, pim_adapter_list, pim_routing"
```

---

### Task 3: Update status command to use config tools

The status command lists only `pim_query_nodes` and `pim_decision_log` as allowed tools. It should use `pim_stats` and `pim_adapter_list`.

**Files:**
- Modify: `plugins/pim/commands/status.md`

**Step 1: Update allowed-tools and instructions**

```yaml
---
description: PIM adapter health and graph statistics
allowed-tools: mcp__pim__pim_stats, mcp__pim__pim_adapter_list, mcp__pim__pim_decision_log
---
```

Update the task section:

```markdown
## Your task

1. Call `pim_stats` to get node/edge counts by type and register
2. Call `pim_adapter_list` to check adapter health
3. Call `pim_decision_log(limit=10)` for recent operations
4. Present as a concise status dashboard
5. Flag any unhealthy adapters or anomalies (empty registers, zero edges, etc.)
```

**Step 2: Commit**

```bash
git add plugins/pim/commands/status.md
git commit -m "fix(pim): update status command to use config tools"
```

---

### Task 4: Fix skill API documentation

Several skills show the wrong calling convention for `pim_query_nodes`. The server uses top-level parameters, not a nested `filters` dict.

**Files:**
- Modify: `plugins/pim/skills/search/SKILL.md`
- Modify: `plugins/pim/skills/daily-review/SKILL.md`
- Modify: `plugins/pim/skills/linking/SKILL.md`

**Step 1: Fix search skill**

Replace any instances of `pim_query_nodes(type="X", filters={"text_search": "Y"})` with the actual signature: `pim_query_nodes(type="X", text_search="Y")`. Do the same for `register` and `attributes` — they're top-level params, not nested.

**Step 2: Fix daily-review skill**

The daily review queries events by date. `pim_query_nodes` doesn't have date params, but attributes can contain date fields. Update the skill to use `attributes={"date": "2026-03-13"}` or `text_search` as the filtering mechanism, matching what the server actually supports.

**Step 3: Fix linking skill**

Update `pim_discover` reference to match the actual tool signature: `pim_discover(node_id="pim://...", auto_create=False)`.

**Step 4: Commit**

```bash
git add plugins/pim/skills/
git commit -m "fix(pim): update skills to match actual MCP tool signatures"
```

---

### Task 5: Wire post-create discovery

Doc 10 system prompts say "After capture, invoke discovery on the new nodes." Currently, `create_node` does not trigger discovery. Two options: (a) auto-trigger in orchestrator, or (b) let skills direct it. Option (b) is better — keeps the orchestrator lean and lets the agent decide when discovery is appropriate.

**Files:**
- Modify: `plugins/pim/skills/capture/SKILL.md`
- Modify: `plugins/pim/skills/triage/SKILL.md`

**Step 1: Update capture skill**

After the node creation step, add:

```markdown
6. **Run discovery**: Call `pim_discover(node_id=<created_uri>)` on the new node to find potential relations
7. **Auto-link high-confidence suggestions**: If any suggestions have confidence ≥ 0.7, call `pim_discover(node_id=<created_uri>, auto_create=True)` to wire them automatically
```

**Step 2: Update triage skill**

After filing decisions, add a discovery step for newly promoted items.

**Step 3: Commit**

```bash
git add plugins/pim/skills/
git commit -m "feat(pim): add post-create discovery to capture and triage skills"
```

---

### Task 6: Create Claude Code agent definitions

The architecture defines 6 agents with system prompts (doc 09, doc 10). No agent `.md` files exist in the plugin. These define how Claude Code subagents behave.

**Files:**
- Create: `plugins/pim/agents/interpreter.md`
- Create: `plugins/pim/agents/executor.md`
- Create: `plugins/pim/agents/research.md`
- Create: `plugins/pim/agents/discovery.md`
- Create: `plugins/pim/agents/briefing.md`
- Create: `plugins/pim/agents/config.md`

Each agent needs:
- YAML frontmatter (name, description, tools, model hint)
- System prompt content from doc 10
- Tool access scoped per doc 09 authority matrix

**Step 1: Create interpreter agent** (user-facing, delegates to others)

Key directives from doc 10:
- Interpret user intent in ontology terms, respond in natural language
- PIM is an index, not a mirror
- Never ask user to make architectural decisions
- Never ask user to sequence work
- Capture is comprehensive (all types, all adapters)
- Extract from body, not just headers
- After capture, invoke discovery
- Respect write policy

Tools: All read tools + pim_create_node/edge (for simple ops) + Agent tool (for delegation)

**Step 2: Create executor agent** (write-only subagent)

Key directives:
- Only agent with write access
- Executes operation plans from interpreter
- Uses bulk tools for throughput
- Logs all operations via decision log

Tools: All pim_create/update/close tools + batch tools. NO query tools (read-only comes from plan).

**Step 3: Create research agent** (deep retrieval subagent)

Key directives:
- Multi-strategy search: text → graph expansion → semantic
- Traces connections to configurable depth
- Returns structured results, not raw dumps
- Read-only access

Tools: pim_query_nodes, pim_query_edges, pim_resolve, pim_review

**Step 4: Create discovery agent** (relation suggestion subagent)

Key directives:
- Runs relation discovery on nodes
- Proposes edges, does not commit
- Uses enrichment policy for confidence thresholds
- Read-only + pim_discover

Tools: pim_query_nodes, pim_query_edges, pim_discover

**Step 5: Create briefing agent** (session startup subagent)

Key directives:
- Compiles session briefing from scratch + working registers
- Summarizes recent activity
- Read-only

Tools: pim_review, pim_query_nodes, pim_stats

**Step 6: Create config agent** (system admin subagent)

Key directives:
- Manages adapter configuration
- Updates routing table
- Runs health checks
- Only agent that modifies config

Tools: pim_adapter_list, pim_routing, pim_stats

**Step 7: Commit**

```bash
git add plugins/pim/agents/
git commit -m "feat(pim): create 6 Claude Code agent definitions with system prompts"
```

---

### Task 7: Populate decision_log fields properly

The decision_log schema has `candidates` and `resolution` columns that are never populated. Identity resolution should use them.

**Files:**
- Modify: `plugins/pim/src/server.py` (`pim_resolve` tool)
- Modify: `plugins/pim/src/orchestrator.py` (`_log_decision` calls)

**Step 1: Update `pim_resolve` to log resolution outcomes**

After identity resolution returns, log the outcome with candidates and resolution fields:

```python
orch._log_decision(
    "resolve",
    hints.get("name", str(hints)),
    orch._classify_risk("ambiguous_resolution") if len(results) > 1 else RISK_LOW,
    evidence={"hints": hints, "type": type},
)
```

Update the decision_log INSERT to populate `candidates` and `resolution` columns.

**Step 2: Update `_log_decision` to accept candidates and resolution params**

Add optional `candidates` and `resolution` parameters:

```python
def _log_decision(self, operation, target, risk_tier, approval="automatic",
                  evidence=None, candidates=None, resolution=None):
```

**Step 3: Commit**

```bash
git add plugins/pim/src/server.py plugins/pim/src/orchestrator.py
git commit -m "fix(pim): populate decision_log candidates and resolution fields"
```

---

### Task 8: Add duplicate edge idempotency to orchestrator

The internal adapter already has idempotent `create_edge`, but the orchestrator's `create_edges` bulk method doesn't check for duplicates — it delegates to `internal.create_edge` which handles it, but logs a decision for every call even when the edge already exists.

**Files:**
- Modify: `plugins/pim/src/orchestrator.py`

**Step 1: Skip logging for existing edges in bulk create**

In `create_edges()`, check if `internal.create_edge` returned an existing edge (the adapter returns it without creating) and only log if it's actually new. This requires checking the created_at timestamp or adding a return flag.

Actually — the internal adapter's create_edge is already idempotent and returns the existing edge. The decision log entry is still useful for auditing. **This is a non-issue.** Skip this task.

---

### Task 9: Verify and commit all changes

**Step 1: Run full test suite**

```bash
cd plugins/pim && python3 -m pytest tests/ -v
```

**Step 2: Verify server loads with all new tools**

```bash
python3 -c "from src.server import mcp; import asyncio; tools = asyncio.run(mcp.list_tools()); names = sorted(t.name for t in tools); print('\n'.join(names)); print(f'\nTotal: {len(tools)}')"
```

Expected: 23 tools (19 current + pim_discover + pim_stats + pim_adapter_list + pim_routing)

**Step 3: Check git status, ensure no untracked files left behind**

---

## Out of Scope (Genuinely Deferred)

These are gaps identified in the audit that require capabilities not available in Tier 1:

| Gap | Reason Deferred | Tier |
|-----|-----------------|------|
| Semantic embedding generation | Needs external embedding model | 2 |
| Composite scoring (graph + temporal + semantic) | Needs embeddings | 2 |
| 4-stage retrieval pipeline (stages 3-4) | Needs semantic search | 2 |
| Body-level extraction | Needs NLP/LLM in ingestion loop | 4 |
| Cross-adapter register transitions | Only internal adapter active | 3 |
| Adapter sync mechanism | External adapters not loaded | 3 |
| Identity resolution Stage 3 (relation-aware) | Needs graph maturity | 3 |
| Profile-driven prompt injection | Needs agent deployment | 2 |
| Adaptive enrichment (learning from acceptance) | Needs usage data | 4 |
| MCP bridge adapter generation | External adapters not loaded | 3 |
