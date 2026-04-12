"""
NB Insight Crawler v2 — Nephro Brain OS
========================================
智慧爬蟲引擎，從 PubMed 抓取腎臟科文獻，
用分層 AI 策略產出臨床等級的結構化摘要。

核心改進（vs v1 unified_crawler.py）：
1. 統一抓取 → 全域去重（不再三個模式各跑各的）
2. 優先級佇列（Level 1-2 先處理）
3. 分層 AI：Gemini 處理高證據文獻，Groq 處理其餘
4. 嚴格限速（不再撞 quota）
5. 失敗不 fallback 燒錢 → 存入 retry queue 下次跑
6. 新 prompt 產出完整 PICO + 臨床重點 + 限制

使用方式：
  pip install firebase-admin google-genai openai requests python-dotenv
  設定 .env（見 env.example）
  python crawler_v2.py
"""

import firebase_admin
from firebase_admin import credentials, firestore
import requests
import xml.etree.ElementTree as ET
import json
import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI

# ============================================================
# 1. 設定區
# ============================================================
load_dotenv()

BASE_PUBMED_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

# --- Firebase ---
FIREBASE_SERVICE_ACCOUNT_JSON = os.getenv(
    "FIREBASE_SERVICE_ACCOUNT_JSON", "serviceAccountKey.json"
)
if not firebase_admin._apps:
    if FIREBASE_SERVICE_ACCOUNT_JSON.strip().startswith("{"):
        cred = credentials.Certificate(json.loads(FIREBASE_SERVICE_ACCOUNT_JSON))
    elif os.path.exists(FIREBASE_SERVICE_ACCOUNT_JSON):
        cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_JSON)
    else:
        raise FileNotFoundError(
            f"找不到 Firebase 憑證：{FIREBASE_SERVICE_ACCOUNT_JSON}"
        )
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --- AI 模型設定 ---
# Gemini（Level 1-2 高證據文獻）
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
gemini_client = None
gemini_types = None
if GOOGLE_API_KEY:
    from google import genai
    from google.genai import types as _gtypes
    gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
    gemini_types = _gtypes
    print("✅ Gemini 2.5 Flash 已啟用（Level 1-2）")
else:
    print("⚠️ GOOGLE_API_KEY 未設定，Level 1-2 將 fallback 到 Groq")

# Groq（Level 3-5 + fallback）
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = None
if GROQ_API_KEY:
    groq_client = OpenAI(
        api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1"
    )
    print("✅ Groq LLaMA 3.3 70B 已啟用（Level 3-5 + fallback）")
else:
    print("⚠️ GROQ_API_KEY 未設定")

# --- 速率設定 ---
GEMINI_DELAY = 7        # Gemini 免費版 10 RPM → 安全間隔 7 秒
GROQ_DELAY = 2.5        # Groq 免費版 30 RPM → 安全間隔 2.5 秒
MAX_ARTICLES_PER_RUN = 150  # 每次最多處理篇數（擴充期刊後提高）

# ============================================================
# 2. 查詢配置
# ============================================================

TARGET_JOURNALS = {
    "JASN": '"J Am Soc Nephrol"[Journal]',
    "CJASN": '"Clin J Am Soc Nephrol"[Journal]',
    "Kidney Int": '"Kidney Int"[Journal]',
    "Nat Rev Nephrol": '"Nat Rev Nephrol"[Journal]',
    "NEJM": '"N Engl J Med"[Journal] AND (Kidney OR Renal OR Dialysis)',
    "Lancet": '"Lancet"[Journal] AND (Kidney OR Renal OR Dialysis)',
    "JAMA": '"JAMA"[Journal] AND (Kidney OR Renal OR Dialysis)',
    # Phase 4: 擴充期刊
    "AJT": '"Am J Transplant"[Journal]',
    "Transplantation": '"Transplantation"[Journal] AND (Kidney OR Renal)',
    "NDT": '"Nephrol Dial Transplant"[Journal]',
    "AJKD": '"Am J Kidney Dis"[Journal]',
    "Kidney360": '"Kidney360"[Journal]',
    "KI Reports": '"Kidney Int Rep"[Journal]',
}

TOPIC_QUERIES = {
    "ESRD/HD": (
        "((ESRD[tiab] OR ESKD[tiab] OR end stage renal disease[tiab]) "
        "OR (hemodialysis[tiab] OR haemodialysis[tiab] OR dialysis[tiab]))"
    ),
    "AKI": "(acute kidney injury[tiab] OR AKI[tiab]) AND (kidney OR renal)",
    "CKD": "(chronic kidney disease[tiab] OR CKD[tiab]) AND (kidney OR renal)",
    # Phase 2: 新增主題
    "GN": (
        "((glomerulonephritis[tiab] OR glomerulopathy[tiab] OR nephrotic syndrome[tiab] "
        "OR IgA nephropathy[tiab] OR membranous nephropathy[tiab] OR FSGS[tiab] "
        "OR lupus nephritis[tiab] OR ANCA vasculitis[tiab] OR minimal change[tiab]))"
    ),
    "Transplant": (
        "((kidney transplant[tiab] OR renal transplant[tiab] OR transplant rejection[tiab] "
        "OR immunosuppression[tiab]) AND (kidney OR renal))"
    ),
    "Electrolyte": (
        "((hyperkalemia[tiab] OR hypokalemia[tiab] OR hyponatremia[tiab] OR hypernatremia[tiab] "
        "OR metabolic acidosis[tiab] OR hypercalcemia[tiab] OR hypocalcemia[tiab] "
        "OR hyperphosphatemia[tiab]) AND (kidney OR renal OR nephrology))"
    ),
    "PD": (
        "((peritoneal dialysis[tiab] OR PD catheter[tiab] OR peritonitis[tiab]) "
        "AND (kidney OR renal OR dialysis))"
    ),
    # Phase 3: 擴充主題
    "CKM": (
        "((diabetic kidney disease[tiab] OR diabetic nephropathy[tiab] OR DKD[tiab] "
        "OR SGLT2 inhibitor[tiab] OR dapagliflozin[tiab] OR empagliflozin[tiab] "
        "OR canagliflozin[tiab] OR GLP-1[tiab] OR semaglutide[tiab] OR finerenone[tiab] "
        "OR cardiorenal[tiab] OR heart failure[tiab]) AND (kidney OR renal OR nephropathy))"
    ),
    "HTN": (
        "((hypertensive nephrosclerosis[tiab] OR hypertensive kidney[tiab] "
        "OR renal artery stenosis[tiab] OR resistant hypertension[tiab] "
        "OR renovascular[tiab]) AND (kidney OR renal))"
    ),
    "PKD": (
        "((polycystic kidney[tiab] OR ADPKD[tiab] OR ARPKD[tiab] OR tolvaptan[tiab] "
        "OR Alport syndrome[tiab] OR Fabry disease[tiab] OR hereditary nephritis[tiab]) "
        "AND (kidney OR renal))"
    ),
    "CKD-MBD": (
        "((secondary hyperparathyroidism[tiab] OR phosphate binder[tiab] "
        "OR calciphylaxis[tiab] OR renal osteodystrophy[tiab] OR CKD-MBD[tiab] "
        "OR vitamin D[tiab]) AND (kidney OR renal OR dialysis OR CKD))"
    ),
    "Stone": (
        "((nephrolithiasis[tiab] OR kidney stone[tiab] OR renal calculi[tiab] "
        "OR urolithiasis[tiab] OR hyperoxaluria[tiab] OR uric acid stone[tiab]))"
    ),
    "Onco-Nephro": (
        "((checkpoint inhibitor[tiab] OR tumor lysis syndrome[tiab] "
        "OR cisplatin nephrotoxicity[tiab] OR onconephrology[tiab] "
        "OR monoclonal gammopathy[tiab] OR MGRS[tiab] OR amyloidosis[tiab] "
        "OR myeloma kidney[tiab]) AND (kidney OR renal OR nephrology))"
    ),
}

HIGH_EVIDENCE_FILTER = (
    '("meta-analysis"[pt] OR "systematic review"[pt] '
    'OR "randomized controlled trial"[pt] OR "practice guideline"[pt])'
)
MID_EVIDENCE_FILTER = (
    '("clinical trial"[pt] OR "observational study"[pt] OR "cohort study"[pt])'
)

# ============================================================
# 3. NB Insight Prompt
# ============================================================

NB_INSIGHT_PROMPT = """你是資深腎臟科專科醫師，負責為 Nephro Brain OS 的 NB Insight 模組產出臨床等級的結構化文獻摘要。

請閱讀以下論文資訊，並以繁體中文整理，專有名詞可保留英文（如 AKI、CKD、ESRD、CRRT、HDF 等）。

標題：{title}
期刊：{journal}
發表日期：{pubdate}
研究類型：{evidence_group}
主題分類：{topic}
摘要：{abstract}

請以嚴格 JSON 格式回傳（不要加 markdown code block，不要加任何其他文字）：
{{
  "title_zh": "繁體中文標題（15字內，精準傳達核心發現）",
  "study_design": "研究設計與族群（一句話，含國家/中心數/人數）",
  "summary_points": [
    "摘要重點1（含**粗體**標示關鍵數字，如 HR、OR、CI）",
    "摘要重點2",
    "摘要重點3"
  ],
  "pico": {{
    "P": "族群（具體描述，含人數與特徵）",
    "I": "介入/暴露（具體描述）",
    "C": "對照（具體描述）",
    "O": "主要結局（含數字，如 HR、95% CI、p 值）"
  }},
  "clinical_takeaways": [
    "臨床重點1（可行動導向）",
    "臨床重點2",
    "臨床重點3"
  ],
  "limitations": [
    "限制1",
    "限制2"
  ],
  "next_steps": "建議的下一步（臨床或研究延伸，1-2句）",
  "study_quality": {{
    "score": "1-5（5=最高品質，如大型 RCT；1=最低，如 case report）",
    "strengths": ["方法學優點1"],
    "weaknesses": ["方法學缺點1"]
  }}
}}"""

# ============================================================
# 4. PubMed 工具函式
# ============================================================

def get_date_range(days: int) -> str:
    today = datetime.utcnow().date()
    start = today - timedelta(days=days)
    return (
        f'("{start.year}/{start.month:02d}/{start.day:02d}"[dp] : '
        f'"{today.year}/{today.month:02d}/{today.day:02d}"[dp])'
    )


def search_pubmed(query: str, max_results: int = 15) -> list:
    try:
        search_url = (
            f"{BASE_PUBMED_URL}esearch.fcgi?"
            f"db=pubmed&term={query}&retmode=json&retmax={max_results}&sort=date"
        )
        resp = requests.get(search_url, timeout=15).json()
        pmids = resp.get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return []

        summary_url = (
            f"{BASE_PUBMED_URL}esummary.fcgi?"
            f"db=pubmed&id={','.join(pmids)}&retmode=json"
        )
        summary_resp = requests.get(summary_url, timeout=15).json()
        results = summary_resp.get("result", {})

        articles = []
        for pmid in pmids:
            if pmid in results and isinstance(results[pmid], dict):
                data = results[pmid]
                articles.append({
                    "pmid": pmid,
                    "title": data.get("title", ""),
                    "pubdate": data.get("pubdate", ""),
                    "source": data.get("source", ""),
                    "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                })
        return articles
    except Exception as e:
        print(f"  ⚠️ PubMed 搜尋失敗: {e}")
        return []


def fetch_article_details(pmid: str) -> dict:
    try:
        url = f"{BASE_PUBMED_URL}efetch.fcgi?db=pubmed&id={pmid}&retmode=xml"
        resp = requests.get(url, timeout=15)
        root = ET.fromstring(resp.content)

        abstract_parts = []
        for ab in root.findall(".//AbstractText"):
            if ab.text:
                label = ab.get("Label")
                abstract_parts.append(
                    f"{label}: {ab.text}" if label else ab.text
                )

        mesh = [
            m.text
            for m in root.findall(".//MeshHeading/DescriptorName")
            if m.text
        ][:10]

        pub_types = [
            p.text for p in root.findall(".//PublicationType") if p.text
        ]

        journal = root.findtext(".//Journal/Title") or ""
        year = root.findtext(".//PubDate/Year") or ""
        month = root.findtext(".//PubDate/Month") or ""
        day = root.findtext(".//PubDate/Day") or ""
        pubdate = f"{year} {month} {day}".strip()

        return {
            "abstract": "\n".join(abstract_parts),
            "mesh_terms": mesh,
            "publication_types": pub_types,
            "journal": journal,
            "pubdate": pubdate,
        }
    except Exception as e:
        print(f"  ⚠️ efetch 失敗 ({pmid}): {e}")
        return {
            "abstract": "",
            "mesh_terms": [],
            "publication_types": [],
            "journal": "",
            "pubdate": "",
        }


# ============================================================
# 5. 證據等級分類（零 AI 成本）
# ============================================================

def classify_evidence(pub_types: list) -> tuple:
    """回傳 (evidence_group, evidence_level, priority)"""
    lower = [p.lower() for p in pub_types]

    if any(x in lower for x in ["meta-analysis", "systematic review"]):
        return "Meta-analysis / Systematic Review", "Level 1", 0
    if any(x in lower for x in ["practice guideline", "guideline"]):
        return "Guideline", "Level 1", 0
    if any(
        x in lower
        for x in ["randomized controlled trial", "clinical trial, phase iii"]
    ):
        return "RCT", "Level 2", 0
    if "clinical trial" in lower:
        return "Clinical Trial", "Level 2", 0
    if any(x in lower for x in ["observational study", "cohort study"]):
        return "Observational", "Level 3", 1
    if "case reports" in lower:
        return "Case Report", "Level 4", 2
    return "Other", "Level 5", 2


def detect_topics(title: str, abstract: str, mesh_terms: list) -> list:
    text = f"{title} {abstract} {' '.join(mesh_terms)}".lower()
    topics = []

    esrd_kw = [
        "esrd", "eskd", "end stage", "hemodialysis", "haemodialysis",
        "dialysis", "hemodiafiltration",
    ]
    aki_kw = [
        "acute kidney injury", " aki ", "acute renal failure",
        "crrt", "continuous renal replacement",
    ]
    ckd_kw = [
        "chronic kidney disease", " ckd ", "chronic renal",
        "proteinuria", "albuminuria",
    ]
    # Phase 2: 新增主題偵測
    gn_kw = [
        "glomerulonephritis", "glomerulopathy", "nephrotic syndrome",
        "iga nephropathy", "membranous nephropathy", "fsgs",
        "lupus nephritis", "anca vasculitis", "minimal change",
        "nephritic", "complement", "c3 glomerulopathy",
    ]
    transplant_kw = [
        "kidney transplant", "renal transplant", "transplantation",
        "rejection", "tacrolimus", "immunosuppression",
        "donor", "allograft", "bk virus",
    ]
    electrolyte_kw = [
        "hyperkalemia", "hypokalemia", "hyponatremia", "hypernatremia",
        "metabolic acidosis", "metabolic alkalosis",
        "hypercalcemia", "hypocalcemia", "hyperphosphatemia",
        "electrolyte", "acid-base",
    ]
    pd_kw = [
        "peritoneal dialysis", "pd catheter", "peritonitis",
        "capd", "apd", "automated peritoneal",
    ]
    # Phase 3: 擴充主題偵測
    ckm_kw = [
        "diabetic kidney", "diabetic nephropathy", " dkd ",
        "sglt2", "dapagliflozin", "empagliflozin", "canagliflozin",
        "glp-1", "semaglutide", "liraglutide", "tirzepatide",
        "finerenone", "cardiorenal", "cardio-renal",
        "heart failure", "type 2 diabetes",
    ]
    htn_kw = [
        "hypertensive nephrosclerosis", "hypertensive kidney",
        "renal artery stenosis", "resistant hypertension",
        "renovascular", "malignant hypertension",
    ]
    pkd_kw = [
        "polycystic kidney", "adpkd", "arpkd", "tolvaptan",
        "alport syndrome", "fabry disease", "hereditary nephritis",
        "thin basement membrane",
    ]
    ckd_mbd_kw = [
        "hyperparathyroidism", "phosphate binder", "calciphylaxis",
        "renal osteodystrophy", "ckd-mbd", "vitamin d",
        "calcimimetic", "cinacalcet", "etelcalcetide",
        "paricalcitol", "bone mineral",
    ]
    stone_kw = [
        "nephrolithiasis", "kidney stone", "renal calculi",
        "urolithiasis", "hyperoxaluria", "uric acid stone",
        "calcium oxalate", "struvite", "cystinuria",
    ]
    onco_nephro_kw = [
        "checkpoint inhibitor", "tumor lysis", "cisplatin nephrotoxicity",
        "onconephrology", "monoclonal gammopathy", " mgrs ",
        "amyloidosis", "myeloma kidney", "myeloma cast",
        "light chain deposition",
    ]

    if any(kw in text for kw in esrd_kw):
        topics.append("ESRD/HD")
    if any(kw in text for kw in aki_kw):
        topics.append("AKI")
    if any(kw in text for kw in ckd_kw):
        topics.append("CKD")
    if any(kw in text for kw in gn_kw):
        topics.append("GN")
    if any(kw in text for kw in transplant_kw):
        topics.append("Transplant")
    if any(kw in text for kw in electrolyte_kw):
        topics.append("Electrolyte")
    if any(kw in text for kw in pd_kw):
        topics.append("PD")
    if any(kw in text for kw in ckm_kw):
        topics.append("CKM")
    if any(kw in text for kw in htn_kw):
        topics.append("HTN")
    if any(kw in text for kw in pkd_kw):
        topics.append("PKD")
    if any(kw in text for kw in ckd_mbd_kw):
        topics.append("CKD-MBD")
    if any(kw in text for kw in stone_kw):
        topics.append("Stone")
    if any(kw in text for kw in onco_nephro_kw):
        topics.append("Onco-Nephro")

    return topics if topics else ["CKD"]


# ============================================================
# 6. AI 摘要生成（分層策略）
# ============================================================

def _build_prompt(article: dict) -> str:
    return NB_INSIGHT_PROMPT.format(
        title=article["title"],
        journal=article.get("journal", ""),
        pubdate=article.get("pubdate", ""),
        evidence_group=article.get("evidence_group", ""),
        topic=", ".join(article.get("topics", [])),
        abstract=article["abstract"],
    )


def generate_summary_gemini(article: dict) -> dict:
    if not gemini_client:
        return None
    prompt = _build_prompt(article)
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=gemini_types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )
        result = json.loads(response.text)
        if isinstance(result, list):
            result = result[0]
        result["ai_model"] = "gemini-2.5-flash"
        return result
    except Exception as e:
        print(f"  ⚠️ Gemini 失敗 ({article['pmid']}): {e}")
        return None


def generate_summary_groq(article: dict) -> dict:
    if not groq_client:
        return None
    prompt = _build_prompt(article)
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000,
        )
        raw = response.choices[0].message.content.strip()
        # 清理 markdown code block
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        result = json.loads(raw)
        if isinstance(result, list):
            result = result[0]
        result["ai_model"] = "groq-llama-3.3-70b"
        return result
    except json.JSONDecodeError as e:
        print(f"  ⚠️ Groq JSON 解析失敗 ({article['pmid']}): {e}")
        return None
    except Exception as e:
        print(f"  ⚠️ Groq 失敗 ({article['pmid']}): {e}")
        return None


def generate_summary(article: dict) -> dict:
    """
    分層 AI 策略：
    - priority 0 (Level 1-2) → Gemini，失敗降級 Groq
    - priority 1-2 (Level 3-5) → Groq
    """
    priority = article.get("priority", 2)

    if priority == 0:
        result = generate_summary_gemini(article)
        if result:
            time.sleep(GEMINI_DELAY)
            return result
        print(f"  ↘️ Gemini 失敗，降級到 Groq")
        result = generate_summary_groq(article)
        if result:
            time.sleep(GROQ_DELAY)
            return result
    else:
        result = generate_summary_groq(article)
        if result:
            time.sleep(GROQ_DELAY)
            return result

    return None


# ============================================================
# 7. Firestore 儲存
# ============================================================

def article_exists(pmid: str) -> bool:
    doc = db.collection("articles_v2").document(pmid).get()
    if not doc.exists:
        return False
    data = doc.to_dict()
    return bool(data.get("pico")) and bool(data.get("clinical_takeaways"))


def save_article(pmid: str, data: dict) -> str:
    doc_ref = db.collection("articles_v2").document(pmid)
    existing = doc_ref.get()

    if existing.exists:
        existing_data = existing.to_dict()
        data["topics"] = list(
            set(existing_data.get("topics", []) + data.get("topics", []))
        )
        data["journals"] = list(
            set(existing_data.get("journals", []) + data.get("journals", []))
        )

        if existing_data.get("pico") and existing_data.get("clinical_takeaways"):
            doc_ref.update({
                "topics": data["topics"],
                "journals": data["journals"],
                "updated_at": datetime.utcnow(),
            })
            return "updated_tags"

    data["updated_at"] = datetime.utcnow()
    data.setdefault("created_at", datetime.utcnow())
    doc_ref.set(data, merge=True)
    return "created"


def save_to_retry_queue(article: dict, error: str):
    db.collection("crawler_retry_queue").document(article["pmid"]).set(
        {
            "pmid": article["pmid"],
            "title": article["title"],
            "priority": article.get("priority", 2),
            "error": error,
            "retry_count": firestore.Increment(1),
            "last_attempt": datetime.utcnow(),
        },
        merge=True,
    )


# ============================================================
# 8. 主流程 Pipeline
# ============================================================

def step1_fetch_all_pmids() -> dict:
    """統一抓取所有來源的 PMID，回傳去重後的 dict"""
    print("\n" + "=" * 60)
    print("📥 Step 1：統一抓取 PubMed")
    print("=" * 60)

    all_articles = {}
    date_range = get_date_range(14)

    # 7 大期刊
    print("\n📰 期刊來源：")
    for journal_tag, search_term in TARGET_JOURNALS.items():
        query = f"{search_term} AND {date_range}"
        articles = search_pubmed(query, max_results=10)
        for a in articles:
            pmid = a["pmid"]
            if pmid not in all_articles:
                all_articles[pmid] = {
                    **a,
                    "journals": [journal_tag],
                    "sources": ["journal"],
                    "topics": [],
                }
            else:
                if journal_tag not in all_articles[pmid]["journals"]:
                    all_articles[pmid]["journals"].append(journal_tag)
        print(f"  {journal_tag}: {len(articles)} 篇")
        time.sleep(0.5)

    # 3 大主題
    print("\n🔬 主題來源：")
    for topic, base_query in TOPIC_QUERIES.items():
        query = f"({base_query}) AND {HIGH_EVIDENCE_FILTER} AND {date_range}"
        articles = search_pubmed(query, max_results=10)
        if len(articles) < 5:
            query2 = f"({base_query}) AND {MID_EVIDENCE_FILTER} AND {date_range}"
            articles += search_pubmed(query2, max_results=5)

        for a in articles:
            pmid = a["pmid"]
            if pmid not in all_articles:
                all_articles[pmid] = {
                    **a,
                    "journals": [],
                    "sources": ["topic"],
                    "topics": [topic],
                }
            else:
                if topic not in all_articles[pmid].get("topics", []):
                    all_articles[pmid]["topics"].append(topic)
                if "topic" not in all_articles[pmid]["sources"]:
                    all_articles[pmid]["sources"].append("topic")
        print(f"  {topic}: {len(articles)} 篇")
        time.sleep(0.5)

    print(f"\n  📊 去重後共 {len(all_articles)} 篇唯一文章")
    return all_articles


def step2_dedup_and_enrich(all_articles: dict) -> list:
    """比對 Firestore 去重 + 補充資訊 + 證據分類 + 排序"""
    print("\n" + "=" * 60)
    print("🔍 Step 2：去重 + 證據分類")
    print("=" * 60)

    to_process = []
    skipped = 0

    for pmid, article in all_articles.items():
        if article_exists(pmid):
            skipped += 1
            continue

        details = fetch_article_details(pmid)
        abstract = details["abstract"]
        if not abstract or len(abstract) < 50:
            continue

        evidence_group, evidence_level, priority = classify_evidence(
            details["publication_types"]
        )
        detected_topics = detect_topics(
            article["title"], abstract, details["mesh_terms"]
        )
        merged_topics = list(set(article.get("topics", []) + detected_topics))

        to_process.append({
            **article,
            "abstract": abstract,
            "journal": details["journal"] or article.get("source", ""),
            "pubdate": details["pubdate"] or article.get("pubdate", ""),
            "mesh_terms": details["mesh_terms"],
            "publication_types": details["publication_types"],
            "evidence_group": evidence_group,
            "evidence_level": evidence_level,
            "priority": priority,
            "topics": merged_topics,
        })
        time.sleep(0.4)

    to_process.sort(key=lambda x: x["priority"])

    if len(to_process) > MAX_ARTICLES_PER_RUN:
        print(f"  ⚠️ 超過上限，截取前 {MAX_ARTICLES_PER_RUN} 篇")
        to_process = to_process[:MAX_ARTICLES_PER_RUN]

    level_counts = {}
    for a in to_process:
        lv = a["evidence_level"]
        level_counts[lv] = level_counts.get(lv, 0) + 1

    print(f"  ⏭️ 已跳過（已有完整摘要）：{skipped} 篇")
    print(f"  📋 待處理：{len(to_process)} 篇")
    for lv, count in sorted(level_counts.items()):
        model = "→ Gemini" if lv in ("Level 1", "Level 2") else "→ Groq"
        print(f"     {lv}: {count} 篇 {model}")

    return to_process


def step3_generate_summaries(articles: list) -> tuple:
    """用分層 AI 生成結構化摘要，回傳 (成功, 失敗)"""
    print("\n" + "=" * 60)
    print("🤖 Step 3：AI 結構化摘要生成")
    print("=" * 60)

    success, failed = [], []

    for i, article in enumerate(articles, 1):
        pmid = article["pmid"]
        level = article["evidence_level"]
        model_hint = "Gemini" if article["priority"] == 0 else "Groq"
        print(f"\n  [{i}/{len(articles)}] {pmid} [{level}] → {model_hint}")
        print(f"  📄 {article['title'][:60]}...")

        result = generate_summary(article)

        if result:
            article["ai_summary"] = result
            success.append(article)
            model_used = result.get("ai_model", "?")
            title_zh = result.get("title_zh", "?")[:20]
            print(f"  ✅ {title_zh}... ({model_used})")
        else:
            failed.append(article)
            save_to_retry_queue(article, "AI summary generation failed")
            print(f"  ❌ 失敗，已加入 retry queue")

    print(f"\n  📊 結果：✅ {len(success)} / ❌ {len(failed)}")
    return success, failed


def step4_save_to_firestore(articles: list) -> dict:
    """將成功的文章存入 Firestore articles_v2"""
    print("\n" + "=" * 60)
    print("💾 Step 4：存入 Firestore")
    print("=" * 60)

    stats = {"created": 0, "updated_tags": 0, "errors": 0}

    for article in articles:
        pmid = article["pmid"]
        summary = article.get("ai_summary", {})

        try:
            data = {
                "id": pmid,
                "title": article["title"],
                "title_zh": summary.get("title_zh", ""),
                "abstract": article["abstract"],
                "study_design": summary.get("study_design", ""),
                "summary_points": summary.get("summary_points", []),
                "pico": summary.get("pico", {}),
                "clinical_takeaways": summary.get("clinical_takeaways", []),
                "limitations": summary.get("limitations", []),
                "next_steps": summary.get("next_steps", ""),
                "link": article["link"],
                "pubdate": article.get("pubdate", ""),
                "journal": article.get("journal", ""),
                "journals": article.get("journals", []),
                "topics": article.get("topics", []),
                "mesh_terms": article.get("mesh_terms", []),
                "publication_types": article.get("publication_types", []),
                "evidence_group": article.get("evidence_group", ""),
                "evidence_level": article.get("evidence_level", ""),
                "priority": article.get("priority", 2),
                "ai_model": summary.get("ai_model", ""),
                "sources": article.get("sources", []),
                "process_status": "completed",
            }

            result = save_article(pmid, data)
            stats[result] = stats.get(result, 0) + 1
            title_zh = summary.get("title_zh", pmid)[:30]
            print(f"  ✅ {result}: {title_zh}")

        except Exception as e:
            stats["errors"] += 1
            print(f"  ❌ 儲存失敗 ({pmid}): {e}")

    return stats


def process_retry_queue():
    """處理之前失敗的 retry queue（每次最多 10 篇）"""
    print("\n" + "=" * 60)
    print("🔄 處理 Retry Queue")
    print("=" * 60)

    try:
        retries = (
            db.collection("crawler_retry_queue")
            .where("retry_count", "<", 3)
            .order_by("last_attempt")
            .limit(10)
            .stream()
        )

        retry_list = list(retries)
        if not retry_list:
            print("  📭 沒有待重試的文章")
            return

        print(f"  📋 找到 {len(retry_list)} 篇待重試")

        for doc in retry_list:
            item = doc.to_dict()
            pmid = item["pmid"]

            if article_exists(pmid):
                db.collection("crawler_retry_queue").document(pmid).delete()
                continue

            details = fetch_article_details(pmid)
            if not details["abstract"]:
                continue

            evidence_group, evidence_level, priority = classify_evidence(
                details["publication_types"]
            )

            article = {
                "pmid": pmid,
                "title": item["title"],
                "abstract": details["abstract"],
                "journal": details["journal"],
                "pubdate": details["pubdate"],
                "evidence_group": evidence_group,
                "evidence_level": evidence_level,
                "priority": priority,
                "topics": detect_topics(
                    item["title"],
                    details["abstract"],
                    details.get("mesh_terms", []),
                ),
                "mesh_terms": details.get("mesh_terms", []),
                "publication_types": details.get("publication_types", []),
                "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "journals": [],
                "sources": ["retry"],
            }

            result = generate_summary(article)
            if result:
                article["ai_summary"] = result
                step4_save_to_firestore([article])
                db.collection("crawler_retry_queue").document(pmid).delete()
                print(f"  ✅ 重試成功：{pmid}")
            else:
                print(f"  ❌ 重試仍失敗：{pmid}")

    except Exception as e:
        print(f"  ⚠️ Retry queue 處理失敗: {e}")


# ============================================================
# 9. 主程式
# ============================================================

def main():
    start_time = time.time()

    print("\n" + "=" * 60)
    print("🚀 NB Insight Crawler v2")
    print(f"⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("🤖 Gemini 2.5 Flash (L1-2) + Groq LLaMA 3.3 70B (L3-5)")
    print("=" * 60)

    # Pipeline
    all_articles = step1_fetch_all_pmids()
    to_process = step2_dedup_and_enrich(all_articles)

    if to_process:
        success, failed = step3_generate_summaries(to_process)
        save_stats = step4_save_to_firestore(success) if success else {}
    else:
        success, failed = [], []
        save_stats = {}
        print("\n  📭 沒有新文章需要處理")

    # Retry queue
    process_retry_queue()

    # 執行記錄
    elapsed = round(time.time() - start_time, 1)
    db.collection("crawler_runs_v2").add({
        "timestamp": datetime.utcnow(),
        "total_fetched": len(all_articles),
        "processed": len(success),
        "failed": len(failed),
        "created": save_stats.get("created", 0),
        "updated_tags": save_stats.get("updated_tags", 0),
        "errors": save_stats.get("errors", 0),
        "elapsed_seconds": elapsed,
        "status": "completed",
        "version": "v2",
    })

    # 報告
    print("\n" + "=" * 60)
    print("📊 執行完成！")
    print("=" * 60)
    print(f"  📥 抓取：{len(all_articles)} 篇（去重後）")
    print(f"  🤖 處理：{len(success)} 篇成功 / {len(failed)} 篇失敗")
    print(f"  💾 新增：{save_stats.get('created', 0)} 篇")
    print(f"  🏷️ 更新標籤：{save_stats.get('updated_tags', 0)} 篇")
    print(f"  ⏱️ 耗時：{elapsed} 秒")
    print("=" * 60)


if __name__ == "__main__":
    main()
