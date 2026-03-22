/**
 * PPT Builder — 使用 pptxgenjs 將結構化 JSON 轉為 .pptx 下載
 * 設計風格：橘色主題 + 幾何裝飾 + 漸層色塊 + 圓角卡片感
 */

// ── 色彩系統 ──
const C = {
  primary:    'F97316',  // orange-500
  primaryDk:  'EA580C',  // orange-600
  primaryLt:  'FFEDD5',  // orange-100
  primaryBg:  'FFF7ED',  // orange-50
  accent:     '0D9488',  // teal-600
  accentLt:   'CCFBF1',  // teal-100
  dark:       '0F172A',  // slate-900
  text:       '1E293B',  // slate-800
  textMd:     '475569',  // slate-600
  textLt:     '94A3B8',  // slate-400
  border:     'E2E8F0',  // slate-200
  bgLight:    'F8FAFC',  // slate-50
  bgCard:     'F1F5F9',  // slate-100
  white:      'FFFFFF',
  red:        'DC2626',
}
const CHART_COLORS = ['F97316', '0D9488', '3B82F6', '8B5CF6', 'EC4899', 'EAB308']
const FONT = 'Microsoft JhengHei'
const FONT_EN = 'Segoe UI'

// ── Markdown 解析工具 ──

function parseMarkdownRuns(str) {
  if (!str || typeof str !== 'string') return [{ text: str || '' }]
  const runs = []
  const regex = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)/g
  let lastIndex = 0
  let match
  while ((match = regex.exec(str)) !== null) {
    if (match.index > lastIndex) runs.push({ text: str.slice(lastIndex, match.index) })
    if (match[2] !== undefined) runs.push({ text: match[2], bold: true })
    else if (match[3] !== undefined) runs.push({ text: match[3], italic: true })
    else if (match[4] !== undefined) runs.push({ text: match[4], code: true })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < str.length) runs.push({ text: str.slice(lastIndex) })
  if (runs.length === 0) runs.push({ text: str })
  return runs
}

function bulletToRuns(bulletText, baseOpts, bulletOpt) {
  const segments = parseMarkdownRuns(bulletText)
  return segments.map((seg, i) => {
    const opts = { ...baseOpts }
    if (seg.bold) { opts.bold = true; opts.color = C.dark }
    if (seg.italic) opts.italic = true
    if (seg.code) { opts.fontFace = 'Consolas'; opts.color = C.red }
    if (i === 0 && bulletOpt) opts.bullet = bulletOpt
    if (i < segments.length - 1) opts.breakLine = false
    return { text: seg.text, options: opts }
  })
}

function stripMd(str) {
  if (!str || typeof str !== 'string') return str || ''
  return str.replace(/\*\*(.+?)\*\*/g, '$1').replace(/\*(.+?)\*/g, '$1').replace(/`(.+?)`/g, '$1')
}

// ── 共用裝飾元素 ──

/** 頂部橘色粗條 + 底部細線 */
function addFrameBars(s) {
  // 頂部橘色粗條
  s.addShape('rect', { x: 0, y: 0, w: '100%', h: 0.12, fill: { color: C.primary } })
  // 底部細線
  s.addShape('rect', { x: 0, y: 7.38, w: '100%', h: 0.12, fill: { color: C.bgCard } })
}

/** 右下角裝飾圓圈 */
function addCornerDeco(s) {
  s.addShape('ellipse', { x: 11.8, y: 5.8, w: 2.2, h: 2.2, fill: { color: C.primaryLt }, line: { color: C.primaryLt } })
  s.addShape('ellipse', { x: 12.3, y: 6.3, w: 1.5, h: 1.5, fill: { color: C.primaryBg }, line: { color: C.primaryBg } })
}

/** 頁碼 + NB Teach 浮水印 */
function addFooter(s, num, total) {
  s.addText(`${num} / ${total}`, {
    x: '88%', y: '93%', w: '10%', h: 0.3,
    fontSize: 9, color: C.textLt, align: 'right', fontFace: FONT_EN,
  })
  s.addText('NB Teach', {
    x: 0.4, y: '93%', w: 1.5, h: 0.3,
    fontSize: 8, color: C.border, fontFace: FONT_EN, italic: true,
  })
}

/** 標題列：左側橘色豎條 + 標題文字 */
function addSectionTitle(s, title) {
  // 左側橘色豎條
  s.addShape('rect', { x: 0.5, y: 0.35, w: 0.08, h: 0.55, fill: { color: C.primary }, rectRadius: 0.04 })
  s.addText(stripMd(title), {
    x: 0.8, y: 0.3, w: '85%', h: 0.65,
    fontSize: 22, bold: true, color: C.dark, fontFace: FONT, valign: 'middle',
  })
}

// ── Layout Builders ──

function addTitleSlide(pptx, slide) {
  const s = pptx.addSlide()
  // 全頁橘色背景
  s.background = { fill: C.primary }
  // 右上大圓裝飾
  s.addShape('ellipse', { x: 9, y: -1.5, w: 6, h: 6, fill: { color: C.primaryDk }, line: { color: C.primaryDk } })
  s.addShape('ellipse', { x: 10, y: -0.8, w: 4.5, h: 4.5, fill: { color: C.primary }, line: { color: C.primary } })
  // 左下小圓裝飾
  s.addShape('ellipse', { x: -0.8, y: 5.5, w: 3, h: 3, fill: { color: C.primaryDk }, line: { color: C.primaryDk } })
  // 主標題
  s.addText(stripMd(slide.title), {
    x: 1.0, y: 2.0, w: 9, h: 2.0,
    fontSize: 40, bold: true, color: C.white, fontFace: FONT,
    align: 'left', valign: 'middle',
  })
  // 底線裝飾
  s.addShape('rect', { x: 1.0, y: 4.1, w: 2.5, h: 0.06, fill: { color: C.white } })
  // 副標題
  s.addText(stripMd(slide.subtitle), {
    x: 1.0, y: 4.3, w: 9, h: 0.8,
    fontSize: 18, color: C.primaryLt, fontFace: FONT, align: 'left',
  })
  // NB Teach 品牌
  s.addText('NB Teach', {
    x: 1.0, y: 6.6, w: 3, h: 0.5,
    fontSize: 12, color: C.primaryLt, fontFace: FONT_EN, italic: true,
  })
  if (slide.notes) s.addNotes(slide.notes)
}

function addContentSlide(pptx, slide, idx, total) {
  const s = pptx.addSlide()
  s.background = { fill: C.white }
  addFrameBars(s)
  addCornerDeco(s)
  addFooter(s, idx, total)
  addSectionTitle(s, slide.title)

  if (slide.bullets && slide.bullets.length) {
    // 淺灰卡片背景
    s.addShape('roundRect', {
      x: 0.5, y: 1.15, w: 11.5, h: 5.5,
      fill: { color: C.bgLight }, rectRadius: 0.15,
      line: { color: C.border, width: 0.5 },
    })

    const baseOpts = {
      fontSize: 15, color: C.text, fontFace: FONT,
      lineSpacingMultiple: 1.6, paraSpaceAfter: 10,
    }
    const items = slide.bullets.flatMap(b =>
      bulletToRuns(b, baseOpts, { code: '25CF', color: C.primary })
    )
    s.addText(items, { x: 0.9, y: 1.35, w: 10.7, h: 5.1, valign: 'top' })
  }
  if (slide.notes) s.addNotes(slide.notes)
}

function addTwoColumnSlide(pptx, slide, idx, total) {
  const s = pptx.addSlide()
  s.background = { fill: C.white }
  addFrameBars(s)
  addFooter(s, idx, total)
  addSectionTitle(s, slide.title)

  const colW = 5.6
  const configs = [
    { data: slide.left, x: 0.5, accent: C.primary, accentBg: C.primaryBg },
    { data: slide.right, x: 6.7, accent: C.accent, accentBg: C.accentLt },
  ]

  for (const col of configs) {
    if (!col.data) continue
    // 欄位卡片
    s.addShape('roundRect', {
      x: col.x, y: 1.15, w: colW, h: 5.5,
      fill: { color: C.bgLight }, rectRadius: 0.15,
      line: { color: C.border, width: 0.5 },
    })
    // 欄位標題背景
    s.addShape('roundRect', {
      x: col.x, y: 1.15, w: colW, h: 0.65,
      fill: { color: col.accentBg }, rectRadius: 0.15,
    })
    // 遮住底部圓角讓標題底邊是直的
    s.addShape('rect', {
      x: col.x, y: 1.5, w: colW, h: 0.35,
      fill: { color: col.accentBg }, line: { color: col.accentBg },
    })
    // 欄位標題
    s.addText(stripMd(col.data.heading), {
      x: col.x + 0.3, y: 1.2, w: colW - 0.6, h: 0.55,
      fontSize: 16, bold: true, color: col.accent, fontFace: FONT, valign: 'middle',
    })
    if (col.data.bullets && col.data.bullets.length) {
      const baseOpts = {
        fontSize: 13, color: C.text, fontFace: FONT,
        lineSpacingMultiple: 1.5, paraSpaceAfter: 6,
      }
      const items = col.data.bullets.flatMap(b =>
        bulletToRuns(b, baseOpts, { code: '2022', color: col.accent })
      )
      s.addText(items, { x: col.x + 0.3, y: 2.0, w: colW - 0.6, h: 4.4, valign: 'top' })
    }
  }
  if (slide.notes) s.addNotes(slide.notes)
}

function addChartSlide(pptx, slide, idx, total) {
  const s = pptx.addSlide()
  s.background = { fill: C.white }
  addFrameBars(s)
  addFooter(s, idx, total)
  addSectionTitle(s, slide.title)

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
    // 圖表卡片背景
    s.addShape('roundRect', {
      x: 0.5, y: 1.15, w: 11.5, h: 5.5,
      fill: { color: C.bgLight }, rectRadius: 0.15,
      line: { color: C.border, width: 0.5 },
    })

    const isPie = slide.chart_type === 'pie' || slide.chart_type === 'doughnut'
    s.addChart(chartType, datasets, {
      x: isPie ? 2.5 : 1.0, y: 1.4, w: isPie ? 8 : 10.5, h: 5.0,
      showTitle: false,
      showValue: true,
      valueFontSize: 10,
      valueFontFace: FONT_EN,
      catAxisLabelFontSize: 11,
      catAxisLabelFontFace: FONT,
      valAxisLabelFontSize: 10,
      valAxisLabelFontFace: FONT_EN,
      chartColors: CHART_COLORS.slice(0, Math.max(datasets.length, labels.length)),
      legendPos: datasets.length > 1 || isPie ? 'b' : 'none',
      legendFontSize: 10,
      legendFontFace: FONT,
      dataLabelPosition: isPie ? 'outEnd' : 'outEnd',
      showPercent: isPie,
    })
  }
  if (slide.notes) s.addNotes(slide.notes)
}

function addTableSlide(pptx, slide, idx, total) {
  const s = pptx.addSlide()
  s.background = { fill: C.white }
  addFrameBars(s)
  addFooter(s, idx, total)
  addSectionTitle(s, slide.title)

  const headers = slide.headers || []
  const rows = slide.rows || []

  const headerRow = headers.map(h => ({
    text: stripMd(h), options: {
      bold: true, fontSize: 12, color: C.white,
      fill: { color: C.primary },
      fontFace: FONT, align: 'center', valign: 'middle',
    },
  }))

  const dataRows = rows.map((row, ri) =>
    row.map(cell => ({
      text: stripMd(String(cell)), options: {
        fontSize: 11, color: C.text,
        fill: { color: ri % 2 === 0 ? C.white : C.bgLight },
        fontFace: FONT, align: 'center', valign: 'middle',
      },
    }))
  )

  const tableData = [headerRow, ...dataRows]
  const totalW = 11.5
  const colW = headers.length ? (totalW / headers.length) : 2.5
  const tableX = (13.33 - totalW) / 2

  s.addTable(tableData, {
    x: tableX, y: 1.3, w: totalW,
    colW: Array(headers.length).fill(colW),
    border: { pt: 0.75, color: C.border },
    rowH: 0.55,
    autoPage: true,
  })
  if (slide.notes) s.addNotes(slide.notes)
}

function addSummarySlide(pptx, slide, idx, total) {
  const s = pptx.addSlide()
  s.background = { fill: C.white }
  addFrameBars(s)
  addFooter(s, idx, total)

  // 大標題區域（深色背景條）
  s.addShape('rect', { x: 0, y: 0.12, w: '100%', h: 1.2, fill: { color: C.dark } })
  s.addText(stripMd(slide.title) || '總結與重點回顧', {
    x: 0.8, y: 0.2, w: '80%', h: 1.0,
    fontSize: 26, bold: true, color: C.white, fontFace: FONT, valign: 'middle',
  })

  // 左側裝飾粗條
  s.addShape('rect', {
    x: 0.6, y: 1.7, w: 0.1, h: 5.0,
    fill: { color: C.primary }, rectRadius: 0.05,
  })

  if (slide.bullets && slide.bullets.length) {
    const baseOpts = {
      fontSize: 17, color: C.text, fontFace: FONT,
      lineSpacingMultiple: 2.0, paraSpaceAfter: 14,
    }
    const items = slide.bullets.flatMap(b =>
      bulletToRuns(b, baseOpts, { code: '2713', color: C.accent })
    )
    s.addText(items, { x: 1.1, y: 1.7, w: '78%', h: 5.0, valign: 'top' })
  }

  // 右下角裝飾
  s.addShape('ellipse', { x: 10.5, y: 5.0, w: 3.5, h: 3.5, fill: { color: C.primaryBg }, line: { color: C.primaryBg } })
  s.addShape('ellipse', { x: 11.3, y: 5.8, w: 2.5, h: 2.5, fill: { color: C.primaryLt }, line: { color: C.primaryLt } })

  if (slide.notes) s.addNotes(slide.notes)
}

// ── 主要匯出函數 ──

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
