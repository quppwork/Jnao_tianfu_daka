import { motion, AnimatePresence } from "motion/react";

export type ToastVariant = "ack" | "milestone" | "info";

interface Props {
  message: string | null;
  variant?: ToastVariant;
  className?: string;
}

const variantStyles: Record<ToastVariant, string> = {
  milestone:
    "bg-gradient-to-r from-[#6C5CE7] to-[#A78BFA] text-white shadow-lg shadow-[#6C5CE7]/25",
  ack: "bg-white/95 text-[#1f2937] border border-[#6C5CE7]/15 shadow-md backdrop-blur-sm",
  info: "bg-[#F3F0FF]/95 text-[#5A4BD1] border border-[#6C5CE7]/10",
};

export function QuizToast({ message, variant = "info", className }: Props) {
  return (
    <AnimatePresence>
      {message && (
        <motion.div
          key={message}
          className={`px-5 py-3 rounded-2xl text-base font-medium pointer-events-none text-center ${variantStyles[variant]} ${className ?? "absolute top-6 left-1/2 z-50 max-w-[88%]"}`}
          style={className ? undefined : { transform: "translateX(-50%)" }}
          initial={{ opacity: 0, y: -12, scale: 0.94 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -8, scale: 0.96 }}
          transition={{ type: "spring", stiffness: 500, damping: 30 }}
        >
          {variant === "milestone" && <span className="mr-1.5">✨</span>}
          {message}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
