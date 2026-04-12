"""
Cochrane Reviews Crawler — Nephro Brain OS
============================================
從 PubMed 抓取 Cochrane Database of Systematic Reviews 中
與腎臟科相關的系統性回顧文獻，產出 AI 結構化摘要並存入 Firestore。

Cochrane 系統性回顧皆為 Level 1 證據，一律使用 Gemini 摘要。

使用方式：
  pip install firebase-admin google-genai openai requests python-dotenv
  設定 .env（見 env.example）

  # 預設：過去 30 天、最多 50 篇
  python crawler_cochrane.py

  # 自訂天數與上限
  python crawler_cochrane.py --days 60 --limit 100

  # 測試模式（不寫入 Firestore）
  python crawler_cochrane.py --dry-run

  # 組合使用
  python crawler_cochrane.py --days 14 --limit 20 --dry-run
"""

import argparse
import logging
import time
from datetime import datetime, timedelta

from crawler_utils import (
    db, gemini_client, gemini_types, groq_client,
    GEMINI_DELAY, GROQ_DELAY,
    HIGH_EVIDENCE_FILTER,
    search_pubmed, fetch_article_details,
    classify_evidence, detect_topics,
    build_summary_prompt, generate_summary_gemini, generate_summary_groq,
    generate_summary, article_exists, save_article, save_to_retry_queue,
    log_crawler_run,
)
from crawler_utils import get_date_range

# ============================================================
# Logging 設定
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ============================================================
# 常數
# ============================================================
CRAWLER_NAME = "cochrane"

COCHRANE_JOURNAL_FILTER = '"Cochrane Database Syst Rev"[Journal]'

NEPHROLOGY_KEYWORDS = (
    "(kidney OR renal OR dialysis OR nephrology OR transplant "
    "OR glomerulonephritis OR nephrotic OR peritoneal dialysis)"
)


# ============================================================
# 主程式
# ============================================================
def build_query(days: int) -> str:
    """組合 Cochrane 期刊 + 腎臟科關鍵字 + 日期範圍的 PubMed 查詢"""
    date_range = get_date_range(days)
    query = f"{COCHRANE_JOURNAL_FILTER} AND {NEPHROLOGY_KEYWORDS} AND {date_range}"
    logger.info(f"PubMed 查詢: {query}")
    return query


def run(days: int = 30, limit: int = 50, dry_run: bool = False):
    """執行 Cochrane 爬蟲主流程"""
    logger.info("=" * 60)
    logger.info(f"Cochrane Reviews Crawler 啟動 (days={days}, limit={limit}, dry_run={dry_run})")
    logger.info("=" * 60)

    stats = {
        "total_found": 0,
        "skipped_duplicate": 0,
        "skipped_no_abstract": 0,
        "processed": 0,
        "saved": 0,
        "summary_failed": 0,
    }

    # Step 1: 搜尋 PubMed
    query = build_query(days)
    articles = search_pubmed(query, max_results=limit)
    stats["total_found"] = len(articles)
    logger.info(f"PubMed 搜尋到 {len(articles)} 篇 Cochrane 文獻")

    if not articles:
        logger.info("未找到新文獻，結束")
        if not dry_run:
            log_crawler_run(CRAWLER_NAME, stats)
        return stats

    # Step 2: 去重
    new_articles = []
    for art in articles:
        if article_exists(art["pmid"]):
            logger.debug(f"  跳過已存在: {art['pmid']}")
            stats["skipped_duplicate"] += 1
        else:
            new_articles.append(art)

    logger.info(f"去重後剩餘 {len(new_articles)} 篇新文獻（跳過 {stats['skipped_duplicate']} 篇已存在）")

    if not new_articles:
        logger.info("所有文獻皆已存在，結束")
        if not dry_run:
            log_crawler_run(CRAWLER_NAME, stats)
        return stats

    # Step 3: 逐篇處理
    for i, art in enumerate(new_articles, 1):
        pmid = art["pmid"]
        logger.info(f"[{i}/{len(new_articles)}] 處理 PMID {pmid}: {art['title'][:60]}...")

        # 3a: 取得完整資料
        details = fetch_article_details(pmid)
        art.update(details)

        if not art.get("abstract"):
            logger.warning(f"  跳過 PMID {pmid}：無摘要")
            stats["skipped_no_abstract"] += 1
            continue

        # 3b: 證據分類（Cochrane 理論上全部 Level 1，但仍透過函式確認）
        evidence_group, evidence_level, priority = classify_evidence(
            art.get("publication_types", [])
        )
        # Cochrane 系統性回顧強制為 Level 1
        evidence_group = evidence_group or "Systematic Review"
        evidence_level = "Level 1"
        priority = 0

        art["evidence_group"] = evidence_group
        art["evidence_level"] = evidence_level
        art["priority"] = priority

        # 3c: 主題偵測
        topics = detect_topics(
            art["title"],
            art.get("abstract", ""),
            art.get("mesh_terms", []),
        )
        art["topics"] = topics

        if dry_run:
            logger.info(f"  [DRY RUN] {evidence_level} | {evidence_group} | topics={topics}")
            stats["processed"] += 1
            continue

        # 3d: AI 摘要（Level 1 優先 Gemini）
        summary = generate_summary_gemini(art)
        if not summary:
            logger.warning(f"  Gemini 摘要失敗，嘗試 Groq fallback...")
            summary = generate_summary_groq(art)

        if not summary:
            logger.error(f"  PMID {pmid} 摘要產生失敗，存入 retry queue")
            save_to_retry_queue(art, "summary_generation_failed")
            stats["summary_failed"] += 1
            time.sleep(GEMINI_DELAY)
            continue

        # 3e: 組裝文件並儲存
        doc_data = {
            "pmid": pmid,
            "title": art["title"],
            "abstract": art["abstract"],
            "journal": art.get("journal", "Cochrane Database Syst Rev"),
            "pubdate": art.get("pubdate", ""),
            "link": art.get("link", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"),
            "publication_types": art.get("publication_types", []),
            "mesh_terms": art.get("mesh_terms", []),
            "evidence_group": evidence_group,
            "evidence_level": evidence_level,
            "priority": priority,
            "topics": topics,
            "sources": ["cochrane"],
            "journals": ["Cochrane Database Syst Rev"],
            # AI 摘要欄位
            "title_zh": summary.get("title_zh", ""),
            "study_design": summary.get("study_design", ""),
            "summary_points": summary.get("summary_points", []),
            "pico": summary.get("pico", {}),
            "clinical_takeaways": summary.get("clinical_takeaways", []),
            "limitations": summary.get("limitations", []),
            "next_steps": summary.get("next_steps", ""),
            "study_quality": summary.get("study_quality", {}),
            "ai_model": summary.get("model", "unknown"),
        }

        result = save_article(pmid, doc_data)
        logger.info(f"  儲存結果: {result}")
        stats["processed"] += 1
        stats["saved"] += 1

        # 速率控制
        time.sleep(GEMINI_DELAY)

    # Step 4: 記錄執行結果
    logger.info("=" * 60)
    logger.info(f"執行完成: {stats}")
    logger.info("=" * 60)

    if not dry_run:
        log_crawler_run(CRAWLER_NAME, stats)

    return stats


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Cochrane Reviews Crawler — 抓取 Cochrane 腎臟科系統性回顧"
    )
    parser.add_argument(
        "--days", type=int, default=30,
        help="搜尋過去幾天的文獻（預設 30）",
    )
    parser.add_argument(
        "--limit", type=int, default=50,
        help="最多抓取幾篇（預設 50）",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="測試模式，不寫入 Firestore",
    )
    args = parser.parse_args()

    run(days=args.days, limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
