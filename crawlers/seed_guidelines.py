"""
Seed Guidelines — Nephro Brain OS
==================================
一次性寫入 KDIGO 及 KDOQI 臨床指引 metadata 到 Firestore guidelines collection。

使用方式：
  python crawlers/seed_guidelines.py            # 寫入 Firestore
  python crawlers/seed_guidelines.py --dry-run   # 只顯示，不寫入
"""

import argparse
import json
import logging
import os
import sys

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
# Guideline seed data
# ---------------------------------------------------------------------------

GUIDELINES = [
    # ── KDIGO ──
    {
        "org": "KDIGO",
        "topic": "CKD",
        "title": "CKD Evaluation and Management",
        "title_zh": "慢性腎臟病的評估與管理",
        "year": 2024,
        "url": "https://kdigo.org/guidelines/ckd-evaluation-and-management/",
        "status": "current",
        "summary_zh": "涵蓋 CKD 定義、分期、風險評估、治療策略，包括 SGLT2 抑制劑和非甾體 MRA 的使用建議。",
        "key_topics": ["eGFR", "白蛋白尿", "CKD 分期", "SGLT2i", "Finerenone", "心腎保護"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDIGO",
        "topic": "AKI",
        "title": "Acute Kidney Injury (AKI) and Acute Kidney Disease (AKD)",
        "title_zh": "急性腎損傷與急性腎臟疾病",
        "year": 2012,
        "url": "https://kdigo.org/guidelines/acute-kidney-injury/",
        "status": "current",
        "summary_zh": "AKI 定義（KDIGO 分期）、診斷、預防、藥物劑量調整、RRT 時機與處方。",
        "key_topics": ["AKI 分期", "CRRT", "血液淨化", "腎毒性藥物", "液體治療"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDIGO",
        "topic": "GN",
        "title": "Glomerular Diseases (GD)",
        "title_zh": "腎絲球疾病",
        "year": 2021,
        "url": "https://kdigo.org/guidelines/gd/",
        "status": "current",
        "summary_zh": "涵蓋 IgAN、膜性腎病、FSGS、微小變化型、狼瘡腎炎、ANCA 血管炎等腎絲球疾病的診治。",
        "key_topics": ["IgA 腎病", "膜性腎病", "FSGS", "微小變化型", "狼瘡腎炎", "ANCA"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDIGO",
        "topic": "HTN",
        "title": "Blood Pressure in CKD",
        "title_zh": "慢性腎臟病的血壓管理",
        "year": 2021,
        "url": "https://kdigo.org/guidelines/blood-pressure-in-ckd/",
        "status": "current",
        "summary_zh": "CKD 患者的血壓目標、測量方法、RAS 阻斷劑使用、生活型態介入。",
        "key_topics": ["血壓目標", "ACEI/ARB", "居家血壓監測", "RAS 阻斷劑"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDIGO",
        "topic": "CKD-MBD",
        "title": "CKD-Mineral and Bone Disorder (CKD-MBD)",
        "title_zh": "慢性腎臟病礦物質與骨骼代謝異常",
        "year": 2017,
        "url": "https://kdigo.org/guidelines/ckd-mbd/",
        "status": "current",
        "summary_zh": "磷、鈣、PTH、Vitamin D 的監測與治療，磷結合劑選擇，鈣化防禦症。",
        "key_topics": ["副甲狀腺亢進", "磷結合劑", "Vitamin D", "鈣化防禦症", "骨質疏鬆"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDIGO",
        "topic": "CKD",
        "title": "Hepatitis C in CKD",
        "title_zh": "慢性腎臟病的 C 型肝炎管理",
        "year": 2022,
        "url": "https://kdigo.org/guidelines/hepatitis-c-in-ckd/",
        "status": "current",
        "summary_zh": "CKD 及透析患者的 HCV 篩檢、DAA 抗病毒治療、移植相關處理。",
        "key_topics": ["HCV", "DAA 抗病毒", "透析感控", "移植前篩檢"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDIGO",
        "topic": "Transplant",
        "title": "Kidney Transplant Recipient",
        "title_zh": "腎臟移植受者照護",
        "year": 2009,
        "url": "https://kdigo.org/guidelines/transplant-recipient/",
        "status": "current",
        "summary_zh": "移植後免疫抑制、排斥診斷與治療、感染預防、心血管風險管理。",
        "key_topics": ["免疫抑制", "排斥反應", "Tacrolimus", "BK 病毒", "移植後照護"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDIGO",
        "topic": "Transplant",
        "title": "Kidney Transplant Candidate",
        "title_zh": "腎臟移植候選人評估",
        "year": 2020,
        "url": "https://kdigo.org/guidelines/transplant-candidate/",
        "status": "current",
        "summary_zh": "移植前評估、等待名單管理、免疫學檢查、風險分層。",
        "key_topics": ["移植前評估", "等待名單", "免疫配對", "風險分層"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDIGO",
        "topic": "Transplant",
        "title": "Living Kidney Donor",
        "title_zh": "活體腎臟捐贈者",
        "year": 2017,
        "url": "https://kdigo.org/guidelines/living-kidney-donor/",
        "status": "current",
        "summary_zh": "活體捐贈者的評估、長期追蹤、風險告知、心理社會評估。",
        "key_topics": ["捐贈者評估", "長期追蹤", "風險告知"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDIGO",
        "topic": "CKM",
        "title": "Diabetes Management in CKD",
        "title_zh": "慢性腎臟病的糖尿病管理",
        "year": 2022,
        "url": "https://kdigo.org/guidelines/diabetes-ckd/",
        "status": "current",
        "summary_zh": "DKD 綜合管理：血糖目標、SGLT2i、GLP-1 RA、Finerenone、生活型態。",
        "key_topics": ["DKD", "SGLT2i", "GLP-1 RA", "Finerenone", "血糖控制"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDIGO",
        "topic": "GN",
        "title": "Lupus Nephritis (LN)",
        "title_zh": "狼瘡腎炎",
        "year": 2024,
        "url": "https://kdigo.org/guidelines/lupus-nephritis/",
        "status": "current",
        "summary_zh": "狼瘡腎炎的分類、誘導治療、維持治療、Voclosporin 等新藥建議。",
        "key_topics": ["狼瘡腎炎", "ISN/RPS 分類", "MMF", "Voclosporin", "Belimumab"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDIGO",
        "topic": "GN",
        "title": "ANCA-Associated Vasculitis",
        "title_zh": "ANCA 相關血管炎",
        "year": 2024,
        "url": "https://kdigo.org/guidelines/antineutrophilic-cytoplasmic-antibody-anca-associated-vasculitis-aav/",
        "status": "current",
        "summary_zh": "AAV 的診斷、誘導治療（Rituximab vs Cyclophosphamide）、維持治療、Avacopan。",
        "key_topics": ["ANCA 血管炎", "Rituximab", "Cyclophosphamide", "Avacopan", "血漿置換"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDIGO",
        "topic": "PKD",
        "title": "Autosomal Dominant Polycystic Kidney Disease (ADPKD)",
        "title_zh": "體染色體顯性多囊腎病",
        "year": 2025,
        "url": "https://kdigo.org/guidelines/autosomal-dominant-polycystic-kidney-disease-adpkd/",
        "status": "current",
        "summary_zh": "ADPKD 的診斷、風險預測（Mayo 分類）、Tolvaptan 使用、併發症管理。",
        "key_topics": ["ADPKD", "Tolvaptan", "Mayo 分類", "囊腫感染", "TKV"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDIGO",
        "topic": "CKD",
        "title": "Anemia in CKD",
        "title_zh": "慢性腎臟病的貧血管理",
        "year": 2012,
        "url": "https://kdigo.org/guidelines/anemia-in-ckd/",
        "status": "current",
        "summary_zh": "CKD 貧血的診斷、鐵劑補充、ESA 使用、輸血策略。",
        "key_topics": ["ESA", "鐵劑", "Hb 目標", "HIF-PHI", "輸血"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDIGO",
        "topic": "CKD",
        "title": "Lipids in CKD",
        "title_zh": "慢性腎臟病的血脂管理",
        "year": 2013,
        "url": "https://kdigo.org/guidelines/lipids-in-ckd/",
        "status": "current",
        "summary_zh": "CKD 患者的心血管風險評估、Statin 使用建議、透析患者的血脂管理。",
        "key_topics": ["Statin", "心血管風險", "血脂"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDIGO",
        "topic": "GN",
        "title": "IgA Nephropathy (IgAN) / IgA Vasculitis (IgAV)",
        "title_zh": "IgA 腎病 / IgA 血管炎",
        "year": 2024,
        "url": "https://kdigo.org/guidelines/iga-nephropathy/",
        "status": "current",
        "summary_zh": "IgAN 的支持性治療、免疫抑制決策、新藥（Sparsentan、Budesonide）。",
        "key_topics": ["IgA 腎病", "Sparsentan", "Budesonide", "RAS 阻斷", "蛋白尿控制"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDIGO",
        "topic": "CKM",
        "title": "Heart Failure in CKD",
        "title_zh": "慢性腎臟病的心衰竭管理",
        "year": 2025,
        "url": "https://kdigo.org/guidelines/heart-failure-in-ckd/",
        "status": "current",
        "summary_zh": "CKD 合併心衰竭的藥物治療（SGLT2i、ARNI）、容積管理、透析患者特殊考量。",
        "key_topics": ["心衰竭", "SGLT2i", "ARNI", "容積管理", "心腎症候群"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDIGO",
        "topic": "GN",
        "title": "Nephrotic Syndrome in Children",
        "title_zh": "兒童腎病症候群",
        "year": 2025,
        "url": "https://kdigo.org/guidelines/nephrotic-syndrome-in-children/",
        "status": "current",
        "summary_zh": "兒童腎病症候群的初始治療、復發管理、Steroid-sparing 策略。",
        "key_topics": ["兒童腎病", "類固醇", "CNI", "Rituximab", "復發預防"],
        "rag_status": "not_indexed",
    },
    # ── KDOQI ──
    {
        "org": "KDOQI",
        "topic": "ESRD/HD",
        "title": "Hemodialysis Adequacy",
        "title_zh": "血液透析充分性",
        "year": 2015,
        "url": "https://www.ajkd.org/article/S0272-6386(15)01019-7/fulltext",
        "status": "current",
        "summary_zh": "HD 充分性指標（Kt/V、URR）、透析處方、頻率與時間、血管通路監測。",
        "key_topics": ["Kt/V", "URR", "透析處方", "透析充分性"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDOQI",
        "topic": "PD",
        "title": "Peritoneal Dialysis Adequacy",
        "title_zh": "腹膜透析充分性",
        "year": 2006,
        "url": "https://www.kidney.org/professionals/kdoqi",
        "status": "current",
        "summary_zh": "PD 充分性目標、溶質清除、殘餘腎功能、PET 測試、處方調整。",
        "key_topics": ["PD 充分性", "PET", "Kt/V", "殘餘腎功能", "CAPD/APD"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDOQI",
        "topic": "ESRD/HD",
        "title": "Vascular Access",
        "title_zh": "血管通路",
        "year": 2019,
        "url": "https://www.ajkd.org/article/S0272-6386(19)31137-0/fulltext",
        "status": "current",
        "summary_zh": "AVF/AVG/CVC 的選擇、建立時機、監測、併發症處理。",
        "key_topics": ["AVF", "AVG", "導管", "通路監測", "通路併發症"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDOQI",
        "topic": "CKD",
        "title": "Nutrition in CKD",
        "title_zh": "慢性腎臟病的營養管理",
        "year": 2020,
        "url": "https://www.ajkd.org/article/S0272-6386(20)30726-5/fulltext",
        "status": "current",
        "summary_zh": "CKD 各期的蛋白質攝取建議、熱量需求、電解質控制、透析患者營養。",
        "key_topics": ["蛋白質攝取", "熱量", "磷鉀控制", "營養評估", "MNT"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDOQI",
        "topic": "CKM",
        "title": "Diabetes and CKD",
        "title_zh": "糖尿病與慢性腎臟病",
        "year": 2012,
        "url": "https://www.ajkd.org/article/S0272-6386(12)00957-2/fulltext",
        "status": "current",
        "summary_zh": "DKD 的篩檢、血糖控制目標、藥物選擇、多學科照護。",
        "key_topics": ["DKD", "血糖目標", "Metformin", "胰島素"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDOQI",
        "topic": "HTN",
        "title": "Hypertension and Antihypertensive Agents in CKD",
        "title_zh": "慢性腎臟病的高血壓與降壓藥物",
        "year": 2004,
        "url": "https://www.kidney.org/professionals/kdoqi",
        "status": "current",
        "summary_zh": "CKD 各期的血壓目標、降壓藥物選擇、蛋白尿管理。",
        "key_topics": ["血壓目標", "ACEI", "ARB", "蛋白尿"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDOQI",
        "topic": "CKD",
        "title": "Anemia",
        "title_zh": "貧血管理",
        "year": 2006,
        "url": "https://www.kidney.org/professionals/kdoqi",
        "status": "current",
        "summary_zh": "CKD 貧血的鐵劑與 ESA 使用建議、Hb 目標、監測頻率。",
        "key_topics": ["ESA", "鐵劑", "Hb 目標"],
        "rag_status": "not_indexed",
    },
    {
        "org": "KDOQI",
        "topic": "CKD-MBD",
        "title": "Bone Metabolism and Disease in CKD",
        "title_zh": "慢性腎臟病的骨骼代謝與疾病",
        "year": 2003,
        "url": "https://www.kidney.org/professionals/kdoqi",
        "status": "current",
        "summary_zh": "CKD-MBD 的診斷、磷鈣管理、PTH 目標、Vitamin D 使用。",
        "key_topics": ["PTH", "磷控制", "鈣平衡", "Vitamin D"],
        "rag_status": "not_indexed",
    },
]


def seed(dry_run: bool = False) -> None:
    logger.info("開始寫入 guidelines collection (%d 筆)...", len(GUIDELINES))
    collection_ref = db.collection("guidelines")

    for i, g in enumerate(GUIDELINES, 1):
        g["created_at"] = firestore.SERVER_TIMESTAMP
        g["updated_at"] = firestore.SERVER_TIMESTAMP

        if dry_run:
            logger.info("  [%d] %s — %s (%d) [DRY-RUN]", i, g["org"], g["title"], g["year"])
        else:
            try:
                doc_ref = collection_ref.add(g)
                logger.info("  [%d] %s — %s (%d) → %s", i, g["org"], g["title"], g["year"], doc_ref[1].id)
            except Exception as exc:
                logger.error("  [%d] 寫入失敗: %s", i, exc)

    logger.info("完成！共 %d 筆指引。", len(GUIDELINES))


def update(dry_run: bool = False) -> None:
    """以 title 為 key，更新已存在的 guidelines 文件（僅更新有差異的欄位）。"""
    logger.info("開始更新 guidelines collection...")
    collection_ref = db.collection("guidelines")

    # 讀取所有現有文件，以 title 為 key
    existing = {}
    for doc in collection_ref.stream():
        data = doc.to_dict()
        existing[data.get("title", "")] = (doc.id, data)

    updated = 0
    skipped = 0

    for i, g in enumerate(GUIDELINES, 1):
        title = g["title"]
        if title not in existing:
            logger.info("  [%d] %s — 不在 Firestore 中，跳過（請用 seed 模式新增）", i, title)
            skipped += 1
            continue

        doc_id, old_data = existing[title]
        # 比對需更新的欄位
        changes = {}
        for key in ["url", "title_zh", "year", "status", "summary_zh", "key_topics", "org", "topic", "rag_status"]:
            if key in g and g[key] != old_data.get(key):
                changes[key] = g[key]

        if not changes:
            logger.info("  [%d] %s — 無變更", i, title)
            skipped += 1
            continue

        changes["updated_at"] = firestore.SERVER_TIMESTAMP

        if dry_run:
            logger.info("  [%d] %s — 需更新: %s [DRY-RUN]", i, title, list(changes.keys()))
        else:
            try:
                collection_ref.document(doc_id).update(changes)
                logger.info("  [%d] %s — 已更新: %s", i, title, list(changes.keys()))
            except Exception as exc:
                logger.error("  [%d] 更新失敗: %s", i, exc)

        updated += 1

    logger.info("完成！更新 %d 筆，跳過 %d 筆。", updated, skipped)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="寫入/更新 KDIGO/KDOQI 指引 metadata 到 Firestore")
    parser.add_argument("--dry-run", action="store_true", help="只顯示差異，不寫入")
    parser.add_argument("--update", action="store_true", help="更新模式：以 title 為 key 更新已存在的文件")
    args = parser.parse_args()

    if args.update:
        update(dry_run=args.dry_run)
    else:
        seed(dry_run=args.dry_run)
