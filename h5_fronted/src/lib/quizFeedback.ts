const ACK_FALLBACK = [
  "好哒，收到～",
  "嗯嗯，随心想就好",
  "棒，继续！",
  "收到，下一题～",
  "不错，跟着感觉走",
  "妥，继续下一题～",
  "好嘞！",
  "懂你～",
];

const MILESTONES: Record<number, string> = {
  5: "前五题搞定啦！你答得很顺，继续保持「想到就选」～",
  15: "已经过半咯！你一直在真实地表达自己，超棒的！",
  25: "还剩不到三分之一啦～不用加速，保持随心作答的节奏就好。",
  35: "全部完成！谢谢你真诚地分享自己，解读马上就来～",
};

export function randomAck(): string {
  return ACK_FALLBACK[Math.floor(Math.random() * ACK_FALLBACK.length)];
}

export function milestoneFor(n: number): string | undefined {
  return MILESTONES[n];
}
