## Write Policy and Decision Logs

### Risk Tiers

Not all mutations are equally risky. The system classifies every write operation into three risk tiers, each with a different autonomy level.

**Low risk (autonomous).** Append-only or easily reversible operations. The agent performs these without confirmation:

- Creating an entry (append-only, cheap to create)
- Creating associative relations (references, related-to)
- Adding a belongs-to relation to a topic
- Updating a node's register (scratch → working, working → log)
- Logging a read or retrieval action

**Medium risk (validated).** Operations that create durable state or change meaningful attributes. The agent performs these after passing validation rules (identity resolution, type policy checks):

- Creating a new note, task, event, or resource
- Extracting structured records from unstructured content (message → tasks)
- Creating derivation or agency relations
- Updating a task's status or due date
- Proposing a contact link based on Stage 2/3 resolution
- Relation discovery proposals above the confidence threshold

**High risk (confirmed).** Operations that are expensive to reverse or could corrupt graph structure. The agent proposes these and waits for user confirmation:

- Merging two contacts
- Deleting any node
- Overwriting a note's content body
- Creating a new contact from ambiguous identity resolution
- Merging or splitting topics
- Any operation where identity resolution returned "ambiguous"
- Any batch operation that would create more than 5 nodes (must use `pim_batch_propose` workflow)

### Initial Import Policy

During initial import (onboarding), the risk tier for all operations is elevated. The system has no track record with the user, the graph is empty, and every decision sets a precedent that propagates through future relations.

During initial import:

- All node creation uses the batch proposal workflow, presented to the user in manageable groups (e.g., "I found 45 tasks in OmniFocus across 8 projects. Here's a summary — shall I import them?")
- All identity resolution outcomes are presented for confirmation, not resolved autonomously — even deterministic matches. The user should verify that the system's understanding of "Sarah Chen in contacts" and "sarah@acme.com in email" are indeed the same person.
- Topic hierarchy proposals are presented as a complete structure before committing ("Here's how I'd organize your projects based on your JD numbers — does this look right?")
- The system does not run discovery or enrichment during initial import. Those run after the base graph is confirmed and stable.

After the initial import is confirmed and the user has interacted with the system through at least a few sessions, the write policy relaxes to the standard tier system. The profile records when the system transitions from "onboarding" to "steady-state" operation.

### How the Axes Modulate Risk

The ontology's axes predict risk levels:

**Sovereignty** determines mutability constraints. Sovereign objects can be freely modified (lower risk on updates). Referential objects are constrained by external truth (higher risk on updates — did the external reality actually change?). Referential objects that have crossed the sovereignty boundary (sent messages) are immutable (any "update" is high risk).

**Structuredness** determines the visibility of changes. Updates to structured objects are transparent — you can see what changed in the fields. Updates to unstructured objects are opaque — you have to read both versions to assess the change. Content body overwrites on unstructured types are higher risk than attribute changes on structured types.

**Diachrony** determines reversibility. Diachronic objects that have completed their process (a finished task, a sent message) are effectively immutable — reopening or unsending is high risk. Synchronic objects are more reversible because their identity is in their current state, not their trajectory.

### Decision Log Structure

Every agent action that mutates state produces a decision log entry:

- **id** — unique log entry identifier
- **timestamp** — when the action occurred
- **operation** — what was done (create_node, create_edge, update_node, close_node, merge, resolve, etc.)
- **target** — the PIM URI of the node or edge affected
- **evidence** — what was retrieved to support the decision
- **candidates** — for identity resolution, the candidate set and scores
- **resolution** — found / ambiguous / not_found, with justification
- **risk_tier** — low / medium / high
- **approval** — automatic / validated / user_confirmed
- **reversible** — whether and how the action can be undone

Decision logs serve four functions: **audit** (trace any node back to the evidence that created it), **tuning** (analyze resolution failures), **undo** (reverse mistaken operations), and **provenance** (answer "where did this come from?" via the source_op field on nodes and edges).

### Type Policy Matrix

The object type schemas in the ontology define what a thing *is*. The type policy matrix defines how a thing *behaves* operationally — its identity characteristics, mutability pattern, and risk profile.

| Type | Identity Basis | Mutability | Merge Risk |
|---|---|---|---|
| Note | ID + title + content hash | high (content evolves) | medium |
| Entry | ID + timestamp | immutable once written | low |
| Task | ID + title + topic link | state-mutable (status, dates) | medium |
| Event | ID + start time + title | low (attributes may shift) | medium |
| Message | ID + message-id + sent_at | immutable (body fixed after send) | low |
| Contact | name + email + phone + aliases | low (attributes updated, entity stable) | high |
| Resource | URI | low (metadata may update) | low |
| Topic | ID + title | low (title may evolve) | high |

### Enrichment Policy

The agent does not just respond to user requests — it also generates metadata, annotations, descriptions, and proposed relations to make the graph more useful over time. This raises a policy question the write policy alone does not answer: **how much should the agent do without being asked?**

#### Agent-Authored Content

When the agent generates a description of a bookmarked article, or summarizes a contact's interaction history, or annotates a resource with a note about why the user saved it, the result is a sovereign, unstructured object — a Note — but one authored by the agent rather than the user. The system must track this distinction:

- Every node has a **provenance** field in its decision log entry: `user_authored`, `agent_authored`, or `agent_proposed`.
- Agent-authored content is freely overwritable by the agent (it can regenerate a description as context changes). User-authored content is not (overwriting a user's note is a high-risk operation).
- Agent-proposed content (e.g., a suggested annotation) enters the graph in a pending state and is confirmed or discarded by the user during review.

#### Enrichment Density

Not every object in the graph needs annotation. The right density of agent-generated metadata depends on the object type, the user's actual usage patterns, and the cost of being wrong.

**Default enrichment by type:**

- **Resources** (bookmarks, files, saved articles): the agent generates a brief description on ingestion if the resource has readable content (a web page, a PDF). For opaque resources (a binary file, a login page), the agent records the title and URI but does not fabricate a description. If the user later asks about the resource, the agent can enrich at that point.
- **Contacts**: the agent does not generate biographical notes by default. It lets the interaction history (messages, events, tasks involving the contact) serve as the contact's context. If the user asks "tell me about Sarah," the agent synthesizes from the graph neighborhood at query time. **After a substantive synthesis, the agent should persist the result as an agent-authored note linked to the contact via annotation-of.** This avoids re-synthesizing the same intelligence in the next session. The note is tagged `agent_authored` and is freely overwritable — the agent regenerates it as new information arrives. The contact schema stays lean (name, email, role); the rich context lives in the annotation.
- **Messages**: the agent does not annotate individual messages. It may annotate *threads* (a summary of a conversation) when the thread is long or when the user explicitly processes it.
- **Notes, entries, tasks, events, topics**: the agent does not generate annotations for objects the user already authored or explicitly created. These objects are their own metadata.

**Adaptive enrichment:** The default policy is conservative — generate less, not more. Over time, the agent adjusts based on what the user actually retrieves. If the user frequently queries bookmarks by content ("find that article about Rasch measurement"), the agent should proactively describe new bookmarks. If the user never queries bookmarks, the agent should not. The profile's `workflow_patterns` field captures these preferences as they emerge.

#### Proactive vs. Reactive

Enrichment can happen at three moments:

- **On ingestion** (proactive): when a node enters the graph during sync or capture, the agent immediately generates metadata. Appropriate for resources with readable content, contacts extracted from messages, and topics inferred from organizational structure.
- **On access** (reactive): when the user or agent first retrieves a node for an operation, the agent enriches it at that point. Appropriate for objects that might never be accessed (old archived emails, filesystem resources) — don't pay the cost until the value is needed.
- **On review** (batch): during scheduled or user-initiated review, the agent enriches a batch of under-described objects. "You have 15 bookmarks in scratch with no description. Want me to summarize them?"

The choice between proactive and reactive enrichment is a tradeoff between graph quality (proactive produces a richer, more searchable graph) and noise (proactive generates content the user may never need and may not agree with). The default is **reactive for most types, proactive only for resources with readable content**, adjustable through the profile.

#### Relation Enrichment

Relation discovery (described above) is a form of enrichment — the agent proposes edges the user didn't explicitly create. The enrichment policy governs how aggressively discovery runs and what it does with results:

- **After every capture**: always run discovery. New objects should be linked to existing ones. Low cost, high value.
- **During review**: run discovery on the reviewed set. Surface connections the user might not have noticed. Medium cost, variable value.
- **Background passes**: run discovery on the full graph periodically. High cost, diminishing returns as the graph matures. Default to weekly, adjustable.

Discovery results above the confidence threshold become medium-risk write operations (the executor creates the edge on the interpreter's instruction, logged in the decision log). Results below the threshold are surfaced as suggestions during the next review.