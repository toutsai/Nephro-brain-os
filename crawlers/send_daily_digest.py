"""
Daily Email Digest — Nephro Brain OS
======================================
查詢當日（UTC）新增至 articles_v2 的文章，依 priority 分三段
（🟢 高證據 / 🟡 中等證據 / ⚪ 其他）排序，段內以 journal 字母序，
排版為純文字 email 摘要，透過 Gmail SMTP + App Password 寄出。

不呼叫任何 LLM，純取 Firestore 既有欄位排版；藥物名稱英文由
來源資料（articles_v2 既有欄位）保證，本檔不做任何翻譯。

使用方式：
  python crawlers/send_daily_digest.py                     # 寄今天（UTC）的摘要
  python crawlers/send_daily_digest.py --dry-run           # 預覽 subject + 內文，不寄信
  python crawlers/send_daily_digest.py --date 2026-07-07   # 指定日期（UTC）
  python crawlers/send_daily_digest.py --skip-if-empty     # 當日無新文獻時不寄送心跳信

環境變數：
  GMAIL_ADDRESS       寄件（同時作為預設收件）Gmail 帳號
  GMAIL_APP_PASSWORD  Gmail 兩步驟驗證後產生的 16 碼 App Password
  DIGEST_TO_EMAIL     （選填）收件信箱，未設定則同 GMAIL_ADDRESS

若非 --dry-run 但 GMAIL_ADDRESS / GMAIL_APP_PASSWORD 未設定，會印出警告後
以 exit code 0 結束（不視為失敗），避免 daily workflow 在使用者尚未設定
GitHub Secrets 前就顯示紅叉。
"""

import argparse
import logging
import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

# firebase_admin 本身 import 不會觸發 Firebase 初始化（只有呼叫
# firestore.client() 才會），所以可以放在 module level，讓 --help
# 在沒有 Firebase 憑證的環境下也能正常運作。
from firebase_admin import firestore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================
# 常數
# ============================================================

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# (priority, 段落標題)
PRIORITY_SECTIONS = [
    (0, "🟢 高證據（Meta-analysis / Systematic Review / Guideline / RCT）"),
    (1, "🟡 中等證據（Observational）"),
    (2, "⚪ 其他"),
]

CRAWLER_RUN_FIELDS = [
    ("total_fetched", "抓取（去重後）"),
    ("processed", "AI 摘要成功"),
    ("failed", "AI 摘要失敗"),
    ("created", "新增文獻"),
    ("updated_tags", "更新標籤"),
    ("errors", "儲存錯誤"),
    ("elapsed_seconds", "耗時（秒）"),
]


# ============================================================
# Firestore 查詢
# ============================================================

def fetch_articles_for_date(db, range_start, range_end) -> list:
    """查詢 created_at 落在 [range_start, range_end) 的 articles_v2 文件"""
    query = (
        db.collection("articles_v2")
        .where("created_at", ">=", range_start)
        .where("created_at", "<", range_end)
    )
    docs = list(query.stream())
    articles = [doc.to_dict() for doc in docs]

    def sort_key(article):
        priority = article.get("priority", 2)
        try:
            priority = int(priority)
        except (TypeError, ValueError):
            priority = 2
        journal = (article.get("journal") or "").lower()
        return (priority, journal)

    articles.sort(key=sort_key)
    return articles


def fetch_latest_crawler_run(db) -> dict | None:
    """讀取 crawler_runs_v2 最新一筆執行紀錄（用於心跳信佐證爬蟲有跑）"""
    docs = (
        db.collection("crawler_runs_v2")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(1)
        .stream()
    )
    for doc in docs:
        return doc.to_dict()
    return None


# ============================================================
# Email 內文排版
# ============================================================

def format_article_block(article: dict) -> str:
    """排版單篇文章區塊，欄位可能缺漏須防禦性處理"""
    evidence_level = article.get("evidence_level") or "Level ?"
    journal = article.get("journal") or "（期刊未知）"
    topics = [t for t in (article.get("topics") or []) if t]
    topics_str = ", ".join(topics) if topics else "（無主題標記）"

    title = article.get("title") or "（無標題）"
    title_zh = article.get("title_zh") or ""
    title_line = f"{title_zh}（{title}）" if title_zh else title

    lines = [f"[{evidence_level}] {journal}｜{topics_str}", title_line]

    study_design = article.get("study_design")
    if study_design:
        lines.append(f"研究設計：{study_design}")

    summary_points = [p for p in (article.get("summary_points") or []) if p]
    if summary_points:
        lines.append("重點：")
        lines.extend(f"  • {p}" for p in summary_points)

    clinical_takeaways = [t for t in (article.get("clinical_takeaways") or []) if t]
    if clinical_takeaways:
        lines.append("臨床要點：")
        lines.extend(f"  • {t}" for t in clinical_takeaways)

    study_quality = article.get("study_quality")
    score = study_quality.get("score") if isinstance(study_quality, dict) else None
    if score:
        lines.append(f"品質分數：{score}/5")

    link = article.get("link")
    if not link and article.get("id"):
        link = f"https://pubmed.ncbi.nlm.nih.gov/{article['id']}/"
    if link:
        lines.append(f"連結：{link}")

    return "\n".join(lines)


def build_digest_email(articles: list, date_str: str) -> tuple:
    n = len(articles)
    subject = f"🩺 NB Insight 每日摘要 - {date_str}（{n} 篇新文獻）"

    grouped = {0: [], 1: [], 2: []}
    for article in articles:
        priority = article.get("priority", 2)
        try:
            priority = int(priority)
        except (TypeError, ValueError):
            priority = 2
        if priority not in grouped:
            priority = 2
        grouped[priority].append(article)

    lines = [
        f"🩺 NB Insight 每日摘要 - {date_str}",
        f"共 {n} 篇新文獻（依 created_at 落於 {date_str} UTC 判定）",
        "",
    ]

    for priority, label in PRIORITY_SECTIONS:
        group = grouped.get(priority, [])
        if not group:
            continue
        lines.append("=" * 60)
        lines.append(label)
        lines.append("=" * 60)
        for article in group:
            lines.append(format_article_block(article))
            lines.append("-" * 40)
        lines.append("")

    lines.append("--")
    lines.append("本信由 NB Insight 每日爬蟲自動產生。")

    return subject, "\n".join(lines)


def format_crawler_run(run: dict | None) -> str:
    if not run:
        return "（找不到 crawler_runs_v2 執行紀錄）"

    lines = []
    timestamp = run.get("timestamp")
    if timestamp:
        lines.append(f"執行時間：{timestamp}")
    crawler_name = run.get("crawler")
    if crawler_name:
        lines.append(f"爬蟲：{crawler_name}")
    for key, label in CRAWLER_RUN_FIELDS:
        if key in run:
            lines.append(f"{label}：{run[key]}")
    status = run.get("status")
    if status:
        lines.append(f"狀態：{status}")

    return "\n".join(lines) if lines else "（執行紀錄無可用欄位）"


def build_heartbeat_email(db, date_str: str) -> tuple:
    subject = f"🩺 NB Insight 每日摘要 - {date_str}（0 篇新文獻）"

    try:
        run = fetch_latest_crawler_run(db)
    except Exception as e:
        logger.warning("讀取 crawler_runs_v2 最新執行紀錄失敗：%s", e)
        run = None

    lines = [
        f"今日（{date_str} UTC）沒有符合條件的新文獻。",
        "",
        "以下為最近一次爬蟲執行紀錄（crawler_runs_v2），供確認爬蟲仍在正常運作：",
        "",
        format_crawler_run(run),
        "",
        "--",
        "本信由 NB Insight 每日爬蟲自動產生（心跳信）。"
        "若不想在無新文獻時收到此信，可於執行時加上 --skip-if-empty。",
    ]

    return subject, "\n".join(lines)


# ============================================================
# 寄信
# ============================================================

def send_email(gmail_address: str, gmail_app_password: str, to_email: str, subject: str, body: str):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = to_email

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(gmail_address, gmail_app_password)
        server.sendmail(gmail_address, [to_email], msg.as_string())


# ============================================================
# 主程式
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Daily Email Digest — 查詢當日 articles_v2 新文獻並以 Gmail 寄送摘要"
    )
    parser.add_argument(
        "--date", type=str, default=None,
        help="指定查詢日期 YYYY-MM-DD（UTC），未指定則預設今天（UTC）",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="預覽模式：只印出 subject + 內文到 stdout，不寄信、不需要 GMAIL 環境變數",
    )
    parser.add_argument(
        "--skip-if-empty", action="store_true",
        help="當日無新文獻時不寄送心跳信（預設仍會照寄，以便與爬蟲故障區分）",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        logger.error("--date 格式錯誤，需為 YYYY-MM-DD，收到：%s", args.date)
        sys.exit(1)

    range_start = datetime(
        target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc
    )
    range_end = range_start + timedelta(days=1)

    logger.info("=== Daily Email Digest 開始 ===")
    logger.info(
        "查詢區間（UTC，created_at）：%s ~ %s",
        range_start.isoformat(), range_end.isoformat(),
    )

    # 延遲載入 crawler_utils：其 module-level 會初始化 Firebase 並要求憑證，
    # 若在 --help 階段就 import 會讓 --help 無法在無憑證環境下執行。
    from crawler_utils import db

    articles = fetch_articles_for_date(db, range_start, range_end)
    logger.info("查得 %d 篇新文獻", len(articles))

    if not articles:
        if args.skip_if_empty:
            logger.info("當日無新文獻，且 --skip-if-empty 已啟用，不寄送。")
            return
        subject, body = build_heartbeat_email(db, date_str)
    else:
        subject, body = build_digest_email(articles, date_str)

    if args.dry_run:
        print("=" * 60)
        print(f"Subject: {subject}")
        print("=" * 60)
        print(body)
        return

    gmail_address = os.getenv("GMAIL_ADDRESS")
    gmail_app_password = os.getenv("GMAIL_APP_PASSWORD")
    if not gmail_address or not gmail_app_password:
        logger.warning(
            "GMAIL_ADDRESS 或 GMAIL_APP_PASSWORD 尚未設定，略過寄信（不視為失敗）。"
            "請至 GitHub repo Settings → Secrets and variables → Actions 設定後再試。"
        )
        sys.exit(0)

    to_email = os.getenv("DIGEST_TO_EMAIL") or gmail_address

    try:
        send_email(gmail_address, gmail_app_password, to_email, subject, body)
    except Exception as e:
        logger.error("寄信失敗：%s", e)
        sys.exit(1)

    logger.info("Email 已寄出 → %s", to_email)


if __name__ == "__main__":
    main()
