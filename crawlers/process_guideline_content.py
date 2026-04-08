"""
Process Guideline Content — Nephro Brain OS
=============================================
讀取 Firestore books collection 中的指引 PDF，使用 Gemini AI 擷取結構化章節內容，
儲存至 guideline_chapters collection。

使用方式：
  python crawlers/process_guideline_content.py                      # 處理全部
  python crawlers/process_guideline_content.py --limit 1            # 只處理 1 部
  python crawlers/process_guideline_content.py --guideline-id XXX   # 指定 ID
  python crawlers/process_guideline_content.py --resume             # 跳過已處理
  python crawlers/process_guideline_content.py --dry-run            # 預覽模式
"""

import argparse
import json
import logging
import os
import re
import sys
import tempfile
import time

import firebase_admin
import requests
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
from google import genai

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Firebase init
# ---------------------------------------------------------------------------
load_dotenv()
# fallback: 讀取 backend/.env
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

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

# ---------------------------------------------------------------------------
# Gemini setup
# ---------------------------------------------------------------------------
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=GOOGLE_API_KEY)
MODEL = "gemini-2.5-flash"

RATE_LIMIT_DELAY = 2  # seconds between Gemini calls
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
TOC_PROMPT = """請分析這份臨床指引 PDF，擷取完整的章節目錄。
回傳 JSON 陣列，格式：
[
  {"chapter_number": 1, "title": "Chapter title in English"},
  {"chapter_number": 2, "title": "Chapter title in English"},
  ...
]
只列出主要章節（不含附錄、參考文獻、縮寫表等）。
回傳純 JSON，不要加 markdown code fence。"""

CONTENT_PROMPT = """請閱讀這份指引的第 {chapter_number} 章「{chapter_title}」。

產生繁體中文結構化摘要，使用 Markdown 格式：

## 核心概念
（2-3 段說明本章重點）

## 臨床重點
（條列式，用 **粗體** 標示關鍵詞）

## 實作建議
（具體的臨床操作建議）

醫學術語用「中文 (English)」格式。目標 800-1500 字。"""

RECS_PROMPT = """從這份指引的第 {chapter_number} 章「{chapter_title}」中，擷取所有正式的臨床建議 (Recommendations) 和實作要點 (Practice Points)。

回傳 JSON 陣列：
[
  {{
    "text": "建議內容（繁體中文）",
    "grade": "1A",
    "description": "簡要說明為何如此建議"
  }}
]

grade 必須是以下之一：1A, 1B, 1C, 1D, 2A, 2B, 2C, 2D, Not Graded
如果該章節沒有正式建議，回傳空陣列 []。
回傳純 JSON，不要加 markdown code fence。"""

FLOWCHART_PROMPT = """根據這份指引第 {chapter_number} 章「{chapter_title}」的內容，
產生一個診斷或治療決策流程圖。使用 Mermaid flowchart TD 格式。

規則：
- 節點標籤用繁體中文，保持簡短（20 字以內）
- 決策節點使用菱形 {{{{}}}}
- 用 -->|是| 和 -->|否| 表示分支
- 不要超過 15 個節點
- 如果本章不適合做流程圖（例如概論章節），回傳 "SKIP"

範例：
flowchart TD
    A[初始評估] --> B{{{{eGFR < 60?}}}}
    B -->|是| C[CKD 確認]
    B -->|否| D[追蹤觀察]

只回傳 mermaid code 或 "SKIP"，不要加其他文字或 code fence。"""

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def detect_org(title: str) -> str:
    """Detect organization from title."""
    upper = title.upper()
    if "KDIGO" in upper:
        return "KDIGO"
    if "KDOQI" in upper:
        return "KDOQI"
    return "Unknown"


def extract_year(title: str) -> int | None:
    """Extract 4-digit year from title."""
    match = re.search(r"(19|20)\d{2}", title)
    return int(match.group()) if match else None


STOP_WORDS = {"kdigo", "kdoqi", "guideline", "guidelines", "clinical", "practice",
              "for", "the", "and", "in", "of", "a", "an", "english", "final", "gl",
              "update", "2024", "2023", "2022", "2021", "2020", "2019", "2018",
              "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010",
              "2009", "2008", "2007", "2006", "2005", "2004", "2003", "2025"}

ABBREV_MAP = {
    "BP": {"blood", "pressure"},
    "GD": {"glomerular", "diseases"},
    "MBD": {"mineral", "bone"},
    "LN": {"lupus", "nephritis"},
    "AKI": {"acute", "kidney", "injury"},
    "AKD": {"acute", "kidney", "disease"},
    "CKD": {"ckd", "chronic", "kidney"},
    "ADPKD": {"polycystic"},
    "ANCA": {"anca", "vasculitis"},
    "LD": {"living", "donor"},
}


def _normalize(s):
    words = re.sub(r'[^a-z0-9\s]', ' ', s.lower().replace('-', ' ')).split()
    return set(w for w in words if w not in STOP_WORDS and len(w) > 1)


def find_guideline_doc(title: str):
    """Find matching guideline doc in guidelines collection by title similarity."""
    guidelines_ref = db.collection("guidelines")
    docs = list(guidelines_ref.stream())

    title_words = _normalize(title)
    title_upper = set(re.findall(r'[A-Z]{2,}', title))

    # Expand abbreviations
    expanded_title = set(title_words)
    for abbr in title_upper:
        if abbr in ABBREV_MAP:
            expanded_title |= ABBREV_MAP[abbr]

    best_match = None
    best_score = 0

    for doc in docs:
        data = doc.to_dict()
        doc_title = data.get("title", "")
        doc_words = _normalize(doc_title)
        doc_upper = set(re.findall(r'[A-Z]{2,}', doc_title))

        expanded_doc = set(doc_words)
        for abbr in doc_upper:
            if abbr in ABBREV_MAP:
                expanded_doc |= ABBREV_MAP[abbr]

        if not expanded_doc or not expanded_title:
            continue

        overlap = len(expanded_title & expanded_doc)
        abbrev_overlap = len(title_upper & doc_upper)
        score = overlap + abbrev_overlap

        if score > best_score:
            best_score = score
            best_match = (doc.id, data)

    if best_match and best_score >= 1:
        return best_match
    return None, None


def call_gemini(uploaded_file, prompt: str, expect_json: bool = False):
    """Call Gemini with retry logic."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=[uploaded_file, prompt],
            )
            text = response.text.strip()

            # Strip markdown code fences if present
            if text.startswith("```"):
                lines = text.split("\n")
                # Remove first and last lines (code fences)
                lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines).strip()

            if expect_json:
                return json.loads(text)
            return text

        except json.JSONDecodeError as e:
            logger.warning(
                "  JSON 解析失敗 (attempt %d/%d): %s", attempt, MAX_RETRIES, e
            )
            if attempt == MAX_RETRIES:
                logger.error("  JSON 解析最終失敗，回傳原始文字")
                return {"_raw": text, "_error": str(e)} if expect_json else text
            time.sleep(RETRY_DELAY)

        except Exception as e:
            logger.warning(
                "  Gemini 呼叫失敗 (attempt %d/%d): %s", attempt, MAX_RETRIES, e
            )
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_DELAY)

    return None


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_book(book_doc_id: str, book_data: dict, dry_run: bool = False) -> bool:
    """Process a single guideline book. Returns True on success."""
    book_title = book_data.get("title", "Unknown")
    book_url = book_data.get("url", "")

    if not book_url:
        logger.warning("  書籍 %s 沒有 URL，跳過", book_title)
        return False

    org = detect_org(book_title)
    version_year = extract_year(book_title)

    logger.info("  組織: %s | 年份: %s", org, version_year)

    if dry_run:
        logger.info("  [DRY-RUN] 會處理: %s", book_title)
        return True

    # Step 2: Download PDF and upload to Gemini
    temp_path = None
    try:
        logger.info("  下載 PDF...")
        resp = requests.get(book_url, timeout=120)
        resp.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(resp.content)
            temp_path = f.name

        logger.info("  上傳至 Gemini File API...")
        uploaded_file = client.files.upload(
            file=temp_path, config={"display_name": book_title}
        )
        time.sleep(RATE_LIMIT_DELAY)

        # Step 3: Extract TOC
        logger.info("  擷取目錄...")
        toc = call_gemini(uploaded_file, TOC_PROMPT, expect_json=True)

        if not isinstance(toc, list):
            logger.error("  目錄擷取失敗，結果不是陣列: %s", type(toc))
            return False

        logger.info("  找到 %d 個章節", len(toc))
        time.sleep(RATE_LIMIT_DELAY)

        # Step 4: Process each chapter
        chapters_ref = db.collection("guideline_chapters")
        guideline_doc_id, guideline_data = find_guideline_doc(book_title)

        for i, chapter in enumerate(toc, 1):
            ch_num = chapter.get("chapter_number", i)
            ch_title = chapter.get("title", f"Chapter {i}")
            prefix = f"  [{i}/{len(toc)}] Chapter {ch_num}: {ch_title}"

            # 4a: Content
            logger.info("%s — generating content...", prefix)
            content_prompt = CONTENT_PROMPT.format(
                chapter_number=ch_num, chapter_title=ch_title
            )
            try:
                content_result = call_gemini(uploaded_file, content_prompt)
            except Exception as e:
                logger.error("%s — content 生成失敗: %s", prefix, e)
                content_result = None
            time.sleep(RATE_LIMIT_DELAY)

            # 4b: Recommendations
            logger.info("%s — generating recommendations...", prefix)
            recs_prompt = RECS_PROMPT.format(
                chapter_number=ch_num, chapter_title=ch_title
            )
            try:
                recs_result = call_gemini(uploaded_file, recs_prompt, expect_json=True)
            except Exception as e:
                logger.error("%s — recommendations 生成失敗: %s", prefix, e)
                recs_result = []
            time.sleep(RATE_LIMIT_DELAY)

            # 4c: Flowchart
            logger.info("%s — generating flowchart...", prefix)
            flowchart_prompt = FLOWCHART_PROMPT.format(
                chapter_number=ch_num, chapter_title=ch_title
            )
            try:
                flowchart_result = call_gemini(uploaded_file, flowchart_prompt)
            except Exception as e:
                logger.error("%s — flowchart 生成失敗: %s", prefix, e)
                flowchart_result = "SKIP"
            time.sleep(RATE_LIMIT_DELAY)

            # Handle error flags
            processing_status = "ready"
            if content_result is None:
                processing_status = "error"
                content_result = ""
            if isinstance(recs_result, dict) and "_error" in recs_result:
                processing_status = "error"
                recs_result = []

            # Step 5: Store results
            doc_data = {
                "guideline_id": guideline_doc_id,
                "guideline_title": book_title,
                "org": org,
                "version_year": version_year,
                "chapter_number": ch_num,
                "chapter_title": ch_title,
                "chapter_title_zh": "",
                "content_zh": content_result,
                "key_recommendations": recs_result,
                "flowchart_mermaid": flowchart_result if flowchart_result != "SKIP" else None,
                "diff_from_previous": None,
                "book_id": book_doc_id,
                "processing_status": processing_status,
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }

            chapters_ref.add(doc_data)
            logger.info("%s — done (%s)", prefix, processing_status)

        # Step 6: Update guidelines collection
        if guideline_doc_id:
            logger.info("  更新 guidelines doc: %s", guideline_doc_id)
            db.collection("guidelines").document(guideline_doc_id).update({
                "chapters_ready": True,
                "chapters_count": len(toc),
                "book_id": book_doc_id,
                "updated_at": firestore.SERVER_TIMESTAMP,
            })
        else:
            logger.warning("  找不到對應的 guidelines doc: %s", book_title)

        return True

    except Exception as e:
        logger.error("  處理失敗: %s", e)
        return False

    finally:
        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
            logger.info("  已清理暫存檔案")


def process_all(
    limit: int = 0,
    guideline_id: str | None = None,
    resume: bool = False,
    dry_run: bool = False,
) -> None:
    """Process all guideline PDFs from the books collection."""
    logger.info("=== 開始處理指引 PDF ===")

    # Query books with type=guideline and status=ready
    from google.cloud.firestore_v1.base_query import FieldFilter
    books_ref = db.collection("books")
    query = books_ref.where(filter=FieldFilter("type", "==", "guideline")).where(filter=FieldFilter("status", "==", "ready"))
    books = list(query.stream())

    if not books:
        logger.info("沒有找到待處理的指引 PDF")
        return

    logger.info("找到 %d 部指引 PDF", len(books))

    # Filter by guideline_id if specified
    if guideline_id:
        # Match against guidelines collection, then find corresponding book
        books = [b for b in books if b.id == guideline_id]
        if not books:
            logger.error("找不到指定的 book ID: %s", guideline_id)
            return

    # Resume: skip books that already have chapters
    if resume:
        existing_book_ids = set()
        chapters = db.collection("guideline_chapters").stream()
        for ch in chapters:
            ch_data = ch.to_dict()
            bid = ch_data.get("book_id")
            if bid:
                existing_book_ids.add(bid)

        before = len(books)
        books = [b for b in books if b.id not in existing_book_ids]
        logger.info("Resume 模式: 跳過 %d 部已處理，剩餘 %d 部", before - len(books), len(books))

    # Apply limit
    if limit > 0:
        books = books[:limit]
        logger.info("限制處理 %d 部", limit)

    # Process each book
    success = 0
    failed = 0
    for idx, book_doc in enumerate(books, 1):
        book_data = book_doc.to_dict()
        title = book_data.get("title", "Unknown")
        logger.info("[%d/%d] 處理: %s", idx, len(books), title)

        if process_book(book_doc.id, book_data, dry_run=dry_run):
            success += 1
        else:
            failed += 1

    logger.info("=== 完成！成功 %d 部，失敗 %d 部 ===", success, failed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="用 Gemini AI 解析指引 PDF 生成章節內容"
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="最多處理幾部指引 (0=全部)"
    )
    parser.add_argument(
        "--guideline-id", type=str, help="只處理指定的 book doc ID"
    )
    parser.add_argument(
        "--resume", action="store_true", help="跳過已有 chapters 的指引"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="只顯示會處理什麼"
    )
    args = parser.parse_args()

    process_all(
        limit=args.limit,
        guideline_id=args.guideline_id,
        resume=args.resume,
        dry_run=args.dry_run,
    )
