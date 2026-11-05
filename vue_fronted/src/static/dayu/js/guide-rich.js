/**
 * 咨询页等静态 HTML 复用首页引导同款 Markdown→HTML。
 * 与 vue_fronted/src/utils/chatRichText.js 的 formatGuideRichHtml 对齐（无 KaTeX）。
 */
(function (global) {
  'use strict';

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function sanitizeGuideReply(raw) {
    var t = String(raw || '').trim();
    t = t.replace(/^根据(?:知识库|视频解析|视频|资料|检索结果)[^，。\n]{0,56}[，。]\s*/u, '');
    t = t.replace(
      /^关于[「『""'][^」』""']{1,32}[」』""'][^，。\n]{0,20}[，。]\s*/u,
      '',
    );
    return t.trim();
  }

  function normalizeMdMarkers(text) {
    return String(text || '')
      .replace(/\uFF0A/g, '*')
      .replace(/\uFF03/g, '#')
      .replace(/\*(?:[\u200B\u200C\u200D\uFEFF]+)\*/g, '**');
  }

  function guideInline(text) {
    var html = escapeHtml(String(text || ''));
    // 允许 ** 内侧空格（百炼常见：`** “标题” **`）
    html = html.replace(/\*\*\s*(.+?)\s*\*\*/g, '<strong>$1</strong>');
    // 不用 lookbehind：旧 WebView 抛错 → report-v3 richHtml 回退 esc，星号原样露出
    html = html.replace(/(^|[\s，。；：、])\*(?!\*)([^*\n]+?)\*(?!\*)/g, '$1<em>$2</em>');
    // 加粗/斜体转换后仍残留的 * 一律去掉（天赋对话几乎无数学乘号）
    html = html.replace(/\*/g, '');
    return html;
  }

  function isGuideTableRow(line) {
    var t = String(line || '').trim();
    if (!t.startsWith('|')) return false;
    return (t.match(/\|/g) || []).length >= 2;
  }

  function isGuideTableSeparator(line) {
    var t = String(line || '').trim();
    if (!isGuideTableRow(t)) return false;
    var cells = t.replace(/^\|/, '').replace(/\|$/, '').split('|');
    return cells.length > 0 && cells.every(function (c) {
      return /^:?-{3,}:?$/.test(c.trim());
    });
  }

  function splitGuideTableCells(line) {
    var t = String(line || '').trim();
    if (t.startsWith('|')) t = t.slice(1);
    if (t.endsWith('|')) t = t.slice(0, -1);
    return t.split('|').map(function (c) { return c.trim(); });
  }

  function isGuideBlockStart(line) {
    var t = String(line || '').trim();
    if (!t) return false;
    if (/^(-{3,}|\*{3,})$/.test(t)) return true;
    if (/^#{1,6}\s+/.test(t)) return true;
    if (/^[-*•]\s+/.test(t)) return true;
    if (/^\d+[.、)\]]\s+/.test(t)) return true;
    if (t.startsWith('>')) return true;
    if (/^(?:[^*\n]{1,8}\s+)?\*\*\s*.+\s*\*\*\s*[:：]?$/.test(t)) return true;
    if (isGuideTableRow(t)) return true;
    return false;
  }

  function renderGuideTable(rows) {
    if (!rows.length) return '';
    var bodyRows = rows.filter(function (r) { return !isGuideTableSeparator(r); });
    if (!bodyRows.length) return '';
    var headCells = splitGuideTableCells(bodyRows[0]);
    var dataRows = bodyRows.slice(1);
    var thead =
      '<thead><tr>' +
      headCells.map(function (c) { return '<th>' + guideInline(c) + '</th>'; }).join('') +
      '</tr></thead>';
    var tbody = '';
    if (dataRows.length) {
      tbody =
        '<tbody>' +
        dataRows
          .map(function (r) {
            var cells = splitGuideTableCells(r);
            while (cells.length < headCells.length) cells.push('');
            return (
              '<tr>' +
              cells
                .slice(0, headCells.length)
                .map(function (c) { return '<td>' + guideInline(c) + '</td>'; })
                .join('') +
              '</tr>'
            );
          })
          .join('') +
        '</tbody>';
    }
    return '<div class="gd-table-wrap"><table class="gd-table">' + thead + tbody + '</table></div>';
  }

  function formatGuideRichHtml(raw) {
    if (!raw) return '';
    var lines = normalizeMdMarkers(sanitizeGuideReply(raw))
      .replace(/\r\n/g, '\n')
      .split('\n');
    var out = [];
    var i = 0;

    while (i < lines.length) {
      var trimmed = lines[i].trim();
      if (!trimmed) {
        i += 1;
        continue;
      }

      if (/^(-{3,}|\*{3,})$/.test(trimmed)) {
        out.push('<hr class="gd-hr" />');
        i += 1;
        continue;
      }

      var heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
      if (heading) {
        var level = Math.min(heading[1].length, 4);
        out.push(
          '<h' + level + ' class="gd-h gd-h' + level + '">' +
            guideInline(heading[2]) +
            '</h' + level + '>',
        );
        i += 1;
        continue;
      }

      var section = trimmed.match(
        /^(?:[^*\n]{1,8}\s+)?\*\*\s*(.+?)\s*\*\*\s*[:：]?$/,
      );
      if (section) {
        out.push('<div class="gd-sec">' + guideInline(section[1]) + '</div>');
        i += 1;
        continue;
      }

      if (trimmed.startsWith('>')) {
        var quoteLines = [];
        while (i < lines.length && lines[i].trim().startsWith('>')) {
          quoteLines.push(lines[i].trim().replace(/^>\s?/, ''));
          i += 1;
        }
        out.push(
          '<blockquote class="gd-quote">' +
            quoteLines.map(function (l) { return '<p>' + guideInline(l) + '</p>'; }).join('') +
            '</blockquote>',
        );
        continue;
      }

      if (isGuideTableRow(trimmed)) {
        var tableRows = [];
        while (i < lines.length && isGuideTableRow(lines[i].trim())) {
          tableRows.push(lines[i].trim());
          i += 1;
        }
        out.push(renderGuideTable(tableRows));
        continue;
      }

      if (/^[-*•]\s+/.test(trimmed)) {
        var ulItems = [];
        while (i < lines.length && /^[-*•]\s+/.test(lines[i].trim())) {
          ulItems.push(lines[i].trim().replace(/^[-*•]\s+/, ''));
          i += 1;
        }
        out.push(
          '<ul class="gd-ul">' +
            ulItems.map(function (it) { return '<li>' + guideInline(it) + '</li>'; }).join('') +
            '</ul>',
        );
        continue;
      }

      // 1. **标题** + 后续说明段 → 小节标题 + 段落（咨询 AI 常见写法）
      var numberedTitle = trimmed.match(/^(\d+)[.、)\]]\s+(\*\*.+?\*\*)\s*$/);
      if (numberedTitle) {
        out.push(
          '<div class="gd-sec">' +
            escapeHtml(numberedTitle[1] + '. ') +
            guideInline(numberedTitle[2]) +
            '</div>',
        );
        i += 1;
        continue;
      }

      if (/^\d+[.、)\]]\s+/.test(trimmed)) {
        var olItems = [];
        while (i < lines.length && /^\d+[.、)\]]\s+/.test(lines[i].trim())) {
          // 若下一项是「纯标题」行，交回外层用 gd-sec
          if (/^\d+[.、)\]]\s+\*\*.+?\*\*\s*$/.test(lines[i].trim()) && olItems.length) break;
          if (/^\d+[.、)\]]\s+\*\*.+?\*\*\s*$/.test(lines[i].trim()) && !olItems.length) break;
          olItems.push(lines[i].trim().replace(/^\d+[.、)\]]\s+/, ''));
          i += 1;
        }
        if (olItems.length) {
          out.push(
            '<ol class="gd-ol">' +
              olItems.map(function (it) { return '<li>' + guideInline(it) + '</li>'; }).join('') +
              '</ol>',
          );
          continue;
        }
      }

      var para = [trimmed];
      i += 1;
      while (i < lines.length) {
        var next = lines[i].trim();
        if (!next || isGuideBlockStart(next)) break;
        para.push(next);
        i += 1;
      }
      out.push('<p class="gd-p">' + guideInline(para.join(' ')) + '</p>');
    }

    return out.join('');
  }

  global.formatGuideRichHtml = formatGuideRichHtml;
  global.__jnaoFormatGuideRichHtml = formatGuideRichHtml;
})(typeof window !== 'undefined' ? window : this);
