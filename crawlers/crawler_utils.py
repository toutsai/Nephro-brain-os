"""
Crawler Utilities — Nephro Brain OS
====================================
共用工具模組：Firebase 初始化、PubMed API、證據分類、
AI 摘要生成（分層策略）、Firestore 儲存。

所有爬蟲共用此模組以避免程式碼重複。
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
# 1. 環境與 Firebase 初始化
# ============================================================
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

BASE_PUBMED_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

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

# ============================================================
# 2. AI 模型初始化
# ============================================================
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
gemini_client = None
gemini_types = None
if GOOGLE_API_KEY:
    from google import genai
    from google.genai import types as _gtypes
    gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
    gemini_types = _gtypes

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = None
if GROQ_API_KEY:
    groq_client = OpenAI(
        api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1"
    )

# --- 速率設定 ---
GEMINI_DELAY = 7
GROQ_DELAY = 2.5

# ============================================================
# 3. 證據級別篩選器
# ============================================================
HIGH_EVIDENCE_FILTER = (
    '("meta-analysis"[pt] OR "systematic review"[pt] '
    'OR "randomized controlled trial"[pt] OR "practice guideline"[pt])'
)
MID_EVIDENCE_FILTER = (
    '("clinical trial"[pt] OR "observational study"[pt] OR "cohort study"[pt])'
)

# ============================================================
# 4. NB Insight 摘要 Prompt
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
# 5. PubMed API 工具函式
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
# 6. 證據等級分類（零 AI 成本）
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


def _load_mesh_topic_map():
    """載入 MeSH → topic 映射表"""
    mesh_map_path = os.path.join(os.path.dirname(__file__), "mesh_topic_map.json")
    if os.path.exists(mesh_map_path):
        with open(mesh_map_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # 反轉為 {mesh_descriptor_lower: topic}
        mapping = {}
        for topic, descriptors in raw.items():
            if topic.startswith("_"):
                continue
            for desc in descriptors:
                mapping[desc.lower()] = topic
        return mapping
    return {}

_MESH_TOPIC_MAP = _load_mesh_topic_map()


def detect_topics(title: str, abstract: str, mesh_terms: list) -> list:
    # MeSH-first 策略：先用 MeSH descriptor 分類
    topics_from_mesh = set()
    if mesh_terms and _MESH_TOPIC_MAP:
        for term in mesh_terms:
            topic = _MESH_TOPIC_MAP.get(term.lower())
            if topic:
                topics_from_mesh.add(topic)

    # 如果 MeSH 已找到 topic，直接返回（更準確）
    if topics_from_mesh:
        return list(topics_from_mesh)

    # Fallback: keyword-based 偵測
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
# 7. AI 摘要生成（分層策略）
# ============================================================

def build_summary_prompt(article: dict) -> str:
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
    prompt = build_summary_prompt(article)
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
        print(f"  ⚠️ Gemini 失敗 ({article.get('pmid', '?')}): {e}")
        return None


def generate_summary_groq(article: dict) -> dict:
    if not groq_client:
        return None
    prompt = build_summary_prompt(article)
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        result = json.loads(raw)
        if isinstance(result, list):
            result = result[0]
        result["ai_model"] = "groq-llama-3.3-70b"
        return result
    except json.JSONDecodeError as e:
        print(f"  ⚠️ Groq JSON 解析失敗 ({article.get('pmid', '?')}): {e}")
        return None
    except Exception as e:
        print(f"  ⚠️ Groq 失敗 ({article.get('pmid', '?')}): {e}")
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
# 8. Firestore 儲��
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


def log_crawler_run(name: str, stats: dict):
    """記錄爬蟲執行結果到 crawler_runs_v2"""
    db.collection("crawler_runs_v2").add({
        "timestamp": datetime.utcnow(),
        "crawler": name,
        **stats,
        "status": "completed",
    })
