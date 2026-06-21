import { motion } from "motion/react";
import { TalentTest } from "../projects/talent";

interface Props {
  isReturning: boolean;
  onExit: () => void;
}

export function TalentPage({ isReturning, onExit }: Props) {
  return (
    <motion.div
      className="flex-1 flex flex-col"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 30, scale: 0.97 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
    >
      <TalentTest isReturning={isReturning} onExit={onExit} />
    </motion.div>
  );
}
