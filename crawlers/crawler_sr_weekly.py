"""
SR Weekly Crawler — Nephro Brain OS
====================================
每週執行：搜尋 PubMed 上所有腎臟科相關的 Systematic Review
與 Meta-Analysis，不限定期刊，確保高證據文獻不遺漏。

使用方式：
  python crawler_sr_weekly.py                  # 搜尋過去 7 天
  python crawler_sr_weekly.py --days 14        # 搜尋過去 14 天
  python crawler_sr_weekly.py --limit 50       # 最多處理 50 篇
  python crawler_sr_weekly.py --dry-run        # 只搜尋不儲存
"""

import argparse
import logging
import time
from datetime import datetime

from crawler_utils import (
    db,
    GEMINI_DELAY,
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

SR_NEPHRO_QUERY = (
    "(kidney[tiab] OR renal[tiab] OR dialysis[tiab] OR nephrology[tiab] "
    "OR transplant[tiab] OR glomerulonephritis[tiab] OR nephrotic[tiab] "
    "OR peritoneal dialysis[tiab] OR CKD[tiab] OR AKI[tiab] OR ESRD[tiab])"
)
SR_TYPE_FILTER = '("systematic review"[pt] OR "meta-analysis"[pt])'


# ============================================================
# 輔助函式
# ============================================================
def get_date_range_days(days: int) -> str:
    """Return PubMed date range for the last N days."""
    from datetime import timedelta

    today = datetime.utcnow().date()
    start = today - timedelta(days=days)
    return (
        f'("{start.year}/{start.month:02d}/{start.day:02d}"[dp] : '
        f'"{today.year}/{today.month:02d}/{today.day:02d}"[dp])'
    )


# ============================================================
# 主流程
# ============================================================
def run_sr_weekly(days: int = 7, limit: int = 30, dry_run: bool = False):
    """Search PubMed for nephrology systematic reviews and meta-analyses."""
    logger.info(
        "Starting SR Weekly: days=%d, limit=%d, dry_run=%s",
        days, limit, dry_run,
    )

    stats = {
        "total_found": 0,
        "new": 0,
        "skipped_existing": 0,
        "saved": 0,
        "failed": 0,
        "days": days,
    }

    # Build query
    date_range = get_date_range_days(days)
    query = f"{SR_NEPHRO_QUERY} AND {SR_TYPE_FILTER} AND {date_range}"
    logger.info("PubMed query: %s", query)

    # Search
    articles = search_pubmed(query, max_results=limit)
    stats["total_found"] = len(articles)
    logger.info("Found %d articles from PubMed", len(articles))

    # Deduplicate
    new_articles = []
    for article in articles:
        if article_exists(article["pmid"]):
            stats["skipped_existing"] += 1
            logger.debug("  Skip (exists): PMID %s", article["pmid"])
        else:
            new_articles.append(article)

    stats["new"] = len(new_articles)
    logger.info(
        "After dedup: %d new, %d already exist",
        stats["new"], stats["skipped_existing"],
    )

    if dry_run:
        for a in new_articles:
            logger.info(
                "  [DRY RUN] Would process: %s — %s",
                a["pmid"], a["title"][:80],
            )
        logger.info("Dry run complete. Found %d new articles.", stats["new"])
        return stats

    # Process each article
    for i, article in enumerate(new_articles, 1):
        pmid = article["pmid"]
        logger.info(
            "[%d/%d] Processing PMID %s: %s",
            i, len(new_articles), pmid, article["title"][:60],
        )

        try:
            # Fetch full details
            details = fetch_article_details(pmid)
            article.update(details)

            # Classify evidence — SR/MA are always Level 1
            evidence_group, evidence_level, priority = classify_evidence(
                article.get("publication_types", [])
            )
            article["evidence_group"] = evidence_group
            article["evidence_level"] = evidence_level
            article["priority"] = priority  # Should be 0 for SR/MA

            # Detect topics
            topics = detect_topics(
                article["title"],
                article.get("abstract", ""),
                article.get("mesh_terms", []),
            )
            article["topics"] = topics

            # Generate AI summary (Level 1 always uses Gemini)
            summary = generate_summary(article)
            if not summary:
                logger.warning("  AI summary failed for PMID %s", pmid)
                save_to_retry_queue(article, "AI summary generation failed")
                stats["failed"] += 1
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
                "sources": ["sr_weekly"],
                "journals": [article.get("journal", article.get("source", ""))],
                **summary,
            }

            result = save_article(pmid, doc)
            logger.info("  Saved PMID %s (%s)", pmid, result)
            stats["saved"] += 1

        except Exception as e:
            logger.error("  Error processing PMID %s: %s", pmid, e)
            save_to_retry_queue(article, str(e))
            stats["failed"] += 1

    # Log the run
    log_crawler_run("sr_weekly", stats)

    logger.info("=" * 50)
    logger.info(
        "SR Weekly complete: found=%d, new=%d, saved=%d, failed=%d",
        stats["total_found"], stats["new"], stats["saved"], stats["failed"],
    )
    return stats


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="SR Weekly Crawler: 搜尋所有腎臟科 Systematic Review / Meta-Analysis"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只搜尋並列出文章，不進行 AI 摘要或儲存",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="最多處理的文章數（預設 30）",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="搜尋過去幾天的文章（預設 7）",
    )
    args = parser.parse_args()

    run_sr_weekly(
        days=args.days,
        limit=args.limit,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
