/**
 * Markdown → HTML 轉換（含表格、摘要卡片、Mermaid 流程圖支援）
 */

function escapeHtml(text) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

// ── Summary card ───────────────────────────────────────────
/**
 * :::summary
 * - 結論一
 * - 結論二
 * :::
 * → 轉成 <div class="summary-card">...</div>
 */
function renderSummaryBlocks(text) {
  return text.replace(
    /:::summary\s*\n([\s\S]*?):::/g,
    (_, content) => {
      const items = content
        .split('\n')
        .map(l => l.trim())
        .filter(l => l.length > 0)
        .map(l => l.replace(/^[-*]\s*/, ''))       // bullet: - or *
        .map(l => l.replace(/^\d+\.\s*/, ''))       // numbered: 1. 2. 3.
        .filter(l => l.length > 0)
        .map(l => {
          // allow bold inside summary items
          l = l.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
          return `<li>${l}</li>`
        })
        .join('')
      return `<div class="summary-card"><div class="summary-title">📋 關鍵結論</div><ul>${items}</ul></div>`
    }
  )
}

// ── Mermaid code blocks ────────────────────────────────────
/**
 * ```mermaid ... ```
 * → <div class="mermaid-block">...</div>
 * (rendered client-side by mermaid.js)
 */
function sanitizeMermaidCode(raw) {
  // 自動修正常見的 Mermaid 語法錯誤
  let fixed = raw
  // 移除標籤中的禁止符號
  fixed = fixed.replace(/\[([^\]]*)[#/≥≤²（）「」？]+([^\]]*)\]/g, (m, a, b) => `[${a}${b}]`)
  // 修正中文 ID（替換為英文 ID）
  const lines = fixed.split('\n')
  let idCounter = 0
  const idMap = {}
  const fixedLines = lines.map(line => {
    return line.replace(/([^\w\-]|^)([一-龥]+)(\[|\{)/g, (m, pre, zhId, bracket) => {
      if (!idMap[zhId]) {
        idMap[zhId] = `N${idCounter++}`
      }
      return `${pre}${idMap[zhId]}${bracket}`
    })
  })
  return fixedLines.join('\n')
}

function extractMermaidBlocks(text) {
  let counter = 0
  const validStarts = ['graph ', 'flowchart ', 'sequenceDiagram', 'classDiagram', 'stateDiagram', 'erDiagram', 'gantt', 'pie', 'gitGraph', 'mindmap', 'timeline']
  return text.replace(
    /```mermaid\s*\n([\s\S]*?)```/g,
    (_, code) => {
      counter++
      // Un-escape HTML entities so mermaid can parse
      let raw = code.trim()
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
      // Validate: must have content and start with a valid mermaid declaration
      const firstNonEmpty = raw.split('\n').find(l => l.trim())
      if (!raw || !firstNonEmpty || !validStarts.some(s => firstNonEmpty.trim().startsWith(s))) {
        // Not valid mermaid — render as plain code block
        return `<pre class="code-block"><code>${code.trim()}</code></pre>`
      }
      // 自動修正常見語法錯誤
      raw = sanitizeMermaidCode(raw)
      // Error boundary: 存放原始碼作為 fallback
      const escapedFallback = escapeHtml(raw).replace(/"/g, '&quot;')
      return `<div class="mermaid-block" data-mermaid-id="mmd-${counter}" data-mermaid-fallback="${escapedFallback}">${raw}</div>`
    }
  )
}

// ── Tables ─────────────────────────────────────────────────
function renderTables(text) {
  const lines = text.split('\n')
  const result = []
  let i = 0

  while (i < lines.length) {
    if (isTableRow(lines[i]) && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
      const headerCells = parseRow(lines[i])
      const aligns = parseAligns(lines[i + 1])
      let tableHtml = '<div class="table-wrap"><table><thead><tr>'
      headerCells.forEach((cell, idx) => {
        const align = aligns[idx] || ''
        const alignAttr = align ? ` style="text-align:${align}"` : ''
        tableHtml += `<th${alignAttr}>${cell.trim()}</th>`
      })
      tableHtml += '</tr></thead><tbody>'

      i += 2
      while (i < lines.length && isTableRow(lines[i])) {
        const cells = parseRow(lines[i])
        tableHtml += '<tr>'
        cells.forEach((cell, idx) => {
          const align = aligns[idx] || ''
          const alignAttr = align ? ` style="text-align:${align}"` : ''
          let cellHtml = cell.trim()
          cellHtml = cellHtml.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
          cellHtml = cellHtml.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
          tableHtml += `<td${alignAttr}>${cellHtml}</td>`
        })
        tableHtml += '</tr>'
        i++
      }
      tableHtml += '</tbody></table></div>'
      result.push(tableHtml)
    } else {
      result.push(lines[i])
      i++
    }
  }

  return result.join('\n')
}

function isTableRow(line) {
  if (!line) return false
  const trimmed = line.trim()
  return trimmed.startsWith('|') && trimmed.endsWith('|') && trimmed.includes('|')
}

function isTableSeparator(line) {
  if (!line) return false
  const trimmed = line.trim()
  if (!trimmed.startsWith('|') || !trimmed.endsWith('|')) return false
  const inner = trimmed.slice(1, -1)
  return /^[\s\-:|]+$/.test(inner) && inner.includes('-')
}

function parseRow(line) {
  const trimmed = line.trim()
  const inner = trimmed.startsWith('|') ? trimmed.slice(1) : trimmed
  const cleaned = inner.endsWith('|') ? inner.slice(0, -1) : inner
  return cleaned.split('|')
}

function parseAligns(line) {
  const cells = parseRow(line)
  return cells.map(cell => {
    const c = cell.trim()
    if (c.startsWith(':') && c.endsWith(':')) return 'center'
    if (c.endsWith(':')) return 'right'
    return 'left'
  })
}

// ── Main renderer ──────────────────────────────────────────
export function renderMd(text) {
  if (!text) return ''

  let html = escapeHtml(text)

  // 1. Mermaid code blocks (before general code blocks)
  html = extractMermaidBlocks(html)

  // 2. General code blocks
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
    `<pre class="code-block"><code>${code.trim()}</code></pre>`)

  // 3. Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')

  // 4. Summary blocks (before tables/headers)
  html = renderSummaryBlocks(html)

  // 5. Tables
  html = renderTables(html)

  // 6. Headers
  html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')

  // 7. Bold + italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')

  // 8. Links
  html = html.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g,
    '<a href="$2" target="_blank" rel="noreferrer">$1 ↗</a>'
  )

  // 9. Standalone URLs
  html = html.replace(
    /(?<!["\(href=])(https?:\/\/[^\s<]+)/g,
    '<a href="$1" target="_blank" rel="noreferrer">$1</a>'
  )

  // 10. Unordered list
  html = html.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>')
  html = html.replace(
    /(<li>[\s\S]*?<\/li>)(\n(?!<li)|\s*$)/g,
    '<ul>$1</ul>'
  )

  // 11. Ordered list
  html = html.replace(/^\d+\. (.+)$/gm, '<li class="ol">$1</li>')
  html = html.replace(
    /(<li class="ol">[\s\S]*?<\/li>)(\n(?!<li)|\s*$)/g,
    '<ol>$1</ol>'
  )

  // 12. Blockquote
  html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')

  // 13. Horizontal rule
  html = html.replace(/^---$/gm, '<hr />')

  // 14. Paragraphs
  html = html.replace(/\n\n/g, '</p><p>')
  html = html.replace(/\n/g, '<br>')
  html = `<p>${html}</p>`.replace(/<p>\s*<\/p>/g, '')

  return html
}
