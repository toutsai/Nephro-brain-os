"""
Knowledge Graph Consult Processor — Nephro Brain OS
=====================================================
處理 kg_consult_extractions 中 status="raw" 的文件，
透過 Gemini 萃取概念、評估覆蓋度，並建立 kg_links。

處理流程：
  1. 查詢 kg_consult_extractions WHERE status == "raw" LIMIT N
  2. 載入所有 kg_concepts 的 concept_id
  3. 逐筆呼叫 Gemini 萃取概念、評估 coverage
  4. 更新 extraction 文件（concepts_extracted, coverage_score, gap_flag, status）
  5. 為每個 matched concept 建立 kg_link（source_type="consult"）
  6. 輸出統計

使用方式：
  python crawlers/kg_process_consults.py                # 處理最多 50 筆
  python crawlers/kg_process_consults.py --dry-run      # 預覽，不寫入
  python crawlers/kg_process_consults.py --limit 10     # 只處理前 10 筆
"""

import argparse
import json
import logging
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

EXTRACT_PROMPT = """你是腎臟科知識圖譜專家。請分析以下 Consult 問答紀錄，萃取相關腎臟科概念並評估資料覆蓋度。

## Consult 問題
{question}

## 使用的資料來源
{sources_used}

## 現有概念清單（concept_id 列表）
{concept_ids}

請回傳嚴格 JSON（不要加 markdown code block）：
{{
  "concepts": [
    {{"concept_id": "iga-nephropathy", "confidence": 0.95}},
    {{"concept_id": "sglt2-inhibitors", "confidence": 0.8}}
  ],
  "coverage_score": 0.7,
  "gap_topics": ["某個知識庫尚未涵蓋的主題"]
}}

規則：
- concepts[].concept_id 盡量從現有概念清單中匹配，若找不到完全匹配則用 kebab-case 自創新 ID
- concepts[].confidence: 該概念與此問題的相關程度 (0-1)
- coverage_score: 資料來源對此問題的覆蓋程度 (0-1)
  - 1.0 = 完全涵蓋，有充分的指引/文獻支持
  - 0.5-0.9 = 部分涵蓋
  - <0.5 = 資料不足，存在知識缺口
- gap_topics: 若 coverage_score < 0.5，列出缺少的主題；否則為空陣列

只回傳 JSON，不要加任何其他文字。"""


# ============================================================
# 資料載入
# ============================================================

def load_raw_extractions(limit: int = 50) -> list:
    """查詢 status == 'raw' 的 consult extractions"""
    q = (
        db.collection("kg_consult_extractions")
        .where("status", "==", "raw")
        .limit(limit)
    )
    docs = list(q.stream())
    extractions = []
    for doc in docs:
        data = doc.to_dict()
        data["_id"] = doc.id
        extractions.append(data)
    logger.info("載入 %d 筆 raw consult extractions", len(extractions))
    return extractions


def load_concept_ids() -> list:
    """載入所有 kg_concepts 的 concept_id"""
    docs = list(db.collection("kg_concepts").stream())
    concept_ids = [doc.id for doc in docs]
    logger.info("載入 %d 個現有 concept IDs", len(concept_ids))
    return concept_ids


# ============================================================
# Gemini 概念萃取
# ============================================================

def extract_concepts(question: str, sources_used: list, concept_ids: list) -> dict:
    """呼叫 Gemini 萃取概念並評估覆蓋度"""
    if not gemini_client:
        logger.error("Gemini client 未初始化")
        return None

    # 格式化 sources_used
    sources_text = ""
    if sources_used:
        for i, src in enumerate(sources_used, 1):
            if isinstance(src, dict):
                title = src.get("title", src.get("source_id", f"source_{i}"))
                stype = src.get("type", src.get("source_type", "unknown"))
                sources_text += f"  {i}. [{stype}] {title}\n"
            else:
                sources_text += f"  {i}. {src}\n"
    else:
        sources_text = "  (無資料來源)"

    # 限制 concept_ids 長度以避免超出 token 上限
    concept_ids_text = json.dumps(concept_ids, ensure_ascii=False)
    if len(concept_ids_text) > 8000:
        concept_ids_text = json.dumps(concept_ids[:500], ensure_ascii=False)

    prompt = EXTRACT_PROMPT.format(
        question=question,
        sources_used=sources_text,
        concept_ids=concept_ids_text,
    )

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=gemini_types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        result = json.loads(response.text)

        # 基本驗證
        if not isinstance(result, dict):
            logger.warning("Gemini 回傳非 dict: %s", type(result))
            return None

        # 確保必要欄位存在
        result.setdefault("concepts", [])
        result.setdefault("coverage_score", 0.5)
        result.setdefault("gap_topics", [])

        # 確保 coverage_score 為數字
        try:
            result["coverage_score"] = float(result["coverage_score"])
        except (ValueError, TypeError):
            result["coverage_score"] = 0.5

        return result

    except json.JSONDecodeError as e:
        logger.warning("Gemini JSON 解析失敗: %s", e)
        return None
    except Exception as e:
        logger.warning("Gemini 呼叫失敗: %s", e)
        return None


# ============================================================
# kg_link 寫入
# ============================================================

def link_exists(concept_id: str, source_id: str) -> bool:
    """檢查 kg_links 中是否已存在此連結"""
    existing = (
        db.collection("kg_links")
        .where("concept_id", "==", concept_id)
        .where("source_id", "==", source_id)
        .limit(1)
        .stream()
    )
    return any(True for _ in existing)


def write_consult_link(
    concept_id: str,
    extraction_id: str,
    confidence: float,
    question_snippet: str,
    dry_run: bool = False,
) -> bool:
    """建立 consult 類型的 kg_link，回傳是否成功寫入"""
    if link_exists(concept_id, extraction_id):
        logger.debug("  連結已存在: %s -> %s，跳過", concept_id, extraction_id)
        return False

    doc_data = {
        "concept_id": concept_id,
        "source_type": "consult",
        "source_id": extraction_id,
        "source_collection": "kg_consult_extractions",
        "relevance_score": confidence,
        "relevance_reason": "Extracted from consult question",
        "source_snapshot": {
            "question": question_snippet[:200],
        },
        "status": "pending",
        "created_at": SERVER_TIMESTAMP,
        "created_by": "kg_process_consults",
    }

    if dry_run:
        logger.info(
            "  [DRY RUN] 會建立連結: %s -> %s (confidence=%.2f)",
            concept_id, extraction_id, confidence,
        )
        return True

    db.collection("kg_links").add(doc_data)
    return True


# ============================================================
# 主程式
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Process raw consult extractions — 萃取概念並評估覆蓋度"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="預覽模式，不寫入 Firestore",
    )
    parser.add_argument(
        "--limit", type=int, default=50,
        help="處理筆數上限（預設 50）",
    )
    args = parser.parse_args()

    logger.info("=== Knowledge Graph Consult Processor 開始 ===")
    logger.info("模式: dry_run=%s, limit=%d", args.dry_run, args.limit)

    # Step 1: 載入 raw extractions
    logger.info("--- Step 1: 載入 raw extractions ---")
    extractions = load_raw_extractions(args.limit)
    if not extractions:
        logger.info("沒有待處理的 raw extractions，結束")
        return

    # Step 2: 載入現有 concept IDs
    logger.info("--- Step 2: 載入現有 concept IDs ---")
    concept_ids = load_concept_ids()

    # 統計
    stats = {
        "total": len(extractions),
        "processed": 0,
        "gemini_failed": 0,
        "links_created": 0,
        "links_skipped_duplicate": 0,
        "gap_flagged": 0,
    }

    # Step 3-5: 逐筆處理
    for i, ext in enumerate(extractions, 1):
        ext_id = ext["_id"]
        question = ext.get("question", "")
        sources_used = ext.get("sources_used", [])
        question_preview = question[:80].replace("\n", " ")
        logger.info("--- [%d/%d] %s... ---", i, len(extractions), question_preview)

        # Step 3: Gemini 萃取
        result = extract_concepts(question, sources_used, concept_ids)

        if result is None:
            logger.warning("  Gemini 萃取失敗，跳過此筆")
            stats["gemini_failed"] += 1
            continue

        concepts_extracted = result.get("concepts", [])
        coverage_score = result.get("coverage_score", 0.5)
        gap_topics = result.get("gap_topics", [])
        gap_flag = coverage_score < 0.5

        if gap_flag:
            stats["gap_flagged"] += 1

        logger.info(
            "  萃取結果: %d concepts, coverage=%.2f, gap=%s",
            len(concepts_extracted), coverage_score, gap_flag,
        )
        if gap_topics:
            logger.info("  知識缺口: %s", ", ".join(gap_topics))

        # Step 4: 更新 extraction 文件
        update_data = {
            "concepts_extracted": concepts_extracted,
            "coverage_score": coverage_score,
            "gap_flag": gap_flag,
            "gap_topics": gap_topics,
            "status": "processed",
            "processed_at": SERVER_TIMESTAMP,
        }

        if not args.dry_run:
            db.collection("kg_consult_extractions").document(ext_id).update(update_data)
            logger.info("  已更新 extraction 狀態為 processed")
        else:
            logger.info("  [DRY RUN] 會更新 extraction: coverage=%.2f, gap=%s", coverage_score, gap_flag)

        # Step 5: 建立 kg_links
        for concept_info in concepts_extracted:
            cid = concept_info.get("concept_id", "")
            confidence = concept_info.get("confidence", 0.5)
            if not cid:
                continue

            written = write_consult_link(
                concept_id=cid,
                extraction_id=ext_id,
                confidence=confidence,
                question_snippet=question,
                dry_run=args.dry_run,
            )
            if written:
                stats["links_created"] += 1
            else:
                stats["links_skipped_duplicate"] += 1

        stats["processed"] += 1

        # Gemini 速率控制
        if i < len(extractions):
            time.sleep(GEMINI_DELAY)

    # Step 6: 輸出統計
    logger.info("=== 執行完成 ===")
    logger.info("總筆數: %d", stats["total"])
    logger.info("成功處理: %d", stats["processed"])
    logger.info("Gemini 失敗: %d", stats["gemini_failed"])
    logger.info("連結建立: %d", stats["links_created"])
    logger.info("重複跳過: %d", stats["links_skipped_duplicate"])
    logger.info("知識缺口標記: %d", stats["gap_flagged"])

    # 記錄執行結果
    if not args.dry_run and stats["processed"] > 0:
        try:
            db.collection("crawler_runs_v2").add({
                "timestamp": datetime.now(timezone.utc),
                "crawler": "kg_process_consults",
                "status": "completed",
                **stats,
            })
            logger.info("已記錄執行結果到 crawler_runs_v2")
        except Exception as e:
            logger.warning("記錄 crawler run 失敗: %s", e)


if __name__ == "__main__":
    main()
