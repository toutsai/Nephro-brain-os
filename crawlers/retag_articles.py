"""
Retag Articles — Nephro Brain OS
=================================
批次重新標記 articles_v2 集合中所有文章的 topics 欄位。

當 detect_topics() 邏輯更新（新增主題關鍵字等）後，
可用此腳本一次性將既有文章重新分類。

使用方式：
  python crawlers/retag_articles.py            # 實際寫入 Firestore
  python crawlers/retag_articles.py --dry-run   # 只顯示差異，不寫入
"""

import argparse
import json
import logging
import os
import sys
import time

import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

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
# Firebase initialisation (same pattern as crawler_v2.py)
# ---------------------------------------------------------------------------
load_dotenv()

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
# Topic detection (copied from crawler_v2.py to avoid import side-effects)
# ---------------------------------------------------------------------------

def detect_topics(title: str, abstract: str, mesh_terms: list) -> list:
    text = f"{title} {abstract} {' '.join(mesh_terms)}".lower()
    topics = []

    esrd_kw = [
        "esrd", "eskd", "end stage", "hemodialysis", "haemodialysis",
        "dialysis", "hemodiafiltration",
    ]
    aki_kw = [
        "acute kidney injury", " aki ", "acute renal failure",
        "crrt", "continuous renal replacement",
    ]
    ckd_kw = [
        "chronic kidney disease", " ckd ", "chronic renal",
        "proteinuria", "albuminuria",
    ]
    gn_kw = [
        "glomerulonephritis", "glomerulopathy", "nephrotic syndrome",
        "iga nephropathy", "membranous nephropathy", "fsgs",
        "lupus nephritis", "anca vasculitis", "minimal change",
        "nephritic", "complement", "c3 glomerulopathy",
    ]
    transplant_kw = [
        "kidney transplant", "renal transplant", "transplantation",
        "rejection", "tacrolimus", "immunosuppression",
        "donor", "allograft", "bk virus",
    ]
    electrolyte_kw = [
        "hyperkalemia", "hypokalemia", "hyponatremia", "hypernatremia",
        "metabolic acidosis", "metabolic alkalosis",
        "hypercalcemia", "hypocalcemia", "hyperphosphatemia",
        "electrolyte", "acid-base",
    ]
    pd_kw = [
        "peritoneal dialysis", "pd catheter", "peritonitis",
        "capd", "apd", "automated peritoneal",
    ]
    ckm_kw = [
        "diabetic kidney", "diabetic nephropathy", " dkd ",
        "sglt2", "dapagliflozin", "empagliflozin", "canagliflozin",
        "glp-1", "semaglutide", "liraglutide", "tirzepatide",
        "finerenone", "cardiorenal", "cardio-renal",
        "heart failure", "type 2 diabetes",
    ]
    htn_kw = [
        "hypertensive nephrosclerosis", "hypertensive kidney",
        "renal artery stenosis", "resistant hypertension",
        "renovascular", "malignant hypertension",
    ]
    pkd_kw = [
        "polycystic kidney", "adpkd", "arpkd", "tolvaptan",
        "alport syndrome", "fabry disease", "hereditary nephritis",
        "thin basement membrane",
    ]
    ckd_mbd_kw = [
        "hyperparathyroidism", "phosphate binder", "calciphylaxis",
        "renal osteodystrophy", "ckd-mbd", "vitamin d",
        "calcimimetic", "cinacalcet", "etelcalcetide",
        "paricalcitol", "bone mineral",
    ]
    stone_kw = [
        "nephrolithiasis", "kidney stone", "renal calculi",
        "urolithiasis", "hyperoxaluria", "uric acid stone",
        "calcium oxalate", "struvite", "cystinuria",
    ]
    onco_nephro_kw = [
        "checkpoint inhibitor", "tumor lysis", "cisplatin nephrotoxicity",
        "onconephrology", "monoclonal gammopathy", " mgrs ",
        "amyloidosis", "myeloma kidney", "myeloma cast",
        "light chain deposition",
    ]

    if any(kw in text for kw in esrd_kw):
        topics.append("ESRD/HD")
    if any(kw in text for kw in aki_kw):
        topics.append("AKI")
    if any(kw in text for kw in ckd_kw):
        topics.append("CKD")
    if any(kw in text for kw in gn_kw):
        topics.append("GN")
    if any(kw in text for kw in transplant_kw):
        topics.append("Transplant")
    if any(kw in text for kw in electrolyte_kw):
        topics.append("Electrolyte")
    if any(kw in text for kw in pd_kw):
        topics.append("PD")
    if any(kw in text for kw in ckm_kw):
        topics.append("CKM")
    if any(kw in text for kw in htn_kw):
        topics.append("HTN")
    if any(kw in text for kw in pkd_kw):
        topics.append("PKD")
    if any(kw in text for kw in ckd_mbd_kw):
        topics.append("CKD-MBD")
    if any(kw in text for kw in stone_kw):
        topics.append("Stone")
    if any(kw in text for kw in onco_nephro_kw):
        topics.append("Onco-Nephro")

    return topics if topics else ["CKD"]


# ---------------------------------------------------------------------------
# Batch size for Firestore writes (limit is 500; we use 400 for safety)
# ---------------------------------------------------------------------------
BATCH_SIZE = 400


def retag_all(dry_run: bool = False) -> None:
    """Fetch every article in articles_v2, re-detect topics, and batch-update."""

    logger.info("開始從 articles_v2 串流讀取文章...")
    collection_ref = db.collection("articles_v2")

    total = 0
    changed = 0
    errors = 0
    batch = db.batch()
    batch_count = 0

    try:
        docs = collection_ref.stream()
    except Exception as exc:
        logger.error("無法讀取 articles_v2 集合: %s", exc)
        sys.exit(1)

    for doc in docs:
        total += 1
        try:
            data = doc.to_dict()
            title = data.get("title", "")
            abstract = data.get("abstract", "")
            mesh_terms = data.get("mesh_terms", [])
            old_topics = sorted(data.get("topics", []))

            new_topics = detect_topics(title, abstract, mesh_terms)
            new_topics_sorted = sorted(new_topics)

            if old_topics != new_topics_sorted:
                changed += 1
                logger.info(
                    "  [%d] %s — %s -> %s",
                    total,
                    doc.id,
                    old_topics,
                    new_topics_sorted,
                )

                if not dry_run:
                    batch.update(doc.reference, {"topics": new_topics})
                    batch_count += 1

                    if batch_count >= BATCH_SIZE:
                        batch.commit()
                        logger.info("  ✓ 已提交 batch（%d 筆）", batch_count)
                        batch = db.batch()
                        batch_count = 0

        except Exception as exc:
            errors += 1
            logger.warning("  處理文件 %s 時發生錯誤: %s", doc.id, exc)

        if total % 500 == 0:
            logger.info("  已處理 %d 篇...", total)

    # Commit remaining updates
    if batch_count > 0 and not dry_run:
        try:
            batch.commit()
            logger.info("  ✓ 已提交最後 batch（%d 筆）", batch_count)
        except Exception as exc:
            logger.error("最後 batch commit 失敗: %s", exc)
            errors += 1

    # Final report
    mode = "DRY-RUN" if dry_run else "WRITE"
    logger.info("=" * 50)
    logger.info("完成 [%s]", mode)
    logger.info("  總文章數: %d", total)
    logger.info("  需更新:   %d", changed)
    logger.info("  無變化:   %d", total - changed - errors)
    logger.info("  錯誤:     %d", errors)
    logger.info("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="重新標記 articles_v2 集合中所有文章的 topics 欄位",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只顯示差異，不實際寫入 Firestore",
    )
    args = parser.parse_args()

    retag_all(dry_run=args.dry_run)
