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
    })
    return mermaidInstance
  }).catch(() => {
    initPromise = null
    return null
  })
  return initPromise
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
      const code = block.textContent
      const id = block.dataset.mermaidId || `mmd-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
      try {
        const { svg } = await mermaid.render(id, code)
        block.innerHTML = svg
        block.dataset.rendered = 'true'
      } catch {
        block.innerHTML = `<pre class="code-block"><code>${code}</code></pre>`
      }
    }
  } catch {
    // mermaid not available
  }
}
