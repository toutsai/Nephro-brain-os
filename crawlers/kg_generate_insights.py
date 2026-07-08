"""
Knowledge Graph Insights Generator — Nephro Brain OS
======================================================
批次為知識圖譜概念產生跨文獻整合洞見（kg_insights），
彙整概念底下 >= --min-articles 篇已連結文獻（articles_v2）的
title / clinical_takeaways / evidence_level / study_quality，
呼叫 Gemini 產出 1-3 條跨文獻臨床洞見（繁體中文 Markdown，藥名英文），
每條標明來源 article doc id。

AI 產出的洞見一律以 status="pending" 寫入，需人工於前台審核後才生效。

使用方式：
  python crawlers/kg_generate_insights.py                        # 處理前 20 個概念
  python crawlers/kg_generate_insights.py --dry-run              # 預覽，不寫入
  python crawlers/kg_generate_insights.py --limit 5              # 只處理前 5 個概念
  python crawlers/kg_generate_insights.py --concept-id ckd       # 處理指定概念
  python crawlers/kg_generate_insights.py --min-articles 5       # 至少 5 篇文獻才產生洞見
"""

import argparse
import json
import logging
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
MAX_ARTICLES_PER_CONCEPT = 15  # 避免單一概念文獻過多導致 prompt 過長（非契約規定，內部保護值）

INSIGHT_PROMPT = """你是腎臟科知識圖譜的臨床實證整合專家。以下是與概念「{title} ({title_zh})」相關、且已收錄的多篇文獻摘要，請你進行跨文獻整合分析。

{articles_block}

請根據以上文獻，產出 1 到 3 條跨文獻臨床洞見。每條洞見應聚焦一個具體、可行動的臨床重點（例如：多篇證據間的一致結論、證據間的矛盾或差異、劑量趨勢、族群差異、證據強度等）。

規則：
1. 使用繁體中文撰寫，內容為 Markdown 格式（可用 **粗體**、清單）。
2. 藥物名稱一律維持英文（如 Dapagliflozin、Tacrolimus），醫學縮寫亦保留英文（如 AKI、CKD、ESRD 等）。
3. 每條洞見只能引用上面提供的文獻，並在 source_article_ids 精確列出你引用的文獻 doc id（見每篇文獻前的 [doc_id: ...] 標記）。
4. 不要編造未提供的文獻或數據。

請以嚴格 JSON 格式回傳（不要加 markdown code block，不要加任何其他文字），格式如下：
{{
  "insights": [
    {{
      "text": "洞見內容（繁體中文 Markdown，藥名英文）",
      "source_article_ids": ["<doc_id_1>", "<doc_id_2>"]
    }}
  ]
}}"""


# ============================================================
# 查詢需要產生洞見的概念
# ============================================================

def load_concepts_for_insights(
    limit: int = 20,
    concept_id: str | None = None,
) -> list[dict]:
    """載入待處理概念。

    契約 E.1 原文：「kg_concepts（--concept-id 指定或取 status=approved/未設；--limit 筆）」。
    但 repo 現況中 kg_concepts 並無 `status` 欄位，實際欄位是 `synthesis_status`
    （見 crawlers/kg_build_concepts.py:417、backend/api_server.py:3391，
    值域 draft/pending_review/approved/rejected）。此處以 `synthesis_status`
    取代契約字面的 `status`，語意對應：approved 或未設定該欄位；
    跳過 draft/pending_review/rejected（尚未通過人工審核或已被拒絕的概念）。
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

    logger.info("載入 %d 個待產生洞見的概念", len(concepts))
    return concepts


# ============================================================
# 取得概念底下的文獻（經 kg_links）
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


def select_article_ids(links: list[dict]) -> list[str]:
    """從 links 過濾出 source_type=='article' 且 status in ('approved','pending') 的 source_id（去重、保序）"""
    article_ids = []
    seen = set()
    for link in links:
        if link.get("source_type") != "article":
            continue
        if link.get("status") not in ("approved", "pending"):
            continue
        source_id = link.get("source_id")
        if source_id and source_id not in seen:
            article_ids.append(source_id)
            seen.add(source_id)
    return article_ids


def fetch_article_data(article_id: str) -> dict | None:
    """從 articles_v2 取得單篇文獻的 title/clinical_takeaways/evidence_level/study_quality"""
    try:
        doc = db.collection("articles_v2").document(article_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        return {
            "_id": doc.id,
            "title": data.get("title", ""),
            "title_zh": data.get("title_zh", ""),
            "clinical_takeaways": data.get("clinical_takeaways", []),
            "evidence_level": data.get("evidence_level", ""),
            "study_quality": data.get("study_quality", {}),
        }
    except Exception as e:
        logger.warning("取得文獻 %s 失敗: %s", article_id, e)
        return None


def build_articles_block(articles: list[dict]) -> str:
    """將文獻列表組成給 Gemini 的文字區塊，每篇標明 doc_id 供引用"""
    parts = []
    for article in articles:
        doc_id = article["_id"]
        title = article.get("title", "")
        title_zh = article.get("title_zh", "")
        evidence_level = article.get("evidence_level", "")
        study_quality = article.get("study_quality", {})
        quality_score = ""
        if isinstance(study_quality, dict):
            quality_score = study_quality.get("score", "")
        takeaways = article.get("clinical_takeaways", []) or []

        entry = f"[doc_id: {doc_id}] **{title}**"
        if title_zh:
            entry += f"（{title_zh}）"
        meta_bits = []
        if evidence_level:
            meta_bits.append(f"證據等級：{evidence_level}")
        if quality_score != "":
            meta_bits.append(f"研究品質分數：{quality_score}")
        if meta_bits:
            entry += "\n  " + "；".join(meta_bits)
        if takeaways:
            entry += "\n  臨床重點：" + "; ".join(str(t) for t in takeaways[:5])
        parts.append(entry)
    return "\n\n".join(parts) if parts else "（無文獻資料）"


# ============================================================
# Gemini 產生洞見（含防呆解析）
# ============================================================

def generate_insights(concept: dict, articles: list[dict]) -> list[dict]:
    """呼叫 Gemini 產生跨文獻洞見，回傳防呆解析後的 [{"text":..., "source_article_ids":[...]}]。

    任何非預期格式（非 JSON、非 dict、缺 insights 陣列、item 缺 text/source_article_ids
    或型別不符）一律該筆跳過，絕不因解析失敗而產出 approved 或以殘缺資料寫入。
    """
    if not gemini_client:
        logger.error("Gemini client 未初始化，無法產生洞見")
        return []

    articles_block = build_articles_block(articles)
    prompt = INSIGHT_PROMPT.format(
        title=concept.get("title", ""),
        title_zh=concept.get("title_zh", ""),
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
            "Gemini 洞見產生失敗 (%s): %s",
            concept.get("_id", "?"),
            e,
        )
        return []

    if not isinstance(result, dict):
        logger.warning("  Gemini 回傳格式非預期（非 JSON object），跳過")
        return []

    raw_list = result.get("insights")
    if not isinstance(raw_list, list):
        logger.warning("  Gemini 回傳缺少 insights 陣列，跳過")
        return []

    known_ids = {a["_id"] for a in articles}
    valid = []
    for item in raw_list[:3]:  # 最多 3 條
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        source_ids_raw = item.get("source_article_ids")
        if not isinstance(text, str) or not text.strip():
            continue
        if not isinstance(source_ids_raw, list) or not source_ids_raw:
            continue
        if not all(isinstance(x, str) for x in source_ids_raw):
            continue
        # 只保留確實存在於本次餵給 Gemini 的文獻集合中的 doc id，防止幻覺引用
        source_ids = [x for x in source_ids_raw if x in known_ids]
        if not source_ids:
            continue
        valid.append({"text": text.strip(), "source_article_ids": source_ids})

    return valid


# ============================================================
# 寫入 Firestore
# ============================================================

def write_insight(
    concept_id: str,
    insight_text: str,
    source_article_ids: list[str],
    dry_run: bool = False,
):
    """寫入一筆 kg_insights 文件（欄位照契約 A.1），status 永遠是 'pending'。"""
    if dry_run:
        preview = insight_text[:120].replace("\n", " ")
        logger.info(
            "  [DRY RUN] 會建立 kg_insights: concept_id=%s, sources=%s, preview=%s...",
            concept_id, source_article_ids, preview,
        )
        return

    db.collection("kg_insights").add({
        "concept_id": concept_id,
        "insight": insight_text,
        "source_article_ids": source_article_ids,
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
        description="Knowledge Graph Insights Generator — 為概念產生跨文獻整合洞見"
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
        "--min-articles", type=int, default=3,
        help="每概念至少需有幾篇已連結文獻才產生洞見（預設 3）",
    )
    args = parser.parse_args()

    logger.info("=== Knowledge Graph Insights Generator 開始 ===")
    logger.info(
        "模式: dry_run=%s, limit=%d, concept_id=%s, min_articles=%d",
        args.dry_run, args.limit, args.concept_id, args.min_articles,
    )

    if not gemini_client:
        logger.error("Gemini client 未初始化，無法執行。請確認 GOOGLE_API_KEY 設定。")
        return

    # Step 1: 載入待處理概念
    logger.info("--- Step 1: 載入概念 ---")
    concepts = load_concepts_for_insights(
        limit=args.limit,
        concept_id=args.concept_id,
    )
    if not concepts:
        logger.info("沒有符合條件的概念，結束")
        return

    stats = {
        "concepts_processed": 0,
        "concepts_skipped_insufficient_articles": 0,
        "insights_generated": 0,
        "insights_skipped_invalid": 0,
        "gemini_failed": 0,
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

        # 2a: 取得概念底下已連結的文獻 id
        links = fetch_concept_links(concept_id)
        article_ids = select_article_ids(links)

        if len(article_ids) < args.min_articles:
            logger.info(
                "  已連結文獻數不足 (%d < %d)，跳過",
                len(article_ids), args.min_articles,
            )
            stats["concepts_skipped_insufficient_articles"] += 1
            stats["concepts_processed"] += 1
            continue

        article_ids = article_ids[:MAX_ARTICLES_PER_CONCEPT]

        # 2b: 取得文獻詳細內容
        articles = []
        for aid in article_ids:
            data = fetch_article_data(aid)
            if data:
                articles.append(data)

        if len(articles) < args.min_articles:
            logger.info(
                "  可讀取的文獻內容數不足 (%d < %d)，跳過",
                len(articles), args.min_articles,
            )
            stats["concepts_skipped_insufficient_articles"] += 1
            stats["concepts_processed"] += 1
            continue

        logger.info("  文獻數: %d", len(articles))

        # 2c: 呼叫 Gemini 產生洞見
        insights = generate_insights(concept, articles)

        if not insights:
            logger.warning("  未產生任何有效洞見")
            stats["gemini_failed"] += 1
        else:
            for insight in insights:
                write_insight(
                    concept_id,
                    insight["text"],
                    insight["source_article_ids"],
                    dry_run=args.dry_run,
                )
                stats["insights_generated"] += 1
            logger.info("  產生 %d 條洞見", len(insights))

        stats["concepts_processed"] += 1

        # 延遲以避免 rate limit
        if i < len(concepts):
            time.sleep(GEMINI_DELAY)

    # Step 3: 輸出統計
    logger.info("=== 執行完成 ===")
    logger.info("概念處理: %d", stats["concepts_processed"])
    logger.info("洞見產生: %d", stats["insights_generated"])
    logger.info("因文獻不足跳過: %d", stats["concepts_skipped_insufficient_articles"])
    logger.info("Gemini 產生失敗/無有效洞見: %d", stats["gemini_failed"])

    # 記錄到 crawler_runs_v2
    if not args.dry_run:
        try:
            log_crawler_run("kg_generate_insights", stats)
            logger.info("已記錄執行結果到 crawler_runs_v2")
        except Exception as e:
            logger.warning("記錄 crawler run 失敗: %s", e)


if __name__ == "__main__":
    main()
