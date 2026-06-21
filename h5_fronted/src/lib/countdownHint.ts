export function isCountdownUrgent(secondsLeft: number): boolean {
  return secondsLeft <= 3;
}

export function countdownHintText(secondsLeft: number, total: number): string {
  if (secondsLeft <= 3) return "快选一个，凭直觉就好～";
  if (secondsLeft <= 5) return "不用想太多，想到就选～";
  if (secondsLeft <= 7) return "放松心情，随心作答";
  return "根据真实经历，选「是」或「不是」";
}
