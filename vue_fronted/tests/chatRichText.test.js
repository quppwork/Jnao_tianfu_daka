import { describe, it, expect } from 'vitest'
import {
  renderLatexInPlainText,
  formatQaRichHtml,
  formatGuideRichHtml,
  sanitizeGuideReply,
  escapeHtml,
} from '../src/utils/chatRichText.js'

describe('chatRichText', () => {
  it('escapeHtml 转义尖括号', () => {
    expect(escapeHtml('<script>')).toBe('&lt;script&gt;')
  })

  it('renderLatexInPlainText 渲染 \\( x \\)', () => {
    const html = renderLatexInPlainText('原价每本 \\( x \\) 元')
    expect(html).toContain('katex')
    expect(html).not.toContain('\\(')
    expect(html).toContain('原价每本')
    expect(html).toContain('元')
  })

  it('renderLatexInPlainText 渲染 $x$ 与 $$ 块级', () => {
    const inline = renderLatexInPlainText('设 $x=2$')
    expect(inline).toContain('katex')
    const block = renderLatexInPlainText('$$\\frac{1}{2}$$')
    expect(block).toContain('katex-display')
  })

  it('formatQaRichHtml 整段应用题含公式', () => {
    const raw =
      '某文具店促销，原价每本 \\( x \\) 元的笔记本，求 \\( x \\)。'
    const html = formatQaRichHtml(raw)
    expect(html).toContain('qa-line')
    expect(html).toContain('katex')
    expect(html.split('katex').length).toBeGreaterThan(2)
    expect(html).not.toContain('\\(')
  })

  it('formatQaRichHtml 保留 ** 加粗', () => {
    const html = formatQaRichHtml('**步骤一**：先化简')
    expect(html).toContain('<strong>步骤一</strong>')
  })

  it('sanitizeGuideReply 去掉知识库开头', () => {
    const t = sanitizeGuideReply('根据知识库中的信息，关于「五者天赋」。五者指…')
    expect(t).toBe('五者指…')
  })

  it('formatGuideRichHtml 渲染标题与列表', () => {
    const raw = `### 1. 五者天赋

**思者**

- 观察力强
- 逻辑清晰

1. 学者
2. 行者`
    const html = formatGuideRichHtml(raw)
    expect(html).toContain('gd-h3')
    expect(html).toContain('gd-sec')
    expect(html).toContain('gd-ul')
    expect(html).toContain('gd-ol')
    expect(html).toContain('思者')
  })
})
