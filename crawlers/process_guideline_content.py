"""
Process Guideline Content — Nephro Brain OS (v2 - 省錢版)
==========================================================
讀取 Firestore books collection 中的指引 PDF，使用 Gemini AI 擷取結構化章節內容，
儲存至 guideline_chapters collection。

v2 優化：
  - 每章 1 次 Gemini 呼叫（合併 content + recs + flowchart），省 2/3 API 費用
  - TOC 擷取頁碼範圍 → PyPDF 裁切每章頁面 → 只上傳相關頁面，省 input tokens

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

RATE_LIMIT_DELAY = 2
MAX_RETRIES = 3
RETRY_DELAY = 3

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

TOC_PROMPT = """請分析這份臨床指引 PDF，擷取完整的章節目錄，包含每章的起始和結束頁碼。
回傳 JSON 陣列，格式：
[
  {"chapter_number": 1, "title": "Chapter title in English", "page_start": 10, "page_end": 25},
  {"chapter_number": 2, "title": "Chapter title in English", "page_start": 26, "page_end": 40},
  ...
]
注意：
- 只列出主要章節（不含附錄、參考文獻、縮寫表等）
- page_start 和 page_end 是 PDF 的實際頁碼（從 1 開始）
- 如果無法確定頁碼，用 null
回傳純 JSON，不要加 markdown code fence。"""

COMBINED_PROMPT = """請閱讀這份指引章節內容，完成以下三個任務。

=== 任務 1：繁體中文結構化摘要 ===
產生 Markdown 格式的結構化摘要：

## 核心概念
（2-3 段說明本章重點）

## 臨床重點
（條列式，用 **粗體** 標示關鍵詞）

## 實作建議
（具體的臨床操作建議）

醫學術語用「中文 (English)」格式。目標 800-1500 字。

=== 任務 2：關鍵建議擷取 ===
擷取所有正式的臨床建議 (Recommendations) 和實作要點 (Practice Points)。
grade 必須是：1A, 1B, 1C, 1D, 2A, 2B, 2C, 2D, Not Graded
如果沒有正式建議，回傳空陣列。

=== 任務 3：治療/診斷流程圖 ===
產生 Mermaid flowchart TD 格式的流程圖。
- 節點標籤用繁體中文，20 字以內
- 決策節點用菱形 {{{{}}}}
- 不超過 15 個節點
- 如果不適合做流程圖，回傳 null

=== 回傳格式 ===
回傳純 JSON（不要加 markdown code fence），格式：
{{
  "content_zh": "完整的 Markdown 摘要...",
  "key_recommendations": [
    {{"text": "建議內容（繁體中文）", "grade": "1A", "description": "簡要說明"}}
  ],
  "flowchart_mermaid": "flowchart TD\\n    A[節點] --> B[節點]",
  "chapter_title_zh": "本章的繁體中文標題"
}}"""


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def detect_org(title: str) -> str:
    upper = title.upper()
    if "KDIGO" in upper:
        return "KDIGO"
    if "KDOQI" in upper:
        return "KDOQI"
    return "Unknown"


def extract_year(title: str) -> int | None:
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
    """Find matching guideline doc in guidelines collection."""
    guidelines_ref = db.collection("guidelines")
    docs = list(guidelines_ref.stream())

    title_words = _normalize(title)
    title_upper = set(re.findall(r'[A-Z]{2,}', title))

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


def call_gemini(contents, expect_json: bool = False):
    """Call Gemini with retry logic. contents can be [file, prompt] or just prompt."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
            )
            text = response.text.strip()

            # Strip markdown code fences
            if text.startswith("```"):
                lines = text.split("\n")
                lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines).strip()

            if expect_json:
                return json.loads(text)
            return text

        except json.JSONDecodeError as e:
            logger.warning("  JSON 解析失敗 (attempt %d/%d): %s", attempt, MAX_RETRIES, e)
            if attempt == MAX_RETRIES:
                logger.error("  JSON 解析最終失敗")
                return {"_error": str(e)} if expect_json else text
            time.sleep(RETRY_DELAY)

        except Exception as e:
            logger.warning("  Gemini 呼叫失敗 (attempt %d/%d): %s", attempt, MAX_RETRIES, e)
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_DELAY)

    return None


def extract_pages(pdf_path: str, page_start: int, page_end: int) -> str | None:
    """Extract specific pages from PDF, return path to new smaller PDF."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        try:
            from PyPDF2 import PdfReader, PdfWriter
        except ImportError:
            logger.warning("  pypdf/PyPDF2 未安裝，無法裁切頁面，將使用完整 PDF")
            return None

    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)

        # Convert to 0-indexed, clamp to valid range
        start = max(0, page_start - 1)
        end = min(total_pages, page_end)

        if start >= end:
            return None

        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, prefix="chapter_") as f:
            writer.write(f)
            return f.name

    except Exception as e:
        logger.warning("  PDF 裁切失敗: %s", e)
        return None


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_book(book_doc_id: str, book_data: dict, dry_run: bool = False) -> bool:
    """Process a single guideline book."""
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

    temp_path = None
    chapter_temp_files = []
    uploaded_files = []

    try:
        # Download PDF
        logger.info("  下載 PDF...")
        resp = requests.get(book_url, timeout=120)
        resp.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(resp.content)
            temp_path = f.name

        # Upload full PDF for TOC extraction
        logger.info("  上傳至 Gemini File API...")
        full_file = client.files.upload(
            file=temp_path, config={"display_name": book_title}
        )
        uploaded_files.append(full_file)
        time.sleep(RATE_LIMIT_DELAY)

        # Extract TOC with page ranges
        logger.info("  擷取目錄（含頁碼範圍）...")
        toc = call_gemini([full_file, TOC_PROMPT], expect_json=True)

        if not isinstance(toc, list):
            logger.error("  目錄擷取失敗: %s", type(toc))
            return False

        logger.info("  找到 %d 個章節", len(toc))
        time.sleep(RATE_LIMIT_DELAY)

        # Check if page ranges are available
        has_pages = any(
            ch.get("page_start") is not None and ch.get("page_end") is not None
            for ch in toc
        )

        # Delete full PDF from Gemini after TOC (save quota)
        try:
            client.files.delete(name=full_file.name)
            uploaded_files.remove(full_file)
            logger.info("  已刪除 Gemini 上的完整 PDF")
        except Exception:
            pass

        # Process each chapter
        chapters_ref = db.collection("guideline_chapters")
        guideline_doc_id, _ = find_guideline_doc(book_title)

        for i, chapter in enumerate(toc, 1):
            ch_num = chapter.get("chapter_number", i)
            ch_title = chapter.get("title", f"Chapter {i}")
            page_start = chapter.get("page_start")
            page_end = chapter.get("page_end")
            prefix = f"  [{i}/{len(toc)}] Ch.{ch_num}: {ch_title}"

            # Try to extract chapter pages
            chapter_file = None
            chapter_pdf_path = None

            if has_pages and page_start and page_end:
                chapter_pdf_path = extract_pages(temp_path, page_start, page_end)

            if chapter_pdf_path:
                chapter_temp_files.append(chapter_pdf_path)
                chapter_file = client.files.upload(
                    file=chapter_pdf_path,
                    config={"display_name": f"{book_title}_ch{ch_num}"}
                )
                uploaded_files.append(chapter_file)
                pages_info = f"p.{page_start}-{page_end}"
            else:
                # Fallback: re-upload full PDF
                chapter_file = client.files.upload(
                    file=temp_path,
                    config={"display_name": f"{book_title}_full_ch{ch_num}"}
                )
                uploaded_files.append(chapter_file)
                pages_info = "full PDF"

            # Single combined call
            logger.info("%s — 生成中... (%s)", prefix, pages_info)
            prompt = f"這是指引的第 {ch_num} 章「{ch_title}」。\n\n{COMBINED_PROMPT}"

            try:
                result = call_gemini([chapter_file, prompt], expect_json=True)
            except Exception as e:
                logger.error("%s — 生成失敗: %s", prefix, e)
                result = None

            # Delete chapter file from Gemini immediately
            try:
                client.files.delete(name=chapter_file.name)
                uploaded_files.remove(chapter_file)
            except Exception:
                pass

            time.sleep(RATE_LIMIT_DELAY)

            # Parse result
            processing_status = "ready"
            if result is None or (isinstance(result, dict) and "_error" in result):
                processing_status = "error"
                content_zh = ""
                recs = []
                flowchart = None
                title_zh = ""
            else:
                content_zh = result.get("content_zh", "")
                recs = result.get("key_recommendations", [])
                flowchart = result.get("flowchart_mermaid")
                title_zh = result.get("chapter_title_zh", "")

                if not isinstance(recs, list):
                    recs = []
                if flowchart and flowchart.strip().upper() in ("NULL", "SKIP", "NONE", ""):
                    flowchart = None

            # Store
            doc_data = {
                "guideline_id": guideline_doc_id,
                "guideline_title": book_title,
                "org": org,
                "version_year": version_year,
                "chapter_number": ch_num,
                "chapter_title": ch_title,
                "chapter_title_zh": title_zh,
                "content_zh": content_zh,
                "key_recommendations": recs,
                "flowchart_mermaid": flowchart,
                "diff_from_previous": None,
                "book_id": book_doc_id,
                "processing_status": processing_status,
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }

            chapters_ref.add(doc_data)
            logger.info("%s — done (%s)", prefix, processing_status)

        # Update guidelines collection
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
        # Clean up temp files
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
        for f in chapter_temp_files:
            if os.path.exists(f):
                os.unlink(f)
        # Clean up any remaining Gemini files
        for uf in uploaded_files:
            try:
                client.files.delete(name=uf.name)
            except Exception:
                pass
        logger.info("  已清理暫存檔案")


def process_all(
    limit: int = 0,
    guideline_id: str | None = None,
    resume: bool = False,
    dry_run: bool = False,
) -> None:
    """Process all guideline PDFs from the books collection."""
    logger.info("=== 開始處理指引 PDF (v2 省錢版) ===")

    from google.cloud.firestore_v1.base_query import FieldFilter
    books_ref = db.collection("books")
    query = books_ref.where(filter=FieldFilter("type", "==", "guideline")).where(filter=FieldFilter("status", "==", "ready"))
    books = list(query.stream())

    if not books:
        logger.info("沒有找到待處理的指引 PDF")
        return

    logger.info("找到 %d 部指引 PDF", len(books))

    if guideline_id:
        books = [b for b in books if b.id == guideline_id]
        if not books:
            logger.error("找不到指定的 book ID: %s", guideline_id)
            return

    if resume:
        existing_book_ids = set()
        for ch in db.collection("guideline_chapters").stream():
            bid = ch.to_dict().get("book_id")
            if bid:
                existing_book_ids.add(bid)

        before = len(books)
        books = [b for b in books if b.id not in existing_book_ids]
        logger.info("Resume: 跳過 %d 部已處理，剩餘 %d 部", before - len(books), len(books))

    if limit > 0:
        books = books[:limit]
        logger.info("限制處理 %d 部", limit)

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
        description="用 Gemini AI 解析指引 PDF 生成章節內容 (v2 省錢版)"
    )
    parser.add_argument("--limit", type=int, default=0, help="最多處理幾部指引 (0=全部)")
    parser.add_argument("--guideline-id", type=str, help="只處理指定的 book doc ID")
    parser.add_argument("--resume", action="store_true", help="跳過已有 chapters 的指引")
    parser.add_argument("--dry-run", action="store_true", help="只顯示會處理什麼")
    args = parser.parse_args()

    process_all(
        limit=args.limit,
        guideline_id=args.guideline_id,
        resume=args.resume,
        dry_run=args.dry_run,
    )
