/**
 * 簡易 Markdown → HTML 轉換（含表格支援）
 */

function escapeHtml(text) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/**
 * 將 markdown 表格區塊轉換為 HTML <table>
 * 支援 | col1 | col2 | 格式，含對齊 (---:, :---:, :---)
 */
function renderTables(text) {
  const lines = text.split('\n')
  const result = []
  let i = 0

  while (i < lines.length) {
    // 偵測表格：至少需要 header row + separator row
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

      i += 2 // skip header + separator
      while (i < lines.length && isTableRow(lines[i])) {
        const cells = parseRow(lines[i])
        tableHtml += '<tr>'
        cells.forEach((cell, idx) => {
          const align = aligns[idx] || ''
          const alignAttr = align ? ` style="text-align:${align}"` : ''
          // 允許 cell 內的 bold/inline-code
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
  // separator cells contain only -, :, |, spaces
  const inner = trimmed.slice(1, -1)
  return /^[\s\-:|]+$/.test(inner) && inner.includes('-')
}

function parseRow(line) {
  const trimmed = line.trim()
  // Remove leading and trailing |
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

/**
 * 主要的 markdown 渲染函數
 */
export function renderMd(text) {
  if (!text) return ''

  let html = escapeHtml(text)

  // Code blocks (先處理，避免內部被其他 regex 影響)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
    `<pre class="code-block"><code>${code.trim()}</code></pre>`)

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')

  // Tables（在 headers/lists 之前處理）
  html = renderTables(html)

  // Headers
  html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')

  // Bold + italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')

  // Links
  html = html.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g,
    '<a href="$2" target="_blank" rel="noreferrer">$1 ↗</a>'
  )

  // Standalone URLs (not inside href)
  html = html.replace(
    /(?<!["\(href=])(https?:\/\/[^\s<]+)/g,
    '<a href="$1" target="_blank" rel="noreferrer">$1</a>'
  )

  // Unordered list
  html = html.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>')
  html = html.replace(
    /(<li>[\s\S]*?<\/li>)(\n(?!<li)|\s*$)/g,
    '<ul>$1</ul>'
  )

  // Ordered list
  html = html.replace(/^\d+\. (.+)$/gm, '<li class="ol">$1</li>')
  html = html.replace(
    /(<li class="ol">[\s\S]*?<\/li>)(\n(?!<li)|\s*$)/g,
    '<ol>$1</ol>'
  )

  // Blockquote
  html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')

  // Horizontal rule
  html = html.replace(/^---$/gm, '<hr />')

  // Paragraphs
  html = html.replace(/\n\n/g, '</p><p>')
  html = html.replace(/\n/g, '<br>')
  html = `<p>${html}</p>`.replace(/<p>\s*<\/p>/g, '')

  return html
}
