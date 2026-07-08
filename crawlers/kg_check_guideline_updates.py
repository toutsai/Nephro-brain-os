"""
Knowledge Graph Guideline Update Checker — Nephro Brain OS
============================================================
批次比對知識圖譜概念底下已連結的指引章節（guideline_chapters）既有建議，
與該概念底下近期發表的高證據等級文獻（articles_v2, evidence_level Level 1/2），
呼叫 Gemini 判斷是否有可能促使指引建議更新的新證據，
有則寫入 kg_guideline_flags 佇列，草擬 suggested_update_reason（繁體中文，藥名英文）。

AI 產出的 flag 一律以 status="pending" 寫入，需人工於前台審核後才生效
（本檔不得包含任何 auto-approve 邏輯）。

使用方式：
  python crawlers/kg_check_guideline_updates.py                        # 處理前 20 個概念
  python crawlers/kg_check_guideline_updates.py --dry-run              # 預覽，不寫入
  python crawlers/kg_check_guideline_updates.py --limit 5              # 只處理前 5 個概念
  python crawlers/kg_check_guideline_updates.py --concept-id ckd       # 處理指定概念
  python crawlers/kg_check_guideline_updates.py --since-year 2023      # 只考慮 2023 年後的文獻
"""

import argparse
import json
import logging
import re
import time
from datetime import datetime, timezone  # noqa: F401  (契約 E 節共通 import；本檔以 log_crawler_run 記錄時間)

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from crawler_utils import db, gemini_client, gemini_types, GEMINI_DELAY, log_crawler_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================
# 常數
# ============================================================

GEMINI_MODEL = "gemini-2.5-flash"
HIGH_EVIDENCE_LEVELS = {"Level 1", "Level 2"}
MAX_CANDIDATE_ARTICLES_PER_CHAPTER = 10  # 避免單一章節候選文獻過多導致 prompt 過長（非契約規定，內部保護值）
MAX_RECOMMENDATIONS_DISPLAYED = 15  # 同上，內部保護值

GUIDELINE_CHECK_PROMPT = """你是腎臟科臨床指引最新性稽核專家。以下是某指引章節的既有建議，以及該概念底下近期發表、證據等級較高的文獻。
請你判斷：這些新文獻是否提供了可能促使此章節既有建議更新的新證據。

指引章節：{chapter_title}（組織：{org}，版本年份：{version_year}）

既有建議：
{recommendations_block}

近期高證據等級文獻（僅列出可能與本章節相關者）：
{articles_block}

規則：
1. 只有在文獻證據明確可能挑戰或更新既有建議時，才回報 has_update=true；若證據不足、僅重複驗證既有建議、或與既有建議無關，回報 has_update=false。
2. suggested_update_reason 使用繁體中文撰寫（可用 Markdown），只在 has_update=true 時需要非空；藥物名稱一律維持英文（如 Dapagliflozin、Tacrolimus），醫學縮寫亦保留英文（如 AKI、CKD、ESRD 等）。
3. cited_article_ids 只能引用上面提供的文獻（見每篇文獻前的 [doc_id: ...] 標記），不得編造或引用未列出的文獻。
4. current_recommendation 請從上方「既有建議」中摘錄你認為被挑戰的那一條原文（繁體中文）；若不確定或 has_update=false，留空字串。

請以嚴格 JSON 格式回傳（不要加 markdown code block，不要加任何其他文字），格式如下：
{{
  "has_update": true,
  "current_recommendation": "被挑戰的既有建議原文（可空字串）",
  "cited_article_ids": ["<doc_id_1>"],
  "suggested_update_reason": "更新理由（繁體中文 Markdown，藥名英文）"
}}"""


# ============================================================
# 查詢需要檢查的概念
# ============================================================

def load_concepts_for_check(
    limit: int = 20,
    concept_id: str | None = None,
) -> list[dict]:
    """載入待檢查概念。

    契約 E 節原文：「kg_concepts（--concept-id 指定或取 status=approved/未設；--limit 筆）」。
    但 repo 現況中 kg_concepts 並無 `status` 欄位，實際欄位是 `synthesis_status`
    （見 crawlers/kg_build_concepts.py:417、backend/api_server.py:3391，
    值域 draft/pending_review/approved/rejected）。此處比照 crawlers/kg_generate_insights.py
    （同一契約下的姊妹爬蟲，已對此做相同調整）以 `synthesis_status` 取代契約字面的 `status`，
    語意對應：approved 或未設定該欄位；跳過 draft/pending_review/rejected。
    """
    if concept_id:
        doc = db.collection("kg_concepts").document(concept_id).get()
        if not doc.exists:
            logger.warning("找不到概念: %s", concept_id)
            return []
        data = doc.to_dict()
        data["_id"] = doc.id
        return [data]

    concepts = []
    docs = db.collection("kg_concepts").stream()
    for doc in docs:
        data = doc.to_dict()
        synthesis_status = data.get("synthesis_status")
        if synthesis_status not in (None, "", "approved"):
            continue
        data["_id"] = doc.id
        concepts.append(data)

    if limit > 0:
        concepts = concepts[:limit]

    logger.info("載入 %d 個待檢查的概念", len(concepts))
    return concepts


# ============================================================
# 取得概念底下的連結（指引章節 + 文獻）
# ============================================================

def fetch_concept_links(concept_id: str) -> list[dict]:
    """取得概念的所有 kg_links（未過濾 source_type/status，交由呼叫端過濾）"""
    docs = db.collection("kg_links").where("concept_id", "==", concept_id).stream()
    links = []
    for doc in docs:
        data = doc.to_dict()
        data["_id"] = doc.id
        links.append(data)
    return links


def select_ids_by_type(links: list[dict], source_type: str) -> list[str]:
    """從 links 過濾出指定 source_type 且 status in ('approved','pending') 的 source_id（去重、保序）。

    契約 E.2 未明文要求對 guideline links 做 status 過濾（僅 E.1 對 article links 明文如此），
    但 kg_generate_synthesis.py:fetch_links_for_concept 與 kg_generate_insights.py:select_article_ids
    均一致排除 rejected 連結；此處對 guideline 與 article 兩者都比照辦理，避免把已被人工拒絕的
    連結當作有效資料來源。
    """
    ids = []
    seen = set()
    for link in links:
        if link.get("source_type") != source_type:
            continue
        if link.get("status") not in ("approved", "pending"):
            continue
        source_id = link.get("source_id")
        if source_id and source_id not in seen:
            ids.append(source_id)
            seen.add(source_id)
    return ids


# ============================================================
# 取得指引章節與文獻詳細內容
# ============================================================

def fetch_guideline_chapter(chapter_id: str) -> dict | None:
    """從 guideline_chapters 取得章節的 chapter_title/key_recommendations/version_year/org"""
    try:
        doc = db.collection("guideline_chapters").document(chapter_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        recs = data.get("key_recommendations", [])
        if not isinstance(recs, list):
            recs = []
        return {
            "_id": doc.id,
            "chapter_title": data.get("chapter_title", ""),
            "guideline_title": data.get("guideline_title", ""),
            "org": data.get("org", ""),
            "version_year": data.get("version_year"),
            "key_recommendations": recs,
        }
    except Exception as e:
        logger.warning("取得指引章節 %s 失敗: %s", chapter_id, e)
        return None


def fetch_article_data(article_id: str) -> dict | None:
    """從 articles_v2 取得單篇文獻的 evidence_level/pubdate/clinical_takeaways/study_quality"""
    try:
        doc = db.collection("articles_v2").document(article_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        return {
            "_id": doc.id,
            "title": data.get("title", ""),
            "title_zh": data.get("title_zh", ""),
            "evidence_level": data.get("evidence_level", ""),
            "pubdate": data.get("pubdate", ""),
            "clinical_takeaways": data.get("clinical_takeaways", []),
            "study_quality": data.get("study_quality", {}),
        }
    except Exception as e:
        logger.warning("取得文獻 %s 失敗: %s", article_id, e)
        return None


# ============================================================
# 年份判斷（pubdate 可能是自由格式字串，如 "2024 Jan 15"，也可能是 datetime）
# ============================================================

def extract_pubdate_year(pubdate) -> int | None:
    """從 pubdate 擷取發表年份。pubdate 型別在 repo 現況中不一致
    （crawler_utils.fetch_article_details 存成 "YYYY Mon DD" 字串；
    亦可能是 datetime/Firestore Timestamp），故同時處理兩種型態。"""
    if pubdate is None:
        return None
    if hasattr(pubdate, "year"):
        return pubdate.year
    if isinstance(pubdate, str):
        match = re.search(r"(19|20)\d{2}", pubdate)
        if match:
            return int(match.group())
    return None


def is_high_evidence(article: dict) -> bool:
    return article.get("evidence_level") in HIGH_EVIDENCE_LEVELS


def is_candidate_new_evidence(
    article_year: int | None,
    chapter_version_year: int | None,
    since_year: int | None,
) -> bool:
    """回傳 True 表示此篇文獻的發表年份足夠新，可能挑戰指引建議。

    契約 E.2：「只把 pubdate 年份 > 章節 version_year 或 > --since-year 的高證據 article
    視為候選新證據」。此處解讀為聯集（OR）：只要滿足任一門檻（新於章節版本年份，
    或新於使用者指定的 --since-year）即視為候選；若兩門檻皆缺（章節無 version_year
    且未帶 --since-year），因無法判斷「是否夠新」，保守跳過（不視為候選）。
    """
    if article_year is None:
        return False
    thresholds = [t for t in (chapter_version_year, since_year) if t is not None]
    if not thresholds:
        return False
    return any(article_year > t for t in thresholds)


# ============================================================
# 組 Gemini prompt 內容
# ============================================================

def _rec_text(rec) -> str:
    if isinstance(rec, dict):
        return str(rec.get("text", rec.get("recommendation", "")) or "")
    return str(rec)


def build_recommendations_block(key_recommendations: list) -> str:
    parts = []
    for i, rec in enumerate(key_recommendations[:MAX_RECOMMENDATIONS_DISPLAYED], 1):
        text = _rec_text(rec).strip()
        if not text:
            continue
        grade = rec.get("grade", "") if isinstance(rec, dict) else ""
        entry = f"{i}. {text}"
        if grade:
            entry += f"（grade: {grade}）"
        parts.append(entry)
    return "\n".join(parts) if parts else "（無正式建議條列）"


def build_candidate_articles_block(articles: list[dict]) -> str:
    parts = []
    for article in articles:
        doc_id = article["_id"]
        title = article.get("title", "")
        title_zh = article.get("title_zh", "")
        evidence_level = article.get("evidence_level", "")
        year = extract_pubdate_year(article.get("pubdate"))
        study_quality = article.get("study_quality", {})
        quality_score = ""
        if isinstance(study_quality, dict):
            quality_score = study_quality.get("score", "")
        takeaways = article.get("clinical_takeaways", []) or []

        entry = f"[doc_id: {doc_id}] **{title}**"
        if title_zh:
            entry += f"（{title_zh}）"
        meta_bits = []
        if year:
            meta_bits.append(f"發表年份：{year}")
        if evidence_level:
            meta_bits.append(f"證據等級：{evidence_level}")
        if quality_score != "":
            meta_bits.append(f"研究品質分數：{quality_score}")
        if meta_bits:
            entry += "\n  " + "；".join(meta_bits)
        if takeaways:
            entry += "\n  臨床重點：" + "; ".join(str(t) for t in takeaways[:5])
        parts.append(entry)
    return "\n\n".join(parts) if parts else "（無候選文獻）"


# ============================================================
# Gemini 判斷（含防呆解析）
# ============================================================

def generate_guideline_flag(
    concept: dict,
    chapter: dict,
    candidate_articles: list[dict],
) -> dict | None:
    """呼叫 Gemini 判斷是否有可能更新指引的新證據，回傳防呆解析後的 dict 或 None。

    任何非預期格式（非 JSON object、has_update 非 bool True、cited_article_ids 非法或
    引用超出候選集合、suggested_update_reason 為空）一律視為「無候選」跳過，
    絕不因解析失敗或格式異常而寫入 approved 或殘缺資料。
    """
    if not gemini_client:
        logger.error("Gemini client 未初始化，無法檢查指引更新")
        return None

    recommendations_block = build_recommendations_block(chapter.get("key_recommendations", []))
    articles_block = build_candidate_articles_block(candidate_articles)

    prompt = GUIDELINE_CHECK_PROMPT.format(
        chapter_title=chapter.get("chapter_title", ""),
        org=chapter.get("org", ""),
        version_year=chapter.get("version_year", ""),
        recommendations_block=recommendations_block,
        articles_block=articles_block,
    )

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=gemini_types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )
        result = json.loads(response.text)
    except Exception as e:
        logger.error(
            "Gemini 指引更新檢查失敗 (concept=%s, chapter=%s): %s",
            concept.get("_id", "?"), chapter.get("_id", "?"), e,
        )
        return None

    if not isinstance(result, dict):
        logger.warning("  Gemini 回傳格式非預期（非 JSON object），跳過")
        return None

    if result.get("has_update") is not True:
        return None

    cited_ids_raw = result.get("cited_article_ids")
    if not isinstance(cited_ids_raw, list) or not cited_ids_raw:
        logger.warning("  Gemini 回傳缺少有效 cited_article_ids，跳過")
        return None
    if not all(isinstance(x, str) for x in cited_ids_raw):
        logger.warning("  cited_article_ids 含非字串元素，跳過")
        return None

    known_ids = {a["_id"] for a in candidate_articles}
    cited_ids = []
    seen = set()
    for x in cited_ids_raw:
        if x in known_ids and x not in seen:
            cited_ids.append(x)
            seen.add(x)
    if not cited_ids:
        logger.warning("  cited_article_ids 未命中任何候選文獻，跳過")
        return None

    reason = result.get("suggested_update_reason")
    if not isinstance(reason, str) or not reason.strip():
        logger.warning("  suggested_update_reason 為空，跳過")
        return None

    current_rec = result.get("current_recommendation")
    if not isinstance(current_rec, str):
        current_rec = ""

    return {
        "article_id": cited_ids[0],
        "article_ids": cited_ids,
        "suggested_update_reason": reason.strip(),
        "current_recommendation": current_rec.strip(),
    }


# ============================================================
# 寫入 Firestore
# ============================================================

def write_guideline_flag(
    concept_id: str,
    chapter_id: str,
    flag_data: dict,
    dry_run: bool = False,
):
    """寫入一筆 kg_guideline_flags 文件（欄位照契約 A.2），status 永遠是 'pending'。"""
    if dry_run:
        preview = flag_data["suggested_update_reason"][:120].replace("\n", " ")
        logger.info(
            "  [DRY RUN] 會建立 kg_guideline_flags: concept_id=%s, chapter=%s, "
            "article_id=%s, article_ids=%s, preview=%s...",
            concept_id, chapter_id, flag_data["article_id"], flag_data["article_ids"], preview,
        )
        return

    db.collection("kg_guideline_flags").add({
        "concept_id": concept_id,
        "guideline_chapter_id": chapter_id,
        "article_id": flag_data["article_id"],
        "article_ids": flag_data["article_ids"],
        "suggested_update_reason": flag_data["suggested_update_reason"],
        "current_recommendation": flag_data["current_recommendation"],
        "status": "pending",
        "ai_model": GEMINI_MODEL,
        "created_at": SERVER_TIMESTAMP,
        "review_note": "",
    })


# ============================================================
# 主程式
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Knowledge Graph Guideline Update Checker — 檢查指引章節是否有新證據可能需要更新"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="預覽模式，不寫入 Firestore"
    )
    parser.add_argument(
        "--limit", type=int, default=20, help="處理概念數量上限（預設 20）"
    )
    parser.add_argument(
        "--concept-id", type=str, default=None, help="處理指定概念 ID"
    )
    parser.add_argument(
        "--since-year", type=int, default=None,
        help="只把 pubdate 年份大於此值的高證據文獻視為候選新證據（可選，與章節 version_year 取聯集門檻）",
    )
    args = parser.parse_args()

    logger.info("=== Knowledge Graph Guideline Update Checker 開始 ===")
    logger.info(
        "模式: dry_run=%s, limit=%d, concept_id=%s, since_year=%s",
        args.dry_run, args.limit, args.concept_id, args.since_year,
    )

    if not gemini_client:
        logger.error("Gemini client 未初始化，無法執行。請確認 GOOGLE_API_KEY 設定。")
        return

    # Step 1: 載入待檢查概念
    logger.info("--- Step 1: 載入概念 ---")
    concepts = load_concepts_for_check(
        limit=args.limit,
        concept_id=args.concept_id,
    )
    if not concepts:
        logger.info("沒有符合條件的概念，結束")
        return

    stats = {
        "concepts_processed": 0,
        "concepts_skipped_no_guideline_links": 0,
        "concepts_skipped_no_article_links": 0,
        "chapters_checked": 0,
        "chapters_skipped_no_recommendations": 0,
        "chapters_skipped_no_candidate_articles": 0,
        "flags_generated": 0,
        "flags_skipped_no_update_or_failed": 0,
    }

    # Step 2: 逐概念處理
    for i, concept in enumerate(concepts, 1):
        concept_id = concept["_id"]
        concept_title = concept.get("title", concept_id)
        concept_title_zh = concept.get("title_zh", "")
        logger.info(
            "--- [%d/%d] 處理概念: %s (%s) ---",
            i, len(concepts), concept_title, concept_title_zh,
        )

        # 2a: 取得概念底下的連結，分出指引章節與文獻
        links = fetch_concept_links(concept_id)
        chapter_ids = select_ids_by_type(links, "guideline")
        article_ids = select_ids_by_type(links, "article")

        if not chapter_ids:
            logger.info("  無已連結的指引章節，跳過")
            stats["concepts_skipped_no_guideline_links"] += 1
            stats["concepts_processed"] += 1
            continue

        if not article_ids:
            logger.info("  無已連結的文獻，跳過")
            stats["concepts_skipped_no_article_links"] += 1
            stats["concepts_processed"] += 1
            continue

        # 2b: 取得文獻詳細內容（一次性載入，供各章節共用）
        articles = []
        for aid in article_ids:
            data = fetch_article_data(aid)
            if data:
                articles.append(data)

        if not articles:
            logger.info("  已連結文獻皆無法讀取，跳過")
            stats["concepts_skipped_no_article_links"] += 1
            stats["concepts_processed"] += 1
            continue

        # 2c: 逐指引章節檢查
        for chapter_id in chapter_ids:
            chapter = fetch_guideline_chapter(chapter_id)
            if not chapter:
                continue

            recs = chapter.get("key_recommendations", [])
            if not recs:
                logger.info("  章節 %s 無正式建議條列，跳過", chapter_id)
                stats["chapters_skipped_no_recommendations"] += 1
                continue

            chapter_version_year = chapter.get("version_year")
            candidate_articles = [
                a for a in articles
                if is_high_evidence(a)
                and is_candidate_new_evidence(
                    extract_pubdate_year(a.get("pubdate")),
                    chapter_version_year,
                    args.since_year,
                )
            ]

            if not candidate_articles:
                logger.info("  章節 %s 無符合年份/證據等級門檻的候選文獻，跳過", chapter_id)
                stats["chapters_skipped_no_candidate_articles"] += 1
                continue

            candidate_articles = candidate_articles[:MAX_CANDIDATE_ARTICLES_PER_CHAPTER]
            stats["chapters_checked"] += 1

            flag_data = generate_guideline_flag(concept, chapter, candidate_articles)
            time.sleep(GEMINI_DELAY)

            if flag_data:
                write_guideline_flag(concept_id, chapter_id, flag_data, dry_run=args.dry_run)
                stats["flags_generated"] += 1
                logger.info(
                    "  章節 %s 產生 1 筆 guideline flag（引用 %d 篇文獻）",
                    chapter_id, len(flag_data["article_ids"]),
                )
            else:
                stats["flags_skipped_no_update_or_failed"] += 1

        stats["concepts_processed"] += 1

    # Step 3: 輸出統計
    logger.info("=== 執行完成 ===")
    logger.info("概念處理: %d", stats["concepts_processed"])
    logger.info("因無指引連結跳過: %d", stats["concepts_skipped_no_guideline_links"])
    logger.info("因無文獻連結跳過: %d", stats["concepts_skipped_no_article_links"])
    logger.info("章節檢查數: %d", stats["chapters_checked"])
    logger.info("章節因無建議條列跳過: %d", stats["chapters_skipped_no_recommendations"])
    logger.info("章節因無候選文獻跳過: %d", stats["chapters_skipped_no_candidate_articles"])
    logger.info("Flag 產生: %d", stats["flags_generated"])
    logger.info("無更新判斷或失敗: %d", stats["flags_skipped_no_update_or_failed"])

    # 記錄到 crawler_runs_v2
    if not args.dry_run:
        try:
            log_crawler_run("kg_check_guideline_updates", stats)
            logger.info("已記錄執行結果到 crawler_runs_v2")
        except Exception as e:
            logger.warning("記錄 crawler run 失敗: %s", e)


if __name__ == "__main__":
    main()
