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
      theme: 'base',
      fontFamily: '-apple-system, "Noto Sans TC", system-ui, sans-serif',
      flowchart: {
        htmlLabels: true,
        curve: 'basis',
        padding: 16,
        nodeSpacing: 30,
        rankSpacing: 50,
        useMaxWidth: true,
      },
      themeVariables: {
        primaryColor: '#dbeafe',
        primaryTextColor: '#1e293b',
        primaryBorderColor: '#93c5fd',
        lineColor: '#94a3b8',
        secondaryColor: '#fef3c7',
        secondaryTextColor: '#92400e',
        secondaryBorderColor: '#fbbf24',
        tertiaryColor: '#f0fdf4',
        tertiaryTextColor: '#166534',
        tertiaryBorderColor: '#86efac',
        fontFamily: '-apple-system, "Noto Sans TC", system-ui, sans-serif',
        fontSize: '14px',
      },
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
 * Un-escape HTML entities that renderMarkdown.js preserves in mermaid blocks.
 */
function unescapeHtml(text) {
  return text
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
}

/**
 * Sanitize Gemini-generated mermaid code to fix common syntax issues.
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
  let lines = text.split('\n')

  if (lines.length <= 3) {
    const expanded = []
    for (const line of lines) {
      const trimmed = line.trim()
      const declMatch = trimmed.match(/^((?:graph|flowchart)\s+(?:TD|TB|BT|RL|LR))\s+(.+)/)
      if (declMatch) {
        expanded.push(declMatch[1])
        const rest = declMatch[2]
        const nodeParts = splitMermaidNodes(rest)
        expanded.push(...nodeParts)
      } else {
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
    // Only convert {content} → {{content}} if NOT already doubled
    l = l.replace(/([A-Za-z0-9_]+)\{([^{}]+)\}/g, (match, id, content) => {
      return `${id}{{${content}}}`
    })
    // Undo quadruple braces if Gemini already sent {{...}} and we doubled again
    l = l.replace(/\{\{\{\{/g, '{{').replace(/\}\}\}\}/g, '}}')

    // Remove problematic special chars inside labels
    l = l.replace(/≥/g, '>=').replace(/≤/g, '<=')
    l = l.replace(/²/g, '^2')
    // Replace / inside labels with " or "
    l = l.replace(/(\[[^\]]*)\/([^\]]*\])/g, '$1 or $2')
    l = l.replace(/(\{\{[^}]*)\/([^}]*\}\})/g, '$1 or $2')

    // Remove parentheses inside bracket labels (they break mermaid node syntax)
    l = l.replace(/(\[[^\]]*)\(([^\)]*)\)([^\]]*\])/g, '$1$2$3')

    // Remove colons and question marks inside labels (break mermaid parsing)
    // Loop to handle multiple occurrences
    let prev
    do { prev = l; l = l.replace(/(\[[^\]]*)[:?]([^\]]*\])/g, '$1$2') } while (l !== prev)
    do { prev = l; l = l.replace(/(\{\{[^}]*)[:?]([^}]*\}\})/g, '$1$2') } while (l !== prev)

    // Remove quotes inside labels
    do { prev = l; l = l.replace(/(\[[^\]]*)["']([^\]]*\])/g, '$1$2') } while (l !== prev)
    do { prev = l; l = l.replace(/(\{\{[^}]*)["']([^}]*\}\})/g, '$1$2') } while (l !== prev)

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
 */
function splitMermaidNodes(text) {
  const parts = []
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
 * Parse mermaid code into steps for structured fallback display.
 * Extracts node labels and connections to show a useful text list.
 */
function parseMermaidToSteps(code) {
  const nodes = new Map()
  const edges = []

  // Extract node definitions: A[label], A{label}, A{{label}}, A(label)
  const nodeRegex = /([A-Za-z][A-Za-z0-9_]*)\s*(?:\[([^\]]+)\]|\{\{([^}]+)\}\}|\{([^}]+)\}|\(([^)]+)\))/g
  let m
  while ((m = nodeRegex.exec(code)) !== null) {
    const id = m[1]
    const label = m[2] || m[3] || m[4] || m[5] || id
    if (!nodes.has(id)) nodes.set(id, label.trim())
  }

  // Extract edges: A --> B, A -->|label| B
  const edgeRegex = /([A-Za-z][A-Za-z0-9_]*)\s*-->(?:\|([^|]*)\|)?\s*([A-Za-z][A-Za-z0-9_]*)/g
  while ((m = edgeRegex.exec(code)) !== null) {
    edges.push({ from: m[1], label: m[2] || '', to: m[3] })
  }

  // BFS order from root nodes (no incoming edges)
  const incoming = new Set(edges.map(e => e.to))
  const roots = [...nodes.keys()].filter(id => !incoming.has(id))
  if (!roots.length && nodes.size) roots.push(nodes.keys().next().value)

  const ordered = []
  const visited = new Set()
  const queue = [...roots]
  while (queue.length) {
    const id = queue.shift()
    if (visited.has(id)) continue
    visited.add(id)
    ordered.push(id)
    for (const e of edges.filter(e => e.from === id)) {
      queue.push(e.to)
    }
  }
  // Add any unvisited nodes
  for (const id of nodes.keys()) {
    if (!visited.has(id)) ordered.push(id)
  }

  return { nodes, edges, ordered }
}

/**
 * Build a styled HTML fallback from parsed mermaid steps.
 */
function buildFallbackHtml(parsed) {
  if (!parsed.nodes.size) return null

  let html = '<div class="mermaid-fallback">'
  html += '<div style="color:#64748b;font-size:12px;margin-bottom:8px;font-weight:600">📋 流程步驟</div>'
  html += '<ol style="margin:0;padding-left:20px;list-style:decimal">'

  for (const id of parsed.ordered) {
    const label = parsed.nodes.get(id) || id
    const outEdges = parsed.edges.filter(e => e.from === id)
    let arrow = ''
    if (outEdges.length === 1) {
      const e = outEdges[0]
      const targetLabel = parsed.nodes.get(e.to) || e.to
      arrow = ` <span style="color:#94a3b8">→ ${targetLabel}</span>`
    } else if (outEdges.length > 1) {
      const branches = outEdges.map(e => {
        const targetLabel = parsed.nodes.get(e.to) || e.to
        return e.label ? `${e.label}: ${targetLabel}` : targetLabel
      }).join(' / ')
      arrow = ` <span style="color:#94a3b8">→ ${branches}</span>`
    }

    html += `<li style="margin-bottom:4px;font-size:13px;color:#334155"><strong>${label}</strong>${arrow}</li>`
  }

  html += '</ol></div>'
  return html
}

/**
 * Clean up any mermaid error elements left in the DOM
 */
function cleanupMermaidErrors() {
  document.querySelectorAll('[id^="dmmd-"]').forEach(el => el.remove())
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
      // textContent returns HTML-escaped text from renderMarkdown; un-escape it
      const rawCode = unescapeHtml(block.textContent)
      const code = sanitizeMermaidCode(rawCode)
      const id = block.dataset.mermaidId || `mmd-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
      try {
        const { svg } = await mermaid.render(id, code)
        block.innerHTML = svg
        block.dataset.rendered = 'true'
      } catch (err) {
        console.warn('[Mermaid render failed]', err?.message, '\nSanitized code:', code)
        // Try structured fallback: parse nodes and show as step list
        const parsed = parseMermaidToSteps(code)
        const fallbackHtml = buildFallbackHtml(parsed)
        if (fallbackHtml) {
          block.innerHTML = fallbackHtml
        } else {
          // Last resort: show raw code
          const escaped = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
          block.innerHTML = `<div style="text-align:left"><div style="color:#94a3b8;font-size:12px;margin-bottom:6px">⚠ 流程圖語法錯誤，顯示原始碼</div><pre class="code-block"><code>${escaped}</code></pre></div>`
        }
        block.dataset.rendered = 'true'
        cleanupMermaidErrors()
      }
    }
    cleanupMermaidErrors()
  } catch {
    // mermaid not available
  }
}
