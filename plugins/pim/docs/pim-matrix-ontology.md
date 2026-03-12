# PIM Matrix Ontology

## Purpose

This document defines the formal model of a personal information management system. It describes what kinds of things exist, what properties they have, how they relate to each other, and what operations act on them.

Everything in this document is model. There is no implementation here — no databases, no APIs, no adapter contracts, no code. The companion architecture document describes how to build a system that realizes this model. The companion essay describes the philosophy and motivation behind it.

---

## Part I: Rationale

### The Problem

Every personal information management system must decide what kinds of things it contains. Most systems answer this question with an ad hoc list: notes, tasks, events, contacts. The list varies by tool and by tradition. Notion has pages and databases. OmniFocus has tasks, projects, and folders. Apple's ecosystem has separate apps for notes, reminders, calendar, contacts, mail, and files. GTD names inboxes, projects, next actions, waiting-for lists, someday/maybe lists, and reference material.

These lists are useful but unprincipled. They arise from the history of specific tools or methodologies rather than from the structure of the domain itself. This has consequences. When a list is ad hoc, there is no way to know whether it is complete — whether some important kind of thing has been left out. There is no way to know whether two items on the list are genuinely distinct or merely different names for the same thing. And there is no way to know whether the categories will hold up as the system grows, or whether they will need patching with exceptions and special cases.

This ontology takes a different approach. Instead of listing types and defending each one individually, it identifies a small set of independent properties that every piece of personal information possesses, and derives the types as the complete set of combinations those properties produce. The types are not chosen; they are generated.

### Design Criteria

A good decomposition of the PIM space must satisfy three criteria:

**Independence.** The generating properties must be genuinely orthogonal. Each property must vary independently of the others — knowing one tells you nothing about the others. If two properties are correlated (e.g., if "referential" things are always "structured"), the decomposition has a hidden dependency and produces empty or forced cells.

**Exhaustiveness.** Every combination of properties must correspond to a real, recognizable kind of information object. No cell in the resulting table should be empty, and no cell should require a contrived example. If the decomposition is correct, you should be able to point to the objects in each cell and say "yes, I have those, and they behave differently from the objects in every other cell."

**Minimality.** The properties should be the fewest needed to capture the meaningful distinctions. Adding a fourth binary axis would produce sixteen types. If the sixteen-type table contains pairs of types with no meaningful behavioral difference, the fourth axis is not doing useful work. Conversely, if two types in the eight-type table collapse into one under real use, an axis is not carrying its weight.

### Why These Axes

The three properties that generate the object types — diachrony, sovereignty, and structuredness — are not arbitrary. Each one names a distinction that every PIM user encounters in practice, that affects how the object is created, stored, retrieved, and used, and that cannot be reduced to either of the other two.

**Diachrony** captures the distinction between things that exist as processes unfolding across time (a meeting, a journal entry, an email exchange, a task moving from undone to done) and things that exist as states at a point in time (a note, a contact, a saved article, a project). The terms are from Saussure: *diachronic* means "pertaining to change across time," *synchronic* means "pertaining to a state at a moment." This matters because diachronic objects organize by when — you browse your calendar by date, you scan your inbox newest-first. Synchronic objects organize by what — you browse your contacts by name, you search your notes by content. The retrieval logic, the display logic, and the lifecycle are all different.

**Sovereignty** captures the distinction between things whose truth is determined by the user and things whose truth is determined elsewhere. You are the sole authority on what your note says — rewrite it completely and it's still valid. You are not the sole authority on what a contact's phone number is — your record must track an external reality. This matters because sovereign objects are freely mutable (you can edit, restructure, and redefine them at will) while referential objects are constrained by something outside the PIM (you can update your record, but the update must correspond to the world). The mutability model, the authority model, and the decomposition logic are all different.

**Structuredness** captures the distinction between things that are fully described by their fields and things that carry content you have to read. A task is a record: title, status, due date, done. A note is a body of text: you have to read it to know what is in it. This matters because structured objects are legible to machines (queryable, sortable, state-trackable) while unstructured objects are legible primarily to humans (searchable, but not parseable without interpretation). The extraction/narration boundary — turning prose into records and records into prose — runs along this axis.

Each axis affects different aspects of how information behaves. None is redundant. All eight combinations produce recognizable, distinct objects. The decomposition satisfies the three criteria.

### The Second Dimension: Registers

The type axes describe what a piece of information *is*. But there is a second question the ontology must answer: what is the user's relationship to it *right now*?

Consider a note. A note is synchronic, sovereign, unstructured — that is fixed by its type. But the *same* note might be in very different states at different moments. When first jotted down, it is raw, unprocessed, sitting in an inbox waiting to be dealt with. Later, it might be actively being developed — linked to other notes, revised, restructured. Eventually, it might settle into a stable form, looked up occasionally but rarely changed. Or it might become a historical record — a snapshot of thinking at a point in time, never modified again.

These are not type differences. The note remains a note throughout. They are differences in the *mode of cognitive engagement* between the user and the object. The note moves through stages of attention: from needing triage, to being actively worked, to being filed for retrieval, to being part of the historical record.

This dimension is what the ontology calls the **register**. The term is borrowed loosely from linguistics, where a register is the variety of language appropriate to a particular context or relationship — you speak in a different register to your boss than to your child. Here, the register is the variety of *attention* appropriate to a particular stage of engagement with information. You attend to inbox items differently than you attend to filed references. The mode of interaction — how often you touch it, whether you expect it to change, whether it arrived by accretion or was placed deliberately — shifts with the register.

The register is not a workflow stage in the GTD sense (though it overlaps with GTD's categories). It is a property of the node *instance*, not the node type. Any object type can exist in any register. A task can be in scratch (just captured, not yet triaged), working (actively being pursued), reference (a standing checklist you consult repeatedly), or log (completed, part of the historical record). The register is orthogonal to the type.

Two binary properties generate the four registers, following the same logic as the type axes.

**Stability** captures the distinction between things that are expected to change (an inbox item awaiting triage, a draft being revised) and things that are settled (a filed reference, a completed journal entry). This matters because it determines how the system should treat the object: flag it for attention, or trust that it is done.

**Intentionality** captures the distinction between things the user deliberately placed and things that arrived or settled on their own. You *chose* to put that note in your reference files. You *chose* to pull that task onto your workbench. But your inbox filled up by arrival — things landed there without a decision. And your completed-task history grew by byproduct — things settled there because the work finished, not because you filed them. This matters because it determines how the register is populated and therefore how it should be navigated: curated registers reward browsing by content or structure; accrued registers reward browsing by recency or sequence.

A note on why intentionality is not the same as diachrony (the type-generating axis). Diachrony asks whether *the object exists as a process unfolding across time* — whether it is constituted by change. Intentionality asks whether *the user made a deliberate decision* to place the object in its current register. An entry (diachronic type) can be deliberately filed as reference (curated register) or can settle into the log as a byproduct of completion (accrued register). A contact (synchronic type) can accrue in scratch when auto-extracted from an email, or be curated into reference when deliberately added to the address book. The two axes cross independently.

### What the Register Axes Predict

The register axes are not just classificatory — they have operational consequences. Each axis determines a different aspect of how the system should behave toward objects in a given register.

**Stability determines the attention model.** Unstable registers (scratch, working) contain objects that need the system to *surface* them — to proactively show the user what is waiting, what is active, what has changed. These are the registers that drive review. Stable registers (reference, log) contain objects that need the system to *stand by* — to wait until the user asks, because nothing there demands action. These are the registers that serve retrieval.

**Intentionality determines the navigation model.** Accrued registers (scratch, log) are best navigated by *recency and sequence* — things arrived in an order, and that order is usually the most useful organizing principle. You scan your inbox newest-first. You browse your journal chronologically. Curated registers (working, reference) are best navigated by *structure and content* — the user imposed an organization when they placed things here, and that organization is the best retrieval key. You search your reference files by topic. You review your working set by project or priority.

The cross-product of these two consequences predicts the character of each register:

- **Scratch** (unstable, accrued): surface proactively, navigate by recency. This is the inbox: "here is what just arrived, deal with it."
- **Working** (unstable, curated): surface proactively, navigate by structure. This is the workbench: "here is what you chose to engage with, organized the way you set it up."
- **Log** (stable, accrued): retrieve on demand, navigate by sequence. This is the journal: "here is what happened, in order."
- **Reference** (stable, curated): retrieve on demand, navigate by content. This is the filing cabinet: "here is what you filed, find it by what it is."

These predictions extend to the system's core operations. Capture routes new objects into accrued registers (scratch by default; log for completed byproducts). Triage is the act of moving objects from accrued to curated (scratch to working or reference). Review surfaces unstable registers. Retrieval searches stable registers. Dispatch draws primarily from curated registers (working and reference), since those contain the objects the user has deliberately shaped or filed.

Four combinations, four registers, no empty cells.

---

## Part II: The Generating Axes

The rationale above argues for the axes; this section defines them precisely.

### Type-Generating Axes

**Diachrony** — Does the thing exist as a process unfolding across time?

- *Diachronic*: exists as change, transition, or exchange across time. It is constituted by its trajectory.
- *Synchronic*: exists as a state at a point in time. It has history, but its identity is in its current condition.

**Sovereignty** — Is the user the sole authority on this object's truth?

- *Sovereign*: the PIM is the source of truth. The object is what the user says it is.
- *Referential*: the PIM points at or records something whose truth is determined elsewhere. The object must track an external reality.

**Structuredness** — Is the thing fully described by its fields, or does it carry content that must be read?

- *Structured*: a record. Its attributes tell you everything.
- *Unstructured*: carries substance beyond its metadata. You have to read it to know what is in it.

### Register-Generating Axes

**Stability** — Does the content change once it is in this state?

- *Unstable*: expected to change, be processed, or move on.
- *Stable*: settled. Once here, it stays as it is.

**Intentionality** — Did the user deliberately place the object in this state?

- *Curated*: the user made a deliberate decision to place or promote this object here.
- *Accrued*: the object arrived or settled here through process — capture, completion, or byproduct — without a specific placement decision.

### Axis Summary

The five axes:

| Axis | Values | Generates |
|---|---|---|
| Diachrony | diachronic, synchronic | object types (with sovereignty and structuredness) |
| Sovereignty | sovereign, referential | object types (with diachrony and structuredness) |
| Structuredness | structured, unstructured | object types (with diachrony and sovereignty) |
| Stability | stable, unstable | registers (with intentionality) |
| Intentionality | curated, accrued | registers (with stability) |

---

## Part III: Object Types

### The Type Table

Each combination of three type-generating axes produces a cell. Before naming the types, consider what occupies each cell in practice:

|  | Unstructured | Structured |
|---|---|---|
| **Diachronic + Referential** | emails, texts, chat messages | meetings, appointments, deadlines |
| **Diachronic + Sovereign** | journal entries, meeting notes, daily logs | tasks, to-dos, action items |
| **Synchronic + Referential** | saved articles, bookmarks, files, PDFs | people, businesses, organizations |
| **Synchronic + Sovereign** | working notes, evolving ideas, SOPs | projects, areas, categories, tags |

Each cell is recognizable. The examples in each cell share a family resemblance with each other and differ from the examples in every other cell. You manage your journal entries differently from your working notes. You manage your saved articles differently from your contact list. The axes are cutting the space along real joints.

The ontology assigns one name to each cell:

|  | Unstructured | Structured |
|---|---|---|
| **Diachronic + Referential** | Message | Event |
| **Diachronic + Sovereign** | Entry | Task |
| **Synchronic + Referential** | Resource | Contact |
| **Synchronic + Sovereign** | Note | Topic |

This table is exhaustive. Every cell is occupied and no type is forced. The eight types are the complete set of configurations generated by three independent binary properties.

### Why Each Type Sits Where It Does

Some assignments are intuitive — a calendar event is obviously diachronic, referential, and structured. Others deserve argument.

**Task is diachronic.** Not because every task has a due date (many don't), but because a task is inherently a state transition. It moves from undone to done. That trajectory — open, then completed, then behind you — is a process unfolding across time even when no specific date is attached. A "someday/maybe" task is still a thing that hasn't happened yet. Remove the diachronic dimension and you have a label, not a task.

**Task is sovereign.** Even when a task originates from an external request ("Can you send me the report?"), the *task itself* — the commitment to act — is declared by the user. The email is referential. The decision to treat it as an obligation is sovereign. You are the sole authority on whether this task exists, what it means, and when it's done.

**Task is structured.** A task's essential data is its state machine: title, status, due date, done. Tasks can carry notes and descriptions, but that content is supplementary. You check a task; you don't read it. The action is in the fields.

**Entry is diachronic, Note is synchronic.** Both are authored text. Both have timestamps. The difference is whether the object exists as a process or as a state. An entry *is of* a date — "March 12 meeting notes" or "Tuesday's journal." Move it to a different date and you've changed what it is. A note *is about* its content — "API design principles" or "thoughts on the custody case." The same note revised a month later is still the same note. The entry is fixed in the flow of time; the note is revised across it while remaining itself.

**Entry is sovereign.** You are the sole authority on what you experienced, thought, or recorded on a given date. An entry is low-mutability by convention — you choose not to revise journal entries — but not by external constraint. Nobody can overrule your meeting notes. This is what distinguishes an entry from a message: both are diachronic and unstructured, but the entry's truth is yours alone, while the message's truth is shared with a counterparty.

**Message is referential.** Even though you write outbound messages, the message type represents communication *across a sovereignty boundary*. A message is not a monologue — it implies a counterparty. The exchange as a whole, including the context, the thread, the other party's contributions, involves truth that is not solely yours. A sent message is immutable because it became part of a shared record the moment it was sent.

**Contact is referential.** You create the contact record, but the entity it represents — the person, the business — exists independently of your PIM. You don't author Sarah; you record her. The record is yours; the referent is not. You can update your record, but the update must correspond to reality. This is what "referential" means: the PIM is pointing at something whose truth is determined elsewhere.

**Resource is unstructured.** A URL or filepath looks like a structured field, but the *substance* of a resource is the content it points to — a PDF, an article, a dataset. The pointer is metadata; the thing pointed to must be read, viewed, or interpreted. The PIM holds the pointer and some descriptive attributes, but you have to follow the link to know what's there.

**Topic is structured.** A topic might have a description, but the description isn't what makes it a topic. A topic is a label with relations — it is fully described by its title, its status, and the other objects that belong to it. You don't read a topic; you navigate through it.

### Type Definitions

Each type is a schema: a set of expected attributes and typical relation types. Schemas are expectations, not rigid constraints. A task without a due date is still a task.

#### Note

Synchronic, sovereign, unstructured. A living document — authored, revised, evolved. Its value is in its current state. A working idea, a developing argument, an evergreen document.

**Attributes:**
- title (string, optional)
- body (content reference)
- format (enum: plaintext, markdown, rich text, …)

**Typical relations:** belongs-to topic, derived-from message/event/resource, references any node, annotation-of any node.

#### Entry

Diachronic, sovereign, unstructured. A time-stamped record of thought or experience — authored but fixed once written. A journal entry, meeting notes after the fact, a daily log. Its value is in its position in the flow of time.

**Attributes:**
- title (string, optional)
- body (content reference)
- format (enum: plaintext, markdown, rich text, …)
- timestamp (datetime — when the entry refers to, not just when it was created)

**Typical relations:** belongs-to topic, derived-from event/message, annotation-of any node, follows entry.

#### Task

Diachronic, sovereign, structured. A state transition — something that needs to move from undone to done. The essential data is the state machine; everything else is metadata on the transition.

**Attributes:**
- title (string)
- status (enum: open, completed, cancelled, deferred)
- due_date (datetime, optional)
- defer_date (datetime, optional)
- priority (enum or integer, optional)
- context (string, optional)

**Typical relations:** belongs-to topic, delegated-to contact, blocks task, blocked-by task, derived-from message/note/event.

#### Event

Diachronic, referential, structured. A fact about the world anchored in time — something happening at a specific moment, optionally for a duration. The PIM records it; the PIM is not the authority on whether or when it happens.

**Attributes:**
- title (string)
- start (datetime)
- end (datetime, optional)
- duration (interval, optional — alternative to end)
- location (string, optional)
- recurrence (recurrence rule, optional)
- status (enum: confirmed, tentative, cancelled)

**Typical relations:** belongs-to topic, involves contact, derived-from message, generates entry/task.

#### Message

Diachronic, referential, unstructured. Communication across a sovereignty boundary — something with a body, a sender, a recipient, and a timestamp. Email, text, chat. Partially authored (you write replies) but the exchange as a whole involves truth shared with a counterparty.

**Attributes:**
- subject (string, optional)
- body (content reference)
- sent_at (datetime)
- channel (enum: email, sms, imessage, chat, …)
- direction (enum: inbound, outbound, draft)
- thread_id (string, optional)

**Typical relations:** from contact, to contact, belongs-to topic, reply-to message, generates task/event/note/entry.

#### Contact

Synchronic, referential, structured. An entity in the world — a person, business, or organization. The contact information is attributes on the entity; the entity itself is a node that other objects relate to. The PIM records the entity but is not the authority on its truth.

**Attributes:**
- name (string)
- email (string or list, optional)
- phone (string or list, optional)
- address (string, optional)
- organization (string, optional)
- role (string, optional)

**Typical relations:** belongs-to topic, member-of contact, related-to contact.

Contacts are natural hub nodes. They accumulate inbound relations from messages, events, tasks, and notes. The traversal "show me everything related to this contact" is one of the system's most important queries.

#### Resource

Synchronic, referential, unstructured. A pointer to an external resource — a URL, a filepath, a DOI, an ISBN. The PIM holds the pointer and metadata; the substance lives elsewhere and its truth is determined by the external source. Resources subsume what traditional PIMs split into "bookmarks" and "files" — both are pointers to things outside the system, differing only in where the target lives.

**Attributes:**
- uri (URI — URL, filepath, DOI, ISBN, or any resolvable identifier)
- title (string, optional)
- description (string, optional)
- media_type (MIME type, optional)
- read_status (enum: unread, read, archived, optional)

**Typical relations:** belongs-to topic, annotation-of (when a note or entry comments on this resource), sent-by contact, attached-to message, derived-from message/note.

#### Topic

Synchronic, sovereign, structured. A named area of concern — a label that other objects cluster around. A project, an area of responsibility, a client, a goal, a category. Topics relate to other topics, which is where organizational hierarchy comes from. A flat tag is a topic with no parent.

**Attributes:**
- title (string)
- description (string, optional)
- status (enum: active, on hold, completed, archived)
- taxonomy_id (string, optional — e.g., JD number, PARA category)

**Typical relations:** contains topic, parent-of/child-of topic, belongs-to topic.

Topics are the organizational backbone. Every other object type can belong to a topic. The traversal "show me everything under this topic" fans out across the entire graph and returns a unified view of a project or area of concern.

---

## Part IV: Registers

### The Register Table

Each combination of two register-generating axes produces one register:

|  | Accrued | Curated |
|---|---|---|
| **Unstable** | Scratch | Working |
| **Stable** | Log | Reference |

### Register Definitions

As established in Part I, the register is a property of the node instance, not the object type. Any type can exist in any register. What follows are the four registers and their characteristic behaviors.

#### Scratch

Unstable, accrued. An inbox. Things land here by arrival — new captures, auto-extracted objects, inbound messages — without the user making a placement decision. Everything in scratch needs to be processed and moved: triaged into working, filed into reference, or discarded.

**Signals:** recently created, few or no relations beyond auto-generated ones, possibly no explicit topic assignment.

#### Working

Unstable, curated. A workbench. The user deliberately selected or promoted these objects for active engagement. Things here are being shaped, linked, revised, transformed. The current state is what matters; yesterday's draft is overwritten by today's. Working is the active register — everything in it is on its way somewhere.

**Signals:** high modification frequency, dense relations (especially to other working-register nodes), content evolving.

#### Reference

Stable, curated. A filing cabinet. The user deliberately placed these objects for future retrieval. Content is looked up more than written to — the settled fact, the permanent record. Things enter through intentional filing and remain until they are no longer relevant.

**Signals:** low modification frequency, high retrieval frequency, typically organized (has topic relations), content is objective or impersonal.

#### Log

Stable, accrued. A journal. Things settle here as a byproduct of completion or passage — finished tasks, sent messages, concluded interactions, journal entries written and left. The user did not file these objects into log; they arrived because the engagement that produced them ended. Nothing in log changes once it is there.

**Signals:** append-mostly, temporally organized, content is personal or reflective, relations are often backward-looking (annotation-of, derived-from).

### Register Transitions

Objects move between registers over their lifecycle. The transitions follow a pattern: triage is the act of applying intentionality to accrued objects, and completion is the act of releasing curated objects back into accrual.

- **Scratch → Working**: triage with promotion. The user decides this accrued object deserves active engagement. The object moves from accrued to curated, remaining unstable.
- **Scratch → Reference**: triage with filing. The user decides this accrued object is already stable and worth keeping. The object moves from accrued/unstable to curated/stable.
- **Scratch → (discard)**: triage with rejection. The user decides this accrued object is not worth keeping.
- **Working → Log**: completion. The user finishes engaging with a curated object and it settles into the historical record. The object moves from curated/unstable to accrued/stable.
- **Working → Reference**: settling. The curated object stabilizes into something worth consulting indefinitely. It remains curated but becomes stable.

The register is mutable. It can be set explicitly by the user or inferred by the system based on the signals above.

---

## Part V: Relations

### The Fundamental Primitive

The system has one relational primitive: a **directed edge** between two typed nodes. Direction is fundamental — "A → B" is not the same assertion as "B → A." The arrow encodes asymmetry: the source bears on the target. The source is the active party, the asserter, the thing that points. The target is what is pointed at, organized under, derived from, or acted upon.

The system stores one edge per relation, in a canonical direction. The edge can be traversed from either end. When traversed from the target's side, the relation reads in reverse — "task → topic" reads as "belongs-to" from the task and "contains" from the topic, but it is the same edge.

### Relation Semantics Derive from the Model

Relation types are not an independent taxonomy. They are patterns that arise from other parts of the model — primarily the type system and the operation system.

#### Four Families from the Type System

The axis coordinates of the source and target nodes predict four relation families. These are synchronic — they describe the current structure of the graph based on what the connected nodes *are*.

**When the target is a Topic** (synchronic, sovereign, structured), the relation is **structural containment**. Bearing on a topic means belonging to it, being organized under it. Any object can bear on a topic. Topics can bear on other topics, producing hierarchy. This is the mechanism by which Topic fulfills its role as the organizational backbone.

**When the target is a Contact** (synchronic, referential, structured), the relation is **agency**. Bearing on a contact means involving that entity — as sender, recipient, participant, delegate, or provider. Agency relations arise whenever an object connects to the referential-structured type. The specific flavor (sent-by, delegated-to, involves) depends on the source type: messages have senders and recipients, events have participants, tasks have delegates.

**When both endpoints are diachronic**, the relation may carry **sequence or co-occurrence**. One diachronic object bearing on another can mean precedence (this comes before that), or temporal containment (this occurs during that). These relations are what it means for time-positioned objects to be related by their positions.

**When a sovereign unstructured object** (note, entry) **bears on any other object**, the relation is **annotation**. The source carries authored content *about* the target. This is what sovereign-unstructured types do — they are commentary, reflection, elaboration. The "about-ness" is the relation.

#### One Family from the Operation System

The fifth relation family does not depend on the types of the endpoints. It depends on *how the graph got to its current state*.

**Derivation** records provenance: this node was created with that node as input. A task derived from an email. A note derived from another note. A subtask derived from a parent task. An entry derived from an earlier entry. A reply derived from the message it replies to.

Derivation is different from the four type-derived families because any node can be derived from any node, regardless of their axis coordinates. A task can be derived from a message (structuredness axis crossing), but a note can also be derived from another note (no axis crossing at all). Derivation is not "what the nodes are" — it is "how one came to exist." The type-derived families are synchronic (they describe current structure). Derivation is diachronic (it describes history).

Derivation connects to the transform system: when a transform crosses an axis (extraction, narration, capture, dispatch, scheduling, distillation), the output is derived-from the input. Transforms are specific patterns of derivation *where axis crossings happen*. But derivation itself is more general — it is the relational trace of any create operation that takes an existing node as input, whether or not an axis is crossed.

### What Direction Encodes

Direction is not arbitrary. It encodes a consistent asymmetry across all five families:

- In structural relations, the arrow points **toward the container**. The part bears on the whole.
- In agency relations, the arrow points **toward the entity**. The object bears on the person involved.
- In temporal relations, the arrow points **forward in time** (for precedence) or **toward the containing event** (for co-occurrence).
- In annotation relations, the arrow points **toward the subject**. The commentary bears on what it comments on.
- In derivation relations, the arrow points **from the output to the source**. The derived object bears on what it was derived from.

The arrow always points from the thing that *depends on* or *refers to* toward the thing that *exists independently*. A task depends on its topic for organizational context; the topic does not depend on the task. A derived object depends on its source for provenance; the source does not depend on its derivatives. This asymmetry is why direction is fundamental and not merely a storage convention.

### Convenience Labels

For practical use, the system assigns conventional names to common relation patterns. These are labels for patterns the model predicts, not independent primitives.

**Structural:** belongs-to (any → topic), with inverse label contains.

**Agency:** from (message → contact), to (message → contact), involves (event → contact), delegated-to (task → contact), sent-by (resource → contact), member-of (contact → contact). All are specializations of "object → referential entity."

**Derivation:** derived-from (any → any), with inverse label generates. reply-to (message → message) is a domain specialization for threaded communication.

**Temporal:** precedes (diachronic → diachronic), with inverse label follows. occurs-during (any → event).

**Annotation:** annotation-of (note or entry → any), with inverse label annotated-by.

**Generic:** references (any → any) for directed associations where no derived family applies — the source points to the target, but the connection is neither structural, agentive, temporal, annotative, nor provenance-based. related-to (any ↔ any) as a symmetric catch-all.

**Domain-specific:** blocks (task → task, with inverse blocked-by) is a project management convention for dependency ordering. It is not derived from the model but is useful enough to include as a standard extension. The taxonomy is open to further domain-specific additions.

---

## Part VI: Operations

### Where Operations Come From

The model so far describes static structure: types, registers, relations. Operations are what changes the graph — how nodes and edges come into existence, change, are found, and are removed.

Operations derive from two sources within the model.

**The graph itself** entails a lifecycle for its two primitives. The model is a graph: objects are nodes, relations are directed edges between nodes. Both nodes and edges must be created, queried, modified, and removed. This produces eight generic lifecycle operations — four for nodes (objects) and four for edges (relations). These operations are the same regardless of type, register, or axis values; the axes modulate their *behavior*, not their *existence*.

**The sovereignty axis** entails two boundary-crossing operations. If there is a boundary between what the PIM controls (sovereign) and what it does not (referential), then there must be operations that move information across that boundary: inward (capture) and outward (dispatch). No other axis generates boundary operations — structuredness and diachrony describe properties of objects, not crossings between the system and the world.

Ten operations total: eight lifecycle, two boundary.

### Boundary Operations

**Capture** (referential → sovereign)

Information crosses the sovereignty boundary inward. Capture is pre-create: the input may need decomposition before it becomes typed objects and relations. A single email might yield a message, two contacts, three events, and two tasks. A voice memo might yield a note and a task.

The output of capture is one or more create-object and create-relation operations.

**Dispatch** (sovereign → referential)

Objects or aggregates of objects are pushed outward across the sovereignty boundary. Dispatch may target a single object (send an email, open a URL) or a topic-scoped aggregate (publish a body of work, ship a project).

### Lifecycle Operations on Objects

**Create** — Instantiate a new typed node with attributes. Typically the downstream result of capture, but can be invoked directly.

**Query** — Find and read nodes by type, attributes, or content.

**Update** — Mutate a node's attributes, state, or content.

**Close** — Remove a node from active use. Close is intentionally not called "delete" because permanent deletion is only one outcome. Close encompasses completion (task is done), archival (retained but inactive), cancellation (abandoned), and deletion (permanently removed). Completed and archived objects often transition to the log register rather than disappearing.

### Lifecycle Operations on Relations

**Create** — Link two nodes with a typed relation. Relation-create is the primary mechanism of organization.

**Query** — Traverse the graph from a node along its relations. Relation-query is the primary mechanism of review.

**Update** — Change an existing relation's type or target. Re-file a task to a different topic. Re-assign a delegation.

**Close** — Dissolve a relation. The nodes persist; only the edge is removed.

### How the Axes Modulate Operations

The ten operations are generic — they apply to any node or edge. But the axes predict how each operation *behaves* for different types and registers.

**Sovereignty modulates create and update.** Creating a sovereign object is unconstrained — the user authors it freely. Creating a referential object is constrained — the user records something whose truth exists independently. Updating a sovereign object is unconstrained — rewrite at will. Updating a referential object must track external reality. Some referential objects are immutable once they cross the sovereignty boundary (a sent message's body cannot be changed, because it became part of a shared record).

**Structuredness modulates query.** Querying structured objects operates on fields — status, date, priority, exact attribute match. Querying unstructured objects operates on content — full-text search, semantic similarity, reading and interpretation. The structured/unstructured distinction is the difference between "find all tasks due this week" and "search notes about the quarterly review."

**Diachrony modulates close and query.** Closing a diachronic object often means completing a process (a task is done, a message thread is resolved). Closing a synchronic object often means archiving a state (a note is filed, a topic is retired). Querying diachronic objects often involves time ranges and sequence ("messages from last week," "events tomorrow"). Querying synchronic objects often involves content and structure ("notes about X," "contacts at company Y").

**Registers modulate which operations are relevant.** Scratch objects primarily need triage (query + close or query + update to change register). Working objects primarily need update and relation-create (active engagement). Reference objects primarily need query (lookup). Log objects primarily need query by time range (review). The register doesn't change what operations are *available*, but it changes what operations are *expected*.

### Operations and the Essay's Five Verbs

The essay describes five user-facing verbs. They map to these ten operations as convenient groupings:

| Essay Verb | Operations |
|---|---|
| Capture | boundary: capture (decomposition into creates) |
| Retrieve | object: query |
| Organize | relation: create, update, close |
| Review | relation: query |
| Dispatch | boundary: dispatch |

---

## Part VII: Transforms

Beyond the ten operations, the system supports *transforms* — workflows that move information from one region of the type table to another. Transforms are not primitive operations. They are composed of captures, creates, queries, and dispatches. But they are frequent and important enough to name.

Every transform is a crossing of one of the three type-generating axes. Each axis has two directions of crossing, producing six fundamental transforms.

### Structuredness Axis

**Extraction** (unstructured → structured): Read a body of content, derive records from it. A message yields tasks, events, contacts. Meeting notes yield action items. Extraction fans out — one unstructured input typically produces multiple structured outputs.

**Narration** (structured → unstructured): Synthesize records into prose. A set of tasks becomes a status report. A project's accumulated records become an executive summary. Narration fans in — multiple structured inputs consolidate into one unstructured output.

### Sovereignty Axis

**Capture** (referential → sovereign): Information crosses the sovereignty boundary inward. A received email becomes nodes in the graph. Capture fans out — raw referential input typically decomposes into multiple sovereign objects and relations.

Capture is both a boundary operation and a transform. As a boundary operation, it is the mechanism of ingestion. As a transform, it is the axis crossing from referential to sovereign.

**Dispatch** (sovereign → referential): Information crosses the sovereignty boundary outward. Send an email. Publish a document. Ship a project. Dispatch can fan in — a topic-scoped dispatch aggregates everything under a project into a single outward push.

Similarly, dispatch is both a boundary operation and a sovereignty-axis transform.

### Diachrony Axis

**Distillation** (diachronic → synchronic): Extract the timeless from the time-bound. A series of journal entries becomes an evergreen note. A resolved message thread becomes a resource document. A quarter of completed tasks becomes a lessons-learned reference. Distillation fans in, and its defining characteristic is the removal of diachronic anchoring — the output exists as a state, not as a process, even though it was produced from processes.

**Scheduling** (synchronic → diachronic): The reverse crossing does not produce a genuine transform. When you "schedule" a note as a meeting or add a deadline to a topic, you are typically creating a new diachronic object (an event, a task) and linking it to the synchronic source — not transforming the source itself. A note that inspires a meeting remains a note; the meeting is a new event derived from it. This is create + derivation, not an axis crossing.

The diachrony axis is asymmetric, and the asymmetry is informative. Distillation is lossy compression: it summarizes a sequence of episodes into a timeless artifact, discarding the sequential positioning while preserving the substance. There is no inverse of lossy compression. You can always summarize history into a snapshot, but you cannot inflate a snapshot into a history — a process requires *having actually happened*, and you cannot fabricate that from a state.

This asymmetry does not exist on the other two axes. Structuredness is symmetric: extraction adds structure (unstructured → structured), narration removes it (structured → unstructured), and both are genuine transforms. Sovereignty is symmetric: capture claims authority (referential → sovereign), dispatch relinquishes it (sovereign → referential), and both are genuine transforms. But diachrony is one-directional: you can compress process into state, but not expand state into process. Five genuine transforms, not six.

### Composition

Transforms compose. Real-world workflows typically involve multiple axis crossings:

- **Capture + Extraction** (referential → sovereign, unstructured → structured): receive an email and pull tasks from it.
- **Narration + Dispatch** (structured → unstructured, sovereign → referential): write a status report from your task list and send it.
- **Distillation + Narration** (diachronic → synchronic, structured → unstructured): turn a quarter of completed tasks and meeting records into a project retrospective.
- **Capture + Distillation** (referential → sovereign, diachronic → synchronic): ingest a year of email threads with a client and produce a relationship summary.

### Fan-out and Fan-in

The transforms have a characteristic asymmetry:

| Axis | Fan-out direction | Fan-in direction |
|---|---|---|
| Structuredness | Extraction (one document → many records) | Narration (many records → one document) |
| Sovereignty | Capture (one input → many sovereign objects) | Dispatch (one topic → one shipment) |
| Diachrony | — (typically one-to-one) | Distillation (many entries → one note) |

Fan-out creates nodes. Fan-in creates content. The system breathes — inhaling structure from unstructured input, exhaling narrative from accumulated structure.


