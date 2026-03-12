# PIM Matrix Plugin Architecture

## Overview

The PIM Matrix plugin is a Claude Code extension that gives Claude the ability to operate a personal information management system. Claude is both the user interface and the orchestrator — it interprets natural language intent, decomposes it into operations against the ontology, routes those operations to the appropriate adapters, and narrates results back to the user.

This document describes how to build a system that realizes the model defined in the companion ontology. The ontology defines the pure model — axes, types, registers, relations, operations, transforms. This document defines the implementation — data structures, storage, resolution, retrieval, discovery, write policy, tool interfaces, and adapter contracts.

### The Transparency Principle

The ontology is for the system. It is not for the user. Neither are implementation decisions.

The user never sees the words "diachronic," "sovereign," "referential," or "register." They never encounter the type table, the axis names, or the relation families. The ontology is the formal model that the agents reason with internally — it shapes how the system stores, retrieves, organizes, and connects information. But every interaction with the user happens in the user's own language, using the user's own names for their tools, their projects, and their workflows.

Equally, the user is never asked to make implementation decisions. Questions like "should I create one node per project or one per task?" or "do you want me to import all your tasks or just the flagged ones?" are system design questions that the architecture already answers. The user chose to connect OmniFocus — that means its contents enter the graph. The user doesn't need to know how the PIM represents their data internally, how many index entries are created, or what the ingestion policy is. The system knows. If the agent is uncertain about how to model something, it consults the ontology and the adapter's capability declaration — it does not pass the question to the user.

The user should only be asked questions about **their intent** ("which project is this for?", "is this the same Sarah?") — never about the system's implementation ("how many nodes should I create?", "which register should this go in?").

When the user says "remind me to follow up with Sarah," the interpreter silently recognizes this as: create a task (diachronic, sovereign, structured), with an agency relation to a contact, in the working register. The user never hears any of that. They hear: "Got it — I've added a task to follow up with Sarah in OmniFocus."

This principle applies everywhere: during onboarding (the agent asks about tools and habits, not types and registers), during capture (the agent narrates what it created in concrete terms, not ontology terms), during review (the agent says "you have 3 unread emails and 5 tasks due this week," not "scratch register contains 3 message nodes"), and during configuration (the agent says "I'll use Reminders for your quick to-dos," not "routing task type to Reminders adapter for scratch register").

The ontology is the skeleton. The user sees the skin.

The plugin consists of ten components:

1. **Data model** — how the ontology's abstractions are represented in code
2. **Semantic index** — the embedding layer that supports retrieval, resolution, and discovery
3. **Identity resolution** — determining whether new information refers to an existing node
4. **Retrieval pipeline** — how context is assembled for operations
5. **Relation discovery** — surfacing implicit connections that should become explicit edges
6. **Write policy and decision logs** — risk classification, autonomy levels, and audit
7. **Error handling** — failure modes and graceful degradation
8. **Tool interface and adapter system** — the functions Claude calls and the routing layer
9. **Onboarding and profile** — how the system learns the user's tools and conventions
10. **Agent architecture** — the multi-agent constellation that operates the system

