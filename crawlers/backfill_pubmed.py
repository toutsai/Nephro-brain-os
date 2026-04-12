"""
Backfill PubMed — Nephro Brain OS
==================================
一次性歷史回填腳本：爬取過去 12 個月的高證據等級（Level 1-2）
腎臟科 PubMed 文獻，進行 AI 摘要並儲存至 Firestore。

使用方式：
  python backfill_pubmed.py                    # 回填 12 個月，每月最多 50 篇
  python backfill_pubmed.py --months-back 6    # 回填 6 個月
  python backfill_pubmed.py --limit 20         # 每月最多 20 篇
  python backfill_pubmed.py --dry-run          # 只搜尋不儲存
"""

import argparse
import logging
import time
from datetime import datetime

from crawler_utils import (
    db,
    GEMINI_DELAY,
    GROQ_DELAY,
    HIGH_EVIDENCE_FILTER,
    get_date_range,
    search_pubmed,
    fetch_article_details,
    classify_evidence,
    detect_topics,
    generate_summary,
    article_exists,
    save_article,
    save_to_retry_queue,
    log_crawler_run,
)

# ============================================================
# 設定
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

NEPHRO_QUERY = (
    "(kidney OR renal OR dialysis OR nephrology OR transplant OR "
    "glomerulonephritis OR nephrotic OR peritoneal dialysis OR "
    "chronic kidney disease OR acute kidney injury)"
)

MAX_PUBMED_PER_MONTH = 200


# ============================================================
# 輔助函式
# ============================================================
def get_month_date_range(year: int, month: int) -> str:
    """Return PubMed date range for a specific month."""
    start = f"{year}/{month:02d}/01"
    if month == 12:
        end = f"{year + 1}/01/01"
    else:
        end = f"{year}/{month + 1:02d}/01"
    return f'("{start}"[dp] : "{end}"[dp])'


def iter_months_back(months_back: int):
    """Yield (year, month) tuples going backwards from the current month."""
    now = datetime.utcnow()
    year, month = now.year, now.month
    for _ in range(months_back):
        # Go back one month
        month -= 1
        if month == 0:
            month = 12
            year -= 1
        yield year, month


# ============================================================
# 主流程
# ============================================================
def backfill(months_back: int = 12, limit: int = 50, dry_run: bool = False):
    """Run the historical backfill pipeline."""
    logger.info(
        "Starting backfill: months_back=%d, limit=%d/month, dry_run=%s",
        months_back, limit, dry_run,
    )

    total_stats = {
        "months_processed": 0,
        "total_found": 0,
        "total_new": 0,
        "total_saved": 0,
        "total_skipped": 0,
        "total_failed": 0,
    }

    for year, month in iter_months_back(months_back):
        month_label = f"{year}-{month:02d}"
        logger.info("=" * 50)
        logger.info("Processing %s", month_label)

        # Build query
        date_range = get_month_date_range(year, month)
        query = f"{NEPHRO_QUERY} AND {HIGH_EVIDENCE_FILTER} AND {date_range}"

        # Search PubMed
        articles = search_pubmed(query, max_results=MAX_PUBMED_PER_MONTH)
        found_count = len(articles)
        total_stats["total_found"] += found_count

        # Deduplicate
        new_articles = [a for a in articles if not article_exists(a["pmid"])]
        new_count = len(new_articles)
        skipped = found_count - new_count
        total_stats["total_skipped"] += skipped

        logger.info(
            "Processing %s: found %d articles, %d new, %d already exist",
            month_label, found_count, new_count, skipped,
        )

        # Apply per-month limit
        if new_count > limit:
            logger.info("  Limiting to %d articles (from %d)", limit, new_count)
            new_articles = new_articles[:limit]

        total_stats["total_new"] += len(new_articles)

        if dry_run:
            for a in new_articles:
                logger.info("  [DRY RUN] Would process: %s — %s", a["pmid"], a["title"][:80])
            total_stats["months_processed"] += 1
            continue

        # Process each article
        month_saved = 0
        month_failed = 0
        for i, article in enumerate(new_articles, 1):
            pmid = article["pmid"]
            logger.info(
                "  [%d/%d] Processing PMID %s: %s",
                i, len(new_articles), pmid, article["title"][:60],
            )

            try:
                # Fetch full details
                details = fetch_article_details(pmid)
                article.update(details)

                # Classify evidence
                evidence_group, evidence_level, priority = classify_evidence(
                    article.get("publication_types", [])
                )
                article["evidence_group"] = evidence_group
                article["evidence_level"] = evidence_level
                article["priority"] = priority

                # Detect topics
                topics = detect_topics(
                    article["title"],
                    article.get("abstract", ""),
                    article.get("mesh_terms", []),
                )
                article["topics"] = topics

                # Generate AI summary
                summary = generate_summary(article)
                if not summary:
                    logger.warning("  AI summary failed for PMID %s", pmid)
                    save_to_retry_queue(article, "AI summary generation failed")
                    month_failed += 1
                    continue

                # Build document
                doc = {
                    "pmid": pmid,
                    "title": article["title"],
                    "abstract": article.get("abstract", ""),
                    "journal": article.get("journal", article.get("source", "")),
                    "pubdate": article.get("pubdate", ""),
                    "link": article.get("link", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"),
                    "evidence_group": evidence_group,
                    "evidence_level": evidence_level,
                    "priority": priority,
                    "topics": topics,
                    "mesh_terms": article.get("mesh_terms", []),
                    "publication_types": article.get("publication_types", []),
                    "sources": ["backfill"],
                    "journals": [article.get("journal", article.get("source", ""))],
                    **summary,
                }

                result = save_article(pmid, doc)
                logger.info("    Saved PMID %s (%s)", pmid, result)
                month_saved += 1

            except Exception as e:
                logger.error("    Error processing PMID %s: %s", pmid, e)
                save_to_retry_queue(article, str(e))
                month_failed += 1

        total_stats["total_saved"] += month_saved
        total_stats["total_failed"] += month_failed
        total_stats["months_processed"] += 1

        logger.info(
            "  %s complete: %d saved, %d failed",
            month_label, month_saved, month_failed,
        )

    # Log the run
    if not dry_run:
        log_crawler_run("backfill", total_stats)

    logger.info("=" * 50)
    logger.info("Backfill complete: %s", total_stats)
    return total_stats


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Backfill PubMed: 回填過去數月的高證據等級腎臟科文獻"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只搜尋並列出文章，不進行 AI 摘要或儲存",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="每月最多處理的文章數（預設 50）",
    )
    parser.add_argument(
        "--months-back",
        type=int,
        default=12,
        help="回填幾個月（預設 12）",
    )
    args = parser.parse_args()

    backfill(
        months_back=args.months_back,
        limit=args.limit,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
