"""
Patch: 補更新 guideline_chapters 的 guideline_id
===================================================
解決：process_guideline_content.py 初次跑時匹配邏輯不佳，
導致大部分 guideline_chapters 的 guideline_id 為 None。

使用方式：
  python crawlers/patch_chapters_guideline_id.py          # 執行
  python crawlers/patch_chapters_guideline_id.py --dry-run # 預覽
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


def normalize(s):
    words = re.sub(r'[^a-z0-9\s]', ' ', s.lower().replace('-', ' ')).split()
    return set(w for w in words if w not in STOP_WORDS and len(w) > 1)


def find_best_guideline(title, guidelines):
    """Match a guideline_title to a guidelines doc."""
    title_words = normalize(title)
    title_upper = set(re.findall(r'[A-Z]{2,}', title))

    expanded_title = set(title_words)
    for abbr in title_upper:
        if abbr in ABBREV_MAP:
            expanded_title |= ABBREV_MAP[abbr]

    best_doc = None
    best_score = 0

    for gdoc_id, gdata in guidelines:
        gtitle = gdata.get("title", "")
        doc_words = normalize(gtitle)
        doc_upper = set(re.findall(r'[A-Z]{2,}', gtitle))

        expanded_doc = set(doc_words)
        for abbr in doc_upper:
            if abbr in ABBREV_MAP:
                expanded_doc |= ABBREV_MAP[abbr]

        overlap = len(expanded_title & expanded_doc)
        abbrev = len(title_upper & doc_upper)
        score = overlap + abbrev

        if score > best_score:
            best_score = score
            best_doc = (gdoc_id, gdata)

    if best_doc and best_score >= 1:
        return best_doc[0], best_score
    return None, 0


def run(dry_run=False):
    # Load all guidelines
    guidelines = [(doc.id, doc.to_dict()) for doc in db.collection("guidelines").stream()]
    logger.info("guidelines collection 共 %d 筆", len(guidelines))

    # Load all guideline_chapters
    chapters = list(db.collection("guideline_chapters").stream())
    logger.info("guideline_chapters 共 %d 筆", len(chapters))

    # Group chapters by guideline_title
    groups = {}
    for ch in chapters:
        data = ch.to_dict()
        title = data.get("guideline_title", "")
        current_gid = data.get("guideline_id")
        if title not in groups:
            groups[title] = {"chapters": [], "current_gid": current_gid}
        groups[title]["chapters"].append(ch)

    updated = 0
    skipped = 0

    for title, info in groups.items():
        current_gid = info["current_gid"]
        matched_id, score = find_best_guideline(title, guidelines)

        if not matched_id:
            logger.warning("  找不到匹配: %s", title)
            continue

        if current_gid == matched_id:
            logger.info("  [OK] %s → %s (已正確，%d 章)", title, matched_id, len(info["chapters"]))
            skipped += len(info["chapters"])
            continue

        logger.info("  [FIX] %s: %s → %s (score=%d, %d 章)",
                    title, current_gid, matched_id, score, len(info["chapters"]))

        if dry_run:
            continue

        # Batch update
        batch = db.batch()
        for ch in info["chapters"]:
            batch.update(ch.reference, {"guideline_id": matched_id})
        batch.commit()
        updated += len(info["chapters"])
        logger.info("    → 已更新 %d 筆", len(info["chapters"]))

    logger.info("完成！更新 %d 筆，跳過 %d 筆（已正確）", updated, skipped)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="補更新 guideline_chapters 的 guideline_id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
