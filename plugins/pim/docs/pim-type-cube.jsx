import { useState, useRef, useCallback, useEffect } from "react";

const FONT = "'Iowan Old Style', 'Palatino Linotype', Palatino, Georgia, serif";
const MONO = "'IBM Plex Mono', 'SF Mono', 'Fira Code', monospace";
const SAND = "#f5f0e8";
const INK = "#2a2520";
const FADED = "#8a8078";
const ACCENT = "#c4553a";

const types = [
  // [x, y, z] where:
  // x = structuredness: -1 = unstructured, +1 = structured
  // y = diachrony: -1 = synchronic, +1 = diachronic
  // z = sovereignty: -1 = referential, +1 = sovereign
  { name: "Resource",  icon: "⇗", color: "#5a6a8a", pos: [-1, -1, -1], desc: "synchronic · referential · unstructured", ex: "bookmarks, files, PDFs" },
  { name: "Contact",   icon: "⦿", color: "#8a6a8a", pos: [1, -1, -1],  desc: "synchronic · referential · structured", ex: "people, organizations" },
  { name: "Note",      icon: "✎", color: "#5a7a6a", pos: [-1, -1, 1],  desc: "synchronic · sovereign · unstructured", ex: "working ideas, documents" },
  { name: "Topic",     icon: "◈", color: "#a4843a", pos: [1, -1, 1],   desc: "synchronic · sovereign · structured", ex: "projects, areas, tags" },
  { name: "Message",   icon: "✉", color: "#7a6a5a", pos: [-1, 1, -1],  desc: "diachronic · referential · unstructured", ex: "emails, texts, chats" },
  { name: "Event",     icon: "▸", color: "#d4854a", pos: [1, 1, -1],   desc: "diachronic · referential · structured", ex: "meetings, appointments" },
  { name: "Entry",     icon: "◷", color: "#6a8a7a", pos: [-1, 1, 1],   desc: "diachronic · sovereign · unstructured", ex: "journals, meeting notes" },
  { name: "Task",      icon: "◉", color: "#c4553a", pos: [1, 1, 1],    desc: "diachronic · sovereign · structured", ex: "to-dos, action items" },
];

const edges = [
  // Bottom face (synchronic)
  [0, 1], [1, 3], [3, 2], [2, 0],
  // Top face (diachronic)
  [4, 5], [5, 7], [7, 6], [6, 4],
  // Verticals
  [0, 4], [1, 5], [2, 6], [3, 7],
];

const axisLabels = [
  { from: [-1, -1, -1], to: [1, -1, -1], label: "structured →", labelNeg: "← unstructured" },
  { from: [-1, -1, -1], to: [-1, 1, -1], label: "diachronic →", labelNeg: "← synchronic" },
  { from: [-1, -1, -1], to: [-1, -1, 1], label: "sovereign →", labelNeg: "← referential" },
];

function multiply(a, b) {
  const r = [[0,0,0],[0,0,0],[0,0,0]];
  for (let i = 0; i < 3; i++)
    for (let j = 0; j < 3; j++)
      for (let k = 0; k < 3; k++)
        r[i][j] += a[i][k] * b[k][j];
  return r;
}

function rotY(a) {
  const c = Math.cos(a), s = Math.sin(a);
  return [[c,0,s],[0,1,0],[-s,0,c]];
}

function rotX(a) {
  const c = Math.cos(a), s = Math.sin(a);
  return [[1,0,0],[0,c,-s],[0,s,c]];
}

function transform(pt, mat) {
  return [
    mat[0][0]*pt[0] + mat[0][1]*pt[1] + mat[0][2]*pt[2],
    mat[1][0]*pt[0] + mat[1][1]*pt[1] + mat[1][2]*pt[2],
    mat[2][0]*pt[0] + mat[2][1]*pt[1] + mat[2][2]*pt[2],
  ];
}

function project(pt, scale, cx, cy) {
  const perspective = 4;
  const factor = perspective / (perspective + pt[2]);
  return {
    x: cx + pt[0] * scale * factor,
    y: cy - pt[1] * scale * factor,
    z: pt[2],
    scale: factor,
  };
}

export default function PIMCube() {
  const [rotation, setRotation] = useState({ x: -0.45, y: -0.6 });
  const [dragging, setDragging] = useState(false);
  const [hovered, setHovered] = useState(null);
  const lastPos = useRef({ x: 0, y: 0 });
  const animRef = useRef(null);
  const [autoRotate, setAutoRotate] = useState(true);

  useEffect(() => {
    if (!autoRotate || dragging) return;
    let frame;
    const spin = () => {
      setRotation(r => ({ x: r.x, y: r.y + 0.003 }));
      frame = requestAnimationFrame(spin);
    };
    frame = requestAnimationFrame(spin);
    return () => cancelAnimationFrame(frame);
  }, [autoRotate, dragging]);

  const onPointerDown = useCallback((e) => {
    setDragging(true);
    setAutoRotate(false);
    lastPos.current = { x: e.clientX, y: e.clientY };
    e.currentTarget.setPointerCapture(e.pointerId);
  }, []);

  const onPointerMove = useCallback((e) => {
    if (!dragging) return;
    const dx = e.clientX - lastPos.current.x;
    const dy = e.clientY - lastPos.current.y;
    lastPos.current = { x: e.clientX, y: e.clientY };
    setRotation(r => ({
      x: Math.max(-Math.PI / 2.2, Math.min(Math.PI / 2.2, r.x - dy * 0.006)),
      y: r.y + dx * 0.006,
    }));
  }, [dragging]);

  const onPointerUp = useCallback(() => {
    setDragging(false);
  }, []);

  const mat = multiply(rotX(rotation.x), rotY(rotation.y));
  const scale = 130;
  const cx = 350;
  const cy = 260;

  const projected = types.map(t => ({
    ...t,
    proj: project(transform(t.pos, mat), scale, cx, cy),
  }));

  const projectedEdges = edges.map(([a, b]) => ({
    a: projected[a].proj,
    b: projected[b].proj,
    az: (projected[a].proj.z + projected[b].proj.z) / 2,
  }));

  const sortedEdges = [...projectedEdges].sort((a, b) => a.az - b.az);
  const sortedNodes = [...projected].sort((a, b) => a.proj.z - b.proj.z);

  // Axis endpoints
  const axisProjected = axisLabels.map(a => ({
    ...a,
    fromP: project(transform(a.from, mat), scale, cx, cy),
    toP: project(transform(a.to, mat), scale, cx, cy),
    midP: project(transform(
      [(a.from[0]+a.to[0])/2, (a.from[1]+a.to[1])/2, (a.from[2]+a.to[2])/2],
      mat
    ), scale, cx, cy),
  }));

  return (
    <div style={{
      fontFamily: FONT,
      background: SAND,
      color: INK,
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      padding: "32px 16px",
      boxSizing: "border-box",
      userSelect: "none",
    }}>
      <h1 style={{
        fontSize: 24,
        fontWeight: 400,
        letterSpacing: "0.04em",
        margin: "0 0 2px",
        fontVariant: "small-caps",
      }}>
        the type cube
      </h1>
      <p style={{ fontFamily: MONO, fontSize: 11, color: FADED, margin: "0 0 8px" }}>
        eight types at eight vertices — three axes, three binary properties
      </p>
      <p style={{ fontFamily: MONO, fontSize: 10, color: FADED, margin: "0 0 24px" }}>
        drag to rotate{autoRotate ? " · auto-rotating" : ""}
        {!autoRotate && (
          <span
            onClick={() => setAutoRotate(true)}
            style={{ marginLeft: 8, color: ACCENT, cursor: "pointer", textDecoration: "underline" }}
          >
            resume spin
          </span>
        )}
      </p>

      <div style={{ position: "relative", width: 700, maxWidth: "100%" }}>
        <svg
          viewBox="0 0 700 520"
          style={{ width: "100%", cursor: dragging ? "grabbing" : "grab" }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
        >
          {/* Axis lines */}
          {axisProjected.map((a, i) => (
            <g key={i}>
              <line
                x1={a.fromP.x} y1={a.fromP.y}
                x2={a.toP.x} y2={a.toP.y}
                stroke={ACCENT}
                strokeWidth={1}
                strokeDasharray="4,4"
                opacity={0.5}
              />
              <text
                x={a.toP.x + (a.toP.x - cx) * 0.18}
                y={a.toP.y + (a.toP.y - cy) * 0.18}
                textAnchor="middle"
                fontFamily={MONO}
                fontSize={9}
                fill={ACCENT}
                opacity={0.8}
              >
                {a.label}
              </text>
            </g>
          ))}

          {/* Edges */}
          {sortedEdges.map((e, i) => {
            const opacity = 0.12 + (e.az + 1) * 0.15;
            return (
              <line
                key={`e-${i}`}
                x1={e.a.x} y1={e.a.y}
                x2={e.b.x} y2={e.b.y}
                stroke={INK}
                strokeWidth={1}
                opacity={Math.max(0.06, Math.min(0.4, opacity))}
              />
            );
          })}

          {/* Nodes */}
          {sortedNodes.map((t, i) => {
            const p = t.proj;
            const depthFactor = (p.z + 1.5) / 3;
            const r = 28;
            const opacity = 0.35 + depthFactor * 0.65;
            const isHovered = hovered === t.name;

            return (
              <g
                key={t.name}
                onPointerEnter={() => setHovered(t.name)}
                onPointerLeave={() => setHovered(null)}
                style={{ cursor: "pointer" }}
              >
                {/* Glow */}
                {isHovered && (
                  <circle cx={p.x} cy={p.y} r={r + 12} fill={t.color} opacity={0.12} />
                )}
                {/* Background circle */}
                <circle
                  cx={p.x} cy={p.y} r={r}
                  fill={SAND}
                  stroke={t.color}
                  strokeWidth={isHovered ? 2.5 : 1.5}
                  opacity={opacity}
                />
                {/* Fill */}
                <circle
                  cx={p.x} cy={p.y} r={r}
                  fill={`${t.color}${isHovered ? "28" : "14"}`}
                  opacity={opacity}
                />
                {/* Icon */}
                <text
                  x={p.x} y={p.y - 4}
                  textAnchor="middle" dominantBaseline="middle"
                  fontSize={17}
                  opacity={opacity}
                >
                  {t.icon}
                </text>
                {/* Name */}
                <text
                  x={p.x} y={p.y + 14}
                  textAnchor="middle"
                  fontFamily={FONT}
                  fontSize={11}
                  fontWeight={600}
                  fill={t.color}
                  opacity={opacity}
                >
                  {t.name}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Hover tooltip */}
        {hovered && (() => {
          const t = types.find(x => x.name === hovered);
          return (
            <div style={{
              position: "absolute",
              bottom: 12,
              left: "50%",
              transform: "translateX(-50%)",
              background: "white",
              border: `1px solid ${t.color}44`,
              borderRadius: 6,
              padding: "12px 20px",
              textAlign: "center",
              boxShadow: `0 4px 20px ${INK}10`,
              pointerEvents: "none",
              minWidth: 240,
            }}>
              <div style={{ fontSize: 20, marginBottom: 4 }}>{t.icon}</div>
              <div style={{ fontWeight: 600, fontSize: 18, color: t.color, marginBottom: 4 }}>{t.name}</div>
              <div style={{ fontFamily: MONO, fontSize: 10, color: FADED, marginBottom: 6 }}>{t.desc}</div>
              <div style={{ fontSize: 13, color: INK, fontStyle: "italic" }}>{t.ex}</div>
            </div>
          );
        })()}
      </div>

      {/* Legend */}
      <div style={{
        display: "flex",
        gap: 32,
        marginTop: 20,
        flexWrap: "wrap",
        justifyContent: "center",
      }}>
        {[
          ["Structuredness", "← unstructured | structured →", "x-axis"],
          ["Diachrony", "← synchronic | diachronic →", "y-axis (vertical)"],
          ["Sovereignty", "← referential | sovereign →", "z-axis (depth)"],
        ].map(([name, range, axis]) => (
          <div key={name} style={{ textAlign: "center", minWidth: 180 }}>
            <div style={{ fontFamily: MONO, fontSize: 10, color: ACCENT, letterSpacing: "0.06em", marginBottom: 2 }}>
              {name.toUpperCase()}
            </div>
            <div style={{ fontSize: 12, color: INK }}>{range}</div>
            <div style={{ fontFamily: MONO, fontSize: 9, color: FADED }}>{axis}</div>
          </div>
        ))}
      </div>

      {/* Face labels */}
      <div style={{
        marginTop: 28,
        padding: "16px 24px",
        background: `${INK}06`,
        borderRadius: 4,
        maxWidth: 600,
        width: "100%",
      }}>
        <div style={{ fontFamily: MONO, fontSize: 10, color: ACCENT, letterSpacing: "0.06em", marginBottom: 10 }}>
          FACES OF THE CUBE
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 24px", fontSize: 12 }}>
          <div><strong>Top face:</strong> diachronic types</div>
          <div>Message, Event, Entry, Task</div>
          <div><strong>Bottom face:</strong> synchronic types</div>
          <div>Resource, Contact, Note, Topic</div>
          <div><strong>Front face:</strong> sovereign types</div>
          <div>Note, Topic, Entry, Task</div>
          <div><strong>Back face:</strong> referential types</div>
          <div>Resource, Contact, Message, Event</div>
          <div><strong>Left face:</strong> unstructured types</div>
          <div>Resource, Note, Message, Entry</div>
          <div><strong>Right face:</strong> structured types</div>
          <div>Contact, Topic, Event, Task</div>
        </div>
      </div>
    </div>
  );
}
