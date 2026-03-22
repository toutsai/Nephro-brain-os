/**
 * PPT Builder — 使用 pptxgenjs 將結構化 JSON 轉為 .pptx 下載
 */

const PRIMARY = 'F97316'    // orange-500
const SECONDARY = '1E293B'  // slate-800
const LIGHT_BG = 'FFF7ED'   // orange-50
const WHITE = 'FFFFFF'
const GRAY = '64748B'       // slate-500
const LIGHT_GRAY = 'F1F5F9' // slate-100
const CHART_COLORS = ['F97316', '0D9488', '3B82F6', '8B5CF6', 'EC4899', 'EAB308']
const FONT_FACE = 'Microsoft JhengHei'

/**
 * 將含有 markdown 格式的文字轉為 pptxgenjs text runs
 * 支援 **粗體**、*斜體*、`code`
 * 回傳 [{ text, bold, italic, code }]
 */
function parseMarkdownRuns(str) {
  if (!str || typeof str !== 'string') return [{ text: str || '' }]

  const runs = []
  // 匹配 **bold**, *italic*, `code`
  const regex = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)/g
  let lastIndex = 0
  let match

  while ((match = regex.exec(str)) !== null) {
    // 前面的普通文字
    if (match.index > lastIndex) {
      runs.push({ text: str.slice(lastIndex, match.index) })
    }
    if (match[2] !== undefined) {
      // **bold**
      runs.push({ text: match[2], bold: true })
    } else if (match[3] !== undefined) {
      // *italic*
      runs.push({ text: match[3], italic: true })
    } else if (match[4] !== undefined) {
      // `code`
      runs.push({ text: match[4], code: true })
    }
    lastIndex = match.index + match[0].length
  }
  // 剩餘文字
  if (lastIndex < str.length) {
    runs.push({ text: str.slice(lastIndex) })
  }
  if (runs.length === 0) {
    runs.push({ text: str })
  }
  return runs
}

/**
 * 將一個 bullet 字串轉為 pptxgenjs 的 text runs 陣列（支援 inline 粗體/斜體）
 * @param {string} bulletText - 可能含有 **bold** 等 markdown 的文字
 * @param {Object} baseOpts - 基礎樣式（fontSize, color, fontFace 等）
 * @param {Object|null} bulletOpt - bullet 選項（僅第一個 run 需要）
 * @returns {Array} pptxgenjs text run objects
 */
function bulletToRuns(bulletText, baseOpts, bulletOpt) {
  const segments = parseMarkdownRuns(bulletText)
  return segments.map((seg, i) => {
    const opts = { ...baseOpts }
    if (seg.bold) opts.bold = true
    if (seg.italic) opts.italic = true
    if (seg.code) {
      opts.fontFace = 'Consolas'
      opts.color = 'DC2626'
    }
    // 只有第一個 segment 帶 bullet
    if (i === 0 && bulletOpt) opts.bullet = bulletOpt
    // 除了最後一個，都不換行（同一段落）
    if (i < segments.length - 1) opts.breakLine = false
    return { text: seg.text, options: opts }
  })
}

/**
 * 清除文字中的 markdown 格式符號（用於標題、表格等不需要 rich text 的地方）
 */
function stripMarkdown(str) {
  if (!str || typeof str !== 'string') return str || ''
  return str
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/`(.+?)`/g, '$1')
}

function addAccentBar(slide) {
  slide.addShape('rect', {
    x: 0, y: 0, w: '100%', h: 0.08,
    fill: { color: PRIMARY },
  })
}

function addSlideNumber(slide, num, total) {
  slide.addText(`${num} / ${total}`, {
    x: '85%', y: '93%', w: '12%', h: 0.3,
    fontSize: 9, color: GRAY, align: 'right', fontFace: FONT_FACE,
  })
}

function addTitleSlide(pptx, slide) {
  const s = pptx.addSlide()
  s.background = { fill: PRIMARY }
  s.addText(stripMarkdown(slide.title), {
    x: 0.8, y: 1.5, w: '85%', h: 1.5,
    fontSize: 36, bold: true, color: WHITE, fontFace: FONT_FACE,
    align: 'left', valign: 'bottom',
  })
  s.addText(stripMarkdown(slide.subtitle), {
    x: 0.8, y: 3.2, w: '85%', h: 0.8,
    fontSize: 18, color: 'FFEDD5', fontFace: FONT_FACE,
    align: 'left',
  })
  if (slide.notes) s.addNotes(slide.notes)
}

function addContentSlide(pptx, slide, idx, total) {
  const s = pptx.addSlide()
  addAccentBar(s)
  addSlideNumber(s, idx, total)
  s.addText(stripMarkdown(slide.title), {
    x: 0.6, y: 0.3, w: '88%', h: 0.7,
    fontSize: 24, bold: true, color: SECONDARY, fontFace: FONT_FACE,
  })
  if (slide.bullets && slide.bullets.length) {
    const baseOpts = {
      fontSize: 16, color: SECONDARY, fontFace: FONT_FACE,
      lineSpacingMultiple: 1.5, paraSpaceAfter: 8,
    }
    const items = slide.bullets.flatMap(b =>
      bulletToRuns(b, baseOpts, { code: '25CF', color: PRIMARY })
    )
    s.addText(items, {
      x: 0.8, y: 1.2, w: '84%', h: 4.5,
      valign: 'top',
    })
  }
  if (slide.notes) s.addNotes(slide.notes)
}

function addTwoColumnSlide(pptx, slide, idx, total) {
  const s = pptx.addSlide()
  addAccentBar(s)
  addSlideNumber(s, idx, total)
  s.addText(stripMarkdown(slide.title), {
    x: 0.6, y: 0.3, w: '88%', h: 0.7,
    fontSize: 24, bold: true, color: SECONDARY, fontFace: FONT_FACE,
  })

  const colWidth = 5.5
  const cols = [
    { data: slide.left, x: 0.5 },
    { data: slide.right, x: 6.6 },
  ]
  for (const col of cols) {
    if (!col.data) continue
    s.addText(stripMarkdown(col.data.heading), {
      x: col.x, y: 1.2, w: colWidth, h: 0.5,
      fontSize: 18, bold: true, color: PRIMARY, fontFace: FONT_FACE,
    })
    if (col.data.bullets && col.data.bullets.length) {
      const baseOpts = {
        fontSize: 14, color: SECONDARY, fontFace: FONT_FACE,
        lineSpacingMultiple: 1.4, paraSpaceAfter: 6,
      }
      const items = col.data.bullets.flatMap(b =>
        bulletToRuns(b, baseOpts, { code: '2022', color: GRAY })
      )
      s.addText(items, {
        x: col.x, y: 1.8, w: colWidth, h: 4.0,
        valign: 'top',
      })
    }
  }
  if (slide.notes) s.addNotes(slide.notes)
}

function addChartSlide(pptx, slide, idx, total) {
  const s = pptx.addSlide()
  addAccentBar(s)
  addSlideNumber(s, idx, total)
  s.addText(stripMarkdown(slide.title), {
    x: 0.6, y: 0.3, w: '88%', h: 0.7,
    fontSize: 24, bold: true, color: SECONDARY, fontFace: FONT_FACE,
  })

  const chartTypeMap = {
    bar: pptx.charts.BAR,
    pie: pptx.charts.PIE,
    line: pptx.charts.LINE,
    doughnut: pptx.charts.DOUGHNUT,
  }
  const chartType = chartTypeMap[slide.chart_type] || pptx.charts.BAR
  const cd = slide.chart_data || {}
  const labels = cd.labels || []
  const datasets = (cd.datasets || []).map((ds, i) => ({
    name: ds.name || `Series ${i + 1}`,
    labels,
    values: ds.values || [],
  }))

  if (datasets.length && labels.length) {
    s.addChart(chartType, datasets, {
      x: 1.0, y: 1.3, w: 10.5, h: 5.0,
      showTitle: false,
      showValue: true,
      valueFontSize: 10,
      catAxisLabelFontSize: 11,
      valAxisLabelFontSize: 10,
      chartColors: CHART_COLORS.slice(0, datasets.length || 1),
      legendPos: datasets.length > 1 ? 'b' : 'none',
      legendFontSize: 10,
    })
  }
  if (slide.notes) s.addNotes(slide.notes)
}

function addTableSlide(pptx, slide, idx, total) {
  const s = pptx.addSlide()
  addAccentBar(s)
  addSlideNumber(s, idx, total)
  s.addText(stripMarkdown(slide.title), {
    x: 0.6, y: 0.3, w: '88%', h: 0.7,
    fontSize: 24, bold: true, color: SECONDARY, fontFace: FONT_FACE,
  })

  const headers = slide.headers || []
  const rows = slide.rows || []

  const headerRow = headers.map(h => ({
    text: stripMarkdown(h), options: {
      bold: true, fontSize: 12, color: WHITE, fill: { color: PRIMARY },
      fontFace: FONT_FACE, align: 'center', valign: 'middle',
    },
  }))

  const dataRows = rows.map((row, ri) =>
    row.map(cell => ({
      text: stripMarkdown(String(cell)), options: {
        fontSize: 11, color: SECONDARY,
        fill: { color: ri % 2 === 0 ? WHITE : LIGHT_GRAY },
        fontFace: FONT_FACE, align: 'center', valign: 'middle',
      },
    }))
  )

  const tableData = [headerRow, ...dataRows]
  const colW = headers.length ? (11.0 / headers.length) : 2.5

  s.addTable(tableData, {
    x: 0.6, y: 1.2, w: 11.5,
    colW: Array(headers.length).fill(colW),
    border: { pt: 0.5, color: 'CBD5E1' },
    rowH: 0.5,
    autoPage: true,
  })
  if (slide.notes) s.addNotes(slide.notes)
}

function addSummarySlide(pptx, slide, idx, total) {
  const s = pptx.addSlide()
  addAccentBar(s)
  addSlideNumber(s, idx, total)
  s.addText(stripMarkdown(slide.title) || '總結', {
    x: 0.6, y: 0.3, w: '88%', h: 0.7,
    fontSize: 24, bold: true, color: SECONDARY, fontFace: FONT_FACE,
  })
  // Left accent bar for summary bullets
  s.addShape('rect', {
    x: 0.6, y: 1.2, w: 0.06, h: 4.5,
    fill: { color: PRIMARY },
  })
  if (slide.bullets && slide.bullets.length) {
    const baseOpts = {
      fontSize: 18, color: SECONDARY, fontFace: FONT_FACE,
      lineSpacingMultiple: 1.8, paraSpaceAfter: 12,
    }
    const items = slide.bullets.flatMap(b =>
      bulletToRuns(b, baseOpts, { code: '2713', color: PRIMARY })
    )
    s.addText(items, {
      x: 1.0, y: 1.2, w: '80%', h: 4.5,
      valign: 'top',
    })
  }
  if (slide.notes) s.addNotes(slide.notes)
}

/**
 * 將結構化 JSON 轉為 .pptx 並觸發下載
 * @param {Object} slidesJson - { title, slides: [...] }
 * @param {string} filename - 檔名（含 .pptx）
 */
export async function buildAndDownloadPptx(slidesJson, filename) {
  const PptxGenJS = (await import('pptxgenjs')).default
  const pptx = new PptxGenJS()

  pptx.defineLayout({ name: 'WIDE', width: 13.33, height: 7.5 })
  pptx.layout = 'WIDE'
  pptx.author = 'NB Teach'
  pptx.title = slidesJson.title || 'NB Teach PPT'

  const slides = slidesJson.slides || []
  const total = slides.length

  const builders = {
    title: addTitleSlide,
    content: addContentSlide,
    two_column: addTwoColumnSlide,
    chart: addChartSlide,
    table: addTableSlide,
    summary: addSummarySlide,
  }

  for (let i = 0; i < slides.length; i++) {
    const slide = slides[i]
    const builder = builders[slide.layout] || addContentSlide
    builder(pptx, slide, i + 1, total)
  }

  await pptx.writeFile({ fileName: filename })
}
