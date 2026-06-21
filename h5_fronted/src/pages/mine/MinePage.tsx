import { useState, useEffect } from "react";
import { motion } from "motion/react";
import { getHistory, removeHistory, type HistoryEntry } from "../../lib/historyStore";

interface Props {
  onViewReport: (entry: HistoryEntry) => void;
}

export function MinePage({ onViewReport }: Props) {
  const [history, setHistory] = useState<HistoryEntry[]>([]);

  useEffect(() => {
    setHistory(getHistory());
  }, []);

  const handleDelete = (recordId: number) => {
    removeHistory(recordId);
    setHistory((prev) => prev.filter((e) => e.record_id !== recordId));
  };

  return (
    <motion.div
      className="flex flex-col flex-1 bg-white"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
    >
      {/* Profile header */}
      <div className="px-6 pt-10 pb-6">
        <div className="w-16 h-16 rounded-full bg-[#f5f5f5] flex items-center justify-center mx-auto mb-3">
          <span className="text-2xl">👤</span>
        </div>
        <p className="text-[17px] font-semibold text-[#1f2937] text-center">测试用户</p>
        <p className="text-[13px] text-[#A1A1A1] text-center mt-0.5">
          {history.length > 0 ? `共 ${history.length} 次测试记录` : "暂无测试记录"}
        </p>
      </div>

      {/* History list */}
      <div className="border-t border-[#f0f0f0]">
        {history.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <p className="text-[13px] text-[#A1A1A1]">完成天赋测试后，记录将显示在这里</p>
          </div>
        ) : (
          history.map((entry) => (
            <div
              key={entry.record_id}
              className="flex items-center justify-between px-6 py-4 border-b border-[#f0f0f0] active:bg-[#fafafa] cursor-pointer"
              onClick={() => onViewReport(entry)}
            >
              <div className="flex-1 min-w-0">
                <div className="text-[15px] font-medium text-[#1f2937]">
                  {entry.talent}
                  <span className="text-[11px] text-[#A1A1A1] ml-1.5 font-normal">
                    #{entry.record_id}
                  </span>
                </div>
                <div className="text-[12px] text-[#A1A1A1] mt-0.5">
                  {entry.create_time}
                  <span className="mx-1.5">·</span>
                  {entry.type === 0 ? "成人测试" : "孩子测试"}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-[#d1d5db] text-base">›</span>
                <button
                  type="button"
                  className="text-[11px] text-[#d1d5db] hover:text-[#ef4444] px-1"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(entry.record_id);
                  }}
                >
                  删除
                </button>
              </div>
            </div>
          ))
        )}

        {/* Static menu items */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#f0f0f0] active:bg-[#fafafa]">
          <div>
            <div className="text-[15px] font-medium text-[#1f2937]">关于 Jnao</div>
            <div className="text-[12px] text-[#A1A1A1] mt-0.5">版本 0.2.0</div>
          </div>
          <span className="text-[#d1d5db] text-base">›</span>
        </div>
      </div>
    </motion.div>
  );
}
