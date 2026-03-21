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
 * Sanitize Gemini-generated mermaid code to fix common syntax issues.
 * Gemini often outputs everything on one line, uses Chinese punctuation,
 * and includes special characters that break mermaid parsing.
 */
function sanitizeMermaidCode(code) {
  let text = code.trim()

  // ── Step 0: Fix Chinese punctuation globally ──
  text = text.replace(/（/g, '(').replace(/）/g, ')')
  text = text.replace(/「/g, '"').replace(/」/g, '"')
  text = text.replace(/【/g, '[').replace(/】/g, ']')
  text = text.replace(/：/g, ':')
  text = text.replace(/；/g, ';')
  text = text.replace(/？/g, '?')
  text = text.replace(/，/g, ', ')

  // ── Step 1: Split single-line mermaid into multi-line ──
  // Gemini often puts everything on one line like:
  //   graph TD  A[...] --> B{...}  B --> C[...]
  // We need to split before each node definition (letter+bracket or arrow)
  let lines = text.split('\n')

  // Check if the code is mostly on one line (declaration + nodes together)
  if (lines.length <= 3) {
    // Try to split the longest line at node boundaries
    const expanded = []
    for (const line of lines) {
      const trimmed = line.trim()
      // If this line has the declaration AND node definitions, split them
      const declMatch = trimmed.match(/^((?:graph|flowchart)\s+(?:TD|TB|BT|RL|LR))\s+(.+)/)
      if (declMatch) {
        expanded.push(declMatch[1])
        // Split the rest at each new node connection: "A[x] --> B[y]  B --> C[z]"
        // Split before each uppercase letter that starts a node (but not inside labels)
        const rest = declMatch[2]
        const nodeParts = splitMermaidNodes(rest)
        expanded.push(...nodeParts)
      } else {
        // Also try splitting lines that have multiple connections
        if ((trimmed.match(/-->/g) || []).length > 1) {
          const nodeParts = splitMermaidNodes(trimmed)
          expanded.push(...nodeParts)
        } else {
          expanded.push(line)
        }
      }
    }
    lines = expanded
  }

  // ── Step 2: Clean up each line ──
  const cleaned = lines.map(line => {
    let l = line.trim()
    if (!l) return ''

    // Remove # inside labels (mermaid reserved)
    l = l.replace(/(\[[^\]]*?)#([^\]]*?\])/g, '$1$2')
    l = l.replace(/(\{[^}]*?)#([^}]*?\})/g, '$1$2')

    // Fix single braces to double for diamond/decision nodes
    // e.g. B{decision} → B{{decision}} (but don't double-fix already doubled)
    l = l.replace(/([A-Za-z0-9_]+)\{([^{}]+)\}/g, (match, id, content) => {
      return `${id}{{${content}}}`
    })

    // Remove problematic special chars inside labels that break mermaid
    // Replace ≥ ≤ with >= <=
    l = l.replace(/≥/g, '>=').replace(/≤/g, '<=')
    // Replace ² with ^2
    l = l.replace(/²/g, '^2')
    // Replace / inside labels with " or " to avoid mermaid parsing issues
    // Only inside bracket labels
    l = l.replace(/(\[[^\]]*)\/([^\]]*\])/g, '$1 or $2')
    l = l.replace(/(\{\{[^}]*)\/([^}]*\}\})/g, '$1 or $2')

    return '  ' + l
  })

  // Remove empty lines at start, ensure declaration is first
  let result = cleaned.filter((l, i) => i === 0 || l.trim()).join('\n').trim()

  // ── Step 3: Validate declaration line ──
  const resultLines = result.split('\n')
  while (resultLines.length && !resultLines[0].trim()) resultLines.shift()
  const firstLine = resultLines[0]?.trim() || ''
  const validStarts = ['graph ', 'flowchart ', 'sequenceDiagram', 'classDiagram', 'stateDiagram', 'erDiagram', 'gantt', 'pie', 'gitGraph', 'mindmap', 'timeline']
  if (!validStarts.some(s => firstLine.startsWith(s))) {
    const declIdx = resultLines.findIndex(l => validStarts.some(s => l.trim().startsWith(s)))
    if (declIdx > 0) {
      return resultLines.slice(declIdx).join('\n').trim()
    }
  }

  // Fix double-bracket issues from escaping: [[ ]] → [ ]
  result = result.replace(/\[\[([^\]]*)\]\]/g, '[$1]')

  return result
}

/**
 * Split a single line of mermaid node definitions into separate lines.
 * e.g. "A[foo] --> B{bar}  B --> C[baz]" → ["A[foo] --> B{bar}", "B --> C[baz]"]
 */
function splitMermaidNodes(text) {
  const parts = []
  // Match patterns like: NodeID[label] --> NodeID[label] or NodeID{label} etc.
  // Split before each new connection that starts after whitespace
  const regex = /\s{2,}(?=[A-Za-z0-9_]+[\[{(])/g
  let lastIdx = 0
  let match
  while ((match = regex.exec(text)) !== null) {
    const segment = text.slice(lastIdx, match.index).trim()
    if (segment) parts.push(segment)
    lastIdx = match.index
  }
  const last = text.slice(lastIdx).trim()
  if (last) parts.push(last)
  return parts.length > 1 ? parts : [text]
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
