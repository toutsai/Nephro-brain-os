"""
Download KDOQI Guidelines — Nephro Brain OS
=============================================
下載 KDOQI 臨床指引 PDF 並上傳到 Firebase Storage，
同時在 books collection 建立對應的 doc。

使用方式：
  python crawlers/download_kdoqi.py            # 下載並上傳
  python crawlers/download_kdoqi.py --dry-run   # 只顯示，不下載
"""

import argparse
import json
import logging
import os
import sys
import tempfile

import requests
import firebase_admin
from firebase_admin import credentials, firestore, storage
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

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
    firebase_admin.initialize_app(cred, {
        "storageBucket": "nephro-brain.firebasestorage.app"
    })

db = firestore.client()
bucket = storage.bucket()

# ---------------------------------------------------------------------------
# KDOQI PDF sources
# ---------------------------------------------------------------------------

KDOQI_PDFS = [
    {
        "title": "KDOQI-Hemodialysis-Adequacy-2015",
        "url": "https://www.ajkd.org/article/s0272-6386(15)01019-7/pdf",
        "org": "KDOQI",
        "year": 2015,
        "topic": "ESRD/HD",
    },
    {
        "title": "KDOQI-Vascular-Access-2019",
        "url": "https://ajkd.org/article/S0272-6386(19)31137-0/pdf",
        "org": "KDOQI",
        "year": 2019,
        "topic": "ESRD/HD",
    },
    {
        "title": "KDOQI-Nutrition-in-CKD-2020",
        "url": "https://www.ajkd.org/article/s0272-6386(20)30726-5/pdf",
        "org": "KDOQI",
        "year": 2020,
        "topic": "CKD",
    },
    {
        "title": "KDOQI-Diabetes-and-CKD-2012",
        "url": "https://www.ajkd.org/article/S0272-6386(12)00957-2/pdf",
        "org": "KDOQI",
        "year": 2012,
        "topic": "CKM",
    },
    {
        "title": "KDOQI-Peritoneal-Dialysis-Adequacy-2006",
        "url": "https://www.kidney.org/sites/default/files/docs/12-50-0210_jag_dcp_guidelines-va_oct06_sectionc_ofc.pdf",
        "org": "KDOQI",
        "year": 2006,
        "topic": "PD",
        "note": "Combined HD/PD/VA 2006 document, PD section",
    },
    # 以下 3 部較舊，URL 需手動確認或從 kidney.org 下載
    # {
    #     "title": "KDOQI-Hypertension-in-CKD-2004",
    #     "url": "",
    #     "org": "KDOQI",
    #     "year": 2004,
    #     "topic": "HTN",
    # },
    # {
    #     "title": "KDOQI-Anemia-2006",
    #     "url": "",
    #     "org": "KDOQI",
    #     "year": 2006,
    #     "topic": "CKD",
    # },
    # {
    #     "title": "KDOQI-Bone-Metabolism-2003",
    #     "url": "",
    #     "org": "KDOQI",
    #     "year": 2003,
    #     "topic": "CKD-MBD",
    # },
]


def download_pdf(url: str, title: str) -> str | None:
    """Download PDF from URL, return temp file path."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=60, allow_redirects=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "pdf" not in content_type and not resp.content[:5] == b"%PDF-":
            logger.warning("  %s: 回應不是 PDF (Content-Type: %s)", title, content_type)
            return None

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, prefix=f"{title}_") as f:
            f.write(resp.content)
            logger.info("  已下載: %s (%.1f MB)", title, len(resp.content) / 1024 / 1024)
            return f.name

    except Exception as exc:
        logger.error("  下載失敗 %s: %s", title, exc)
        return None


def upload_to_storage(local_path: str, title: str) -> str | None:
    """Upload PDF to Firebase Storage, return download URL."""
    try:
        blob_path = f"guideline_pdfs/{title}.pdf"
        blob = bucket.blob(blob_path)
        blob.upload_from_filename(local_path, content_type="application/pdf")
        blob.make_public()
        logger.info("  已上傳到 Storage: %s", blob_path)
        return blob.public_url
    except Exception as exc:
        logger.error("  上傳 Storage 失敗: %s", exc)
        return None


def create_book_doc(title: str, storage_url: str, meta: dict) -> str | None:
    """Create a document in the books collection."""
    try:
        doc_data = {
            "title": title,
            "url": storage_url,
            "type": "guideline",
            "status": "pending",
            "guideline_id": title,
            "version": str(meta.get("year", "")),
            "uploadedAt": firestore.SERVER_TIMESTAMP,
        }
        _, doc_ref = db.collection("books").add(doc_data)
        logger.info("  已建立 books doc: %s", doc_ref.id)
        return doc_ref.id
    except Exception as exc:
        logger.error("  建立 books doc 失敗: %s", exc)
        return None


def run(dry_run: bool = False) -> None:
    logger.info("開始下載 KDOQI 指引 (%d 部)...", len(KDOQI_PDFS))

    for i, pdf in enumerate(KDOQI_PDFS, 1):
        title = pdf["title"]
        url = pdf.get("url", "")

        if not url:
            logger.info("[%d/%d] %s — 無 URL，跳過", i, len(KDOQI_PDFS), title)
            continue

        logger.info("[%d/%d] %s", i, len(KDOQI_PDFS), title)

        # Check if already exists in books
        existing = list(
            db.collection("books")
            .where("title", "==", title)
            .limit(1)
            .stream()
        )
        if existing:
            logger.info("  已存在於 books collection，跳過")
            continue

        if dry_run:
            logger.info("  [DRY-RUN] 會下載: %s", url)
            continue

        # Download
        local_path = download_pdf(url, title)
        if not local_path:
            continue

        try:
            # Upload to Storage
            storage_url = upload_to_storage(local_path, title)
            if not storage_url:
                continue

            # Create books doc
            create_book_doc(title, storage_url, pdf)

        finally:
            # Cleanup
            if os.path.exists(local_path):
                os.unlink(local_path)

    logger.info("完成！")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="下載 KDOQI 指引 PDF 並上傳到 Firebase")
    parser.add_argument("--dry-run", action="store_true", help="只顯示，不下載")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
