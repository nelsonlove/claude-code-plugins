## Onboarding

The system cannot start cold. Before the PIM is operational, the agent must learn the user's existing tool landscape and organizational structure, configure adapters, and seed the graph with existing data.

Onboarding produces a **profile** — a persistent configuration file at `~/.pim/profile.json` that captures what the agent learned about the user's setup. The profile is injected into the interpreter's prompt alongside the adapter registry, so every session starts with full context about the user's tools, workflows, and conventions.

### Conversational Interview

The transparency principle applies fully during onboarding. The agent never explains the ontology. It asks about tools and habits, listens, and infers the mapping internally.

The interview proceeds through four phases. Each phase is shown with example dialogue — what the agent asks, what a user might say, and what the agent says back (not what it infers internally).

**Phase 1: Tool inventory.**

> **Agent:** "Let's get you set up. What apps do you use day to day for managing your work and life? Things like note-taking, task management, email, calendar — whatever you've got."
>
> **User:** "I use OmniFocus for tasks, Obsidian for notes, Apple Calendar, and my email is through Fastmail."
>
> **Agent:** "Great. Do you keep a journal or daily log? And where do you save things like articles or bookmarks?"
>
> **User:** "I use Day One for journaling. Bookmarks just go in Safari's reading list, I don't have a system for that."
>
> **Agent:** "That's fine — I can work with Safari's reading list. And contacts — just the built-in Apple Contacts?"
>
> **User:** "Yeah."

Internally, the agent maps: OmniFocus → task + topic, Obsidian → note, Apple Calendar → event, Fastmail (via Himalaya or similar) → message, Day One → entry, Safari → resource, Apple Contacts → contact. The user hears none of this.

**Phase 2: Workflow discovery.**

> **Agent:** "When something pops into your head — a quick thought, a reminder, something to deal with later — where does it usually land?"
>
> **User:** "OmniFocus inbox, mostly. Sometimes I'll put a quick note in Obsidian's daily note."
>
> **Agent:** "And when you sit down to really work on something — developing an idea, planning a project — where does that happen?"
>
> **User:** "Obsidian for thinking and writing. OmniFocus for planning the actual tasks."
>
> **Agent:** "Do you have a place for things that are just... settled? Like your Wi-Fi password, your kids' school address, account numbers?"
>
> **User:** "Some of that's in Apple Notes, actually. I forgot to mention that."
>
> **Agent:** "No problem — I'll use Apple Notes for that kind of stable reference material. Last question on this: when you finish a project or complete a bunch of tasks, what happens? Do they just disappear, or do you keep a record?"
>
> **User:** "OmniFocus keeps completed tasks. Day One is sort of my record of what happened."

Internally: OmniFocus inbox → scratch register for tasks. Obsidian daily note → scratch for notes. Obsidian vault → working for notes. Apple Notes → reference register for notes (register-aware routing — Obsidian for working, Apple Notes for reference). OmniFocus completed → log. Day One → log.

**Phase 3: Organizational structure.**

> **Agent:** "How do you organize your projects? In OmniFocus, do you use folders, or is it a flat list?"
>
> **User:** "I have folders for each area — Work, Personal, HarborView. Projects live inside those."
>
> **Agent:** "Do you use a numbering system, or just names?"
>
> **User:** "I use Johnny Decimal. 10-19 is work, 20-29 personal, 30-39 is HarborView stuff."
>
> **Agent:** "Nice. And in Obsidian — same structure, or different?"
>
> **User:** "Similar folders but not as strict. I've been meaning to align them."
>
> **Agent:** "I can help with that. I'll treat your JD numbers as the organizational backbone and link things across your tools using that structure."

Internally: JD system maps to topic hierarchy with taxonomy_ids. OmniFocus folders → topics. Obsidian folder structure → topics. The agent will propose alignment during initial import.

**Phase 4: Relationship patterns.**

> **Agent:** "When you get an email that needs action, what do you do with it?"
>
> **User:** "I usually just flag it and add a task in OmniFocus manually. It's annoying."
>
> **Agent:** "That's exactly the kind of thing I can automate — pull tasks straight from your email and link them back to the original message. How about meetings? Do you take notes?"
>
> **User:** "Yeah, in Day One usually. Sometimes in Obsidian if it's for a specific project."
>
> **Agent:** "Got it. I'll connect your meeting notes to the calendar event and the project they're about, so you can always trace back. One more — do you track who assigned you a task, or who you're waiting on?"
>
> **User:** "Not really, but I should."
>
> **Agent:** "I'll start tracking that automatically when I process your email. You'll be able to ask things like 'what am I waiting on from Sarah?' without having to maintain it yourself."

Internally: email → task extraction is a capture + extraction workflow. Meeting → Day One entry is an event → entry derivation. Delegation tracking is agency relations (task → delegated-to → contact). The user hears concrete benefits, not ontology.

### Profile Structure

The interview produces a profile that captures the user's setup in a form the agent can use:

```json
{
  "tools": {
    "omnifocus": {
      "types": ["task", "topic"],
      "registers": {
        "scratch": "OmniFocus inbox",
        "working": "active projects and flagged tasks",
        "log": "completed tasks"
      },
      "notes": "User calls projects 'matters' in a legal context"
    },
    "obsidian": {
      "types": ["note"],
      "registers": {
        "working": "linked notes in the vault",
        "reference": "stable reference docs in the vault"
      },
      "notes": "JD structure: 10-19 work, 20-29 personal, 30-39 HarborView"
    },
    "apple-calendar": {
      "types": ["event"],
      "registers": {
        "working": "upcoming events",
        "log": "past events"
      }
    },
    "himalaya": {
      "types": ["message"],
      "registers": {
        "scratch": "unread inbox",
        "working": "flagged threads",
        "log": "sent and archived"
      }
    },
    "dayone": {
      "types": ["entry"],
      "registers": {
        "log": "journal entries"
      }
    }
  },
  "topic_hierarchy": {
    "system": "johnny_decimal",
    "areas": [
      {"range": "10-19", "name": "Work"},
      {"range": "20-29", "name": "Personal"},
      {"range": "30-39", "name": "HarborView"}
    ]
  },
  "conventions": {
    "task_contexts": ["@computer", "@phone", "@errands", "@home"],
    "contact_identification": "primarily by first name + company",
    "capture_default": "OmniFocus inbox for tasks, Obsidian daily note for thoughts"
  },
  "workflow_patterns": [
    "Email → extract tasks into OmniFocus",
    "Meetings → journal entry in Day One + action items in OmniFocus",
    "Weekly review: process OmniFocus inbox, review flagged items, check stalled projects"
  ]
}
```

The profile is human-readable — the user can review and correct what the agent learned. It is also machine-readable — the agent consults it to route captures, interpret ambiguous requests ("add this to my projects" → create a topic in OmniFocus), and speak the user's language ("matter" not "topic" if that's the user's term).

### Initial Import

After the interview and adapter configuration, the agent performs an initial sync:

1. **Enumerate** all existing objects from each adapter. This is the largest single operation the system will perform — potentially thousands of nodes from email, hundreds from task managers, etc.

2. **Build the topic hierarchy** from existing organizational structures. OmniFocus projects and folders become topics. Obsidian folder structure becomes topics. JD numbers become taxonomy IDs. The agent proposes the hierarchy and the user confirms before committing.

3. **Run identity resolution across adapters.** This is the riskiest moment in the system's life. The same person appears as a contact, as an email sender, as a calendar participant, and as a name mentioned in notes. Every merge decision propagates through every relation. The system should:
   - Start with deterministic matches only (email addresses, phone numbers)
   - Present ambiguous candidates to the user in batches rather than resolving autonomously
   - Err strongly toward false negatives (creating duplicates) over false merges
   - Log every resolution decision for later review

4. **Run relation discovery** on the initial import to surface cross-tool connections. A task in OmniFocus and a message in email that refer to the same project should be linked via the topic, but the adapter for each tool doesn't know about the other. Discovery proposes these edges.

5. **Present a summary** to the user. "I found 2,400 messages, 340 tasks, 85 topics, 120 contacts, 45 notes, and 30 events. I've linked them into a graph with 1,800 relations. Here are 15 ambiguous identity matches I'd like you to review."

### Profile Evolution

The profile is not static. As the user works with the system, the agent updates it:

- New tools are added (user starts using a new app)
- Workflow patterns change (user stops doing weekly reviews, starts doing daily ones)
- Naming conventions evolve (user adopts a new JD category)
- Register assignments shift (a tool that was scratch becomes working)

Profile updates are low-risk write operations — they change how the agent interprets future requests, not the graph itself.

