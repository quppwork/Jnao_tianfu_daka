import { useState, useEffect } from "react";
import { SafeArea } from "antd-mobile";
import { AnimatePresence, motion } from "motion/react";
import { LoginPage } from "./pages/LoginPage";
import { TalentPage } from "./pages/TalentPage";
import { HomePage } from "./pages/home/HomePage";
import { MinePage } from "./pages/mine/MinePage";
import { BottomNav } from "./components/BottomNav";
import type { HistoryEntry } from "./lib/historyStore";

const LOGIN_KEY = "jnao_logged_in";

type Stage = "splash" | "app";
type Page = "login" | "home" | "talent";
type Tab = "home" | "mine";

function isLoggedIn(): boolean {
  try { return sessionStorage.getItem(LOGIN_KEY) === "1"; } catch { return false; }
}

export function App() {
  const [stage, setStage] = useState<Stage>("splash");
  const [page, setPage] = useState<Page>(() => isLoggedIn() ? "home" : "login");
  const [tab, setTab] = useState<Tab>("home");
  const [pageKey, setPageKey] = useState(0);
  const [isReturning, setIsReturning] = useState(false);

  useEffect(() => {
    const splash = document.getElementById("initial-splash");
    const fast = splash?.getAttribute("data-fast") === "1";
    const delay = fast ? 1100 : 2200;
    const t = setTimeout(() => {
      if (splash) {
        splash.classList.add("fade-out");
        setTimeout(() => splash.remove(), 400);
      }
      setStage("app");
    }, delay);
    return () => clearTimeout(t);
  }, []);

  const navigateTo = (p: Page) => {
    setPage(p);
    setPageKey((k) => k + 1);
  };

  const handleLogin = () => {
    try { sessionStorage.setItem(LOGIN_KEY, "1"); } catch { /* ignore */ }
    navigateTo("home");
  };

  const handleStartTest = () => {
    setIsReturning(false);
    navigateTo("talent");
  };

  const handleExitTalent = () => {
    navigateTo("home");
  };

  const handleViewReport = (entry: HistoryEntry) => {
    try {
      sessionStorage.setItem("savedReport", JSON.stringify({
        reportData: entry.response,
        testType: entry.type === 0 ? "成人" : "孩子",
        isBackup: false,
      }));
    } catch { /* ignore */ }
    setIsReturning(false);
    navigateTo("talent");
  };

  return (
    <div className="phone-screen relative">
      <div className="flex flex-col h-full w-full max-w-[480px] mx-auto bg-white">
      <AnimatePresence mode="wait">
        {stage === "app" && (
          <motion.div
            key="app"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4, delay: 0.15 }}
            className="flex flex-col h-full"
          >
            <SafeArea position="top" />
            <header className="flex items-center justify-center h-11 bg-white border-b border-[#f0f0f0] shrink-0">
              <span className="text-lg font-semibold text-[#1f2937]">
                <span className="text-[#dc2626]">J</span>nao AI
              </span>
            </header>
            <main className="flex-1 flex flex-col overflow-y-auto min-h-0 no-scrollbar">
              <AnimatePresence mode="wait">
                {page === "login" && (
                  <LoginPage key={`login-${pageKey}`} onLogin={handleLogin} />
                )}

                {page === "home" && (
                  <motion.div
                    key={`home-${pageKey}`}
                    className="flex flex-col flex-1"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <div className="flex-1 flex flex-col min-h-0 overflow-y-auto no-scrollbar">
                      {tab === "home" && <HomePage onStartTest={handleStartTest} />}
                      {tab === "mine" && <MinePage onViewReport={handleViewReport} />}
                    </div>
                    <BottomNav active={tab} onNavigate={setTab} />
                  </motion.div>
                )}

                {page === "talent" && (
                  <TalentPage
                    key={`talent-${pageKey}`}
                    isReturning={isReturning}
                    onExit={handleExitTalent}
                  />
                )}
              </AnimatePresence>
            </main>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
    </div>
  );
}
