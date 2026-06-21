const STATE_LABELS = ["相争", "难辨", "牵制", "双生", "本命", "孤显", "无向", "无神"];

interface Props {
  stateName: string;
}

/**
 * SVG mood dashboard matching reference design.
 * 3-zone colored bar + pointer positioned by state name.
 * States from left (low/低迷) to right (high/高涨).
 */
export function MoodDashboard({ stateName }: Props) {
  const idx = STATE_LABELS.indexOf(stateName);
  // Map state index to pointer x: 0 (相争/高涨) → right, 7 (无神/低迷) → left
  const px = idx >= 0 ? 155 - idx * (110 / 7) : 100;

  return (
    <svg width="180" height="44" viewBox="0 0 180 44" className="mx-auto">
      {/* Base bar */}
      <rect x="10" y="30" width="160" height="4" rx="2" fill="#EBEBEB" />
      {/* Zone: 低迷 */}
      <rect x="10" y="30" width="50" height="4" rx="2" fill="#E8D0C0" />
      {/* Zone: 平稳 */}
      <rect x="90" y="30" width="50" height="4" rx="2" fill="#D0D8E8" />
      {/* Zone: 高涨 */}
      <rect x="140" y="30" width="30" height="4" rx="2" fill="#D0E8D0" />
      {/* Pointer */}
      <circle cx={px} cy="32" r="6" fill="#C89060" stroke="#FFF" strokeWidth="2" />
      {/* Labels */}
      <text x="35" y="22" fontSize="7" fill="#888" textAnchor="middle">低迷</text>
      <text x="90" y="14" fontSize="7" fill="#888" textAnchor="middle">平稳</text>
      <text x="140" y="22" fontSize="7" fill="#888" textAnchor="middle">高涨</text>
    </svg>
  );
}
