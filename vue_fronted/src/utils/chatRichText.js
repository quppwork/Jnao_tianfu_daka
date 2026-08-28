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

/** 去掉百炼/KB 常见元信息开头，展示更像老师直接讲 */
export function sanitizeGuideReply(raw) {
  let t = String(raw || '').trim()
  t = t.replace(/^根据(?:知识库|视频解析|视频|资料|检索结果)[^，。\n]{0,56}[，。]\s*/u, '')
  t = t.replace(
    /^关于[「『""'][^」』""']{1,32}[」』""'][^，。\n]{0,20}[，。]\s*/u,
    '',
  )
  return t.trim()
}

function guideInline(text) {
  let html = renderLatexInPlainText(String(text || ''))
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/(?<!\*)\*([^*\n]+?)\*(?!\*)/g, '<em>$1</em>')
  return html
}

function isGuideBlockStart(line) {
  const t = String(line || '').trim()
  if (!t) return false
  if (/^(-{3,}|\*{3,})$/.test(t)) return true
  if (/^#{1,3}\s+/.test(t)) return true
  if (/^[-*•]\s+/.test(t)) return true
  if (/^\d+[.、)\]]\s+/.test(t)) return true
  if (t.startsWith('>')) return true
  if (/^\*\*.+\*\*\s*[:：]?$/.test(t)) return true
  return false
}

/** 首页引导 AI 回复 → DeepSeek 风格 HTML */
export function formatGuideRichHtml(raw) {
  if (!raw) return ''
  const lines = sanitizeGuideReply(raw).replace(/\r\n/g, '\n').split('\n')
  const out = []
  let i = 0

  while (i < lines.length) {
    const trimmed = lines[i].trim()
    if (!trimmed) {
      i += 1
      continue
    }

    if (/^(-{3,}|\*{3,})$/.test(trimmed)) {
      out.push('<hr class="gd-hr" />')
      i += 1
      continue
    }

    const heading = trimmed.match(/^(#{1,3})\s+(.+)$/)
    if (heading) {
      const level = heading[1].length
      out.push(`<h${level} class="gd-h gd-h${level}">${guideInline(heading[2])}</h${level}>`)
      i += 1
      continue
    }

    const section = trimmed.match(/^\*\*(.+?)\*\*\s*[:：]?$/)
    if (section) {
      out.push(`<div class="gd-sec">${guideInline(section[1])}</div>`)
      i += 1
      continue
    }

    if (trimmed.startsWith('>')) {
      const quoteLines = []
      while (i < lines.length && lines[i].trim().startsWith('>')) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ''))
        i += 1
      }
      out.push(
        `<blockquote class="gd-quote">${quoteLines
          .map((l) => `<p>${guideInline(l)}</p>`)
          .join('')}</blockquote>`,
      )
      continue
    }

    if (/^[-*•]\s+/.test(trimmed)) {
      const items = []
      while (i < lines.length && /^[-*•]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*•]\s+/, ''))
        i += 1
      }
      out.push(
        `<ul class="gd-ul">${items.map((it) => `<li>${guideInline(it)}</li>`).join('')}</ul>`,
      )
      continue
    }

    if (/^\d+[.、)\]]\s+/.test(trimmed)) {
      const items = []
      while (i < lines.length && /^\d+[.、)\]]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+[.、)\]]\s+/, ''))
        i += 1
      }
      out.push(
        `<ol class="gd-ol">${items.map((it) => `<li>${guideInline(it)}</li>`).join('')}</ol>`,
      )
      continue
    }

    const para = [trimmed]
    i += 1
    while (i < lines.length) {
      const next = lines[i].trim()
      if (!next || isGuideBlockStart(next)) break
      para.push(next)
      i += 1
    }
    out.push(`<p class="gd-p">${guideInline(para.join(' '))}</p>`)
  }

  return out.join('')
}
