import { useState, useEffect, useRef, useCallback } from "react";
import { sendChat } from "../api/client";

interface SectionTip {
  id: string;
  tip: string;
}

interface Props {
  sections: SectionTip[];
  scrollContainerId: string;
  reportContext: string;
}

interface ChatMsg {
  q: string;
  a: string;
}

export function AiGuideCard({ sections, scrollContainerId, reportContext }: Props) {
  const [dismissed, setDismissed] = useState(false);
  const [tip, setTip] = useState("");
  const [input, setInput] = useState("");
  const [chat, setChat] = useState<ChatMsg[]>([]);
  const [loading, setLoading] = useState(false);
  const lastIdx = useRef(-1);

  // Scroll-based tip switching
  useEffect(() => {
    const el = document.getElementById(scrollContainerId);
    if (!el) return;

    const onScroll = () => {
      if (dismissed) return;
      let found = -1;
      const st = el.scrollTop + 140;
      for (let i = sections.length - 1; i >= 0; i--) {
        const sec = document.getElementById(sections[i].id);
        if (sec && sec.offsetTop < st) { found = i; break; }
      }
      if (found >= 0 && found !== lastIdx.current) {
        lastIdx.current = found;
        setTip(sections[found].tip);
      }
    };

    el.addEventListener("scroll", onScroll, { passive: true });
    // Initial
    setTimeout(onScroll, 100);
    return () => el.removeEventListener("scroll", onScroll);
  }, [sections, scrollContainerId, dismissed]);

  const handleSend = useCallback(async () => {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setLoading(true);
    try {
      const res = await sendChat(q, reportContext);
      setChat((prev) => [...prev, { q, a: res.answer || "抱歉，暂时无法回答。" }]);
    } catch {
      setChat((prev) => [...prev, { q, a: "AI 服务暂不可用。" }]);
    }
    setLoading(false);
  }, [input, loading, reportContext]);

  return (
    <>
      {/* Floating ? button when card dismissed */}
      <div
        className={`fixed bottom-3 right-4 w-9 h-9 rounded-full bg-[#171717] text-white flex items-center justify-center text-base cursor-pointer z-20 shadow-[0_2px_8px_rgba(0,0,0,0.15)] ${dismissed ? "" : "hidden"}`}
        onClick={() => { setDismissed(false); lastIdx.current = -1; }}
      >?</div>

      {/* Guide card */}
      <div className={`fixed bottom-0 left-0 right-0 bg-white/96 backdrop-blur-[12px] border-t border-[#EBEBEB] z-10 transition-transform duration-300 flex flex-col max-h-[60%] ${dismissed ? "translate-y-full opacity-0 pointer-events-none" : ""}`}>
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-[10px]">
          <span className="text-[12px] font-semibold text-[#888] uppercase tracking-[0.5px]">AI 智能解读</span>
          <button type="button" className="text-base text-[#888] w-5 h-5 flex items-center justify-center"
            onClick={() => setDismissed(true)}>x</button>
        </div>

        {/* Tip */}
        {tip && (
          <div className="px-4 pb-2 text-[12px] text-[#171717] leading-[1.5]">{tip}</div>
        )}

        {/* Chat history */}
        {chat.length > 0 && (
          <div className="flex-1 overflow-y-auto px-4 max-h-[120px]">
            {chat.map((m, i) => (
              <div key={i} className="py-2 border-b border-[#EBEBEB] last:border-b-0">
                <div className="text-[12px] font-semibold text-[#171717] mb-0.5">{m.q}</div>
                <div className="text-[12px] text-[#4D4D4D]">{m.a}</div>
              </div>
            ))}
          </div>
        )}

        {/* Input row */}
        <div className="flex gap-2 px-4 py-2 pb-3 items-center">
          <input
            className="flex-1 h-8 px-3 rounded-2xl border border-[#EBEBEB] text-[13px] text-[#171717] outline-none bg-[#FAFAFA] placeholder:text-[#A1A1A1]"
            placeholder="输入问题，比如：协调力低怎么办？"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleSend(); }}
          />
          <button type="button"
            className="w-8 h-8 rounded-full bg-[#171717] text-white border-none cursor-pointer shrink-0 flex items-center justify-center text-base active:bg-[#333]"
            onClick={handleSend}
            disabled={loading}
          >↑</button>
        </div>
      </div>
    </>
  );
}
