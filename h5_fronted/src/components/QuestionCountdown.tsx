import { useEffect, useRef, useState } from "react";
import { QUESTION_TIME_SEC } from "../lib/quizBackgrounds";
import { countdownHintText, isCountdownUrgent } from "../lib/countdownHint";

type Props = {
  questionKey: string | number;
  seconds?: number;
  disabled?: boolean;
  onExpire: () => void;
};

export function QuestionCountdown({
  questionKey,
  seconds = QUESTION_TIME_SEC,
  disabled,
  onExpire,
}: Props) {
  const [left, setLeft] = useState(seconds);
  const firedRef = useRef(false);
  const onExpireRef = useRef(onExpire);
  onExpireRef.current = onExpire;

  useEffect(() => {
    setLeft(seconds);
    firedRef.current = false;
  }, [questionKey, seconds]);

  useEffect(() => {
    if (disabled) return;
    if (left <= 0) {
      if (!firedRef.current) {
        firedRef.current = true;
        onExpireRef.current();
      }
      return;
    }
    const t = window.setTimeout(() => setLeft((n) => n - 1), 1000);
    return () => clearTimeout(t);
  }, [left, disabled]);

  const pct = (left / seconds) * 100;
  const urgent = isCountdownUrgent(left);
  const hint = countdownHintText(left, seconds);

  return (
    <div className="flex items-center gap-2.5 mb-3">
      {/* 倒计时圆环 */}
      <div className="relative w-10 h-10 shrink-0">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
          <circle
            cx="18" cy="18" r="15.5"
            fill="none" stroke="currentColor" strokeWidth="2.5"
            className="text-[#6C5CE7]/12"
          />
          <circle
            cx="18" cy="18" r="15.5"
            fill="none" stroke="currentColor" strokeWidth="2.5"
            strokeLinecap="round"
            className={urgent ? "text-[#E84040] countdown-urgent-ring" : "text-[#6C5CE7]"}
            strokeDasharray={`${pct} 100`}
            pathLength={100}
          />
        </svg>
        <span
          className={`absolute inset-0 flex items-center justify-center text-sm font-bold tabular-nums ${
            urgent ? "text-[#E84040]" : "text-[#6C5CE7]"
          }`}
        >
          {left}
        </span>
      </div>

      {/* 提示文字 + 进度条 */}
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium leading-snug ${urgent ? "text-[#E84040]" : "text-[#8E8E93]"}`}>
          {hint}
        </p>
        <div className="timer-bar mt-1">
          <div
            className={`timer-bar-fill ${left <= 5 ? "warn" : ""} ${left <= 3 ? "danger" : ""}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
}
