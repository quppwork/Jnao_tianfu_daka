interface RadarData {
  abilityName: string;
  value: number;
}

const DIM_ORDER = ["协调力", "执行力", "公信力", "领导力", "创新力"];

// Fixed outer pentagon vertices from reference (viewBox 0 0 130 120)
const OUTER = [
  { x: 65, y: 8 },   // top — 协调力
  { x: 118, y: 45 },  // top-right — 执行力
  { x: 98, y: 105 },  // bottom-right — 公信力
  { x: 32, y: 105 },  // bottom-left — 领导力
  { x: 12, y: 45 },   // top-left — 创新力
];

const CX = 65, CY = 61.6;

// Label positions from reference
const LABELS = [
  { x: 65, y: 5, anchor: "middle", color: "#171717", weight: "600" },
  { x: 125, y: 48, anchor: "start", color: "#888", weight: "400" },
  { x: 100, y: 112, anchor: "middle", color: "#888", weight: "400" },
  { x: 30, y: 112, anchor: "middle", color: "#888", weight: "400" },
  { x: 0, y: 48, anchor: "end", color: "#888", weight: "400" },
];

function lerpVerts(scale: number) {
  return OUTER.map((v) => `${CX + (v.x - CX) * scale},${CY + (v.y - CY) * scale}`).join(" ");
}

export function RadarChart({ data }: { data: RadarData[] }) {
  const sorted = DIM_ORDER
    .map((name) => data.find((d) => d.abilityName === name) || { abilityName: name, value: 0 });
  if (sorted.length === 0) return null;

  const dataPts = sorted.map((d, i) => {
    const ratio = Math.min(100, Math.max(0, d.value)) / 100;
    const v = OUTER[i];
    return `${CX + (v.x - CX) * ratio},${CY + (v.y - CY) * ratio}`;
  }).join(" ");

  const dataDots = sorted.map((d, i) => {
    const ratio = Math.min(100, Math.max(0, d.value)) / 100;
    const v = OUTER[i];
    const dotX = CX + (v.x - CX) * ratio;
    const dotY = CY + (v.y - CY) * ratio;
    const fill = ratio >= 0.5 ? "#171717" : "#999";
    return { x: dotX, y: dotY, fill };
  });

  return (
    <svg viewBox="0 0 130 120" className="mx-auto w-56 h-auto">
      {/* 3 concentric reference pentagons */}
      <polygon points={lerpVerts(1)} fill="none" stroke="#EBEBEB" strokeWidth="1" />
      <polygon points={lerpVerts(0.75)} fill="none" stroke="#E0DCE8" strokeWidth="1" />
      <polygon points={lerpVerts(0.5)} fill="none" stroke="#E0DCE8" strokeWidth="1" />

      {/* Data polygon */}
      <polygon points={dataPts} fill="rgba(0,0,0,0.04)" stroke="#888" strokeWidth="1.5" strokeLinejoin="round" />

      {/* Data points */}
      {dataDots.map((d, i) => (
        <circle key={i} cx={d.x} cy={d.y} r="3" fill={d.fill} />
      ))}

      {/* Labels */}
      {LABELS.map((l, i) => (
        <text key={i} x={l.x} y={l.y} fontSize="7" fill={l.color} textAnchor={l.anchor as "middle" | "start" | "end"}
          fontWeight={l.weight as "600" | "400"}>
          {sorted[i].abilityName}
        </text>
      ))}
    </svg>
  );
}
