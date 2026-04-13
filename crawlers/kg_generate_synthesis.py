"""
Knowledge Graph Synthesis Generator — Nephro Brain OS
======================================================
批次為知識圖譜概念產生整合摘要（synthesis notes），
彙整各連結來源（文獻、指引、臨床試驗、藥物）的重點，
呼叫 Gemini 產出 ~500 字的繁體中文 Markdown 摘要。

使用方式：
  python crawlers/kg_generate_synthesis.py                        # 處理前 20 個需要合成的概念
  python crawlers/kg_generate_synthesis.py --dry-run              # 預覽，不寫入
  python crawlers/kg_generate_synthesis.py --limit 5              # 只處理前 5 個概念
  python crawlers/kg_generate_synthesis.py --concept-id ckd       # 處理指定概念
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from crawler_utils import db, gemini_client, gemini_types, GEMINI_DELAY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================
# 常數
# ============================================================

GEMINI_MODEL = "gemini-2.5-flash"
MAX_ARTICLES_PER_CONCEPT = 10
MAX_GUIDELINES_PER_CONCEPT = 10
MAX_TRIALS_PER_CONCEPT = 10
MAX_DRUGS_PER_CONCEPT = 10

SYNTHESIS_PROMPT = """你是腎臟科知識圖譜的內容專家。請為以下概念撰寫一篇整合摘要。

概念：{title} ({title_zh})

相關指引建議：
{guideline_content}

關鍵文獻：
{article_content}

進行中臨床試驗：
{trial_content}

相關藥物：
{drug_content}

請以繁體中文撰寫 ~500 字的 Markdown 格式整合摘要，涵蓋：
1. 定義與流行病學（簡短）
2. 目前指引建議重點
3. 最新實證摘要
4. 藥物治療要點
5. 未來發展方向

藥物名稱一律維持英文。醫學縮寫保留英文。"""


# ============================================================
# 查詢需要合成的概念
# ============================================================

def load_concepts_needing_synthesis(
    limit: int = 20,
    concept_id: str | None = None,
) -> list[dict]:
    """查詢 synthesis_status == 'draft' 或 synthesis_note 為空的概念"""
    if concept_id:
        doc = db.collection("kg_concepts").document(concept_id).get()
        if not doc.exists:
            logger.warning("找不到概念: %s", concept_id)
            return []
        data = doc.to_dict()
        data["_id"] = doc.id
        return [data]

    concepts = []

    # Query 1: synthesis_status == "draft"
    draft_docs = (
        db.collection("kg_concepts")
        .where("synthesis_status", "==", "draft")
        .stream()
    )
    seen_ids = set()
    for doc in draft_docs:
        data = doc.to_dict()
        data["_id"] = doc.id
        concepts.append(data)
        seen_ids.add(doc.id)

    # Query 2: synthesis_note == "" (may overlap with draft, dedup)
    empty_docs = (
        db.collection("kg_concepts")
        .where("synthesis_note", "==", "")
        .stream()
    )
    for doc in empty_docs:
        if doc.id not in seen_ids:
            data = doc.to_dict()
            data["_id"] = doc.id
            concepts.append(data)
            seen_ids.add(doc.id)

    if limit > 0:
        concepts = concepts[:limit]

    logger.info("載入 %d 個需要合成的概念", len(concepts))
    return concepts


# ============================================================
# 取得連結來源
# ============================================================

def fetch_links_for_concept(concept_id: str) -> list[dict]:
    """取得概念的所有 approved/pending kg_links"""
    links = []
    for status in ("approved", "pending"):
        docs = (
            db.collection("kg_links")
            .where("concept_id", "==", concept_id)
            .where("status", "==", status)
            .stream()
        )
        for doc in docs:
            data = doc.to_dict()
            data["_id"] = doc.id
            links.append(data)
    return links


def group_links_by_type(links: list[dict]) -> dict[str, list[dict]]:
    """將 links 按 source_type 分組"""
    grouped = {}
    for link in links:
        stype = link.get("source_type", "other")
        if stype not in grouped:
            grouped[stype] = []
        grouped[stype].append(link)
    return grouped


# ============================================================
# 取得各來源的詳細內容
# ============================================================

def fetch_article_content(links: list[dict]) -> str:
    """從 articles_v2 取得文獻內容"""
    links = links[:MAX_ARTICLES_PER_CONCEPT]
    if not links:
        return "（無相關文獻）"

    parts = []
    for link in links:
        source_id = link.get("source_id", "")
        if not source_id:
            continue
        try:
            doc = db.collection("articles_v2").document(source_id).get()
            if not doc.exists:
                continue
            data = doc.to_dict()
            title = data.get("title", "")
            title_zh = data.get("title_zh", "")
            takeaways = data.get("clinical_takeaways", [])
            pico = data.get("pico", {})

            entry = f"- **{title}**"
            if title_zh:
                entry += f"\n  中文標題：{title_zh}"
            if takeaways:
                takeaway_str = "; ".join(takeaways[:3])
                entry += f"\n  臨床重點：{takeaway_str}"
            if pico and isinstance(pico, dict):
                outcome = pico.get("O", "")
                if outcome:
                    entry += f"\n  主要結局：{outcome}"
            parts.append(entry)
        except Exception as e:
            logger.warning("取得文獻 %s 失敗: %s", source_id, e)

    return "\n".join(parts) if parts else "（無相關文獻）"


def fetch_guideline_content(links: list[dict]) -> str:
    """從 guideline_chapters 取得指引內容"""
    links = links[:MAX_GUIDELINES_PER_CONCEPT]
    if not links:
        return "（無相關指引）"

    parts = []
    for link in links:
        source_id = link.get("source_id", "")
        if not source_id:
            continue
        try:
            doc = db.collection("guideline_chapters").document(source_id).get()
            if not doc.exists:
                continue
            data = doc.to_dict()
            chapter_title = data.get("chapter_title", "")
            recs = data.get("key_recommendations", [])

            entry = f"- **{chapter_title}**"
            if recs:
                for rec in recs[:5]:
                    if isinstance(rec, dict):
                        rec_text = rec.get("text", rec.get("recommendation", str(rec)))
                    else:
                        rec_text = str(rec)
                    entry += f"\n  - {rec_text}"
            parts.append(entry)
        except Exception as e:
            logger.warning("取得指引 %s 失敗: %s", source_id, e)

    return "\n".join(parts) if parts else "（無相關指引）"


def fetch_trial_content(links: list[dict]) -> str:
    """從 clinical_trials 取得臨床試驗內容"""
    links = links[:MAX_TRIALS_PER_CONCEPT]
    if not links:
        return "（無相關臨床試驗）"

    parts = []
    for link in links:
        source_id = link.get("source_id", "")
        if not source_id:
            continue
        try:
            doc = db.collection("clinical_trials").document(source_id).get()
            if not doc.exists:
                continue
            data = doc.to_dict()
            title = data.get("title", "")
            title_zh = data.get("title_zh", "")
            conditions = data.get("conditions", [])
            phase = data.get("phase", "")
            status = data.get("status", "")

            entry = f"- **{title}**"
            if title_zh:
                entry += f"\n  中文標題：{title_zh}"
            if conditions:
                entry += f"\n  適應症：{', '.join(conditions[:5])}"
            if phase:
                entry += f"\n  Phase：{phase}"
            if status:
                entry += f"\n  狀態：{status}"
            parts.append(entry)
        except Exception as e:
            logger.warning("取得臨床試驗 %s 失敗: %s", source_id, e)

    return "\n".join(parts) if parts else "（無相關臨床試驗）"


def load_drug_database() -> dict:
    """載入 drug_database.json"""
    drug_path = os.path.join(
        os.path.dirname(__file__), "..", "backend", "drug_database.json"
    )
    if not os.path.exists(drug_path):
        logger.warning("找不到藥物資料庫: %s", drug_path)
        return {}
    with open(drug_path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_drug_content(links: list[dict], drug_db: dict) -> str:
    """從 drug_database.json 取得藥物內容"""
    links = links[:MAX_DRUGS_PER_CONCEPT]
    if not links:
        return "（無相關藥物）"

    parts = []
    for link in links:
        source_id = link.get("source_id", "")
        if not source_id:
            continue

        drug_data = drug_db.get(source_id)
        if not drug_data:
            continue

        drug_name = drug_data.get("drug_name_en", source_id)
        class_zh = drug_data.get("class_zh", "")
        dose_adj = drug_data.get("dose_adjustments", {})

        entry = f"- **{drug_name}**"
        if class_zh:
            entry += f"（{class_zh}）"

        # Summarize dose adjustments
        if dose_adj and isinstance(dose_adj, dict):
            adj_parts = []
            for stage, adj in dose_adj.items():
                if isinstance(adj, str) and adj:
                    adj_parts.append(f"{stage}: {adj}")
                elif isinstance(adj, dict):
                    dose_text = adj.get("dose", adj.get("recommendation", ""))
                    if dose_text:
                        adj_parts.append(f"{stage}: {dose_text}")
            if adj_parts:
                entry += f"\n  劑量調整：{'; '.join(adj_parts[:4])}"

        parts.append(entry)

    return "\n".join(parts) if parts else "（無相關藥物）"


# ============================================================
# Gemini 合成
# ============================================================

def generate_synthesis(
    concept: dict,
    guideline_content: str,
    article_content: str,
    trial_content: str,
    drug_content: str,
) -> str | None:
    """呼叫 Gemini 產生整合摘要"""
    if not gemini_client:
        logger.error("Gemini client 未初始化，無法產生合成摘要")
        return None

    prompt = SYNTHESIS_PROMPT.format(
        title=concept.get("title", ""),
        title_zh=concept.get("title_zh", ""),
        guideline_content=guideline_content,
        article_content=article_content,
        trial_content=trial_content,
        drug_content=drug_content,
    )

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        return response.text
    except Exception as e:
        logger.error(
            "Gemini 合成失敗 (%s): %s",
            concept.get("_id", "?"),
            e,
        )
        return None


# ============================================================
# 更新 Firestore
# ============================================================

def update_concept_synthesis(
    concept_id: str,
    synthesis_note: str,
    dry_run: bool = False,
):
    """更新概念的 synthesis_note 與 synthesis_status"""
    if dry_run:
        logger.info(
            "  [DRY RUN] 會更新 %s 的 synthesis_note (%d 字)",
            concept_id,
            len(synthesis_note),
        )
        return

    db.collection("kg_concepts").document(concept_id).update({
        "synthesis_note": synthesis_note,
        "synthesis_status": "pending_review",
        "synthesis_updated_at": SERVER_TIMESTAMP,
    })


# ============================================================
# 主程式
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Knowledge Graph Synthesis Generator — 為概念產生整合摘要"
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
    args = parser.parse_args()

    logger.info("=== Knowledge Graph Synthesis Generator 開始 ===")
    logger.info(
        "模式: dry_run=%s, limit=%d, concept_id=%s",
        args.dry_run, args.limit, args.concept_id,
    )

    if not gemini_client:
        logger.error("Gemini client 未初始化，無法執行。請確認 GOOGLE_API_KEY 設定。")
        return

    # Step 1: 載入需要合成的概念
    logger.info("--- Step 1: 載入概念 ---")
    concepts = load_concepts_needing_synthesis(
        limit=args.limit,
        concept_id=args.concept_id,
    )
    if not concepts:
        logger.info("沒有需要合成的概念，結束")
        return

    # 載入藥物資料庫（一次性）
    drug_db = load_drug_database()

    # 統計
    stats = {
        "concepts_processed": 0,
        "synthesis_generated": 0,
        "synthesis_failed": 0,
        "skipped_no_links": 0,
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

        # 2a: 取得所有連結
        links = fetch_links_for_concept(concept_id)
        if not links:
            logger.info("  無連結來源，跳過")
            stats["skipped_no_links"] += 1
            stats["concepts_processed"] += 1
            continue

        # 2b: 按 source_type 分組
        grouped = group_links_by_type(links)
        logger.info(
            "  連結數: 文獻=%d, 指引=%d, 試驗=%d, 藥物=%d",
            len(grouped.get("article", [])),
            len(grouped.get("guideline", [])),
            len(grouped.get("trial", [])),
            len(grouped.get("drug", [])),
        )

        # 2c: 取得各來源內容
        guideline_content = fetch_guideline_content(grouped.get("guideline", []))
        article_content = fetch_article_content(grouped.get("article", []))
        trial_content = fetch_trial_content(grouped.get("trial", []))
        drug_content = fetch_drug_content(grouped.get("drug", []), drug_db)

        # 2d: 預覽 prompt 長度
        total_content_len = (
            len(guideline_content)
            + len(article_content)
            + len(trial_content)
            + len(drug_content)
        )
        logger.info("  來源內容總長: %d 字元", total_content_len)

        # 2e: 呼叫 Gemini
        synthesis = generate_synthesis(
            concept,
            guideline_content,
            article_content,
            trial_content,
            drug_content,
        )

        if synthesis:
            logger.info("  合成摘要產生成功 (%d 字)", len(synthesis))

            # 2f: 更新 Firestore
            update_concept_synthesis(concept_id, synthesis, dry_run=args.dry_run)
            stats["synthesis_generated"] += 1

            if args.dry_run:
                # 在 dry-run 模式下顯示摘要開頭
                preview = synthesis[:200].replace("\n", " ")
                logger.info("  [DRY RUN] 摘要預覽: %s...", preview)
        else:
            logger.warning("  合成摘要產生失敗")
            stats["synthesis_failed"] += 1

        stats["concepts_processed"] += 1

        # 延遲以避免 rate limit
        if i < len(concepts):
            time.sleep(GEMINI_DELAY)

    # Step 3: 輸出統計
    logger.info("=== 執行完成 ===")
    logger.info("概念處理: %d", stats["concepts_processed"])
    logger.info("合成成功: %d", stats["synthesis_generated"])
    logger.info("合成失敗: %d", stats["synthesis_failed"])
    logger.info("無連結跳過: %d", stats["skipped_no_links"])

    # 記錄到 crawler_runs_v2
    if not args.dry_run:
        try:
            db.collection("crawler_runs_v2").add({
                "timestamp": datetime.now(timezone.utc),
                "crawler": "kg_generate_synthesis",
                "status": "completed",
                **stats,
            })
            logger.info("已記錄執行結果到 crawler_runs_v2")
        except Exception as e:
            logger.warning("記錄 crawler run 失敗: %s", e)


if __name__ == "__main__":
    main()
