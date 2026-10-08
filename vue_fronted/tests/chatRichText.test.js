import { beforeAll, describe, it, expect } from 'vitest'
import {
  renderLatexInPlainText,
  formatQaRichHtml,
  formatGuideRichHtml,
  sanitizeGuideReply,
  escapeHtml,
  wrapBareLatex,
  looksLikeMathLine,
  collapseMultilineDisplayMath,
  buildLatexRepairCandidates,
  prefetchKatex,
} from '../src/utils/chatRichText.js'

describe('chatRichText', () => {
  beforeAll(async () => {
    await prefetchKatex()
  })

  it('escapeHtml 转义尖括号', () => {
    expect(escapeHtml('<script>')).toBe('&lt;script&gt;')
  })

  it('wrapBareLatex 包住 Navier-Stokes 裸公式行', () => {
    const raw = `它大概是这个形式：
\\rho\\frac{D\\mathbf{u}}{Dt} = -\\nabla p +
\\mu\\nabla^2\\mathbf{u} + \\mathbf{f}
拆开看：
- \\rho \\frac{Du}{Dt}：一小团流体的质量`
    expect(looksLikeMathLine('\\rho\\frac{D\\mathbf{u}}{Dt} = -\\nabla p +')).toBe(true)
    const wrapped = wrapBareLatex(raw)
    expect(wrapped).toContain('$$')
    expect(wrapped).toMatch(/\$\\rho\s*\\frac\{Du\}\{Dt\}\$/)
  })

  it('formatQaRichHtml 渲染裸公式为 katex', () => {
    const raw =
      '\\rho\\frac{D\\mathbf{u}}{Dt} = -\\nabla p +\n\\mu\\nabla^2\\mathbf{u} + \\mathbf{f}'
    const html = formatQaRichHtml(raw)
    expect(html).toContain('katex-display')
    expect(html).toContain('qa-math')
    // 可见层已渲染；MathML annotation 里仍会保留源 TeX，不算失败
    expect(html).toContain('katex-html')
  })

  it('renderLatexInPlainText 渲染 \\( x \\)', () => {
    const html = renderLatexInPlainText('原价每本 \\( x \\) 元')
    expect(html).toContain('katex')
    expect(html).not.toContain('\\(')
    expect(html).toContain('原价每本')
    expect(html).toContain('元')
  })

  it('多行 \\[...\\] 收拢后不露出定界符', () => {
    const raw = `由正弦定理：
\\[
a = \\frac{c\\sin A}{\\sin C},\\quad b = \\frac{c\\sin B}{\\sin C}
\\]
面积：
\\[
S=\\frac12 ab\\sin C
\\]`
    const collapsed = collapseMultilineDisplayMath(raw)
    expect(collapsed).not.toMatch(/\\\[/)
    expect(collapsed).not.toMatch(/\\\]/)
    expect(collapsed).toContain('$$')
    const html = formatQaRichHtml(raw)
    expect(html).toContain('qa-math')
    expect(html).toContain('katex-display')
    // 可见层不应再出现裸定界符
    expect(html.replace(/annotation[\s\S]*?<\/annotation>/g, '')).not.toContain('\\[')
    expect(html.replace(/annotation[\s\S]*?<\/annotation>/g, '')).not.toContain('\\]')
  })

  it('截断半截 \\frac 会修复后再渲染，不露源码', () => {
    const broken = 'S=\\frac12 ab\\sin C=\\frac12\\cdot\\frac{c\\sin'
    const candidates = buildLatexRepairCandidates(broken)
    expect(candidates.some((c) => c.includes('S=\\frac12 ab\\sin C') && !c.includes('\\frac{c\\sin'))).toBe(
      true,
    )
    const html = formatQaRichHtml(`\\[\n${broken}\n\\]`)
    expect(html).toContain('qa-math')
    expect(html).toContain('katex-display')
    expect(html).not.toContain('katex-error')
    const visible = html.replace(/annotation[\s\S]*?<\/annotation>/g, '')
    expect(visible).not.toContain('\\frac{c\\sin')
    expect(visible).not.toContain('\\frac12 ab\\sin')
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

  it('renderLatexInPlainText 未闭合 $ 不卡死且保留原文', () => {
    const html = renderLatexInPlainText('价格约 $2980 元')
    expect(html).toContain('2980')
    expect(html).toContain('价格约')
    expect(html).toContain('元')
  })

  it('加粗内裸 LaTeX 不吞 **，可渲染', () => {
    const raw = '对 **\\ln \\frac{x}{2 - x}** 求导，先令 **u = \\frac{x}{2 - x}**'
    const wrapped = wrapBareLatex(raw)
    // 正确形态：**$…$**，而不是 $…**$
    expect(wrapped).toContain('**$\\ln')
    expect(wrapped).toContain('}$**')
    expect(wrapped).not.toContain('$**$')
    const html = formatQaRichHtml(raw)
    expect(html).toContain('katex-html')
    expect(html).toContain('<strong>')
  })

  it('行内 $b=0$ 在加粗里可渲染', () => {
    const html = formatQaRichHtml('先带你过第(1)问：**$b=0$，且 $f(x)\\ge 0$，求 $a$ 的最小**值。')
    expect(html).toContain('katex-html')
    expect(html).not.toContain('$b=0$')
  })

  it('整行 ** 章节里的行内公式可渲染', () => {
    const html = formatQaRichHtml(
      '**先带你过第(1)问：$b=0$，且 $f(x)\\ge 0$，求 $a$ 的最小值。**',
    )
    expect(html).toContain('qa-sec')
    expect(html).toContain('katex-html')
    expect(html).toContain('qa-math-inline')
    expect(html).not.toContain('$b=0$')
    // 可见 HTML 层已渲染 ≥；annotation 里仍可有源 TeX
    expect(html).toContain('≥')
  })

  it('分隔线 --- 渲染为 qa-hr', () => {
    const html = formatQaRichHtml('上文\n---\n下文')
    expect(html).toContain('qa-hr')
    expect(html).toContain('上文')
    expect(html).toContain('下文')
  })

  it('jnao-svg 围栏渲染为 qa-sketch', () => {
    const raw = '见图：\n```jnao-svg\n<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>\n```\n完'
    const html = formatQaRichHtml(raw)
    expect(html).toContain('qa-sketch')
    expect(html).toContain('<svg')
    expect(html).not.toContain('jnao-svg')
  })

  it('formatGuideRichHtml 渲染 Markdown 表格', () => {
    const raw = `#### 4. 练习目标

| 学段 | 入门参考目标 |
| :--- | :--- |
| 小学 (1-3年级) | ≥1000 字 |
| 初中 | ≥1500 字 |`
    const html = formatGuideRichHtml(raw)
    expect(html).toContain('gd-table')
    expect(html).toContain('<th>')
    expect(html).toContain('<td>')
    expect(html).toContain('小学 (1-3年级)')
    expect(html).not.toContain('| :---')
  })
})
