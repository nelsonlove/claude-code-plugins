import { useState } from "react";

const FONT = "'Iowan Old Style', 'Palatino Linotype', Palatino, Georgia, serif";
const MONO = "'IBM Plex Mono', 'SF Mono', 'Fira Code', monospace";
const SAND = "#f5f0e8";
const INK = "#2a2520";
const FADED = "#8a8078";
const RULE = "#d4cdc4";
const ACCENT = "#c4553a";

const typeColors = {
  Note: "#5a7a6a",
  Entry: "#6a8a7a",
  Task: "#c4553a",
  Event: "#d4854a",
  Message: "#7a6a5a",
  Contact: "#8a6a8a",
  Resource: "#5a6a8a",
  Topic: "#a4843a",
};

const registerColors = {
  Scratch: "#c4553a",
  Working: "#d4854a",
  Reference: "#5a7a6a",
  Log: "#7a6a5a",
};

export default function PIMOntologyDiagram() {
  const [view, setView] = useState("types");

  return (
    <div style={{
      fontFamily: FONT,
      background: SAND,
      color: INK,
      minHeight: "100vh",
      padding: "40px 24px",
      boxSizing: "border-box",
    }}>
      <div style={{ maxWidth: 900, margin: "0 auto" }}>
        <h1 style={{
          fontSize: 28,
          fontWeight: 400,
          letterSpacing: "0.04em",
          margin: "0 0 4px",
          fontVariant: "small-caps",
        }}>
          the pim matrix
        </h1>
        <p style={{ color: FADED, fontSize: 14, margin: "0 0 32px", fontFamily: MONO, letterSpacing: "0.02em" }}>
          ontology diagram
        </p>

        <nav style={{ display: "flex", gap: 0, marginBottom: 40, borderBottom: `1px solid ${RULE}` }}>
          {[
            ["types", "Type Table"],
            ["registers", "Registers"],
            ["relations", "Relations"],
            ["transforms", "Transforms"],
            ["full", "Full Model"],
          ].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setView(key)}
              style={{
                fontFamily: MONO,
                fontSize: 12,
                letterSpacing: "0.03em",
                padding: "10px 20px",
                background: view === key ? INK : "transparent",
                color: view === key ? SAND : FADED,
                border: "none",
                cursor: "pointer",
                transition: "all 0.2s",
              }}
            >
              {label}
            </button>
          ))}
        </nav>

        {view === "types" && <TypeTable />}
        {view === "registers" && <RegisterTable />}
        {view === "relations" && <RelationDiagram />}
        {view === "transforms" && <TransformDiagram />}
        {view === "full" && <FullModel />}
      </div>
    </div>
  );
}

function TypeTable() {
  const types = [
    { name: "Message", d: "diachronic", s: "referential", st: "unstructured", desc: "emails, texts, chats", icon: "✉" },
    { name: "Event", d: "diachronic", s: "referential", st: "structured", desc: "meetings, appointments", icon: "▸" },
    { name: "Entry", d: "diachronic", s: "sovereign", st: "unstructured", desc: "journals, meeting notes", icon: "◷" },
    { name: "Task", d: "diachronic", s: "sovereign", st: "structured", desc: "to-dos, action items", icon: "◉" },
    { name: "Resource", d: "synchronic", s: "referential", st: "unstructured", desc: "bookmarks, files, PDFs", icon: "⇗" },
    { name: "Contact", d: "synchronic", s: "referential", st: "structured", desc: "people, organizations", icon: "⦿" },
    { name: "Note", d: "synchronic", s: "sovereign", st: "unstructured", desc: "working ideas, documents", icon: "✎" },
    { name: "Topic", d: "synchronic", s: "sovereign", st: "structured", desc: "projects, areas, tags", icon: "◈" },
  ];

  return (
    <div>
      <SectionHead title="The Type Table" subtitle="Three axes × two values each = eight types" />

      <div style={{ display: "flex", gap: 32, marginBottom: 40, flexWrap: "wrap" }}>
        {[
          ["Diachrony", "diachronic / synchronic", "Does it exist as a process or a state?"],
          ["Sovereignty", "sovereign / referential", "Is the user the sole authority on its truth?"],
          ["Structuredness", "structured / unstructured", "Is it fully described by its fields?"],
        ].map(([name, vals, q]) => (
          <div key={name} style={{ flex: "1 1 240px" }}>
            <div style={{ fontFamily: MONO, fontSize: 11, color: ACCENT, letterSpacing: "0.05em", marginBottom: 4 }}>
              {name.toUpperCase()}
            </div>
            <div style={{ fontSize: 13, color: FADED, marginBottom: 2 }}>{vals}</div>
            <div style={{ fontSize: 13, fontStyle: "italic" }}>{q}</div>
          </div>
        ))}
      </div>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
          <thead>
            <tr>
              <th style={thStyle}></th>
              <th style={{ ...thStyle, textAlign: "center" }} colSpan={2}>Unstructured</th>
              <th style={{ ...thStyle, textAlign: "center" }} colSpan={2}>Structured</th>
            </tr>
            <tr>
              <th style={thStyle}></th>
              <th style={{ ...thStyle, fontWeight: 400, color: FADED, fontSize: 11, textAlign: "center" }}>referential</th>
              <th style={{ ...thStyle, fontWeight: 400, color: FADED, fontSize: 11, textAlign: "center" }}>sovereign</th>
              <th style={{ ...thStyle, fontWeight: 400, color: FADED, fontSize: 11, textAlign: "center" }}>referential</th>
              <th style={{ ...thStyle, fontWeight: 400, color: FADED, fontSize: 11, textAlign: "center" }}>sovereign</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={{ ...tdStyle, fontFamily: MONO, fontSize: 11, color: FADED, verticalAlign: "top", paddingTop: 16 }}>
                DIACHRONIC
              </td>
              {["Message", "Entry", "Event", "Task"].map(name => {
                const t = types.find(x => x.name === name);
                return <TypeCell key={name} t={t} />;
              })}
            </tr>
            <tr>
              <td style={{ ...tdStyle, fontFamily: MONO, fontSize: 11, color: FADED, verticalAlign: "top", paddingTop: 16 }}>
                SYNCHRONIC
              </td>
              {["Resource", "Note", "Contact", "Topic"].map(name => {
                const t = types.find(x => x.name === name);
                return <TypeCell key={name} t={t} />;
              })}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TypeCell({ t }) {
  return (
    <td style={{
      ...tdStyle,
      textAlign: "center",
      padding: "12px 8px",
      verticalAlign: "top",
    }}>
      <div style={{
        display: "inline-flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "16px 12px",
        borderRadius: 4,
        background: `${typeColors[t.name]}11`,
        border: `1px solid ${typeColors[t.name]}33`,
        minWidth: 120,
      }}>
        <span style={{ fontSize: 24, marginBottom: 6 }}>{t.icon}</span>
        <span style={{ fontWeight: 600, fontSize: 15, color: typeColors[t.name], marginBottom: 4 }}>{t.name}</span>
        <span style={{ fontSize: 11, color: FADED }}>{t.desc}</span>
      </div>
    </td>
  );
}

function RegisterTable() {
  return (
    <div>
      <SectionHead title="The Register Table" subtitle="Two axes × two values each = four registers" />

      <div style={{ display: "flex", gap: 32, marginBottom: 40, flexWrap: "wrap" }}>
        {[
          ["Stability", "stable / unstable", "Does it change once it's here?"],
          ["Intentionality", "curated / accrued", "Did the user deliberately place it?"],
        ].map(([name, vals, q]) => (
          <div key={name} style={{ flex: "1 1 300px" }}>
            <div style={{ fontFamily: MONO, fontSize: 11, color: ACCENT, letterSpacing: "0.05em", marginBottom: 4 }}>
              {name.toUpperCase()}
            </div>
            <div style={{ fontSize: 13, color: FADED, marginBottom: 2 }}>{vals}</div>
            <div style={{ fontSize: 13, fontStyle: "italic" }}>{q}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "auto 1fr 1fr", gap: 0, maxWidth: 700 }}>
        <div style={gridHeader}></div>
        <div style={{ ...gridHeader, textAlign: "center" }}>Accrued</div>
        <div style={{ ...gridHeader, textAlign: "center" }}>Curated</div>

        <div style={{ ...gridLabel }}>UNSTABLE</div>
        <RegisterCell name="Scratch" desc="inbox" detail="surface by recency" icon="↓" color={registerColors.Scratch}
          attention="surface proactively" navigation="navigate by recency" />
        <RegisterCell name="Working" desc="workbench" detail="surface by structure" icon="⚒" color={registerColors.Working}
          attention="surface proactively" navigation="navigate by structure" />

        <div style={{ ...gridLabel }}>STABLE</div>
        <RegisterCell name="Log" desc="journal" detail="retrieve by sequence" icon="☰" color={registerColors.Log}
          attention="retrieve on demand" navigation="navigate by sequence" />
        <RegisterCell name="Reference" desc="filing cabinet" detail="retrieve by content" icon="▤" color={registerColors.Reference}
          attention="retrieve on demand" navigation="navigate by content" />
      </div>

      <div style={{ marginTop: 32, padding: 20, background: `${INK}08`, borderRadius: 4 }}>
        <div style={{ fontFamily: MONO, fontSize: 11, color: ACCENT, marginBottom: 8, letterSpacing: "0.05em" }}>
          TRANSITIONS
        </div>
        <div style={{ fontSize: 13, lineHeight: 1.8 }}>
          <span style={{ color: registerColors.Scratch, fontWeight: 600 }}>Scratch</span>
          <span style={{ color: FADED }}> →  triage → </span>
          <span style={{ color: registerColors.Working, fontWeight: 600 }}>Working</span>
          <span style={{ color: FADED }}> →  completion → </span>
          <span style={{ color: registerColors.Log, fontWeight: 600 }}>Log</span>
          <br />
          <span style={{ color: registerColors.Scratch, fontWeight: 600 }}>Scratch</span>
          <span style={{ color: FADED }}> →  filing → </span>
          <span style={{ color: registerColors.Reference, fontWeight: 600 }}>Reference</span>
          <br />
          <span style={{ color: registerColors.Working, fontWeight: 600 }}>Working</span>
          <span style={{ color: FADED }}> →  settling → </span>
          <span style={{ color: registerColors.Reference, fontWeight: 600 }}>Reference</span>
        </div>
      </div>
    </div>
  );
}

function RegisterCell({ name, desc, icon, color, attention, navigation }) {
  return (
    <div style={{
      padding: 20,
      border: `1px solid ${RULE}`,
      margin: -0.5,
      textAlign: "center",
    }}>
      <div style={{ fontSize: 20, marginBottom: 6 }}>{icon}</div>
      <div style={{ fontWeight: 600, color, fontSize: 15, marginBottom: 2 }}>{name}</div>
      <div style={{ fontSize: 12, color: FADED, fontStyle: "italic", marginBottom: 8 }}>{desc}</div>
      <div style={{ fontSize: 11, fontFamily: MONO, color: FADED, lineHeight: 1.6 }}>
        {attention}<br />{navigation}
      </div>
    </div>
  );
}

function RelationDiagram() {
  const families = [
    {
      name: "Structural",
      source: "The graph",
      derived: "target is Topic",
      color: typeColors.Topic,
      labels: ["belongs-to → contains"],
      arrow: "any → Topic",
    },
    {
      name: "Agency",
      source: "The graph",
      derived: "target is Contact",
      color: typeColors.Contact,
      labels: ["from, to, involves, delegated-to, sent-by, member-of"],
      arrow: "any → Contact",
    },
    {
      name: "Temporal",
      source: "The graph",
      derived: "both endpoints diachronic",
      color: "#d4854a",
      labels: ["precedes → follows", "occurs-during"],
      arrow: "diachronic → diachronic",
    },
    {
      name: "Annotation",
      source: "The graph",
      derived: "source is sovereign + unstructured",
      color: typeColors.Note,
      labels: ["annotation-of → annotated-by"],
      arrow: "note|entry → any",
    },
    {
      name: "Derivation",
      source: "Operations",
      derived: "create took existing node as input",
      color: "#8a6a5a",
      labels: ["derived-from → generates", "reply-to"],
      arrow: "any → any (provenance)",
    },
  ];

  return (
    <div>
      <SectionHead title="Relation Families" subtitle="One primitive (directed edge) — five derived families" />

      <div style={{
        padding: 20,
        background: `${INK}08`,
        borderRadius: 4,
        marginBottom: 32,
        textAlign: "center",
      }}>
        <div style={{ fontFamily: MONO, fontSize: 11, color: ACCENT, marginBottom: 8, letterSpacing: "0.05em" }}>
          THE FUNDAMENTAL PRIMITIVE
        </div>
        <div style={{ fontSize: 16 }}>
          <span style={{ fontWeight: 600 }}>A → B</span>
          <span style={{ color: FADED, fontSize: 13, marginLeft: 12 }}>
            "A bears on B" — the source depends on or refers to the target
          </span>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {families.map((f, i) => (
          <div key={f.name} style={{
            display: "grid",
            gridTemplateColumns: "140px 1fr",
            gap: 0,
            padding: "16px 0",
            borderBottom: i < families.length - 1 ? `1px solid ${RULE}` : "none",
          }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 15, color: f.color }}>{f.name}</div>
              <div style={{ fontFamily: MONO, fontSize: 10, color: FADED, marginTop: 2 }}>
                from: {f.source}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 13, marginBottom: 4 }}>
                <span style={{ fontFamily: MONO, fontSize: 11, color: ACCENT }}>when: </span>
                {f.derived}
              </div>
              <div style={{ fontSize: 13, marginBottom: 4 }}>
                <span style={{ fontFamily: MONO, fontSize: 11, color: ACCENT }}>pattern: </span>
                <span style={{ fontFamily: MONO, fontSize: 12 }}>{f.arrow}</span>
              </div>
              <div style={{ fontSize: 12, color: FADED }}>
                {f.labels.join("  ·  ")}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div style={{
        marginTop: 24,
        padding: 16,
        borderLeft: `3px solid ${FADED}`,
        fontSize: 13,
        color: FADED,
      }}>
        <strong style={{ color: INK }}>Four synchronic</strong> families derive from endpoint types (what the nodes <em>are</em>).
        <br />
        <strong style={{ color: INK }}>One diachronic</strong> family derives from operation history (how one node <em>came to exist</em>).
      </div>
    </div>
  );
}

function TransformDiagram() {
  const transforms = [
    { axis: "Structuredness", from: "unstructured", to: "structured", name: "Extraction", desc: "read content → derive records", fan: "fan-out", real: true },
    { axis: "Structuredness", from: "structured", to: "unstructured", name: "Narration", desc: "synthesize records → produce prose", fan: "fan-in", real: true },
    { axis: "Sovereignty", from: "referential", to: "sovereign", name: "Capture", desc: "ingest from world → claim authority", fan: "fan-out", real: true },
    { axis: "Sovereignty", from: "sovereign", to: "referential", name: "Dispatch", desc: "push outward → relinquish authority", fan: "fan-in", real: true },
    { axis: "Diachrony", from: "diachronic", to: "synchronic", name: "Distillation", desc: "compress history → timeless artifact", fan: "fan-in", real: true },
    { axis: "Diachrony", from: "synchronic", to: "diachronic", name: "Scheduling", desc: "not a genuine transform", fan: "—", real: false },
  ];

  return (
    <div>
      <SectionHead title="Transforms" subtitle="Axis crossings — five genuine, one asymmetric" />

      <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
        {transforms.map((t, i) => (
          <div key={t.name} style={{
            display: "grid",
            gridTemplateColumns: "120px 1fr auto",
            alignItems: "center",
            padding: "14px 0",
            borderBottom: i < transforms.length - 1 ? `1px solid ${RULE}` : "none",
            opacity: t.real ? 1 : 0.4,
          }}>
            <div>
              <div style={{ fontFamily: MONO, fontSize: 10, color: ACCENT, letterSpacing: "0.05em" }}>
                {t.axis.toUpperCase()}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 14, marginBottom: 2 }}>
                <span style={{ fontWeight: 600 }}>{t.name}</span>
                {!t.real && <span style={{ fontFamily: MONO, fontSize: 10, color: ACCENT, marginLeft: 8 }}>✕ asymmetric</span>}
              </div>
              <div style={{ fontFamily: MONO, fontSize: 11, color: FADED }}>
                {t.from} → {t.to}
              </div>
              <div style={{ fontSize: 12, color: FADED, marginTop: 2 }}>{t.desc}</div>
            </div>
            <div style={{
              fontFamily: MONO,
              fontSize: 10,
              color: t.fan === "fan-out" ? ACCENT : t.fan === "fan-in" ? typeColors.Note : FADED,
              textAlign: "right",
              minWidth: 60,
            }}>
              {t.fan}
            </div>
          </div>
        ))}
      </div>

      <div style={{
        marginTop: 32,
        padding: 16,
        borderLeft: `3px solid ${ACCENT}`,
        fontSize: 13,
      }}>
        <strong>The diachrony axis is asymmetric.</strong> Distillation is lossy compression of history into summary.
        There is no inverse of lossy compression — you cannot inflate a state into a process.
      </div>

      <div style={{ marginTop: 32 }}>
        <div style={{ fontFamily: MONO, fontSize: 11, color: ACCENT, marginBottom: 12, letterSpacing: "0.05em" }}>
          COMPOSITIONS
        </div>
        {[
          ["Capture + Extraction", "referential → sovereign, unstructured → structured", "receive email → pull tasks"],
          ["Narration + Dispatch", "structured → unstructured, sovereign → referential", "task list → status report → send"],
          ["Distillation + Narration", "diachronic → synchronic, structured → unstructured", "quarter of tasks → retrospective"],
        ].map(([name, axes, example]) => (
          <div key={name} style={{ marginBottom: 12 }}>
            <span style={{ fontWeight: 600, fontSize: 13 }}>{name}</span>
            <span style={{ fontFamily: MONO, fontSize: 11, color: FADED, marginLeft: 8 }}>{axes}</span>
            <div style={{ fontSize: 12, color: FADED, marginTop: 2, fontStyle: "italic" }}>{example}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FullModel() {
  return (
    <div>
      <SectionHead title="Full Model" subtitle="Five axes → types, registers, relations, operations, transforms" />

      <svg viewBox="0 0 800 520" style={{ width: "100%", maxWidth: 800 }}>
        <defs>
          <marker id="arrow" viewBox="0 0 10 7" refX="10" refY="3.5" markerWidth="8" markerHeight="6" orient="auto">
            <path d="M 0 0 L 10 3.5 L 0 7 Z" fill={FADED} />
          </marker>
          <marker id="arrow-accent" viewBox="0 0 10 7" refX="10" refY="3.5" markerWidth="8" markerHeight="6" orient="auto">
            <path d="M 0 0 L 10 3.5 L 0 7 Z" fill={ACCENT} />
          </marker>
        </defs>

        {/* Title */}
        <text x="400" y="28" textAnchor="middle" fontFamily={MONO} fontSize="10" fill={ACCENT} letterSpacing="0.1em">
          THE PIM MATRIX — FULL MODEL
        </text>

        {/* Axes box */}
        <rect x="20" y="44" width="760" height="70" rx="3" fill={`${INK}06`} stroke={RULE} strokeWidth="0.5" />
        <text x="40" y="64" fontFamily={MONO} fontSize="9" fill={ACCENT} letterSpacing="0.08em">GENERATING AXES</text>
        <text x="40" y="82" fontFamily={FONT} fontSize="11" fill={INK}>
          <tspan fontWeight="600">Type:</tspan> diachrony · sovereignty · structuredness
        </text>
        <text x="40" y="100" fontFamily={FONT} fontSize="11" fill={INK}>
          <tspan fontWeight="600">Register:</tspan> stability · intentionality
        </text>

        {/* Types */}
        <rect x="20" y="130" width="370" height="170" rx="3" fill="white" stroke={RULE} strokeWidth="0.5" />
        <text x="40" y="152" fontFamily={MONO} fontSize="9" fill={ACCENT} letterSpacing="0.08em">8 OBJECT TYPES</text>

        {[
          [60, 172, "Message", typeColors.Message],
          [160, 172, "Entry", typeColors.Entry],
          [260, 172, "Event", typeColors.Event],
          [340, 172, "Task", typeColors.Task],
          [60, 208, "Resource", typeColors.Resource],
          [160, 208, "Note", typeColors.Note],
          [260, 208, "Contact", typeColors.Contact],
          [340, 208, "Topic", typeColors.Topic],
        ].map(([x, y, name, color]) => (
          <g key={name}>
            <rect x={x - 30} y={y - 12} width={70} height={24} rx={3} fill={`${color}18`} stroke={`${color}44`} strokeWidth="0.5" />
            <text x={x + 5} y={y + 4} textAnchor="middle" fontFamily={FONT} fontSize="11" fontWeight="600" fill={color}>{name}</text>
          </g>
        ))}
        <text x="40" y="250" fontFamily={MONO} fontSize="8" fill={FADED}>diachronic</text>
        <text x="40" y="286" fontFamily={MONO} fontSize="8" fill={FADED}>synchronic</text>
        <line x1="40" y1="196" x2="380" y2="196" stroke={RULE} strokeWidth="0.5" strokeDasharray="3,3" />
        <text x="125" y="250" fontFamily={MONO} fontSize="8" fill={FADED}>referential</text>
        <text x="125" y="264" fontFamily={MONO} fontSize="8" fill={FADED}>sovereign</text>
        <text x="280" y="250" fontFamily={MONO} fontSize="8" fill={FADED}>referential</text>
        <text x="280" y="264" fontFamily={MONO} fontSize="8" fill={FADED}>sovereign</text>
        <text x="100" y="286" fontFamily={MONO} fontSize="8" fill={FADED}>unstructured</text>
        <text x="300" y="286" fontFamily={MONO} fontSize="8" fill={FADED}>structured</text>

        {/* Registers */}
        <rect x="410" y="130" width="370" height="170" rx="3" fill="white" stroke={RULE} strokeWidth="0.5" />
        <text x="430" y="152" fontFamily={MONO} fontSize="9" fill={ACCENT} letterSpacing="0.08em">4 REGISTERS</text>

        {[
          [480, 185, "Scratch", registerColors.Scratch, "unstable · accrued"],
          [630, 185, "Working", registerColors.Working, "unstable · curated"],
          [480, 230, "Log", registerColors.Log, "stable · accrued"],
          [630, 230, "Reference", registerColors.Reference, "stable · curated"],
        ].map(([x, y, name, color, sub]) => (
          <g key={name}>
            <rect x={x - 50} y={y - 16} width={100} height={38} rx={3} fill={`${color}18`} stroke={`${color}44`} strokeWidth="0.5" />
            <text x={x} y={y + 2} textAnchor="middle" fontFamily={FONT} fontSize="12" fontWeight="600" fill={color}>{name}</text>
            <text x={x} y={y + 14} textAnchor="middle" fontFamily={MONO} fontSize="7" fill={FADED}>{sub}</text>
          </g>
        ))}

        {/* Relations */}
        <rect x="20" y="316" width="370" height="115" rx="3" fill="white" stroke={RULE} strokeWidth="0.5" />
        <text x="40" y="338" fontFamily={MONO} fontSize="9" fill={ACCENT} letterSpacing="0.08em">5 RELATION FAMILIES</text>
        <text x="40" y="355" fontFamily={FONT} fontSize="10" fill={INK}>
          <tspan fontWeight="600" fill={typeColors.Topic}>Structural</tspan> — target is Topic
        </text>
        <text x="40" y="370" fontFamily={FONT} fontSize="10" fill={INK}>
          <tspan fontWeight="600" fill={typeColors.Contact}>Agency</tspan> — target is Contact
        </text>
        <text x="40" y="385" fontFamily={FONT} fontSize="10" fill={INK}>
          <tspan fontWeight="600" fill="#d4854a">Temporal</tspan> — both endpoints diachronic
        </text>
        <text x="40" y="400" fontFamily={FONT} fontSize="10" fill={INK}>
          <tspan fontWeight="600" fill={typeColors.Note}>Annotation</tspan> — source is sovereign + unstructured
        </text>
        <text x="40" y="415" fontFamily={FONT} fontSize="10" fill={INK}>
          <tspan fontWeight="600" fill="#8a6a5a">Derivation</tspan> — from operation history (provenance)
        </text>

        {/* Operations */}
        <rect x="410" y="316" width="370" height="115" rx="3" fill="white" stroke={RULE} strokeWidth="0.5" />
        <text x="430" y="338" fontFamily={MONO} fontSize="9" fill={ACCENT} letterSpacing="0.08em">10 OPERATIONS</text>
        <text x="430" y="358" fontFamily={FONT} fontSize="10" fill={FADED}>
          <tspan fontWeight="600" fill={INK}>Boundary</tspan> (from sovereignty axis):
        </text>
        <text x="430" y="373" fontFamily={MONO} fontSize="10" fill={INK}>capture · dispatch</text>
        <text x="430" y="393" fontFamily={FONT} fontSize="10" fill={FADED}>
          <tspan fontWeight="600" fill={INK}>Lifecycle</tspan> (from the graph):
        </text>
        <text x="430" y="408" fontFamily={MONO} fontSize="10" fill={INK}>create · query · update · close</text>
        <text x="430" y="421" fontFamily={MONO} fontSize="9" fill={FADED}>× objects and relations</text>

        {/* Transforms */}
        <rect x="20" y="447" width="760" height="65" rx="3" fill="white" stroke={RULE} strokeWidth="0.5" />
        <text x="40" y="468" fontFamily={MONO} fontSize="9" fill={ACCENT} letterSpacing="0.08em">5 TRANSFORMS (AXIS CROSSINGS)</text>
        <text x="40" y="488" fontFamily={FONT} fontSize="10" fill={INK}>
          <tspan fontWeight="600">Structuredness:</tspan> extraction ↔ narration
          <tspan dx="24" fontWeight="600">Sovereignty:</tspan> capture ↔ dispatch
          <tspan dx="24" fontWeight="600">Diachrony:</tspan> distillation →
        </text>
        <text x="40" y="503" fontFamily={MONO} fontSize="8" fill={FADED}>
          diachrony is asymmetric: distillation (lossy compression) has no inverse
        </text>

        {/* Connecting arrows */}
        <line x1="205" y1="114" x2="205" y2="130" stroke={FADED} strokeWidth="0.8" markerEnd="url(#arrow)" />
        <line x1="595" y1="114" x2="595" y2="130" stroke={FADED} strokeWidth="0.8" markerEnd="url(#arrow)" />
        <line x1="205" y1="300" x2="205" y2="316" stroke={FADED} strokeWidth="0.8" markerEnd="url(#arrow)" />
        <line x1="595" y1="300" x2="595" y2="316" stroke={FADED} strokeWidth="0.8" markerEnd="url(#arrow)" />
        <line x1="400" y1="431" x2="400" y2="447" stroke={FADED} strokeWidth="0.8" markerEnd="url(#arrow)" />
      </svg>
    </div>
  );
}

function SectionHead({ title, subtitle }) {
  return (
    <div style={{ marginBottom: 28 }}>
      <h2 style={{ fontSize: 22, fontWeight: 400, margin: "0 0 4px", letterSpacing: "0.02em" }}>{title}</h2>
      <p style={{ color: FADED, fontSize: 13, margin: 0, fontFamily: MONO }}>{subtitle}</p>
    </div>
  );
}

const thStyle = {
  fontFamily: MONO,
  fontSize: 11,
  fontWeight: 600,
  color: FADED,
  padding: "8px 12px",
  borderBottom: `1px solid ${RULE}`,
  letterSpacing: "0.03em",
};

const tdStyle = {
  padding: "8px 4px",
  borderBottom: `1px solid ${RULE}`,
};

const gridHeader = {
  fontFamily: MONO,
  fontSize: 11,
  fontWeight: 600,
  color: FADED,
  padding: "8px 12px",
  letterSpacing: "0.03em",
};

const gridLabel = {
  fontFamily: MONO,
  fontSize: 10,
  color: FADED,
  letterSpacing: "0.05em",
  padding: "20px 12px 20px 0",
  display: "flex",
  alignItems: "center",
};
