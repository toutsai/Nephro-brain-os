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
  s.addText(slide.title || '', {
    x: 0.8, y: 1.5, w: '85%', h: 1.5,
    fontSize: 36, bold: true, color: WHITE, fontFace: FONT_FACE,
    align: 'left', valign: 'bottom',
  })
  s.addText(slide.subtitle || '', {
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
  s.addText(slide.title || '', {
    x: 0.6, y: 0.3, w: '88%', h: 0.7,
    fontSize: 24, bold: true, color: SECONDARY, fontFace: FONT_FACE,
  })
  if (slide.bullets && slide.bullets.length) {
    const items = slide.bullets.map(b => ({
      text: b, options: {
        bullet: { code: '25CF', color: PRIMARY },
        fontSize: 16, color: SECONDARY, fontFace: FONT_FACE,
        lineSpacingMultiple: 1.5,
        indentLevel: 0,
        paraSpaceAfter: 8,
      },
    }))
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
  s.addText(slide.title || '', {
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
    s.addText(col.data.heading || '', {
      x: col.x, y: 1.2, w: colWidth, h: 0.5,
      fontSize: 18, bold: true, color: PRIMARY, fontFace: FONT_FACE,
    })
    if (col.data.bullets && col.data.bullets.length) {
      const items = col.data.bullets.map(b => ({
        text: b, options: {
          bullet: { code: '2022', color: GRAY },
          fontSize: 14, color: SECONDARY, fontFace: FONT_FACE,
          lineSpacingMultiple: 1.4,
          paraSpaceAfter: 6,
        },
      }))
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
  s.addText(slide.title || '', {
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
  s.addText(slide.title || '', {
    x: 0.6, y: 0.3, w: '88%', h: 0.7,
    fontSize: 24, bold: true, color: SECONDARY, fontFace: FONT_FACE,
  })

  const headers = slide.headers || []
  const rows = slide.rows || []

  const headerRow = headers.map(h => ({
    text: h, options: {
      bold: true, fontSize: 12, color: WHITE, fill: { color: PRIMARY },
      fontFace: FONT_FACE, align: 'center', valign: 'middle',
    },
  }))

  const dataRows = rows.map((row, ri) =>
    row.map(cell => ({
      text: String(cell), options: {
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
  s.addText(slide.title || '總結', {
    x: 0.6, y: 0.3, w: '88%', h: 0.7,
    fontSize: 24, bold: true, color: SECONDARY, fontFace: FONT_FACE,
  })
  // Left accent bar for summary bullets
  s.addShape('rect', {
    x: 0.6, y: 1.2, w: 0.06, h: 4.5,
    fill: { color: PRIMARY },
  })
  if (slide.bullets && slide.bullets.length) {
    const items = slide.bullets.map(b => ({
      text: b, options: {
        bullet: { code: '2713', color: PRIMARY },
        fontSize: 18, color: SECONDARY, fontFace: FONT_FACE,
        lineSpacingMultiple: 1.8,
        paraSpaceAfter: 12,
      },
    }))
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
