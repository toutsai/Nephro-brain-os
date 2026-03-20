let mermaidInstance = null
let initPromise = null

const CDN_URL = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs'

async function getMermaid() {
  if (mermaidInstance) return mermaidInstance
  if (initPromise) return initPromise

  initPromise = import(/* @vite-ignore */ CDN_URL).then(m => {
    mermaidInstance = m.default
    mermaidInstance.initialize({
      startOnLoad: false,
      theme: 'neutral',
      fontFamily: 'system-ui, sans-serif',
      flowchart: { htmlLabels: true, curve: 'basis' },
      suppressErrors: true,
    })
    return mermaidInstance
  }).catch(() => {
    initPromise = null
    return null
  })
  return initPromise
}

/**
 * Sanitize Gemini-generated mermaid code to fix common syntax issues
 */
function sanitizeMermaidCode(code) {
  let lines = code.split('\n')

  // Remove empty lines at the start
  while (lines.length && !lines[0].trim()) lines.shift()

  // Ensure first line is a valid diagram type declaration
  const firstLine = lines[0]?.trim() || ''
  const validStarts = ['graph ', 'flowchart ', 'sequenceDiagram', 'classDiagram', 'stateDiagram', 'erDiagram', 'gantt', 'pie', 'gitGraph', 'mindmap', 'timeline']
  if (!validStarts.some(s => firstLine.startsWith(s))) {
    // Try to find the declaration in subsequent lines
    const declIdx = lines.findIndex(l => validStarts.some(s => l.trim().startsWith(s)))
    if (declIdx > 0) {
      lines = lines.slice(declIdx)
    }
  }

  let result = lines.join('\n')

  // Fix Chinese punctuation inside node labels
  result = result.replace(/（/g, '(').replace(/）/g, ')')
  result = result.replace(/「/g, '"').replace(/」/g, '"')
  result = result.replace(/【/g, '[').replace(/】/g, ']')
  result = result.replace(/：/g, ':')
  result = result.replace(/；/g, ';')

  // Fix double-bracket issues: [[ ]] → [ ]
  result = result.replace(/\[\[([^\]]*)\]\]/g, '[$1]')

  // Remove problematic characters inside node labels (between [] or {})
  // Mermaid chokes on # inside labels
  result = result.replace(/(\[[^\]]*?)#([^\]]*?\])/g, '$1$2')
  result = result.replace(/(\{[^}]*?)#([^}]*?\})/g, '$1$2')

  return result.trim()
}

/**
 * Clean up any mermaid error elements left in the DOM
 */
function cleanupMermaidErrors() {
  // Mermaid v11 inserts error elements with id starting with 'd'
  document.querySelectorAll('[id^="dmmd-"]').forEach(el => el.remove())
  // Also clean up any error containers mermaid adds
  document.querySelectorAll('.mermaid-error, .error-icon, [id*="mermaid-"] .error-text').forEach(el => {
    const parent = el.closest('[id*="mermaid-"]') || el
    parent.remove()
  })
}

/**
 * Render all .mermaid-block elements inside a container
 * @param {HTMLElement} container
 */
export async function renderMermaidIn(container) {
  if (!container) return
  const blocks = container.querySelectorAll('.mermaid-block:not([data-rendered])')
  if (!blocks.length) return

  try {
    const mermaid = await getMermaid()
    if (!mermaid) return
    for (const block of blocks) {
      const rawCode = block.textContent
      const code = sanitizeMermaidCode(rawCode)
      const id = block.dataset.mermaidId || `mmd-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
      try {
        const { svg } = await mermaid.render(id, code)
        block.innerHTML = svg
        block.dataset.rendered = 'true'
      } catch {
        // Fallback: show raw code with a hint
        const escaped = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        block.innerHTML = `<div style="text-align:left"><div style="color:#94a3b8;font-size:12px;margin-bottom:6px">⚠ 流程圖語法錯誤，顯示原始碼</div><pre class="code-block"><code>${escaped}</code></pre></div>`
        block.dataset.rendered = 'true'
        cleanupMermaidErrors()
      }
    }
    // Final cleanup pass
    cleanupMermaidErrors()
  } catch {
    // mermaid not available
  }
}
