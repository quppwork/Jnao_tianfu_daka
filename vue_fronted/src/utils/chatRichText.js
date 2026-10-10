/**
 * 聊天气泡富文本：Markdown 轻量语法 + KaTeX 公式
 * 支持 \( \)、\[ \]、$ $、$$ $$，以及模型常见的「裸 LaTeX」行/片段
 *
 * KaTeX 改为同步静态导入：手机微信里动态 import 分片常失败，
 * 失败时会退化成带青底的 `\(...\)` 源码胶囊（线上已踩坑）。
 */
import katex from 'katex'
import 'katex/dist/katex.min.css'

let katexMod = katex
let katexLoading = null
let katexCssLoaded = true
/** 加载完成后递增，页面可依赖此值触发 v-html 重算 */
let katexEpoch = 1

function loadKatexCss() {
  katexCssLoaded = true
}

export function getKatexEpoch() {
  return katexEpoch
}

export function isKatexReady() {
  return Boolean(katexMod)
}

/** 预热：答疑页 onMounted 应 await，并在完成后 bump 本地 ref 以重绘气泡 */
export function prefetchKatex() {
  loadKatexCss()
  if (katexMod) return Promise.resolve(katexMod)
  if (katexLoading) return katexLoading
  katexLoading = import('katex')
    .then((m) => {
      katexMod = m.default || m
      katexEpoch += 1
      return katexMod
    })
    .catch(() => {
      katexLoading = null
      return null
    })
  return katexLoading
}

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

function wrapMathHtml(html, displayMode) {
  return displayMode ? html : `<span class="qa-math-inline">${html}</span>`
}

function katexOpts(displayMode, throwOnError) {
  return {
    displayMode,
    throwOnError,
    strict: 'ignore',
    trust: false,
    errorColor: 'inherit',
  }
}

function closeUnbalancedLatex(tex) {
  let s = String(tex || '')
  let depth = 0
  for (let i = 0; i < s.length; i += 1) {
    const ch = s[i]
    if (ch === '{' && s[i - 1] !== '\\') depth += 1
    else if (ch === '}' && s[i - 1] !== '\\') depth = Math.max(0, depth - 1)
  }
  if (depth > 0) s += '}'.repeat(depth)
  const lefts = (s.match(/\\left\b/g) || []).length
  const rights = (s.match(/\\right\b/g) || []).length
  if (lefts > rights) s += '\\right.'.repeat(lefts - rights)
  return s
}

/** 去掉末尾半截命令 / 只写了分子的 \frac，便于二次渲染 */
function stripTrailingBrokenLatex(tex) {
  let s = String(tex || '').trim()
  if (!s) return s
  // 未闭合的 \frac{... 或 \sqrt{...
  s = s.replace(/\\(?:frac|dfrac|tfrac|binom|sqrt)\s*\{[^{}]*$/u, '')
  // 已补全 } 但仍缺分母：\frac{num} 结尾
  s = s.replace(/\\(?:frac|dfrac|tfrac|binom)\s*\{[^{}]*\}\s*$/u, '')
  // 尾部悬挂运算符
  s = s.replace(/(?:\\cdot|\\times|\\div|\\pm|\\mp|\+|=|-|\/|,|;|:|\.|·|⋅)\s*$/u, '')
  // 尾部半截控制字（如 \si）
  s = s.replace(/\\[a-zA-Z]{1,2}$/u, '')
  return s.trim()
}

/**
 * 失败公式的修复候选：原串 → 补括号 → 砍半截 → 按 = 取最长前缀。
 * 供 renderTex 依次试渲染，第一个成功的用于展示。
 */
export function buildLatexRepairCandidates(tex) {
  const raw = String(tex || '').trim()
  const out = []
  const push = (v) => {
    const t = String(v || '').trim()
    if (t && !out.includes(t)) out.push(t)
  }
  push(raw)
  push(closeUnbalancedLatex(raw))

  let cur = closeUnbalancedLatex(raw)
  for (let i = 0; i < 4; i += 1) {
    const next = closeUnbalancedLatex(stripTrailingBrokenLatex(cur))
    if (!next || next === cur) break
    push(next)
    cur = next
  }

  const parts = raw.split('=')
  if (parts.length > 1) {
    for (let n = parts.length - 1; n >= 1; n -= 1) {
      const prefix = parts.slice(0, n).join('=').trim()
      push(closeUnbalancedLatex(prefix))
      push(closeUnbalancedLatex(stripTrailingBrokenLatex(prefix)))
    }
  }
  return out
}

function renderTex(tex, displayMode) {
  const body = String(tex || '').trim()
  if (!body) return ''
  if (!katexMod) {
    prefetchKatex()
    const fallback = escapeHtml(displayMode ? `\\[${body}\\]` : `\\(${body}\\)`)
    return displayMode ? fallback : `<span class="qa-math-inline">${fallback}</span>`
  }

  const candidates = buildLatexRepairCandidates(body)
  for (const candidate of candidates) {
    try {
      const html = katexMod.renderToString(candidate, katexOpts(displayMode, true))
      if (html && !html.includes('katex-error')) {
        return wrapMathHtml(html, displayMode)
      }
    } catch {
      /* try next */
    }
  }

  // 仍失败：软渲染最长候选（不抛），避免红字源码胶囊
  for (let i = candidates.length - 1; i >= 0; i -= 1) {
    try {
      const html = katexMod.renderToString(candidates[i], katexOpts(displayMode, false))
      if (html && !html.includes('katex-error')) {
        return wrapMathHtml(html, displayMode)
      }
    } catch {
      /* continue */
    }
  }
  return ''
}

/** 整行是否像「裸公式」（无 $ 定界、几乎无中文） */
export function looksLikeMathLine(line) {
  const t = String(line || '').trim()
  if (!t) return false
  if (/\$|\\\(|\\\[|\\\]|\\\)/.test(t)) return false
  if (!/\\[a-zA-Z]/.test(t)) return false
  const zh = (t.match(/[\u4e00-\u9fff]/g) || []).length
  if (zh > 4) return false
  return /[=]|\\frac|\\nabla|\\sum|\\int|\\mathbf|\\mathrm|\\partial|\\begin|\\left|\\right|\\vec|\\hat|\\dot|\\bar/.test(
    t,
  ) || ((t.match(/\\[a-zA-Z]+/g) || []).length >= 2 && zh === 0)
}

/**
 * 多行 \[...\] / $$...$$ 收成单行 $$...$$。
 * formatQaRichHtml 按行排版，若不收拢，定界符 \[ \] 会单独成行露在公式框外。
 */
export function collapseMultilineDisplayMath(text) {
  let s = String(text || '').replace(/\r\n/g, '\n')
  const toDisplay = (body) => {
    const inner = String(body || '').trim().replace(/\s*\n\s*/g, ' ')
    return inner ? `$$${inner}$$` : ''
  }
  // \[ ... \]（可跨行；非贪婪）
  s = s.replace(/\\\[([\s\S]*?)\\\]/g, (_, body) => toDisplay(body))
  // 已是 $$...$$ 但跨多行 → 压成单行，便于后面的 displayOnly 匹配
  s = s.replace(/\$\$([\s\S]*?)\$\$/g, (_, body) => toDisplay(body))
  return s
}

/** 全角 $、常见转义定界 → ASCII，避免行内公式扫不到 */
export function normalizeMathDelimiters(text) {
  return collapseMultilineDisplayMath(
    String(text || '')
      .replace(/\uFF04/g, '$')
      .replace(/＄/g, '$')
      .replace(/\\\$/g, '$'),
  )
}

/**
 * 模型常写 **\frac{...}**（加粗包裸公式）。先把粗体内的裸 LaTeX 包成 $…$，
 * 避免后面扫描把闭合 ** 吞进公式（会变成乱码 $…**$）。
 */
function wrapBareLatexInsideBold(line) {
  return String(line || '').replace(/\*\*((?:(?!\*\*).)+?)\*\*/g, (full, inner) => {
    const t = String(inner || '').trim()
    if (!t) return full
    // 已有定界则只做内层裸片段修补
    if (/\$|\\\(|\\\[/.test(t)) {
      return `**${wrapInlineBareLatex(t)}**`
    }
    if (/\\[a-zA-Z]/.test(t) || /^[a-zA-Z]'?\s*=\s*\\/.test(t)) {
      const wrapped = wrapInlineBareLatex(t)
      // 整段像公式但未包上时，整包
      if (wrapped === t && /\\[a-zA-Z]/.test(t)) {
        return `**$${t}$**`
      }
      return `**${wrapped}**`
    }
    return full
  })
}

/**
 * 模型常不写 $…$：把裸公式行包成 $$，行内 \frac/\rho… 包成 $
 * 已有定界符的区域不改。
 */
export function wrapBareLatex(text) {
  const lines = normalizeMathDelimiters(text).replace(/\r\n/g, '\n').split('\n')
  const out = []
  let mathBuf = []
  const flushMath = () => {
    if (!mathBuf.length) return
    out.push(`$$${mathBuf.join(' ')}$$`)
    mathBuf = []
  }
  for (const line of lines) {
    if (looksLikeMathLine(line)) {
      mathBuf.push(line.trim())
      continue
    }
    flushMath()
    out.push(wrapInlineBareLatex(wrapBareLatexInsideBold(line)))
  }
  flushMath()
  return out.join('\n')
}

/** 在非定界区域，把连续 LaTeX 命令串包进 $…$ */
function wrapInlineBareLatex(line) {
  const src = String(line || '')
  if (!/\\[a-zA-Z]/.test(src)) return src
  // 已有完整定界则仍可能夹杂裸片段；统一走扫描
  let i = 0
  let out = ''
  while (i < src.length) {
    // 跳过已有定界块
    let skipped = false
    for (const rule of MATH_RULES) {
      if (!src.startsWith(rule.start, i)) continue
      const contentStart = i + rule.start.length
      const endIdx = src.indexOf(rule.end, contentStart)
      if (endIdx === -1) continue
      out += src.slice(i, endIdx + rule.end.length)
      i = endIdx + rule.end.length
      skipped = true
      break
    }
    if (skipped) continue

    // 跳过 markdown **，避免与公式交叉
    if (src.startsWith('**', i)) {
      out += '**'
      i += 2
      continue
    }

    if (src[i] === '\\' && /[a-zA-Z]/.test(src[i + 1] || '')) {
      const end = consumeBareLatexExpr(src, i)
      if (end > i) {
        const tex = src.slice(i, end).trim()
        out += `$${tex}$`
        i = end
        continue
      }
    }
    out += src[i]
    i += 1
  }
  return out
}

/** 从 \command 起吞掉一段裸公式（命令、括号、^_、运算符、空格） */
function consumeBareLatexExpr(src, start) {
  let i = start
  if (src[i] !== '\\') return start
  // 含 *：防止吞掉 markdown 的 ** 闭合符（否则出现 $…**$ 乱码）
  const stopAt = /[\u4e00-\u9fff：；。，、！？【】（）()「」""''：:*`]/
  while (i < src.length) {
    if (stopAt.test(src[i])) break
    if (src.startsWith('**', i)) break
    if (src[i] === '\\' && /[a-zA-Z]/.test(src[i + 1] || '')) {
      i += 1
      while (i < src.length && /[a-zA-Z]/.test(src[i])) i += 1
      continue
    }
    if (src[i] === '{') {
      let depth = 1
      i += 1
      while (i < src.length && depth > 0) {
        if (src[i] === '{') depth += 1
        else if (src[i] === '}') depth -= 1
        i += 1
      }
      if (depth !== 0) return start
      continue
    }
    if (src[i] === '^' || src[i] === '_') {
      i += 1
      if (src[i] === '{') continue
      if (i < src.length && /[a-zA-Z0-9'\\]/.test(src[i])) i += 1
      continue
    }
    // f'(x) 这类撇号
    if (src[i] === "'" || src[i] === '’') {
      i += 1
      continue
    }
    if (/[+\-=*/<>|,.]/.test(src[i])) {
      i += 1
      continue
    }
    if (/\s/.test(src[i])) {
      // 空格后若仍是公式续写则保留，否则结束
      let j = i + 1
      while (j < src.length && /\s/.test(src[j])) j += 1
      if (
        j < src.length &&
        (src[j] === '\\' || src[j] === '{' || src[j] === '^' || src[j] === '_' || /[+\-=]/.test(src[j]))
      ) {
        i = j
        continue
      }
      break
    }
    // 普通拉丁/数字可跟在公式里（如 Du Dt）
    if (/[a-zA-Z0-9]/.test(src[i])) {
      i += 1
      continue
    }
    break
  }
  // 太短或几乎不是公式
  const slice = src.slice(start, i)
  if (slice.length < 3 || !/\\[a-zA-Z]{2,}/.test(slice)) return start
  return i
}

/** 将 plain 文本中的 LaTeX 片段转为 KaTeX HTML，其余 escape */
export function renderLatexInPlainText(text) {
  if (!text) return ''
  let i = 0
  let out = ''
  const src = wrapBareLatex(String(text))

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
    // 未闭合定界符：当作普通字符吐出并前进，避免死循环卡死流式渲染
    if (nextSpecial === i) {
      out += escapeHtml(src[i])
      i += 1
      continue
    }
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

function normalizeMdMarkers(text) {
  // 模型偶发全角标记，先归一再解析
  return String(text || '')
    .replace(/\uFF0A/g, '*') // ＊
    .replace(/\uFF03/g, '#') // ＃
    .replace(/\u2014{3,}/g, '---') // ——— → hr
}

function applyInlineMarkdown(html) {
  let out = html
  // 先 ** 再单层 *斜体*，避免把 ** 拆坏
  out = out.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  out = out.replace(/(^|[\s，。；：、])\*(?!\*)([^*\n]+?)\*(?!\*)/g, '$1<em>$2</em>')
  out = out.replace(/`([^`\n]+)`/g, '<code class="qa-code">$1</code>')
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

/** 抽取 ```jnao-svg ... ```，只允许 svg 标签，防止 XSS */
function extractSafeSvgBlock(raw) {
  const t = String(raw || '').trim()
  if (!t.toLowerCase().startsWith('<svg') || !t.toLowerCase().includes('</svg>')) return ''
  // 去掉脚本与事件属性
  let s = t.replace(/<script[\s\S]*?<\/script>/gi, '')
  s = s.replace(/\son[a-z]+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '')
  s = s.replace(/javascript:/gi, '')
  return s
}

function qaInline(text) {
  return applyInlineMarkdown(renderLatexInPlainText(String(text || '')))
}

function renderQaTable(rows) {
  if (!rows.length) return ''
  const bodyRows = rows.filter((r) => !isGuideTableSeparator(r))
  if (!bodyRows.length) return ''
  const headCells = splitGuideTableCells(bodyRows[0])
  const dataRows = bodyRows.slice(1)
  const thead = `<thead><tr>${headCells
    .map((c) => `<th>${qaInline(c)}</th>`)
    .join('')}</tr></thead>`
  const tbody = dataRows.length
    ? `<tbody>${dataRows
        .map((r) => {
          const cells = splitGuideTableCells(r)
          while (cells.length < headCells.length) cells.push('')
          return `<tr>${cells
            .slice(0, headCells.length)
            .map((c) => `<td>${qaInline(c)}</td>`)
            .join('')}</tr>`
        })
        .join('')}</tbody>`
    : ''
  return `<div class="qa-table-wrap"><table class="qa-table">${thead}${tbody}</table></div>`
}

/** 生词行：词：across = 在……对面（无「词：」前缀时须含中文释义，避免误伤数学 a=1） */
function tryRenderVocabLine(trimmed) {
  const labeled = trimmed.match(/^(?:词|生词|单词|词汇)[：:]\s*(.+)$/u)
  const body = labeled ? labeled[1].trim() : trimmed
  const m = body.match(
    /^(?:\*\*)?([A-Za-z][A-Za-z\-']*)(?:\*\*)?(?:\s*[\/／]([^\/／]+)[\/／])?\s*[=＝:：]\s*(.+)$/u,
  )
  if (!m) return ''
  const word = m[1]
  const ipa = (m[2] || '').trim()
  const gloss = m[3].trim()
  if (!gloss) return ''
  if (!labeled) {
    if (word.length < 3) return ''
    if (!/[\u4e00-\u9fff]/.test(gloss)) return ''
  }
  return (
    `<div class="qa-vocab">` +
    `<span class="qa-vocab-word">${escapeHtml(word)}</span>` +
    (ipa ? `<span class="qa-vocab-ipa">/${escapeHtml(ipa)}/</span>` : '') +
    `<span class="qa-vocab-eq">=</span>` +
    `<span class="qa-vocab-gloss">${qaInline(gloss)}</span>` +
    `</div>`
  )
}

/** 学科答疑 AI 回复 → HTML（含公式、表格、原文引用、生词） */
export function formatQaRichHtml(raw) {
  if (!raw) return ''
  // 先规范化裸 LaTeX，再按行排版（$$ 块可能占一行）
  const lines = wrapBareLatex(normalizeMdMarkers(String(raw)))
    .replace(/\r\n/g, '\n')
    .split('\n')
  const out = []
  let li = 0
  while (li < lines.length) {
    const line = lines[li]
    const trimmed = line.trimEnd()
    const t = trimmed.trim()
    if (!t) {
      out.push('<div class="qa-gap"></div>')
      li += 1
      continue
    }
    // math_sketch 返回的 SVG 围栏
    if (/^```jnao-svg\s*$/i.test(t)) {
      const buf = []
      li += 1
      while (li < lines.length && !/^```\s*$/.test(lines[li].trim())) {
        buf.push(lines[li])
        li += 1
      }
      const svg = extractSafeSvgBlock(buf.join('\n'))
      if (svg) out.push(`<div class="qa-sketch">${svg}</div>`)
      li += 1
      continue
    }
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(t)) {
      out.push('<hr class="qa-hr" />')
      li += 1
      continue
    }
    // 流式未收拢时，单独成行的定界符直接丢掉，避免公式框外露出 \[ \]
    if (/^(\\\[|\\\]|\\\(|\\\))$/.test(t)) {
      li += 1
      continue
    }
    // Markdown ATX 标题：### Question 24
    const mdHeading = t.match(/^(#{1,6})\s+(.+)$/)
    if (mdHeading) {
      const level = Math.min(mdHeading[1].length, 4)
      out.push(`<div class="qa-sec qa-h qa-h${level}">${qaInline(mdHeading[2])}</div>`)
      li += 1
      continue
    }
    // Markdown 表格（外语阅读对照最常见）
    if (isGuideTableRow(t)) {
      const tableRows = []
      while (li < lines.length && isGuideTableRow(lines[li].trim())) {
        tableRows.push(lines[li].trim())
        li += 1
      }
      out.push(renderQaTable(tableRows))
      continue
    }
    // 原文/引用块：> 【原文 · Paragraph 2】…
    if (t.startsWith('>')) {
      const quoteLines = []
      while (li < lines.length && lines[li].trim().startsWith('>')) {
        quoteLines.push(lines[li].trim().replace(/^>\s?/, ''))
        li += 1
      }
      const joined = quoteLines.join('\n')
      const isSource = /原文|Paragraph|paragraph|Passage|passage|Text\s*\d/i.test(joined)
      const cls = isSource ? 'qa-source' : 'qa-quote'
      const label = isSource
        ? '<div class="qa-source-label">原文定位</div>'
        : ''
      out.push(
        `<div class="${cls}">${label}` +
          quoteLines.map((l) => `<p>${qaInline(l)}</p>`).join('') +
          `</div>`,
      )
      continue
    }
    // 无序列表
    if (/^[-*•]\s+/.test(t)) {
      const items = []
      while (li < lines.length && /^[-*•]\s+/.test(lines[li].trim())) {
        items.push(lines[li].trim().replace(/^[-*•]\s+/, ''))
        li += 1
      }
      out.push(
        `<ul class="qa-ul">${items.map((it) => `<li>${qaInline(it)}</li>`).join('')}</ul>`,
      )
      continue
    }
    // 有序列表：1. / 1、 / 1)
    if (/^\d+[.、)\]]\s+/.test(t)) {
      const items = []
      while (li < lines.length && /^\d+[.、)\]]\s+/.test(lines[li].trim())) {
        items.push(lines[li].trim().replace(/^\d+[.、)\]]\s+/, ''))
        li += 1
      }
      out.push(
        `<ol class="qa-ol">${items.map((it) => `<li>${qaInline(it)}</li>`).join('')}</ol>`,
      )
      continue
    }
    const header = t.match(/^\*\*(.+?)\*\*\s*[:：]?$/)
    if (header) {
      out.push(`<div class="qa-sec">${qaInline(header[1])}</div>`)
      li += 1
      continue
    }
    const challenge = trimmed.match(/^[（(]\s*小挑战[：:]\s*(.+?)[）)]\s*$/)
    if (challenge) {
      out.push(
        `<div class="qa-challenge"><span class="qa-challenge-label">小挑战</span>` +
          `<span class="qa-challenge-text">${qaInline(challenge[1])}</span></div>`,
      )
      li += 1
      continue
    }
    const vocabHtml = tryRenderVocabLine(trimmed.trim())
    if (vocabHtml) {
      out.push(vocabHtml)
      li += 1
      continue
    }
    const kv = trimmed.match(/^(.+?)\s*(?:->|→)\s*(.+)$/)
    if (kv && !trimmed.includes('**') && trimmed.length <= 80) {
      out.push(
        `<div class="qa-kv"><span class="qa-k">${qaInline(kv[1].trim())}</span>` +
          `<span class="qa-arrow">→</span>` +
          `<span class="qa-v">${qaInline(kv[2].trim())}</span></div>`,
      )
      li += 1
      continue
    }
    // $$…$$ 或 \[…\] 单独成行 → 块级公式容器
    const displayOnly =
      trimmed.match(/^\$\$([\s\S]+)\$\$$/) || trimmed.match(/^\\\[([\s\S]+)\\\]$/)
    if (displayOnly) {
      const mathHtml = renderTex(displayOnly[1], true)
      if (mathHtml) out.push(`<div class="qa-math">${mathHtml}</div>`)
      li += 1
      continue
    }
    let html = qaInline(trimmed)
    if (trimmed.includes(' + ') && /(主语|谓语|宾语|定语|状语)/.test(trimmed)) {
      out.push(`<div class="qa-struct">${html}</div>`)
      li += 1
      continue
    }
    out.push(`<div class="qa-line">${html}</div>`)
    li += 1
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
  if (/^#{1,6}\s+/.test(t)) return true
  if (/^[-*•]\s+/.test(t)) return true
  if (/^\d+[.、)\]]\s+/.test(t)) return true
  if (t.startsWith('>')) return true
  if (/^\*\*.+\*\*\s*[:：]?$/.test(t)) return true
  if (isGuideTableRow(t)) return true
  return false
}

function isGuideTableRow(line) {
  const t = String(line || '').trim()
  if (!t.startsWith('|')) return false
  // 至少两根竖线，避免误伤普通句子
  return (t.match(/\|/g) || []).length >= 2
}

function isGuideTableSeparator(line) {
  const t = String(line || '').trim()
  if (!isGuideTableRow(t)) return false
  const cells = t.replace(/^\|/, '').replace(/\|$/, '').split('|')
  return cells.length > 0 && cells.every((c) => /^:?-{3,}:?$/.test(c.trim()))
}

function splitGuideTableCells(line) {
  let t = String(line || '').trim()
  if (t.startsWith('|')) t = t.slice(1)
  if (t.endsWith('|')) t = t.slice(0, -1)
  return t.split('|').map((c) => c.trim())
}

function renderGuideTable(rows) {
  if (!rows.length) return ''
  const bodyRows = rows.filter((r) => !isGuideTableSeparator(r))
  if (!bodyRows.length) return ''
  const headCells = splitGuideTableCells(bodyRows[0])
  const dataRows = bodyRows.slice(1)
  const thead = `<thead><tr>${headCells
    .map((c) => `<th>${guideInline(c)}</th>`)
    .join('')}</tr></thead>`
  const tbody = dataRows.length
    ? `<tbody>${dataRows
        .map((r) => {
          const cells = splitGuideTableCells(r)
          while (cells.length < headCells.length) cells.push('')
          return `<tr>${cells
            .slice(0, headCells.length)
            .map((c) => `<td>${guideInline(c)}</td>`)
            .join('')}</tr>`
        })
        .join('')}</tbody>`
    : ''
  return `<div class="gd-table-wrap"><table class="gd-table">${thead}${tbody}</table></div>`
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

    const heading = trimmed.match(/^(#{1,6})\s+(.+)$/)
    if (heading) {
      // 气泡里 h1–h6 都支持；样式档位压到 1–4，避免字号过大
      const level = Math.min(heading[1].length, 4)
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

    if (isGuideTableRow(trimmed)) {
      const tableRows = []
      while (i < lines.length && isGuideTableRow(lines[i].trim())) {
        tableRows.push(lines[i].trim())
        i += 1
      }
      out.push(renderGuideTable(tableRows))
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
