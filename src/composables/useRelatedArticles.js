/**
 * Composable: useRelatedArticles
 * Finds related Insight articles based on keyword-to-topic matching.
 */

const KEYWORD_TOPIC_MAP = {
  'ESRD/HD': [
    '透析', 'dialysis', 'hemodialysis', '血液透析',
    'esrd', 'eskd', 'end stage', 'hemodiafiltration',
  ],
  'AKI': [
    '急性腎損傷', 'acute kidney injury', 'aki', 'crrt', '急性腎衰竭',
  ],
  'CKD': [
    '慢性腎臟病', 'chronic kidney', 'ckd', 'proteinuria', 'albuminuria', '蛋白尿',
  ],
  'GN': [
    '腎絲球腎炎', 'glomerulonephritis', 'nephrotic', 'iga',
    'lupus nephritis', 'fsgs', '膜性腎病',
  ],
  'Transplant': [
    '腎移植', 'transplant', '移植', 'rejection', 'tacrolimus', 'immunosuppression',
  ],
  'Electrolyte': [
    '電解質', 'electrolyte', 'hyperkalemia', 'hyponatremia',
    '高血鉀', '低血鈉', 'acid-base',
  ],
  'PD': [
    '腹膜透析', 'peritoneal dialysis', 'capd', 'apd',
  ],
  'CKM': [
    '糖尿病腎病', 'diabetic kidney', 'sglt2', 'finerenone', 'cardiorenal', '心腎',
  ],
  'HTN': [
    '高血壓', 'hypertension', 'renovascular', '腎動脈',
  ],
  'PKD': [
    '多囊腎', 'polycystic', 'adpkd', 'tolvaptan',
  ],
  'CKD-MBD': [
    '副甲狀腺', 'hyperparathyroidism', 'phosphate', 'calciphylaxis', '骨礦', 'vitamin d',
  ],
  'Stone': [
    '腎結石', 'nephrolithiasis', 'kidney stone', 'urolithiasis', '結石',
  ],
  'Onco-Nephro': [
    '腫瘤腎臟', 'tumor lysis', 'cisplatin', 'amyloidosis', 'myeloma',
  ],
}

/**
 * Detect which topics are relevant to the given question text.
 * @param {string} text - The question text (will be lowercased internally)
 * @returns {string[]} Array of matched topic keys
 */
function detectTopics(text) {
  const lower = text.toLowerCase()
  const matched = []

  for (const [topic, keywords] of Object.entries(KEYWORD_TOPIC_MAP)) {
    for (const kw of keywords) {
      if (lower.includes(kw.toLowerCase())) {
        matched.push(topic)
        break
      }
    }
  }

  return matched
}

/**
 * Parse a created_at value into a Date for sorting.
 * Handles Firestore Timestamp objects (with .toDate()) and plain values.
 */
function parseDate(createdAt) {
  if (!createdAt) return new Date(0)
  if (typeof createdAt.toDate === 'function') return createdAt.toDate()
  const d = new Date(createdAt)
  return isNaN(d.getTime()) ? new Date(0) : d
}

/**
 * Find related articles based on topic overlap with a question text.
 *
 * @param {string} questionText - The user's question or search text
 * @param {Array} articles - Array of article objects (each should have a `topics` array)
 * @param {number} [limit=5] - Maximum number of articles to return
 * @returns {Array} Matching articles sorted by created_at descending
 */
function findRelated(questionText, articles, limit = 5) {
  if (!questionText || !articles || !articles.length) return []

  const matchedTopics = detectTopics(questionText)
  if (!matchedTopics.length) return []

  const topicSet = new Set(matchedTopics)

  const filtered = articles.filter((article) => {
    const articleTopics = article.topics || []
    return articleTopics.some((t) => topicSet.has(t))
  })

  filtered.sort((a, b) => {
    const dateA = parseDate(a.created_at)
    const dateB = parseDate(b.created_at)
    return dateB.getTime() - dateA.getTime()
  })

  return filtered.slice(0, limit)
}

export function useRelatedArticles() {
  return { findRelated }
}
