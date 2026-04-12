"""
ClinicalTrials.gov Crawler — Nephro Brain OS
=============================================
從 ClinicalTrials.gov REST API v2 抓取腎臟科相關臨床試驗，
翻譯標題與摘要後存入 Firestore。

API 免費、無需 API key。

使用方式：
  pip install firebase-admin openai requests python-dotenv
  設定 .env（見 env.example）
  python crawler_clinicaltrials.py
  python crawler_clinicaltrials.py --dry-run --limit 10
"""

import argparse
import json
import logging
import time
from datetime import datetime

import requests

from crawler_utils import db, groq_client, GROQ_DELAY, detect_topics, log_crawler_run

# ============================================================
# 設定
# ============================================================

CLINICALTRIALS_API = "https://clinicaltrials.gov/api/v2/studies"

SEARCH_COND = (
    "chronic kidney disease OR acute kidney injury OR dialysis "
    "OR nephrology OR glomerulonephritis OR kidney transplant "
    "OR nephrotic syndrome OR polycystic kidney OR IgA nephropathy "
    "OR lupus nephritis OR ANCA vasculitis OR FSGS "
    "OR diabetic kidney disease OR peritoneal dialysis "
    "OR hemodialysis OR renal replacement therapy"
)

# 排除純腫瘤試驗的關鍵字（conditions 中包含這些且不含腎臟內科關鍵字時跳過）
ONCO_EXCLUDE_KEYWORDS = [
    "renal cell carcinoma", "kidney cancer", "bladder cancer",
    "urothelial", "solid tumor", "advanced solid",
    "metastatic cancer", "metastatic renal",
]
NEPHRO_INCLUDE_KEYWORDS = [
    "kidney disease", "ckd", "akut", "aki", "dialysis", "nephro",
    "glomerul", "nephrotic", "transplant", "lupus nephritis",
    "vasculitis", "fsgs", "iga", "polycystic", "membranous",
    "proteinuria", "renal insufficiency", "eskd", "esrd",
]

FIELDS = (
    "NCTId,BriefTitle,OfficialTitle,OverallStatus,BriefSummary,"
    "Condition,InterventionName,InterventionType,Phase,"
    "EnrollmentCount,EnrollmentType,LeadSponsorName,"
    "StartDate,PrimaryCompletionDate,StudyType,"
    "LocationCity,LocationCountry"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# API 抓取
# ============================================================

def fetch_studies(status_filter: str, page_size: int = 100, max_results: int = 100):
    """從 ClinicalTrials.gov API v2 分頁抓取研究。"""
    all_studies = []
    next_page_token = None

    while len(all_studies) < max_results:
        params = {
            "query.cond": SEARCH_COND,
            "filter.overallStatus": status_filter,
            "fields": FIELDS,
            "pageSize": min(page_size, max_results - len(all_studies)),
            "sort": "LastUpdatePostDate:desc",
        }
        if next_page_token:
            params["pageToken"] = next_page_token

        logger.info("Fetching page (已取得 %d 筆)...", len(all_studies))
        resp = requests.get(CLINICALTRIALS_API, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        studies = data.get("studies", [])
        if not studies:
            break

        all_studies.extend(studies)
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    logger.info("共取得 %d 筆研究", len(all_studies))
    return all_studies[:max_results]


# ============================================================
# 資料解析
# ============================================================

def parse_study(study: dict) -> dict:
    """將 API 回傳的 study 結構解析為扁平 dict。"""
    proto = study.get("protocolSection", {})
    ident = proto.get("identificationModule", {})
    status_mod = proto.get("statusModule", {})
    desc = proto.get("descriptionModule", {})
    design = proto.get("designModule", {})
    sponsor_mod = proto.get("sponsorCollaboratorsModule", {})
    arms = proto.get("armsInterventionsModule", {})
    cond_mod = proto.get("conditionsModule", {})
    contacts_loc = proto.get("contactsLocationsModule", {})

    nct_id = ident.get("nctId", "")
    brief_title = ident.get("briefTitle", "")
    official_title = ident.get("officialTitle", "")
    overall_status = status_mod.get("overallStatus", "")
    brief_summary = desc.get("briefSummary", "")

    # Conditions
    conditions = cond_mod.get("conditions", [])

    # Interventions
    interventions = []
    for iv in arms.get("interventions", []):
        interventions.append({
            "type": iv.get("type", ""),
            "name": iv.get("name", ""),
        })

    # Phase
    phases = design.get("phases", [])
    phase = ", ".join(phases) if phases else ""

    # Enrollment
    enrollment_info = design.get("enrollmentInfo", {})
    enrollment = enrollment_info.get("count", 0) or 0
    study_type = design.get("studyType", "")

    # Sponsor
    lead_sponsor = sponsor_mod.get("leadSponsor", {})
    sponsor = lead_sponsor.get("name", "")

    # Dates
    start_date_struct = status_mod.get("startDateStruct", {})
    start_date = start_date_struct.get("date", "")
    completion_struct = status_mod.get("primaryCompletionDateStruct", {})
    estimated_completion = completion_struct.get("date", "")

    # Locations — check for Taiwan
    has_taiwan_site = False
    locations = contacts_loc.get("locations", [])
    for loc in locations:
        country = loc.get("country", "")
        if country and country.lower() in ("taiwan", "taiwan, province of china"):
            has_taiwan_site = True
            break

    return {
        "nct_id": nct_id,
        "title": brief_title,
        "official_title": official_title,
        "status": overall_status,
        "brief_summary": brief_summary,
        "conditions": conditions,
        "interventions": interventions,
        "phase": phase,
        "enrollment": enrollment,
        "study_type": study_type,
        "sponsor": sponsor,
        "start_date": start_date,
        "estimated_completion": estimated_completion,
        "has_taiwan_site": has_taiwan_site,
    }


# ============================================================
# AI 翻譯（Groq，最低成本）
# ============================================================

TRANSLATE_PROMPT = """請將以下臨床試驗資訊翻譯成繁體中文。藥物名稱一律維持英文（如 Dapagliflozin、Rituximab），醫學縮寫亦保留英文（如 CKD、SGLT2、GFR 等）。

請以 JSON 格式回傳（不要加 markdown code block）：
{{"title_zh": "繁體中文標題", "summary_zh": "繁體中文簡要摘要（2-3句話）"}}

標題：{title}
摘要：{summary}"""


def translate_with_groq(title: str, summary: str) -> dict:
    """用 Groq 翻譯標題與摘要。"""
    if not groq_client:
        logger.warning("Groq 未設定，跳過翻譯")
        return {"title_zh": "", "summary_zh": ""}

    prompt = TRANSLATE_PROMPT.format(title=title, summary=summary[:1500])
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=500,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        result = json.loads(raw)
        return {
            "title_zh": result.get("title_zh", ""),
            "summary_zh": result.get("summary_zh", ""),
        }
    except json.JSONDecodeError as e:
        logger.warning("Groq JSON 解析失敗: %s", e)
        return {"title_zh": "", "summary_zh": ""}
    except Exception as e:
        logger.warning("Groq 翻譯失敗: %s", e)
        return {"title_zh": "", "summary_zh": ""}


# ============================================================
# Firestore 存儲
# ============================================================

def check_existing(nct_id: str) -> dict | None:
    """檢查 clinical_trials 是否已存在該文件。"""
    doc = db.collection("clinical_trials").document(nct_id).get()
    if doc.exists:
        return doc.to_dict()
    return None


def save_trial(nct_id: str, data: dict) -> str:
    """儲存或更新臨床試驗到 Firestore。"""
    doc_ref = db.collection("clinical_trials").document(nct_id)
    data["updated_at"] = datetime.utcnow()
    data.setdefault("created_at", datetime.utcnow())
    doc_ref.set(data, merge=True)
    return "saved"


# ============================================================
# 主流程
# ============================================================

def run(dry_run: bool = False, limit_count: int = 100, status_filter: str = "RECRUITING,ACTIVE_NOT_RECRUITING"):
    logger.info("=== ClinicalTrials.gov Crawler 開始 ===")
    logger.info("篩選狀態: %s | 上限: %d | dry_run: %s", status_filter, limit_count, dry_run)

    stats = {
        "total_fetched": 0,
        "new": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }

    # 1. 抓取
    try:
        studies = fetch_studies(status_filter, page_size=100, max_results=limit_count)
    except Exception as e:
        logger.error("API 抓取失敗: %s", e)
        stats["errors"] = 1
        log_crawler_run("clinicaltrials", stats)
        return stats

    stats["total_fetched"] = len(studies)

    # 2. 逐筆處理
    for i, study in enumerate(studies):
        parsed = parse_study(study)
        nct_id = parsed["nct_id"]
        if not nct_id:
            stats["errors"] += 1
            continue

        logger.info("[%d/%d] %s — %s", i + 1, len(studies), nct_id, parsed["title"][:60])

        # 過濾純腫瘤試驗（conditions 中只有癌症，沒有腎臟內科關鍵字）
        all_text = f"{parsed['title']} {' '.join(parsed['conditions'])} {parsed.get('brief_summary', '')}".lower()
        is_onco = any(kw in all_text for kw in ONCO_EXCLUDE_KEYWORDS)
        is_nephro = any(kw in all_text for kw in NEPHRO_INCLUDE_KEYWORDS)
        if is_onco and not is_nephro:
            logger.info("  → 跳過（純腫瘤試驗）")
            stats["skipped"] += 1
            continue

        # 去重檢查
        existing = check_existing(nct_id)
        if existing:
            if existing.get("status") == parsed["status"]:
                logger.info("  → 已存在且狀態未變，跳過")
                stats["skipped"] += 1
                continue
            else:
                logger.info("  → 狀態更新: %s → %s", existing.get("status"), parsed["status"])

        # 主題偵測
        conditions_text = " ".join(parsed["conditions"])
        intervention_names = " ".join(iv["name"] for iv in parsed["interventions"])
        topics = detect_topics(
            parsed["title"],
            f"{parsed['brief_summary']} {conditions_text} {intervention_names}",
            [],
        )

        # AI 翻譯
        title_zh = ""
        summary_zh = ""
        if not dry_run and groq_client:
            translation = translate_with_groq(parsed["title"], parsed["brief_summary"])
            title_zh = translation["title_zh"]
            summary_zh = translation["summary_zh"]
            time.sleep(GROQ_DELAY)

        # 組合文件
        doc_data = {
            "nct_id": nct_id,
            "title": parsed["title"],
            "official_title": parsed["official_title"],
            "title_zh": title_zh,
            "status": parsed["status"],
            "phase": parsed["phase"],
            "conditions": parsed["conditions"],
            "interventions": parsed["interventions"],
            "sponsor": parsed["sponsor"],
            "enrollment": parsed["enrollment"],
            "study_type": parsed["study_type"],
            "topics": topics,
            "summary_zh": summary_zh,
            "has_taiwan_site": parsed["has_taiwan_site"],
            "start_date": parsed["start_date"],
            "estimated_completion": parsed["estimated_completion"],
            "link": f"https://clinicaltrials.gov/study/{nct_id}",
            "source": "clinicaltrials",
            "process_status": "completed",
        }

        if dry_run:
            logger.info("  [DRY RUN] 資料: %s", json.dumps(doc_data, ensure_ascii=False, default=str)[:200])
            stats["new"] += 1
            continue

        # 儲存
        try:
            save_trial(nct_id, doc_data)
            if existing:
                stats["updated"] += 1
            else:
                stats["new"] += 1
        except Exception as e:
            logger.error("  儲存失敗 (%s): %s", nct_id, e)
            stats["errors"] += 1

    # 3. 記錄執行結果
    if not dry_run:
        log_crawler_run("clinicaltrials", stats)

    logger.info("=== 完成 === %s", stats)
    return stats


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ClinicalTrials.gov 腎臟科臨床試驗爬蟲")
    parser.add_argument("--dry-run", action="store_true", help="僅抓取不寫入 Firestore")
    parser.add_argument("--limit", type=int, default=100, help="最多抓取筆數 (預設 100)")
    parser.add_argument(
        "--status",
        type=str,
        default="RECRUITING,ACTIVE_NOT_RECRUITING",
        help="篩選試驗狀態 (預設 RECRUITING,ACTIVE_NOT_RECRUITING)",
    )
    args = parser.parse_args()

    run(dry_run=args.dry_run, limit_count=args.limit, status_filter=args.status)
