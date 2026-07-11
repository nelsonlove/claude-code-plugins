> **Experimental / optional.** Reference infrastructure for a mobile client — *not* part of
> the core plugin. Real push needs Apple Developer credentials + an iOS app; the bridge ships
> with the APNs step stubbed. The core approval loop (skill, hook, resume) works without any of this.

# iOS client — build guide

A companion to [architecture.md](architecture.md). The iOS app is a client of
`pickle serve`. Answering on it writes a response file that ripples to Obsidian and
resumes the agent — the app itself only lists and answers requests.

## Two tiers of "realtime"

1. **Foreground:** the app holds a WebSocket to `/api/v1/stream` and updates live. On every
   launch/foreground it **reconciles** via `GET /api/v1/inbox?status=pending` — the inbox is
   truth; the socket is just a nudge.
2. **Background push (optional):** iOS suspends the socket in the background, so for a real
   "your phone buzzes when a request lands" you need **APNs**, which `pickle serve` doesn't
   speak. Bridge it.

You can ship tier 1 alone (works, just no background alerts) and add tier 2 later.

## The APNs bridge

A tiny always-on service next to `pickle serve` (same host, supervised by launchd or a Tickle
`manual`/interval job). It turns Pickle events into Apple pushes.

```
                     POST /register {device_token}
   ┌────────────┐   ◄───────────────────────────────   ┌──────────┐
   │  iOS app   │                                        │          │
   └─────┬──────┘                                        │ apns-    │
         │ APNs token (didRegisterForRemoteNotifications)│ bridge   │
         ▼                                                │ (daemon) │
   ┌──────────┐   push   ┌──────┐   HTTP/2 + JWT(ES256)  │  token   │
   │  iPhone  │ ◄─────────│ APNs │ ◄─────────────────────│  store   │
   └──────────┘           └──────┘                        └────▲─────┘
                                          WS /api/v1/stream     │
                                     request.created  ┌─────────┴───┐
                                     ─────────────────▶│ pickle serve│
                                                       └─────────────┘
```

**Loop:**
1. Subscribe to `wss://<host>:8787/api/v1/stream` (server-side, persistent — no iOS backgrounding).
2. On `request.created` for a watched collection, **dedup on `request_id`** (WS may re-emit;
   event ids are not a stable cursor — see architecture.md §7).
3. Get title/message from the event payload (or `GET /api/v1/requests/{id}`).
4. Build the APNs payload and send to each registered device token over HTTP/2 to
   `api.push.apple.com` (or `api.sandbox.push.apple.com`), authenticated with a **provider JWT**
   (ES256, signed with your `.p8` AuthKey; header `kid`=Key ID, claim `iss`=Team ID; `apns-topic`
   = bundle id). Refresh the JWT ~hourly.
5. On APNs `410 Gone`, drop that device token from the store.

**APNs payload:**
```json
{
  "aps": { "alert": { "title": "<request.title>", "body": "<request.message>" }, "sound": "default" },
  "request_id": "<id>", "collection": "<name>"
}
```
Tapping deep-links into the app, which fetches `GET /api/v1/requests/{id}` and shows the form.

**Bridge config / secrets:**
- APNs: `.p8` AuthKey, Key ID, Team ID, bundle id.
- Pickle: server URL + token (from `pickle token`), and which collections to notify on.
- A device-token store (a JSON file or SQLite).

**Registration endpoint** (on the bridge, reached over Tailscale):
`POST /register { "device_token": "...", "collection": "..." }` — called after the app receives
its APNs token. Store per-device; support multiple devices.

Reference libs: `apns2`/`node-apn` (Node), `apns` (Swift/Vapor), or the `a2` crate (Rust).
Push is **best-effort**; the app's reconcile-on-launch covers anything missed while the bridge
or app was down.

## Swift data models (mapped from the schema)

Decode with an ISO-8601 date strategy that allows fractional seconds (Pickle emits e.g.
`2026-07-03T15:07:36.081891Z`).

```swift
import Foundation

// MARK: Request
struct PickleRequest: Codable, Identifiable {
    let id: String
    let title: String
    let source: String?
    let message: String
    let body: String?
    let kind: Kind
    let priority: Priority
    let state: State                       // derived: pending | answered | conflict | cancelled
    let responseType: String
    let responseTypeDefinition: TypeDefinition?
    let attachments: [Attachment]
    let links: [String]?
    let metadata: [String: JSONValue]?     // our join fields (workflow/session_id/…) live here; opaque
    let tags: [String]?
    let responseCount: Int?
    let createdAt: Date
    let updatedAt: Date?

    enum Kind: String, Codable { case approval, choice, input, notice, message }
    enum Priority: String, Codable { case low, normal, high, urgent }
    enum State: String, Codable { case pending, answered, conflict, cancelled }

    enum CodingKeys: String, CodingKey {
        case id, title, source, message, body, kind, priority, state, attachments, links, metadata, tags
        case responseType = "response_type"
        case responseTypeDefinition = "response_type_definition"
        case responseCount = "response_count"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

// MARK: Type definition — drives the answer form
struct TypeDefinition: Codable {
    let name: String
    let description: String?
    let displayNameKey: String?
    let fields: [String: Field]
    enum CodingKeys: String, CodingKey {
        case name, description, fields
        case displayNameKey = "display_name_key"
    }
}
struct Field: Codable {
    let type: String            // string | enum | bool | list | object | link | datetime
    let required: Bool?
    let values: [String]?       // enum options
    let description: String?
    let generated: String?      // ulid | now  (skip in the form)
    let target: String?         // link target type
}

// MARK: Answer you POST
struct SubmitResponse: Codable {
    var decision: String?       // approve | reject | revise (approval type)
    var comment: String?
    var responder: String? = "ios"
}

// MARK: Attachment
struct Attachment: Codable, Identifiable {
    let id: String
    let filename: String
    let path: String?
    let mime: String?
    let size: Int?
}

// MARK: Events / stream
struct EventsResponse: Codable { let events: [Event] }
struct Event: Codable {
    let id: Int
    let eventType: String       // request.created | request.answered
    let requestId: String
    let payload: JSONValue?
    let createdAt: Date
    enum CodingKeys: String, CodingKey {
        case id, payload
        case eventType = "type"
        case requestId = "request_id"
        case createdAt = "created_at"
    }
}

// MARK: Envelopes
struct InboxResponse: Codable { let requests: [PickleRequest] }
struct CollectionsResponse: Codable { let collections: [PickleCollection] }
struct PickleCollection: Codable, Identifiable {
    var id: String { name }
    let name: String
    let path: String?
}

// MARK: Arbitrary JSON (for metadata / event payload)
enum JSONValue: Codable {
    case string(String), number(Double), bool(Bool), object([String: JSONValue]), array([JSONValue]), null
    init(from d: Decoder) throws {
        let c = try d.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let v = try? c.decode(Bool.self) { self = .bool(v) }
        else if let v = try? c.decode(Double.self) { self = .number(v) }
        else if let v = try? c.decode(String.self) { self = .string(v) }
        else if let v = try? c.decode([String: JSONValue].self) { self = .object(v) }
        else if let v = try? c.decode([JSONValue].self) { self = .array(v) }
        else { self = .null }
    }
    func encode(to e: Encoder) throws {
        var c = e.singleValueContainer()
        switch self {
        case .string(let v): try c.encode(v); case .number(let v): try c.encode(v)
        case .bool(let v): try c.encode(v); case .object(let v): try c.encode(v)
        case .array(let v): try c.encode(v); case .null: try c.encodeNil()
        }
    }
}
```

## API client sketch

```swift
struct PickleClient {
    let baseURL: URL            // https://<tailscale-host>:8787
    let token: String
    var collection: String?     // nil => server default

    private func req(_ path: String, _ method: String = "GET", _ body: Data? = nil) -> URLRequest {
        var r = URLRequest(url: baseURL.appendingPathComponent(path))
        r.httpMethod = method
        r.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")   // or X-Pickle-Token
        if let c = collection { r.setValue(c, forHTTPHeaderField: "X-Pickle-Collection") }
        if let body { r.httpBody = body; r.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        return r
    }

    private var decoder: JSONDecoder {
        let d = JSONDecoder()
        let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        d.dateDecodingStrategy = .custom { dec in
            let s = try dec.singleValueContainer().decode(String.self)
            if let dt = f.date(from: s) { return dt }
            f.formatOptions = [.withInternetDateTime]                 // fall back: no fractional
            guard let dt = f.date(from: s) else { throw DecodingError.dataCorrupted(.init(codingPath: [], debugDescription: "bad date \(s)")) }
            return dt
        }
        return d
    }

    func collections() async throws -> [PickleCollection] { /* GET /api/v1/collections */ }
    func inbox(status: String = "pending") async throws -> [PickleRequest] { /* GET /api/v1/inbox?status= */ }
    func request(_ id: String) async throws -> PickleRequest { /* GET /api/v1/requests/{id} */ }
    func answer(_ id: String, _ r: SubmitResponse) async throws {
        _ = try await URLSession.shared.data(for: req("/api/v1/requests/\(id)/responses", "POST", try JSONEncoder().encode(r)))
    }
    // stream: URLSessionWebSocketTask against /api/v1/stream with the same Authorization header
}
```

## Answer flow

1. `inbox(status: "pending")` → list.
2. Open a request → render its form from `responseTypeDefinition.fields` (an `enum` field like
   `decision` → segmented control of `values`; a `string` `comment` → text field; skip
   `generated` fields).
3. `answer(id, SubmitResponse(decision: "approve", comment: …))` → POST.
4. The server writes the response file → Obsidian reflects it and the agent resumes. Done.

## Checklist / gotchas

- **Tailscale only** for the base URL; never hit a public interface. Token required.
- **Dedup on `request_id` + `state`**, not the event `id` (unstable cursor).
- **Conflict state** exists (two answers) — show it; don't hide it.
- **Reconcile on launch** via `/inbox` — push is best-effort.
- Attachments: `GET /api/v1/requests/{id}/attachments/{attachmentId}` → bytes; render inline.

## Free push without Apple's $99 (ntfy)

Native APNs needs the paid Apple Developer Program. To skip it, use **ntfy**: the
`apns-bridge` can POST to an ntfy topic (free iOS app) with **Approve/Reject buttons** that
POST straight to `pickle serve` — a full phone approve/reject loop with no Apple account and
no custom app. Self-host ntfy on your Tailscale box for privacy. See `../apns-bridge/README.md`.
