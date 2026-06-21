type Tab = "home" | "mine";

interface Props {
  active: Tab;
  onNavigate: (tab: Tab) => void;
}

const TABS: { key: Tab; label: string; icon: (active: boolean) => string }[] = [
  {
    key: "home",
    label: "首页",
    icon: (a) =>
      a
        ? "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
        : "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6",
  },
  {
    key: "mine",
    label: "我的",
    icon: (a) =>
      a
        ? "M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
        : "M16 7a4 4 0 11-8 0 4 4 0 018 0zm-4 7a7 7 0 00-7 7h14a7 7 0 00-7-7z",
  },
];

export function BottomNav({ active, onNavigate }: Props) {
  return (
    <nav className="flex items-center justify-around h-[50px] border-t border-[#f0f0f0] bg-white shrink-0">
      {TABS.map((t) => {
        const isActive = active === t.key;
        return (
          <button
            key={t.key}
            type="button"
            className={`flex flex-col items-center justify-center gap-0.5 w-16 h-full ${
              isActive ? "text-[#1f2937]" : "text-[#A1A1A1]"
            }`}
            onClick={() => onNavigate(t.key)}
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill={isActive ? "#1f2937" : "none"}
              stroke="currentColor"
              strokeWidth={isActive ? 1.5 : 1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d={t.icon(isActive)} />
            </svg>
            <span className="text-[12px] font-medium">{t.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
