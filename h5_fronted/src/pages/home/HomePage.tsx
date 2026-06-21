import { motion } from "motion/react";

interface Props {
  onStartTest: () => void;
}

export function HomePage({ onStartTest }: Props) {
  return (
    <motion.div
      className="flex flex-col items-center justify-start flex-1 px-6 pt-[20vh] bg-white"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      {/* Logo area */}
      <motion.div
        className="mb-8"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15, duration: 0.5 }}
      >
        <span className="text-[30px] font-bold text-[#1f2937] tracking-[-0.5px]">
          <span className="text-[#dc2626]">J</span>nao
        </span>
        <p className="text-[13px] text-[#888] mt-1 text-center">天赋测评</p>
      </motion.div>

      {/* Main card */}
      <motion.div
        className="w-full max-w-[300px] bg-white rounded-2xl border border-[#f0f0f0] shadow-sm p-6 text-center"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25, duration: 0.6, ease: "easeOut" }}
      >
        <p className="text-[16px] font-semibold text-[#1f2937] mb-2">
          发现你的天赋
        </p>
        <p className="text-[13px] text-[#888] leading-[1.6] mb-6">
          35 道题，了解你的天赋类型、能力画像与能量状态
        </p>

        <motion.button
          className="w-full h-12 text-[17px] font-medium text-white bg-[#1f2937] rounded-xl active:bg-[#111827] transition-colors shadow-sm"
          onClick={onStartTest}
          whileTap={{ scale: 0.97 }}
        >
          开始天赋测试
        </motion.button>
      </motion.div>

      {/* Feature hints */}
      <motion.div
        className="w-full max-w-[300px] mt-8 grid grid-cols-3 gap-3"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.45, duration: 0.5 }}
      >
        {[
          { icon: "🎯", label: "天赋类型" },
          { icon: "📊", label: "能力雷达" },
          { icon: "💡", label: "AI 解读" },
        ].map((f) => (
          <div key={f.label} className="text-center">
            <div className="text-xl mb-1">{f.icon}</div>
            <div className="text-[12px] text-[#888]">{f.label}</div>
          </div>
        ))}
      </motion.div>
    </motion.div>
  );
}
