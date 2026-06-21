import { useRef, useCallback } from "react";
import { DotLottieReact } from "@lottiefiles/dotlottie-react";
import type { DotLottie } from "@lottiefiles/dotlottie-web";

interface Props {
  src: string;
  className?: string;
}

export function HoverLottie({ src, className }: Props) {
  const dotLottieRef = useRef<DotLottie | null>(null);

  const playOnce = useCallback(() => {
    const dl = dotLottieRef.current;
    if (!dl) return;
    dl.stop();
    dl.play();
  }, []);

  return (
    <div
      className={className}
      onMouseEnter={playOnce}
      onTouchStart={playOnce}
    >
      <DotLottieReact
        src={src}
        autoplay
        loop={false}
        dotLottieRefCallback={(dl) => { dotLottieRef.current = dl; }}
      />
    </div>
  );
}
