import { useState, useEffect } from "react";
import { motion } from "motion/react";
import { DotLottieReact } from "@lottiefiles/dotlottie-react";

interface Props {
  onGenerateReport: () => void;
  submitting?: boolean;
  error?: string | null;
}

export function CompletionPage({ onGenerateReport, submitting, error }: Props) {
  const [phase, setPhase] = useState<"animating" | "text" | "button">("animating");

  useEffect(() => {
    const t1 = setTimeout(() => setPhase("text"), 1200);
    const t2 = setTimeout(() => setPhase("button"), 1800);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);

  return (
    <div className="flex flex-col items-center justify-start flex-1 px-6 pt-[33vh]">
      <div className="-translate-y-1/2 flex flex-col items-center">
        {/* Lottie checkmark animation */}
        <div className="w-56 h-56 mb-6">
          <DotLottieReact
            src="/success confetti.lottie"
            autoplay
            loop={false}
          />
        </div>

        {/* Title */}
        <motion.p
          className="text-[#1f2937] text-[19px] font-semibold leading-relaxed text-center"
          initial={{ opacity: 0, y: 12 }}
          animate={phase !== "animating" ? { opacity: 1, y: 0 } : { opacity: 0, y: 12 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        >
          35 题已完成
        </motion.p>

        {/* Subtitle */}
        <motion.p
          className="text-[#6b7280] text-base leading-relaxed text-center mt-2 mb-8"
          initial={{ opacity: 0, y: 12 }}
          animate={phase !== "animating" ? { opacity: 1, y: 0 } : { opacity: 0, y: 12 }}
          transition={{ delay: 0.15, duration: 0.5, ease: "easeOut" }}
        >
          AI 将为你生成专属天赋解读
        </motion.p>

        {/* Error message */}
        {error && (
          <motion.p
            className="text-[#ef4444] text-[15px] leading-relaxed text-center mb-4 max-w-[280px]"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
          >
            {error}
          </motion.p>
        )}

        {/* Button */}
        <motion.button
          className="w-full max-w-[300px] h-12 flex items-center justify-center text-[17px] font-medium text-white bg-[#6C5CE7] rounded-2xl active:bg-[#5A4BD1] transition-colors shadow-[0_4px_14px_rgba(108,92,231,0.25)]"
          initial={{ opacity: 0, y: 12, scale: 0.97 }}
          animate={phase === "button" ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 12, scale: 0.97 }}
          transition={{ type: "spring", stiffness: 420, damping: 24 }}
          whileTap={{ scale: 0.97 }}
          onClick={onGenerateReport}
          disabled={submitting}
        >
          {submitting ? "生成中..." : "生成报告"}
        </motion.button>
      </div>
    </div>
  );
}
