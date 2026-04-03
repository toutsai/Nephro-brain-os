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
        padding: 24,
        nodeSpacing: 50,
        rankSpacing: 60,
        useMaxWidth: false,
        wrappingWidth: 200,
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
    let prev
    do { prev = l; l = l.replace(/(\[[^\]]*)[:?]([^\]]*\])/g, '$1$2') } while (l !== prev)
    do { prev = l; l = l.replace(/(\{\{[^}]*)[:?]([^}]*\}\})/g, '$1$2') } while (l !== prev)

    // Remove quotes inside labels
    do { prev = l; l = l.replace(/(\[[^\]]*)["']([^\]]*\])/g, '$1$2') } while (l !== prev)
    do { prev = l; l = l.replace(/(\{\{[^}]*)["']([^}]*\}\})/g, '$1$2') } while (l !== prev)

    // Clean edge labels: remove problematic chars from -->|...|
    l = l.replace(/-->\|([^|]*)\|/g, (_, label) => {
      const cleaned = label.replace(/[:?#"';\\/{}\[\]()]/g, '').trim()
      return `-->|${cleaned}|`
    })

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

// ── Mermaid parser ──────────────────────────────────────────

/**
 * Parse mermaid code into a graph structure with typed nodes.
 * Returns { nodes: Map<id, {label, type}>, edges: [{from, to, label}], ordered: [ids] }
 */
function parseMermaidToSteps(code) {
  const nodes = new Map()
  const edges = []

  // Extract node definitions: A[label], A{label}, A{{label}}, A(label)
  const nodeRegex = /([A-Za-z][A-Za-z0-9_]*)\s*(?:\[([^\]]+)\]|\{\{([^}]+)\}\}|\{([^}]+)\}|\(([^)]+)\))/g
  let m
  while ((m = nodeRegex.exec(code)) !== null) {
    const id = m[1]
    let label, type
    if (m[2]) { label = m[2]; type = 'action' }        // [label]
    else if (m[3]) { label = m[3]; type = 'decision' }  // {{label}}
    else if (m[4]) { label = m[4]; type = 'decision' }  // {label}
    else if (m[5]) { label = m[5]; type = 'rounded' }   // (label)
    else { label = id; type = 'action' }
    if (!nodes.has(id)) nodes.set(id, { label: label.trim(), type })
  }

  // Extract edges: A --> B, A[label] -->|label| B{{label}}, etc.
  const edgeRegex = /([A-Za-z][A-Za-z0-9_]*)(?:\[[^\]]*\]|\{\{[^}]*\}\}|\{[^}]*\}|\([^)]*\))?\s*-->(?:\|([^|]*)\|)?\s*([A-Za-z][A-Za-z0-9_]*)/g
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
  for (const id of nodes.keys()) {
    if (!visited.has(id)) ordered.push(id)
  }

  return { nodes, edges, ordered }
}

// ── Custom SVG Flowchart Renderer ───────────────────────────

/** Escape text for use in SVG elements */
function escSvg(text) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

/** Measure approximate text width for Chinese/ASCII mix (rough estimate) */
function textWidth(str, fontSize) {
  let w = 0
  for (const ch of str) {
    w += ch.charCodeAt(0) > 0x7f ? fontSize : fontSize * 0.6
  }
  return w
}

/**
 * Assign each node to a vertical level using BFS.
 * Returns array of arrays: [[root ids], [level 1 ids], ...]
 */
function assignLevels(nodes, edges) {
  const levels = new Map()
  const childMap = new Map()
  const inDeg = new Map()

  for (const id of nodes.keys()) {
    childMap.set(id, [])
    inDeg.set(id, 0)
  }
  for (const e of edges) {
    if (childMap.has(e.from) && nodes.has(e.to)) {
      childMap.get(e.from).push(e.to)
      inDeg.set(e.to, (inDeg.get(e.to) || 0) + 1)
    }
  }

  // Roots: no incoming edges
  const roots = [...nodes.keys()].filter(id => !inDeg.get(id))
  if (!roots.length && nodes.size) roots.push(nodes.keys().next().value)

  const queue = roots.map(id => ({ id, level: 0 }))
  for (const r of roots) levels.set(r, 0)

  // Track per-node enqueue count to detect cycles
  const enqueueCount = new Map()
  const maxEnqueues = nodes.size // in a DAG a node is re-leveled at most V times
  let iterations = 0
  const maxIterations = nodes.size * edges.length + 200 // hard safety cap

  while (queue.length && iterations < maxIterations) {
    iterations++
    const { id, level } = queue.shift()
    for (const child of childMap.get(id) || []) {
      const newLvl = level + 1
      if (!levels.has(child) || levels.get(child) < newLvl) {
        const count = (enqueueCount.get(child) || 0) + 1
        if (count > maxEnqueues) continue // cycle detected, skip
        enqueueCount.set(child, count)
        levels.set(child, newLvl)
        queue.push({ id: child, level: newLvl })
      }
    }
  }

  // Any unvisited nodes get appended to last level
  const maxLvl = levels.size ? Math.max(...levels.values()) : 0
  for (const id of nodes.keys()) {
    if (!levels.has(id)) levels.set(id, maxLvl + 1)
  }

  // Group by level
  const byLevel = []
  for (const [id, lvl] of levels) {
    if (!byLevel[lvl]) byLevel[lvl] = []
    byLevel[lvl].push(id)
  }
  return byLevel.filter(Boolean) // remove empty slots
}

/**
 * Build an SVG flowchart from parsed mermaid data.
 * Returns SVG HTML string, or null if not enough data.
 */
function buildFlowchartSvg(parsed) {
  const { nodes, edges } = parsed
  if (nodes.size < 2) return null

  const FONT = 13
  const LABEL_FONT = 11
  const NODE_H = 52
  const GAP_X = 40
  const GAP_Y = 64
  const PAD_X = 24
  const PAD_Y = 20
  const MIN_NODE_W = 120
  const MAX_NODE_W = 300
  const DIAMOND_R = 48 // half-diagonal of diamond

  // Calculate node widths based on label length
  const nodeWidths = new Map()
  for (const [id, node] of nodes) {
    const tw = textWidth(node.label, FONT) + 28 // padding
    nodeWidths.set(id, Math.max(MIN_NODE_W, Math.min(MAX_NODE_W, tw)))
  }

  const levels = assignLevels(nodes, edges)

  // Calculate row widths and SVG dimensions
  let maxRowW = 0
  for (const row of levels) {
    let rowW = 0
    for (const id of row) rowW += (nodeWidths.get(id) || MIN_NODE_W) + GAP_X
    rowW -= GAP_X
    if (rowW > maxRowW) maxRowW = rowW
  }

  const svgW = Math.max(maxRowW + 2 * PAD_X, 300)
  const svgH = levels.length * (NODE_H + GAP_Y) - GAP_Y + 2 * PAD_Y + 10

  // Position each node
  const pos = new Map() // id → {x, y, w, h, cx, cy}
  for (let lvl = 0; lvl < levels.length; lvl++) {
    const row = levels[lvl]
    let rowW = 0
    for (const id of row) rowW += (nodeWidths.get(id) || MIN_NODE_W) + GAP_X
    rowW -= GAP_X

    let curX = (svgW - rowW) / 2
    const y = PAD_Y + lvl * (NODE_H + GAP_Y)
    for (const id of row) {
      const w = nodeWidths.get(id) || MIN_NODE_W
      pos.set(id, { x: curX, y, w, h: NODE_H, cx: curX + w / 2, cy: y + NODE_H / 2 })
      curX += w + GAP_X
    }
  }

  // Build SVG
  const parts = []
  parts.push(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${svgW} ${svgH}" class="flowchart-svg" style="overflow:visible;font-family:-apple-system,'Noto Sans TC',system-ui,sans-serif">`)

  // Defs: arrow marker + shadow filter
  parts.push(`<defs>
    <marker id="fc-arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0 0L10 5L0 10z" fill="#94a3b8"/>
    </marker>
    <filter id="fc-shadow" x="-4%" y="-4%" width="108%" height="116%">
      <feDropShadow dx="0" dy="1" stdDeviation="1.5" flood-opacity="0.08"/>
    </filter>
  </defs>`)

  // Draw edges
  for (const edge of edges) {
    const from = pos.get(edge.from)
    const to = pos.get(edge.to)
    if (!from || !to) continue

    const x1 = from.cx
    const y1 = from.y + from.h
    const x2 = to.cx
    const y2 = to.y

    // Bezier curve for smooth connection
    const midY = (y1 + y2) / 2
    parts.push(`<path d="M${x1} ${y1} C${x1} ${midY},${x2} ${midY},${x2} ${y2}" fill="none" stroke="#94a3b8" stroke-width="1.5" marker-end="url(#fc-arr)"/>`)

    // Edge label
    if (edge.label) {
      const lx = (x1 + x2) / 2
      const ly = midY
      const labelTw = textWidth(edge.label, LABEL_FONT) + 12
      const labelH = 18
      parts.push(`<rect x="${lx - labelTw / 2}" y="${ly - labelH / 2}" width="${labelTw}" height="${labelH}" rx="4" fill="white" stroke="#e2e8f0" stroke-width="0.75"/>`)
      parts.push(`<text x="${lx}" y="${ly + 4}" text-anchor="middle" font-size="${LABEL_FONT}" fill="#64748b">${escSvg(edge.label)}</text>`)
    }
  }

  // Draw nodes
  for (const [id, node] of nodes) {
    const p = pos.get(id)
    if (!p) continue

    if (node.type === 'decision') {
      // Diamond: rotated rectangle
      const r = Math.min(DIAMOND_R, p.w / 2.2)
      parts.push(`<g transform="translate(${p.cx},${p.cy})">`)
      parts.push(`<rect x="${-r}" y="${-r}" width="${r * 2}" height="${r * 2}" rx="3" transform="rotate(45)" fill="#fef3c7" stroke="#f59e0b" stroke-width="1.5" filter="url(#fc-shadow)"/>`)
      // Text (counter-rotated, multi-line if needed)
      const maxChars = Math.floor(r * 1.6 / (FONT * 0.8))
      const textLines = wrapLabel(node.label, maxChars)
      const lineH = FONT + 3
      const startY = -(textLines.length - 1) * lineH / 2 + 4
      for (let i = 0; i < textLines.length; i++) {
        parts.push(`<text x="0" y="${startY + i * lineH}" text-anchor="middle" font-size="${FONT}" font-weight="500" fill="#92400e">${escSvg(textLines[i])}</text>`)
      }
      parts.push(`</g>`)
    } else {
      // Rectangle node
      const fill = node.type === 'rounded' ? '#f0fdf4' : '#eff6ff'
      const stroke = node.type === 'rounded' ? '#86efac' : '#93c5fd'
      const textFill = node.type === 'rounded' ? '#166534' : '#1e293b'
      const rx = node.type === 'rounded' ? 22 : 8

      parts.push(`<rect x="${p.x}" y="${p.y}" width="${p.w}" height="${p.h}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="1.5" filter="url(#fc-shadow)"/>`)

      // Text (possibly multi-line)
      const maxChars = Math.floor((p.w - 16) / (FONT * 0.8))
      const textLines = wrapLabel(node.label, maxChars)
      const lineH = FONT + 3
      const startY = p.cy - (textLines.length - 1) * lineH / 2 + 4
      for (let i = 0; i < textLines.length; i++) {
        parts.push(`<text x="${p.cx}" y="${startY + i * lineH}" text-anchor="middle" font-size="${FONT}" font-weight="500" fill="${textFill}">${escSvg(textLines[i])}</text>`)
      }
    }
  }

  parts.push('</svg>')
  return parts.join('\n')
}

/** Wrap a label string into lines of at most maxChars characters */
function wrapLabel(label, maxChars) {
  if (maxChars < 4) maxChars = 4
  if (label.length <= maxChars) return [label]
  const lines = []
  let remaining = label
  while (remaining.length > maxChars) {
    // Try to break at a natural boundary (space, comma)
    let breakAt = -1
    for (let i = maxChars; i >= maxChars / 2; i--) {
      if (remaining[i] === ' ' || remaining[i] === ',' || remaining[i] === '、') {
        breakAt = i
        break
      }
    }
    if (breakAt < 0) breakAt = maxChars
    lines.push(remaining.slice(0, breakAt).trim())
    remaining = remaining.slice(breakAt).trim()
  }
  if (remaining) lines.push(remaining)
  return lines.length > 3 ? [...lines.slice(0, 2), lines.slice(2).join('')] : lines
}

// ── Text fallback (Tier 3) ──────────────────────────────────

/**
 * Build a styled HTML fallback from parsed mermaid steps (last resort).
 */
function buildFallbackHtml(parsed) {
  if (!parsed.nodes.size) return null

  let html = '<div class="mermaid-fallback">'
  html += '<div style="color:#64748b;font-size:12px;margin-bottom:8px;font-weight:600">📋 流程步驟</div>'
  html += '<ol style="margin:0;padding-left:20px;list-style:decimal">'

  for (const id of parsed.ordered) {
    const node = parsed.nodes.get(id)
    const label = node?.label || node || id
    const outEdges = parsed.edges.filter(e => e.from === id)
    let arrow = ''
    if (outEdges.length === 1) {
      const e = outEdges[0]
      const targetNode = parsed.nodes.get(e.to)
      const targetLabel = targetNode?.label || targetNode || e.to
      arrow = ` <span style="color:#94a3b8">→ ${targetLabel}</span>`
    } else if (outEdges.length > 1) {
      const branches = outEdges.map(e => {
        const targetNode = parsed.nodes.get(e.to)
        const targetLabel = targetNode?.label || targetNode || e.to
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
 * Render all .mermaid-block elements inside a container.
 * Tier 1: Mermaid library → Tier 2: Custom SVG → Tier 3: Text fallback
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
      const rawCode = unescapeHtml(block.textContent)
      const code = sanitizeMermaidCode(rawCode)
      const id = block.dataset.mermaidId || `mmd-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
      try {
        // Tier 1: Mermaid library rendering
        const { svg } = await mermaid.render(id, code)
        block.innerHTML = svg
        block.dataset.rendered = 'true'
      } catch (err) {
        console.warn('[Mermaid render failed]', err?.message, '\nSanitized code:', code)

        // Tier 2: Custom SVG flowchart renderer
        let parsed = null
        let svgHtml = null
        try {
          parsed = parseMermaidToSteps(code)
          svgHtml = buildFlowchartSvg(parsed)
        } catch (svgErr) {
          console.warn('[Custom SVG renderer failed]', svgErr?.message)
          try { parsed = parseMermaidToSteps(code) } catch { /* ignore */ }
        }

        if (svgHtml) {
          block.innerHTML = svgHtml
        } else {
          // Tier 3: Text fallback (last resort)
          const fallbackHtml = parsed ? buildFallbackHtml(parsed) : null
          if (fallbackHtml) {
            block.innerHTML = fallbackHtml
          } else {
            const escaped = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            block.innerHTML = `<div style="text-align:left"><div style="color:#94a3b8;font-size:12px;margin-bottom:6px">⚠ 流程圖語法錯誤，顯示原始碼</div><pre class="code-block"><code>${escaped}</code></pre></div>`
          }
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
