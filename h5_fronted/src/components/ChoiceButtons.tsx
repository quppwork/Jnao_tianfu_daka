import { motion, AnimatePresence } from "motion/react";

interface Props {
  choices: string[];
  onSelect: (choice: string) => void;
  disabled?: boolean;
  className?: string;
  containerRef?: React.RefObject<HTMLDivElement | null>;
  /** 测试答题模式：yes/no 双按钮 pill 风格 */
  variant?: "default" | "yesno";
}

export function ChoiceButtons({ choices, onSelect, disabled, className = "", containerRef, variant = "default" }: Props) {
  if (variant === "yesno") {
    return (
      <div ref={containerRef} className={`flex justify-center gap-3 ${className}`}>
        <AnimatePresence>
          {choices.map((choice, i) => {
            const isYes = choice === "完全符合" || choice === "符合" || choice === "是";
            return (
              <motion.button
                key={choice}
                className={`${isYes ? "btn-test-yes" : "btn-test-no"} ${disabled ? "pointer-events-none" : ""}`}
                initial={{ opacity: 0, y: 12, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{
                  delay: i * 0.06,
                  type: "spring",
                  stiffness: 420,
                  damping: 24,
                }}
                whileTap={disabled ? {} : { scale: 0.97 }}
                disabled={disabled}
                onClick={() => { if (!disabled) onSelect(choice); }}
              >
                {choice}
              </motion.button>
            );
          })}
        </AnimatePresence>
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`flex gap-2.5 ${className}`}>
      <AnimatePresence>
        {choices.map((choice, i) => (
          <motion.button
            key={choice}
            className="flex-1 min-w-0 h-12 flex items-center justify-center text-[17px] font-medium text-[#1f2937] bg-white border border-[#d1d5db] rounded-lg active:bg-[#f9fafb] transition-colors"
            initial={{ opacity: 0, y: 12, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{
              delay: i * 0.06,
              type: "spring",
              stiffness: 420,
              damping: 24,
            }}
            whileTap={{ scale: 0.97 }}
            disabled={disabled}
            onClick={() => onSelect(choice)}
          >
            {choice}
          </motion.button>
        ))}
      </AnimatePresence>
    </div>
  );
}
