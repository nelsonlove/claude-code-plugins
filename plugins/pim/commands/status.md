---
description: PIM adapter health and graph statistics
allowed-tools: mcp__pim__pim_stats, mcp__pim__pim_adapter_list, mcp__pim__pim_decision_log
---

Show the current state of the PIM system.

## Your task

1. Call `pim_stats` to get node/edge counts by type and register
2. Call `pim_adapter_list` to check adapter health
3. Call `pim_decision_log(limit=10)` for recent operations
4. Present as a concise status dashboard
5. Flag any unhealthy adapters or anomalies (empty registers, zero edges, etc.)
