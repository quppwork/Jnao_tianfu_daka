/**
 * 聊天气泡富文本：Markdown 轻量语法 + KaTeX 公式
 * 支持 \( \)、\[ \]、$ $、$$ $$
 */
import katex from 'katex'

export function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

const MATH_RULES = [
  { start: '$$', end: '$$', display: true },
  { start: '\\[', end: '\\]', display: true },
  { start: '\\(', end: '\\)', display: false },
  { start: '$', end: '$', display: false },
]

function renderTex(tex, displayMode) {
  try {
    return katex.renderToString(tex.trim(), {
      displayMode,
      throwOnError: false,
      strict: 'ignore',
      trust: false,
    })
  } catch {
    return escapeHtml(displayMode ? `\\[${tex}\\]` : `\\(${tex}\\)`)
  }
}

/** 将 plain 文本中的 LaTeX 片段转为 KaTeX HTML，其余 escape */
export function renderLatexInPlainText(text) {
  if (!text) return ''
  let i = 0
  let out = ''
  const src = String(text)

  while (i < src.length) {
    let matched = false
    for (const rule of MATH_RULES) {
      if (!src.startsWith(rule.start, i)) continue
      const contentStart = i + rule.start.length
      const endIdx = src.indexOf(rule.end, contentStart)
      if (endIdx === -1) continue
      out += renderTex(src.slice(contentStart, endIdx), rule.display)
      i = endIdx + rule.end.length
      matched = true
      break
    }
    if (matched) continue

    const nextSpecial = findNextDelimiterIndex(src, i)
    const chunkEnd = nextSpecial === -1 ? src.length : nextSpecial
    out += escapeHtml(src.slice(i, chunkEnd))
    i = chunkEnd
  }
  return out
}

function findNextDelimiterIndex(src, from) {
  let best = -1
  for (const rule of MATH_RULES) {
    const idx = src.indexOf(rule.start, from)
    if (idx !== -1 && (best === -1 || idx < best)) best = idx
  }
  return best
}

function applyInlineMarkdown(html) {
  let out = html
  out = out.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  out = out.replace(
    /\((主语|谓语|宾语|定语|状语|补语|表语)\)/g,
    '<span class="qa-tag">$1</span>',
  )
  out = out.replace(
    /（(主语|谓语|宾语|定语|状语|补语|表语)）/g,
    '<span class="qa-tag">$1</span>',
  )
  return out
}

/** 学科答疑 AI 回复 → HTML（含公式） */
export function formatQaRichHtml(raw) {
  if (!raw) return ''
  const lines = String(raw).replace(/\r\n/g, '\n').split('\n')
  const out = []
  for (const line of lines) {
    const trimmed = line.trimEnd()
    if (!trimmed.trim()) {
      out.push('<div class="qa-gap"></div>')
      continue
    }
    const header = trimmed.match(/^\*\*(.+?)\*\*\s*[:：]?$/)
    if (header) {
      out.push(`<div class="qa-sec">${escapeHtml(header[1])}</div>`)
      continue
    }
    const challenge = trimmed.match(/^[（(]\s*小挑战[：:]\s*(.+?)[）)]\s*$/)
    if (challenge) {
      out.push(
        `<div class="qa-challenge"><span class="qa-challenge-label">小挑战</span>` +
          `<span class="qa-challenge-text">${renderLatexInPlainText(challenge[1])}</span></div>`,
      )
      continue
    }
    const kv = trimmed.match(/^(.+?)\s*(?:->|→)\s*(.+)$/)
    if (kv && !trimmed.includes('**') && trimmed.length <= 80) {
      out.push(
        `<div class="qa-kv"><span class="qa-k">${renderLatexInPlainText(kv[1].trim())}</span>` +
          `<span class="qa-arrow">→</span>` +
          `<span class="qa-v">${renderLatexInPlainText(kv[2].trim())}</span></div>`,
      )
      continue
    }
    let html = renderLatexInPlainText(trimmed)
    html = applyInlineMarkdown(html)
    if (trimmed.includes(' + ') && /(主语|谓语|宾语|定语|状语)/.test(trimmed)) {
      out.push(`<div class="qa-struct">${html}</div>`)
      continue
    }
    out.push(`<div class="qa-line">${html}</div>`)
  }
  return out.join('')
}
