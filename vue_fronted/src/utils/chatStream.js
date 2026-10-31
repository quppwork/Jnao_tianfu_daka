/** 判断是否为前端主动中止流式输出 */
export function isStreamAborted(err) {
  return err?.name === 'AbortError' || err?.message === 'Aborted'
}

const STOPPED_HINT = '\n\n（已停止生成）'

/** 在 AI 气泡末尾追加「已停止」提示（避免重复） */
export function applyStreamStoppedHint(messages, aiIdx) {
  const msg = messages.value?.[aiIdx]
  if (!msg) return
  const text = String(msg.text || '').trim()
  if (!text) {
    msg.text = '（已停止生成）'
  } else if (!msg.text.includes('已停止生成')) {
    msg.text += STOPPED_HINT
  }
}
