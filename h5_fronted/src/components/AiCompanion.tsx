import { motion } from "motion/react";

interface Props {
  hint: string;
}

export function AiCompanion({ hint }: Props) {

  return (
    <div className="flex items-start gap-2.5 px-1 min-h-[32px]">
      {/* AI Avatar */}
      <div className="shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-[#6C5CE7] to-[#A78BFA] flex items-center justify-center shadow-sm mt-0.5">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2a4 4 0 014 4c0 2.21-2.24 4-4 4s-4-1.79-4-4a4 4 0 014-4z" />
          <path d="M6 14c0-2 2.5-3 6-3s6 1 6 3v4H6v-4z" />
          <circle cx="9.5" cy="9.5" r="1" fill="white" stroke="none" />
          <circle cx="14.5" cy="9.5" r="1" fill="white" stroke="none" />
          <path d="M10 12c.6.8 1.5 1 2 1s1.4-.2 2-1" />
        </svg>
      </div>

      {/* Hint bubble */}
      <div className="flex-1 min-w-0">
        {hint && (
          <motion.p
            key={hint}
            className="text-[14px] text-[#6b7280] leading-relaxed bg-[#F8F7FF] rounded-xl px-3 py-2 border border-[#EDE9FE]"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
          >
            {hint}
          </motion.p>
        )}
      </div>
    </div>
  );
}
