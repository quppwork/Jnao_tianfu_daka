interface Props {
  current: number;
  total: number;
}

export function ProgressBar({ current, total }: Props) {
  const pct = Math.round((current / total) * 100);

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-[#9ca3af] font-medium tabular-nums shrink-0 w-12 text-right">
        {current}/{total}
      </span>
      <div className="flex-1 h-1.5 bg-[#f3f4f6] rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500 ease-out"
          style={{
            width: `${pct}%`,
            background: "linear-gradient(90deg, #6C5CE7, #A78BFA)",
          }}
        />
      </div>
      <span className="text-sm text-[#9ca3af] font-medium tabular-nums shrink-0 w-9">
        {pct}%
      </span>
    </div>
  );
}
