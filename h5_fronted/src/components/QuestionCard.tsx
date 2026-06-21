import { motion, AnimatePresence } from "motion/react";
import { QuestionCountdown } from "./QuestionCountdown";
import { ChoiceButtons } from "./ChoiceButtons";

interface Props {
  questionText: string;
  questionNumber: number;
  questionKey: string | number;
  busy: boolean;
  choices: string[];
  seconds?: number;
  previousAnswer?: string;
  onSelect: (choice: string) => void;
  onTimeout: () => void;
}

export function QuestionCard({
  questionText,
  questionNumber,
  questionKey,
  busy,
  choices,
  seconds,
  previousAnswer,
  onSelect,
  onTimeout,
}: Props) {
  return (
    <div className="rounded-3xl bg-white/90 backdrop-blur-md border border-white/60 shadow-xl shadow-black/5 p-6">
      {/* Badge: overlay dissolve */}
      <div className="flex items-center mb-4">
        <div className="relative inline-flex items-center h-7" style={{ minWidth: "4.5rem" }}>
          <AnimatePresence>
            <motion.span
              key={questionKey}
              className="absolute left-0 inline-flex items-center px-3 py-1 rounded-full text-[15px] font-semibold text-[#6C5CE7] bg-[#F3F0FF] whitespace-nowrap"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25, ease: "easeInOut" }}
            >
              第 {questionNumber} 题
            </motion.span>
          </AnimatePresence>
        </div>
      </div>

      {/* Countdown timer */}
      <div className="mb-5">
        <QuestionCountdown
          questionKey={questionKey}
          seconds={seconds}
          disabled={busy}
          onExpire={onTimeout}
        />
      </div>

      {/* Question text: overlay dissolve */}
      <div className="relative min-h-[3.5rem] mb-12">
        <AnimatePresence>
          <motion.p
            key={questionKey}
            className="absolute inset-0 text-[19px] font-medium text-[#1f2937] leading-relaxed"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
          >
            {questionText}
          </motion.p>
        </AnimatePresence>
      </div>

      {/* Previous answer indicator */}
      {previousAnswer && (
        <div className="flex items-center justify-center mb-3">
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-[13px] text-[#9ca3af] bg-[#f3f4f6]">
            上次选择：<span className="font-medium text-[#6b7280]">{previousAnswer}</span>
          </span>
        </div>
      )}

      {/* Choice buttons */}
      <ChoiceButtons
        choices={choices}
        onSelect={onSelect}
        variant="yesno"
        disabled={busy}
      />
    </div>
  );
}
