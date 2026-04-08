"""
Patch: 補更新 guidelines collection 的 chapters_ready / chapters_count
=========================================================================
用途：guideline_chapters 已有資料但 guidelines doc 尚未更新時，執行此腳本補上。

使用方式：
  python crawlers/patch_guidelines_chapters_ready.py          # 執行
  python crawlers/patch_guidelines_chapters_ready.py --dry-run # 預覽
"""

import argparse
import json
import logging
import os
import re

import firebase_admin
from firebase_admin import credentials, firestore
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
        raise FileNotFoundError(f"找不到 Firebase 憑證：{FIREBASE_SERVICE_ACCOUNT_JSON}")
    firebase_admin.initialize_app(cred)

db = firestore.client()


STOP_WORDS = {"kdigo", "kdoqi", "guideline", "guidelines", "clinical", "practice",
              "for", "the", "and", "in", "of", "a", "an", "english", "final", "gl",
              "update", "2024", "2023", "2022", "2021", "2020", "2019", "2018",
              "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010",
              "2009", "2008", "2007", "2006", "2005", "2004", "2003", "2025"}

# 縮寫 → 全稱關鍵字映射（處理 BP → Blood Pressure 等）
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
}


def normalize(s):
    words = re.sub(r'[^a-z0-9\s]', ' ', s.lower().replace('-', ' ')).split()
    return set(w for w in words if w not in STOP_WORDS and len(w) > 1)


def run(dry_run=False):
    # 1. 取得所有 guideline_chapters，按 guideline_title 分組統計
    chapters = list(db.collection("guideline_chapters").stream())
    logger.info("找到 %d 筆 guideline_chapters", len(chapters))

    # Group by guideline_title
    groups = {}
    for ch in chapters:
        data = ch.to_dict()
        title = data.get("guideline_title", "unknown")
        book_id = data.get("book_id", "")
        status = data.get("processing_status", "")
        if title not in groups:
            groups[title] = {"count": 0, "ready": 0, "book_id": book_id}
        groups[title]["count"] += 1
        if status == "ready":
            groups[title]["ready"] += 1

    logger.info("共 %d 部指引有章節資料", len(groups))

    # 2. 取得所有 guidelines docs
    guidelines = list(db.collection("guidelines").stream())
    logger.info("guidelines collection 共 %d 筆", len(guidelines))

    matched = 0
    for title, info in groups.items():
        # 找匹配的 guideline doc
        title_words = normalize(title)
        title_upper = set(re.findall(r'[A-Z]{2,}', title))

        best_doc = None
        best_score = 0

        # Expand abbreviations to keywords for better matching
        expanded_title_words = set(title_words)
        for abbr in title_upper:
            if abbr in ABBREV_MAP:
                expanded_title_words |= ABBREV_MAP[abbr]

        for gdoc in guidelines:
            gdata = gdoc.to_dict()
            gtitle = gdata.get("title", "")
            doc_words = normalize(gtitle)
            doc_upper = set(re.findall(r'[A-Z]{2,}', gtitle))

            # Expand doc abbreviations too
            expanded_doc_words = set(doc_words)
            for abbr in doc_upper:
                if abbr in ABBREV_MAP:
                    expanded_doc_words |= ABBREV_MAP[abbr]

            overlap = len(expanded_title_words & expanded_doc_words)
            abbrev = len(title_upper & doc_upper)
            score = overlap + abbrev

            if score > best_score:
                best_score = score
                best_doc = gdoc

        if best_doc and best_score >= 1:
            matched += 1
            gdata = best_doc.to_dict()
            logger.info("  [%d] %s → %s (score=%d, chapters=%d/%d)",
                        matched, title, gdata.get("title", ""), best_score,
                        info["ready"], info["count"])

            if dry_run:
                continue

            best_doc.reference.update({
                "chapters_ready": info["ready"] == info["count"],
                "chapters_count": info["count"],
                "book_id": info["book_id"],
                "updated_at": firestore.SERVER_TIMESTAMP,
            })
            logger.info("    → 已更新 guidelines doc")
        else:
            logger.warning("  找不到匹配: %s (best_score=%d)", title, best_score)

    logger.info("完成！匹配 %d / %d 部", matched, len(groups))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="補更新 guidelines 的 chapters_ready")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
