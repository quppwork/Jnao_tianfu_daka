import type { QuizBgTheme } from "../lib/quizBackgrounds";
import { backgroundForQuestionIndex } from "../lib/quizBackgrounds";

interface Props {
  questionIndex: number;
  active: boolean;
  theme?: { id: number; name: string; gradient: string; blobs: [string, string, string] };
}

function BlobScene({ theme }: { theme: QuizBgTheme | { id: number; name: string; gradient: string; blobs: [string, string, string] } }) {
  const [b1, b2, b3] = theme.blobs;

  return (
    <div className="quiz-bg-fade absolute inset-0 overflow-hidden">
      <div className="absolute inset-0" style={{ background: theme.gradient }} />
      <div
        className="quiz-blob-1 absolute -top-[12%] -left-[18%] w-[60%] h-[50%] rounded-full opacity-40 blur-3xl"
        style={{ background: b1 }}
      />
      <div
        className="quiz-blob-2 absolute top-[40%] -right-[12%] w-[55%] h-[45%] rounded-full opacity-35 blur-3xl"
        style={{ background: b2 }}
      />
      <div
        className="quiz-blob-3 absolute -bottom-[8%] left-[18%] w-[50%] h-[42%] rounded-full opacity-30 blur-3xl"
        style={{ background: b3 }}
      />
      <div className="absolute inset-0 bg-white/20" />
    </div>
  );
}

export function QuizBackground({ questionIndex, active, theme }: Props) {
  if (!active) {
    return (
      <div className="absolute inset-0 pointer-events-none" aria-hidden>
        <div className="absolute inset-0 bg-white" />
      </div>
    );
  }

  const resolved = theme || backgroundForQuestionIndex(questionIndex);

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden>
      <div key={questionIndex} className="absolute inset-0">
        <BlobScene theme={resolved} />
      </div>
    </div>
  );
}
