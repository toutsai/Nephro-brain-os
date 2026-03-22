/**
 * PPT Builder — 使用 pptxgenjs 將結構化 JSON 轉為 .pptx 下載
 * 支援 4 種色彩主題 + 重要文字自動粗體紅色
 */

const FONT = 'Microsoft JhengHei'
const FONT_EN = 'Segoe UI'

// ── 色彩主題預設 ──
const THEMES = {
  orange: {
    primary:    'F97316', primaryDk: 'EA580C', primaryLt: 'FFEDD5', primaryBg: 'FFF7ED',
    accent:     '0D9488', accentLt:  'CCFBF1',
    dark:       '0F172A', text: '1E293B', textLt: '94A3B8',
    border:     'E2E8F0', bgLight: 'F8FAFC', bgCard: 'F1F5F9', white: 'FFFFFF',
    highlight:  'DC2626',
    chartColors: ['F97316', '0D9488', '3B82F6', '8B5CF6', 'EC4899', 'EAB308'],
  },
  blue: {
    primary:    '3B82F6', primaryDk: '2563EB', primaryLt: 'DBEAFE', primaryBg: 'EFF6FF',
    accent:     'F59E0B', accentLt:  'FEF3C7',
    dark:       '0F172A', text: '1E293B', textLt: '94A3B8',
    border:     'E2E8F0', bgLight: 'F8FAFC', bgCard: 'F1F5F9', white: 'FFFFFF',
    highlight:  'DC2626',
    chartColors: ['3B82F6', 'F59E0B', '10B981', '8B5CF6', 'EC4899', 'F97316'],
  },
  green: {
    primary:    '10B981', primaryDk: '059669', primaryLt: 'D1FAE5', primaryBg: 'ECFDF5',
    accent:     '6366F1', accentLt:  'E0E7FF',
    dark:       '0F172A', text: '1E293B', textLt: '94A3B8',
    border:     'E2E8F0', bgLight: 'F8FAFC', bgCard: 'F1F5F9', white: 'FFFFFF',
    highlight:  'DC2626',
    chartColors: ['10B981', '6366F1', 'F97316', '3B82F6', 'EC4899', 'EAB308'],
  },
  bw: {
    primary:    '1E293B', primaryDk: '0F172A', primaryLt: 'E2E8F0', primaryBg: 'F8FAFC',
    accent:     '475569', accentLt:  'F1F5F9',
    dark:       '0F172A', text: '1E293B', textLt: '94A3B8',
    border:     'CBD5E1', bgLight: 'F8FAFC', bgCard: 'F1F5F9', white: 'FFFFFF',
    highlight:  'DC2626',
    chartColors: ['1E293B', '64748B', '94A3B8', 'CBD5E1', '475569', '334155'],
  },
}

/** 取得主題色彩，預設 orange */
function getTheme(name) {
  return THEMES[name] || THEMES.orange
}

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

/** 將 bullet 轉為 pptxgenjs text runs — **粗體** 自動變成粗體+紅色 */
function bulletToRuns(bulletText, baseOpts, bulletOpt, T) {
  const segments = parseMarkdownRuns(bulletText)
  return segments.map((seg, i) => {
    const opts = { ...baseOpts }
    if (seg.bold) { opts.bold = true; opts.color = T.highlight }
    if (seg.italic) opts.italic = true
    if (seg.code) { opts.fontFace = 'Consolas'; opts.color = T.highlight }
    if (i === 0 && bulletOpt) opts.bullet = bulletOpt
    if (i < segments.length - 1) opts.breakLine = false
    return { text: seg.text, options: opts }
  })
}

function stripMd(str) {
  if (!str || typeof str !== 'string') return str || ''
  return str.replace(/\*\*(.+?)\*\*/g, '$1').replace(/\*(.+?)\*/g, '$1').replace(/`(.+?)`/g, '$1')
}

// ── 共用裝飾元素（主題感知） ──

function addFrameBars(s, T) {
  s.addShape('rect', { x: 0, y: 0, w: '100%', h: 0.12, fill: { color: T.primary } })
  s.addShape('rect', { x: 0, y: 7.38, w: '100%', h: 0.12, fill: { color: T.bgCard } })
}

function addCornerDeco(s, T) {
  s.addShape('ellipse', { x: 11.8, y: 5.8, w: 2.2, h: 2.2, fill: { color: T.primaryLt }, line: { color: T.primaryLt } })
  s.addShape('ellipse', { x: 12.3, y: 6.3, w: 1.5, h: 1.5, fill: { color: T.primaryBg }, line: { color: T.primaryBg } })
}

function addFooter(s, num, total, T) {
  s.addText(`${num} / ${total}`, {
    x: '88%', y: '93%', w: '10%', h: 0.3,
    fontSize: 9, color: T.textLt, align: 'right', fontFace: FONT_EN,
  })
  s.addText('NB Teach', {
    x: 0.4, y: '93%', w: 1.5, h: 0.3,
    fontSize: 8, color: T.border, fontFace: FONT_EN, italic: true,
  })
}

function addSectionTitle(s, title, T) {
  s.addShape('rect', { x: 0.5, y: 0.35, w: 0.08, h: 0.55, fill: { color: T.primary }, rectRadius: 0.04 })
  s.addText(stripMd(title), {
    x: 0.8, y: 0.3, w: '85%', h: 0.65,
    fontSize: 22, bold: true, color: T.dark, fontFace: FONT, valign: 'middle',
  })
}

// ── Layout Builders（主題感知） ──

function addTitleSlide(pptx, slide, _idx, _total, T) {
  const s = pptx.addSlide()
  s.background = { fill: T.primary }
  s.addShape('ellipse', { x: 9, y: -1.5, w: 6, h: 6, fill: { color: T.primaryDk }, line: { color: T.primaryDk } })
  s.addShape('ellipse', { x: 10, y: -0.8, w: 4.5, h: 4.5, fill: { color: T.primary }, line: { color: T.primary } })
  s.addShape('ellipse', { x: -0.8, y: 5.5, w: 3, h: 3, fill: { color: T.primaryDk }, line: { color: T.primaryDk } })
  s.addText(stripMd(slide.title), {
    x: 1.0, y: 2.0, w: 9, h: 2.0,
    fontSize: 40, bold: true, color: T.white, fontFace: FONT, align: 'left', valign: 'middle',
  })
  s.addShape('rect', { x: 1.0, y: 4.1, w: 2.5, h: 0.06, fill: { color: T.white } })
  s.addText(stripMd(slide.subtitle), {
    x: 1.0, y: 4.3, w: 9, h: 0.8,
    fontSize: 18, color: T.primaryLt, fontFace: FONT, align: 'left',
  })
  s.addText('NB Teach', {
    x: 1.0, y: 6.6, w: 3, h: 0.5,
    fontSize: 12, color: T.primaryLt, fontFace: FONT_EN, italic: true,
  })
  if (slide.notes) s.addNotes(slide.notes)
}

function addContentSlide(pptx, slide, idx, total, T) {
  const s = pptx.addSlide()
  s.background = { fill: T.white }
  addFrameBars(s, T)
  addCornerDeco(s, T)
  addFooter(s, idx, total, T)
  addSectionTitle(s, slide.title, T)

  if (slide.bullets && slide.bullets.length) {
    s.addShape('roundRect', {
      x: 0.5, y: 1.15, w: 11.5, h: 5.5,
      fill: { color: T.bgLight }, rectRadius: 0.15,
      line: { color: T.border, width: 0.5 },
    })
    const baseOpts = {
      fontSize: 15, color: T.text, fontFace: FONT,
      lineSpacingMultiple: 1.6, paraSpaceAfter: 10,
    }
    const items = slide.bullets.flatMap(b =>
      bulletToRuns(b, baseOpts, { code: '25CF', color: T.primary }, T)
    )
    s.addText(items, { x: 0.9, y: 1.35, w: 10.7, h: 5.1, valign: 'top' })
  }
  if (slide.notes) s.addNotes(slide.notes)
}

function addTwoColumnSlide(pptx, slide, idx, total, T) {
  const s = pptx.addSlide()
  s.background = { fill: T.white }
  addFrameBars(s, T)
  addFooter(s, idx, total, T)
  addSectionTitle(s, slide.title, T)

  const colW = 5.6
  const configs = [
    { data: slide.left, x: 0.5, accent: T.primary, accentBg: T.primaryBg },
    { data: slide.right, x: 6.7, accent: T.accent, accentBg: T.accentLt },
  ]

  for (const col of configs) {
    if (!col.data) continue
    s.addShape('roundRect', {
      x: col.x, y: 1.15, w: colW, h: 5.5,
      fill: { color: T.bgLight }, rectRadius: 0.15,
      line: { color: T.border, width: 0.5 },
    })
    s.addShape('roundRect', {
      x: col.x, y: 1.15, w: colW, h: 0.65,
      fill: { color: col.accentBg }, rectRadius: 0.15,
    })
    s.addShape('rect', {
      x: col.x, y: 1.5, w: colW, h: 0.35,
      fill: { color: col.accentBg }, line: { color: col.accentBg },
    })
    s.addText(stripMd(col.data.heading), {
      x: col.x + 0.3, y: 1.2, w: colW - 0.6, h: 0.55,
      fontSize: 16, bold: true, color: col.accent, fontFace: FONT, valign: 'middle',
    })
    if (col.data.bullets && col.data.bullets.length) {
      const baseOpts = {
        fontSize: 13, color: T.text, fontFace: FONT,
        lineSpacingMultiple: 1.5, paraSpaceAfter: 6,
      }
      const items = col.data.bullets.flatMap(b =>
        bulletToRuns(b, baseOpts, { code: '2022', color: col.accent }, T)
      )
      s.addText(items, { x: col.x + 0.3, y: 2.0, w: colW - 0.6, h: 4.4, valign: 'top' })
    }
  }
  if (slide.notes) s.addNotes(slide.notes)
}

function addChartSlide(pptx, slide, idx, total, T) {
  const s = pptx.addSlide()
  s.background = { fill: T.white }
  addFrameBars(s, T)
  addFooter(s, idx, total, T)
  addSectionTitle(s, slide.title, T)

  const chartTypeMap = {
    bar: pptx.charts.BAR, pie: pptx.charts.PIE,
    line: pptx.charts.LINE, doughnut: pptx.charts.DOUGHNUT,
  }
  const chartType = chartTypeMap[slide.chart_type] || pptx.charts.BAR
  const cd = slide.chart_data || {}
  const labels = cd.labels || []
  const datasets = (cd.datasets || []).map((ds, i) => ({
    name: ds.name || `Series ${i + 1}`, labels, values: ds.values || [],
  }))

  if (datasets.length && labels.length) {
    s.addShape('roundRect', {
      x: 0.5, y: 1.15, w: 11.5, h: 5.5,
      fill: { color: T.bgLight }, rectRadius: 0.15,
      line: { color: T.border, width: 0.5 },
    })
    const isPie = slide.chart_type === 'pie' || slide.chart_type === 'doughnut'
    s.addChart(chartType, datasets, {
      x: isPie ? 2.5 : 1.0, y: 1.4, w: isPie ? 8 : 10.5, h: 5.0,
      showTitle: false, showValue: true,
      valueFontSize: 10, valueFontFace: FONT_EN,
      catAxisLabelFontSize: 11, catAxisLabelFontFace: FONT,
      valAxisLabelFontSize: 10, valAxisLabelFontFace: FONT_EN,
      chartColors: T.chartColors.slice(0, Math.max(datasets.length, labels.length)),
      legendPos: datasets.length > 1 || isPie ? 'b' : 'none',
      legendFontSize: 10, legendFontFace: FONT,
      dataLabelPosition: 'outEnd', showPercent: isPie,
    })
  }
  if (slide.notes) s.addNotes(slide.notes)
}

function addTableSlide(pptx, slide, idx, total, T) {
  const s = pptx.addSlide()
  s.background = { fill: T.white }
  addFrameBars(s, T)
  addFooter(s, idx, total, T)
  addSectionTitle(s, slide.title, T)

  const headers = slide.headers || []
  const rows = slide.rows || []

  const headerRow = headers.map(h => ({
    text: stripMd(h), options: {
      bold: true, fontSize: 12, color: T.white,
      fill: { color: T.primary },
      fontFace: FONT, align: 'center', valign: 'middle',
    },
  }))
  const dataRows = rows.map((row, ri) =>
    row.map(cell => ({
      text: stripMd(String(cell)), options: {
        fontSize: 11, color: T.text,
        fill: { color: ri % 2 === 0 ? T.white : T.bgLight },
        fontFace: FONT, align: 'center', valign: 'middle',
      },
    }))
  )

  const totalW = 11.5
  const colW = headers.length ? (totalW / headers.length) : 2.5
  const tableX = (13.33 - totalW) / 2

  s.addTable([headerRow, ...dataRows], {
    x: tableX, y: 1.3, w: totalW,
    colW: Array(headers.length).fill(colW),
    border: { pt: 0.75, color: T.border }, rowH: 0.55, autoPage: true,
  })
  if (slide.notes) s.addNotes(slide.notes)
}

function addSummarySlide(pptx, slide, idx, total, T) {
  const s = pptx.addSlide()
  s.background = { fill: T.white }
  addFrameBars(s, T)
  addFooter(s, idx, total, T)

  s.addShape('rect', { x: 0, y: 0.12, w: '100%', h: 1.2, fill: { color: T.dark } })
  s.addText(stripMd(slide.title) || '總結與重點回顧', {
    x: 0.8, y: 0.2, w: '80%', h: 1.0,
    fontSize: 26, bold: true, color: T.white, fontFace: FONT, valign: 'middle',
  })

  s.addShape('rect', {
    x: 0.6, y: 1.7, w: 0.1, h: 5.0,
    fill: { color: T.primary }, rectRadius: 0.05,
  })

  if (slide.bullets && slide.bullets.length) {
    const baseOpts = {
      fontSize: 17, color: T.text, fontFace: FONT,
      lineSpacingMultiple: 2.0, paraSpaceAfter: 14,
    }
    const items = slide.bullets.flatMap(b =>
      bulletToRuns(b, baseOpts, { code: '2713', color: T.accent }, T)
    )
    s.addText(items, { x: 1.1, y: 1.7, w: '78%', h: 5.0, valign: 'top' })
  }

  s.addShape('ellipse', { x: 10.5, y: 5.0, w: 3.5, h: 3.5, fill: { color: T.primaryBg }, line: { color: T.primaryBg } })
  s.addShape('ellipse', { x: 11.3, y: 5.8, w: 2.5, h: 2.5, fill: { color: T.primaryLt }, line: { color: T.primaryLt } })

  if (slide.notes) s.addNotes(slide.notes)
}

// ── 主要匯出函數 ──

/**
 * 將結構化 JSON 轉為 .pptx 並觸發下載
 * @param {Object} slidesJson - { title, slides: [...] }
 * @param {string} filename - 檔名（含 .pptx）
 * @param {Object} options - { theme: 'orange'|'blue'|'green'|'bw' }
 */
export async function buildAndDownloadPptx(slidesJson, filename, options = {}) {
  const PptxGenJS = (await import('pptxgenjs')).default
  const pptx = new PptxGenJS()
  const T = getTheme(options.theme || slidesJson.theme || 'orange')

  pptx.defineLayout({ name: 'WIDE', width: 13.33, height: 7.5 })
  pptx.layout = 'WIDE'
  pptx.author = 'NB Teach'
  pptx.title = slidesJson.title || 'NB Teach PPT'

  const slides = slidesJson.slides || []
  const total = slides.length

  const builders = {
    title: addTitleSlide, content: addContentSlide,
    two_column: addTwoColumnSlide, chart: addChartSlide,
    table: addTableSlide, summary: addSummarySlide,
  }

  for (let i = 0; i < slides.length; i++) {
    const slide = slides[i]
    const builder = builders[slide.layout] || addContentSlide
    builder(pptx, slide, i + 1, total, T)
  }

  await pptx.writeFile({ fileName: filename })
}
