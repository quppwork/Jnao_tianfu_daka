import { useState } from "react";
import { motion } from "motion/react";

interface Props {
  onLogin: () => void;
}

export function LoginPage({ onLogin }: Props) {
  const [account, setAccount] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!account.trim() || !password.trim()) {
      setError("请输入账号和密码");
      return;
    }
    onLogin();
  };

  return (
    <motion.div
      className="flex flex-col items-center justify-start flex-1 px-8 pt-[33vh] bg-white"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      {/* 登录卡片 */}
      <motion.div
        className="w-full max-w-[300px] -translate-y-1/2"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25, duration: 0.6, ease: "easeOut" }}
      >
        <div className="bg-white rounded-2xl border border-[#f0f0f0] shadow-sm p-6">
        <p className="text-[17px] font-semibold text-[#1f2937] text-center mb-5">
          欢迎回来
        </p>

        <form onSubmit={handleSubmit}>
          <input
            type="text"
            value={account}
            onChange={(e) => setAccount(e.target.value)}
            placeholder="请输入账号"
            className="w-full h-12 px-4 text-[17px] text-[#1f2937] bg-[#f9fafb] border border-[#e5e7eb] rounded-xl outline-none focus:border-[#1677ff] focus:bg-white transition-all text-center mb-3"
          />

          <div className="relative">
            <input
              type="password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); setError(""); }}
              placeholder="请输入密码"
              autoFocus
              className="w-full h-12 px-4 text-[17px] text-[#1f2937] bg-[#f9fafb] border border-[#e5e7eb] rounded-xl outline-none focus:border-[#1677ff] focus:bg-white transition-all text-center tracking-widest"
            />
            {error && (
              <motion.p
                className="absolute -bottom-5 left-0 right-0 text-[#ef4444] text-sm text-center"
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
              >
                {error}
              </motion.p>
            )}
          </div>

          <motion.button
            type="submit"
            className="w-full h-12 mt-6 text-[17px] font-medium text-white bg-[#1f2937] rounded-xl active:bg-[#111827] transition-colors shadow-sm"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4, duration: 0.5, ease: "easeOut" }}
            whileTap={{ scale: 0.97 }}
          >
            登 录
          </motion.button>
        </form>
        </div>
      </motion.div>

      <motion.p
        className="text-[13px] text-[#d1d5db] mt-6 text-center"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6 }}
      >
        登录即代表您同意服务条款
      </motion.p>
    </motion.div>
  );
}
