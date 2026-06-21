import { useState, useEffect, useCallback, useRef } from "react";
import { SafeArea } from "antd-mobile";
import { motion, AnimatePresence } from "motion/react";
import { ProgressBar } from "../../components/ProgressBar";
import { QuestionCard } from "../../components/QuestionCard";
import { AiCompanion } from "../../components/AiCompanion";
import { CompletionPage } from "../../components/CompletionPage";
import { QuizBackground } from "../../components/QuizBackground";
import { QuizToast } from "../../components/QuizToast";
import type { ToastVariant } from "../../components/QuizToast";
import { HoverLottie } from "../../components/HoverLottie";
import { getQuestionsBySet } from "../../data/questions";
import { getHint } from "../../data/questionHints";
import { randomAck, milestoneFor } from "../../lib/quizFeedback";
import { QUESTION_TIME_SEC, QUIZ_BACKGROUNDS } from "../../lib/quizBackgrounds";
import { shuffle, requeueAtBack, getOrCreateUid, encodeAnswers } from "../../lib/testHelpers";
import type { JnaoReportData } from "../../api/types";
import { ReportPage } from "../../pages/ReportPage";

// ── Constants ──
const UNDO_SEC = 5;
const TOTAL = 35;

type Phase = "door" | "ageGate" | "confirm" | "testing" | "completed" | "report";

interface Props {
  isReturning: boolean;
  onExit: () => void;
}

export function TalentTest({ isReturning, onExit }: Props) {
  const [phase, setPhase] = useState<Phase>("door");
  const [testType, setTestType] = useState<"成人" | "孩子" | null>(null);
  const [isBackup, setIsBackup] = useState(false);
  const [messages, setMessages] = useState<string[]>(["首先我们来打开 Jnao 的大门，测试一下天赋吧！"]);
  const [ageGateNotice, setAgeGateNotice] = useState(false);
  const [busy, setBusy] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ text: string; key: number; variant: ToastVariant } | null>(null);
  const [showChoices, setShowChoices] = useState(false);
  const [reportData, setReportData] = useState<JnaoReportData | null>(null);
  const [currentQIndex, setCurrentQIndex] = useState(0);
  const [questionOrder, setQuestionOrder] = useState<number[]>([]);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [prevCard, setPrevCard] = useState<{ idx: number; text: string; answer: string } | null>(null);
  const [undoMode, setUndoMode] = useState(false);

  const uidRef = useRef(getOrCreateUid());
  const tickRef = useRef(0);
  const skippedRef = useRef(false);
  const noticeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const undoRef = useRef(false);

  const showToast = useCallback((text: string, variant: ToastVariant = "ack") => {
    const key = Date.now();
    setToast({ text, key, variant });
    setTimeout(() => setToast((prev) => (prev?.key === key ? null : prev)), variant === "milestone" ? 2800 : 2000);
  }, []);

  // ── Init ──
  useEffect(() => {
    const t = setTimeout(() => setShowChoices(true), 400);
    return () => clearTimeout(t);
  }, []);

  // Restore saved report (from sessionStorage) — used when viewing past reports or returning from external links
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("savedReport");
      if (!raw) return;
      const saved = JSON.parse(raw);
      if (saved.reportData && saved.reportData.id) {
        setReportData(saved.reportData);
        setTestType(saved.testType || "成人");
        setIsBackup(saved.isBackup || false);
        setPhase("report");
        sessionStorage.removeItem("savedReport");
      }
    } catch { /* ignore */ }
  }, []);

  // ── Start test ──
  const startTest = useCallback((type: "成人" | "孩子", backup: boolean) => {
    const setName = backup ? "child_backup" : (type === "成人" ? "adult" : "child");
    const ids = getQuestionsBySet(setName).map((q) => q.id);
    setPhase("testing");
    setTestType(type);
    setIsBackup(backup);
    setQuestionOrder(shuffle(ids));
    setCurrentQIndex(0);
    setAnswers({});
    setPrevCard(null);
    setUndoMode(false);
    undoRef.current = false;
    tickRef.current++;
  }, []);

  // ── Pre-test choices ──
  const handlePreTestChoice = useCallback((choice: string) => {
    setShowChoices(false);
    if (phase === "door") {
      if (choice === "孩子测试") {
        setPhase("ageGate");
        setMessages(["注意！请确认您的孩子是否满18岁"]);
        setTimeout(() => setShowChoices(true), 50);
      } else {
        setTestType("成人");
        setPhase("confirm");
        setMessages(["好的，成人测试。"]);
        setTimeout(() => setShowChoices(true), 50);
      }
    } else if (phase === "ageGate") {
      if (choice === "已满18岁") {
        setTestType("成人");
        setPhase("confirm");
        setMessages(["好的，成人测试。"]);
        setTimeout(() => setShowChoices(true), 50);
      } else {
        setTestType("孩子");
        setAgeGateNotice(true);
        setMessages(["您的孩子未满18岁，请您帮助您的孩子完成测试，否则测试可能会与事实产生误差"]);
        noticeTimerRef.current = setTimeout(() => {
          setAgeGateNotice(false);
          setPhase("confirm");
          setMessages([]);
          setShowChoices(true);
        }, 2200);
      }
    } else if (phase === "confirm") {
      if (choice === "准备好了，开始吧") {
        startTest(testType || "成人", false);
        setTimeout(() => setShowChoices(true), 50);
      } else {
        setPhase("door");
        setTestType(null);
        setMessages(["首先我们来打开 Jnao 的大门，测试一下天赋吧！"]);
        setTimeout(() => setShowChoices(true), 50);
      }
    }
  }, [phase, testType, startTest]);

  // ── Handle answer ──
  const handleAnswer = useCallback((choice: string) => {
    if (busy || submitting) return;
    setBusy(true);
    setShowChoices(false);
    const qid = questionOrder[currentQIndex];
    const qi = currentQIndex + 1;
    setAnswers((prev) => ({ ...prev, [qid]: choice }));
    setPrevCard({ idx: qi, text: "", answer: choice });
    if (undoRef.current) undoRef.current = false;
    const ack = randomAck();
    const ms = milestoneFor(qi);
    showToast(ack, "ack");
    if (ms) setTimeout(() => showToast(ms, "milestone"), 1200);

    const next = currentQIndex + 1;
    if (next >= TOTAL) {
      setPhase("completed");
    } else {
      setCurrentQIndex(next);
      tickRef.current++;
      setTimeout(() => setShowChoices(true), 50);
    }
    setTimeout(() => setBusy(false), 600);
  }, [busy, submitting, questionOrder, currentQIndex, showToast]);

  // ── Timeout ──
  const handleQuestionTimeout = useCallback(() => {
    const qid = questionOrder[currentQIndex];
    const remaining = questionOrder.slice(currentQIndex);
    const reordered = requeueAtBack(remaining, qid);
    setQuestionOrder([...questionOrder.slice(0, currentQIndex), ...reordered]);
    tickRef.current++;
    showToast("时间到～这道题先跳过，我们最后再回来答", "info");
  }, [questionOrder, currentQIndex, showToast]);

  // ── Undo ──
  const handleUndo = useCallback(() => {
    if (!prevCard || undoRef.current) return;
    setCurrentQIndex(prevCard.idx - 1);
    undoRef.current = true;
    setUndoMode(true);
    setPrevCard(null);
    showToast(`已返回第 ${prevCard.idx} 题，${UNDO_SEC}秒内可修改`, "info");
  }, [prevCard, showToast]);

  // ── Undo timeout (5s) ──
  useEffect(() => {
    if (!undoMode) return;
    const t = setTimeout(() => {
      setUndoMode(false);
      const next = currentQIndex + 1;
      if (next >= TOTAL) {
        setPhase("completed");
      } else {
        setCurrentQIndex(next);
        tickRef.current++;
        showToast(`${UNDO_SEC}秒未修改，已保留原答案`, "info");
      }
    }, UNDO_SEC * 1000);
    return () => clearTimeout(t);
  }, [undoMode]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Submit report ──
  const submitReport = useCallback(async () => {
    if (submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const bits = skippedRef.current ? "11000111110001001001011111000101001" : encodeAnswers(questionOrder, answers);
      const type = testType === "成人" ? 0 : 1;
      const res = await fetch("/api/talent/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer: bits, uid: uidRef.current, type }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      const data = json.data as JnaoReportData;
      setReportData(data);
      setPhase("report");
      try {
        const key = "jnao_test_history";
        const raw = localStorage.getItem(key) || "[]";
        const history = JSON.parse(raw);
        history.push({
          encoding: bits, uid: uidRef.current, type,
          talent: data.talent, property: data.property,
          create_time: data.create_time, record_id: data.id,
          response: data, saved_at: new Date().toISOString(),
        });
        localStorage.setItem(key, JSON.stringify(history));
      } catch { /* silent */ }
    } catch (err) {
      setSubmitError(`提交失败：${err instanceof Error ? err.message : "请稍后重试"}`);
    }
    setSubmitting(false);
  }, [submitting, questionOrder, answers, testType]);

  // ── Backup test ──
  const handleBackupTest = useCallback(() => {
    startTest("孩子", true);
    setTimeout(() => setShowChoices(true), 50);
  }, [startTest]);

  // ── Restart ──
  const handleRestart = useCallback(() => {
    setShowChoices(false);
    onExit();
  }, [onExit]);

  // ── Derived ──
  const qid = questionOrder[currentQIndex];
  const currentQuestion = qid ? {
    index: currentQIndex + 1,
    text: getQuestionsBySet("adult").find(q => q.id === qid)?.text
      || getQuestionsBySet("child").find(q => q.id === qid)?.text
      || getQuestionsBySet("child_backup").find(q => q.id === qid)?.text
      || "",
    ai_hint: getHint(qid),
    background: QUIZ_BACKGROUNDS[Math.min(currentQIndex, QUIZ_BACKGROUNDS.length - 1)],
    timeout_seconds: undoMode ? UNDO_SEC : QUESTION_TIME_SEC,
    can_undo: prevCard !== null && !undoMode,
    previous_answer: undoMode ? answers[qid] ?? null : null,
  } : null;

  const isTesting = phase === "testing";
  const isCompleted = phase === "completed";
  const isPreTest = phase === "door" || phase === "ageGate" || phase === "confirm";
  const showPreTestChoices = isPreTest && showChoices;

  return (
    <div className="flex flex-col flex-1 bg-white relative z-0 overflow-y-auto no-scrollbar">
      {/* Toast */}
      {!isTesting && !isCompleted && <QuizToast message={toast?.text ?? null} variant={toast?.variant} />}

      {/* Testing header */}
      {isTesting && testType && (
        <div className="sticky top-0 z-20 bg-white px-4 pt-2.5 pb-2">
          <div className="flex justify-center pb-1">
            <span className="inline-block text-[13px] font-medium text-[#6b7280] bg-[#F3F0FF] px-2.5 py-0.5 rounded-full border border-[#E8E4F0]">
              {isBackup ? "深度校准" : (testType === "孩子" ? "孩子测试" : "成人测试")}
            </span>
            <button
              type="button"
              className="absolute right-4 text-[12px] text-[#c5c5c5] border border-dashed border-[#e5e7eb] rounded px-2 py-0.5 active:bg-[#f9fafb]"
              onClick={() => { skippedRef.current = true; setPhase("completed"); }}>
              跳过→报告
            </button>
          </div>
          <ProgressBar current={(currentQIndex + 1) || 1} total={TOTAL} />
        </div>
      )}

      {/* ── Pre-test rooms ── */}
      {showPreTestChoices && (
        <AnimatePresence>
          {/* DOOR */}
          {phase === "door" && (
            <motion.div
              key="door"
              className="flex flex-col items-center justify-start flex-1 px-6 pt-[33vh]"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }}
            >
              <div className="-translate-y-1/2 flex flex-col items-center">
                <motion.p className="text-[#1f2937] text-[19px] font-semibold leading-relaxed text-center max-w-sm"
                  initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.15, duration: 0.6, ease: "easeOut" }}>
                  {isReturning ? "又来测试天赋了吗，欢迎" : messages[0]}
                </motion.p>
                <motion.p className="text-[#6b7280] text-base leading-relaxed text-center mt-2 mb-10 max-w-xs"
                  initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.35, duration: 0.6, ease: "easeOut" }}>
                  以下您将完成 35 道题目，做好准备了吗？请问你想进行哪种类型的天赋测试呢？
                </motion.p>
                <div className="flex gap-4 w-full max-w-[360px]">
                  <motion.button
                    className="flex-1 aspect-square flex flex-col items-center justify-center rounded-2xl border-2 border-[#93c5fd] bg-[#eff6ff] active:bg-[#dbeafe] transition-colors shadow-sm"
                    initial={{ opacity: 0, x: -20, scale: 0.95 }} animate={{ opacity: 1, x: 0, scale: 1 }}
                    transition={{ delay: 0.5, type: "spring", stiffness: 300, damping: 24 }}
                    whileTap={{ scale: 0.96 }} onClick={() => handlePreTestChoice("孩子测试")}>
                    <HoverLottie src="/child.lottie" className="w-16 h-16 mb-1" />
                    <span className="text-[17px] font-semibold text-[#1f2937]">孩子测试</span>
                    <span className="text-[13px] text-[#9ca3af] mt-1 text-center leading-tight px-2">家长辅助完成<br />了解孩子的天赋</span>
                  </motion.button>
                  <motion.button
                    className="flex-1 aspect-square flex flex-col items-center justify-center rounded-2xl border-2 border-[#93c5fd] bg-[#eff6ff] active:bg-[#dbeafe] transition-colors shadow-sm"
                    initial={{ opacity: 0, x: 20, scale: 0.95 }} animate={{ opacity: 1, x: 0, scale: 1 }}
                    transition={{ delay: 0.65, type: "spring", stiffness: 300, damping: 24 }}
                    whileTap={{ scale: 0.96 }} onClick={() => handlePreTestChoice("成人测试")}>
                    <HoverLottie src="/account.lottie" className="w-16 h-16 mb-1" />
                    <span className="text-[17px] font-semibold text-[#1f2937]">成人测试</span>
                    <span className="text-[13px] text-[#9ca3af] mt-1 text-center leading-tight px-2">自行评估完成<br />探索内在潜能</span>
                  </motion.button>
                </div>
              </div>
            </motion.div>
          )}

          {/* AGE GATE */}
          {phase === "ageGate" && (
            <motion.div
              key="ageGate"
              className="flex flex-col items-center justify-start flex-1 px-6 pt-[33vh]"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }}
            >
              <div className="-translate-y-1/2 flex flex-col items-center">
                <motion.p className="text-[#1f2937] text-[19px] font-semibold leading-relaxed text-center max-w-sm"
                  initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.15, duration: 0.6, ease: "easeOut" }}>
                  注意<span className="text-[#ef4444]">！</span>请确认您的孩子是否满18岁
                </motion.p>
                <div className="flex gap-4 w-full max-w-[360px] mt-10">
                  <motion.button
                    className="flex-1 flex flex-col items-center justify-center rounded-2xl border-2 border-[#93c5fd] bg-[#eff6ff] active:bg-[#dbeafe] transition-colors shadow-sm py-8"
                    initial={{ opacity: 0, x: -20, scale: 0.95 }} animate={{ opacity: 1, x: 0, scale: 1 }}
                    transition={{ delay: 0.5, type: "spring", stiffness: 300, damping: 24 }}
                    whileTap={{ scale: 0.96 }} onClick={() => handlePreTestChoice("已满18岁")}>
                    <span className="text-[17px] font-semibold text-[#1f2937]">已满18岁</span>
                    <span className="text-[13px] text-[#9ca3af] mt-1">进入成人测试</span>
                  </motion.button>
                  <motion.button
                    className="flex-1 flex flex-col items-center justify-center rounded-2xl border-2 border-[#fbbf24] bg-[#fffbeb] active:bg-[#fef3c7] transition-colors shadow-sm py-8"
                    initial={{ opacity: 0, x: 20, scale: 0.95 }} animate={{ opacity: 1, x: 0, scale: 1 }}
                    transition={{ delay: 0.65, type: "spring", stiffness: 300, damping: 24 }}
                    whileTap={{ scale: 0.96 }} onClick={() => handlePreTestChoice("未满18岁")}>
                    <span className="text-[17px] font-semibold text-[#1f2937]">未满18岁</span>
                    <span className="text-[13px] text-[#9ca3af] mt-1">家长辅助完成</span>
                  </motion.button>
                </div>
              </div>
            </motion.div>
          )}

          {/* CONFIRM */}
          {phase === "confirm" && (
            <motion.div
              key="confirm"
              className="flex flex-col items-center justify-start flex-1 px-6 pt-[33vh]"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }}
            >
              <div className="-translate-y-1/2 flex flex-col items-center">
                <motion.p className="text-[#1f2937] text-[19px] font-semibold leading-relaxed text-center max-w-sm"
                  initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.15, duration: 0.6, ease: "easeOut" }}>
                  好的，{testType || "成人"}测试。
                </motion.p>
                <motion.p className="text-[#6b7280] text-base leading-relaxed text-center mt-3 max-w-xs"
                  initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.35, duration: 0.6, ease: "easeOut" }}>
                  共 35 道题，每题两个选项：「完全符合」或「有差异」。根据实际情况选择即可，大约需要 10-15 分钟。
                </motion.p>
                <motion.p className="text-[#1f2937] text-[17px] font-medium text-center mt-5 mb-10"
                  initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.5, duration: 0.5, ease: "easeOut" }}>
                  准备好了吗？
                </motion.p>
                <div className="flex gap-3 w-full max-w-[340px]">
                  <motion.button
                    className="flex-1 flex flex-col items-center justify-center rounded-2xl border-2 border-[#1677ff] bg-[#eff6ff] active:bg-[#dbeafe] transition-colors shadow-sm py-7"
                    initial={{ opacity: 0, y: 16, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{ delay: 0.65, type: "spring", stiffness: 300, damping: 24 }}
                    whileTap={{ scale: 0.96 }} onClick={() => handlePreTestChoice("准备好了，开始吧")}>
                    <span className="text-xl mb-1">✅</span>
                    <span className="text-[17px] font-semibold text-[#1f2937]">准备好了，开始吧</span>
                  </motion.button>
                  <motion.button
                    className="flex-1 flex flex-col items-center justify-center rounded-2xl border-2 border-[#e5e7eb] bg-[#f9fafb] active:bg-[#f3f4f6] transition-colors shadow-sm py-7"
                    initial={{ opacity: 0, y: 16, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{ delay: 0.8, type: "spring", stiffness: 300, damping: 24 }}
                    whileTap={{ scale: 0.96 }} onClick={() => handlePreTestChoice("⏸ 稍后再说")}>
                    <span className="text-xl mb-1">⏸</span>
                    <span className="text-[17px] font-semibold text-[#6b7280]">稍后再说</span>
                  </motion.button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      )}

      {/* AgeGate under-18 notice */}
      {ageGateNotice && phase === "ageGate" && (
        <motion.div className="flex flex-col items-center justify-start flex-1 px-6 pt-[33vh]"
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <div className="-translate-y-1/2">
            <motion.p className="text-[#1f2937] text-[17px] font-medium leading-relaxed text-center max-w-xs">
              {messages[0]}
            </motion.p>
          </div>
        </motion.div>
      )}

      {/* COMPLETED */}
      {isCompleted && (
        <CompletionPage
          onGenerateReport={submitReport}
          submitting={submitting}
          error={submitError}
        />
      )}

      {/* TESTING */}
      {isTesting && testType && currentQuestion && (
        <>
          <div className="flex-1 relative min-h-0">
            <QuizBackground
              questionIndex={currentQIndex}
              active={true}
              theme={currentQuestion.background}
            />
            <div className="absolute inset-0 flex flex-col items-center justify-center px-4">
              <div className="w-full max-w-[400px] relative flex flex-col items-center">
                <QuizToast message={toast?.text ?? null} variant={toast?.variant} className="absolute -top-11 left-1/2 -translate-x-1/2 z-50 max-w-[88%]" />

                {/* Undo previous card */}
                <AnimatePresence>
                  {prevCard && !undoMode && (
                    <motion.div
                      initial={{ opacity: 0, height: 0, marginBottom: 0 }}
                      animate={{ opacity: 1, height: "auto", marginBottom: 12 }}
                      exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                      transition={{ duration: 0.3, ease: "easeInOut" }}
                      className="w-[92%] relative cursor-pointer overflow-hidden"
                      onClick={handleUndo}>
                      <div className="rounded-2xl bg-white/90 border border-[#e5e7eb] p-4 shadow-sm">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[13px] font-medium text-[#b0b0b0] bg-[#f3f4f6]">
                            第 {prevCard.idx} 题
                          </span>
                          <span className="text-[13px] text-[#b0b0b0]">已答：{prevCard.answer}</span>
                        </div>
                        <p className="text-[15px] text-[#b0b0b0] leading-relaxed line-clamp-2">
                          {prevCard.text}
                        </p>
                      </div>
                      <div className="absolute inset-0 rounded-2xl bg-white/55 backdrop-blur-[2px] flex items-center justify-center">
                        <span className="text-[14px] text-[#6b7280] font-medium">↩ 点击撤回</span>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                <div className="w-full">
                  <QuestionCard
                    questionText={currentQuestion.text}
                    questionNumber={currentQuestion.index}
                    questionKey={`${currentQuestion.index}-${tickRef.current}`}
                    busy={busy}
                    choices={["完全符合", "有差异"]}
                    seconds={currentQuestion.timeout_seconds}
                    previousAnswer={currentQuestion.previous_answer ?? undefined}
                    onSelect={handleAnswer}
                    onTimeout={handleQuestionTimeout}
                  />
                  <div className="mt-3 min-h-[32px]">
                    <AiCompanion hint={currentQuestion.ai_hint} />
                  </div>
                </div>
              </div>
            </div>
          </div>
          <SafeArea position="bottom" />
        </>
      )}

      {/* REPORT */}
      {phase === "report" && reportData && (
        <ReportPage
          reportData={reportData}
          testType={testType || "成人"}
          isBackup={isBackup}
          onRestart={handleRestart}
          onBackupTest={handleBackupTest}
        />
      )}
    </div>
  );
}
