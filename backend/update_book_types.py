#!/usr/bin/env python3
"""
批次更新 books collection 的 type 欄位
書名含 KDIGO、Guideline、GL、指引 → type: "guideline"
"""
import firebase_admin
from firebase_admin import credentials, firestore
import os
import re
from dotenv import load_dotenv

load_dotenv()

# Firebase 初始化
if not firebase_admin._apps:
    firebase_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if firebase_json and firebase_json.strip().startswith("{"):
        import json
        cred = credentials.Certificate(json.loads(firebase_json))
    else:
        cred_path = firebase_json or "serviceAccountKey.json"
        cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# 匹配指引的關鍵字 pattern（不區分大小寫）
GUIDELINE_PATTERN = re.compile(
    r'KDIGO|Guideline|指引|指南|-GL-|-GL$|^GL-', re.IGNORECASE
)

def main():
    import sys
    dry_run = '--dry-run' in sys.argv

    print("=" * 60)
    print("📚 批次更新 books type 欄位")
    if dry_run:
        print("🔍 DRY RUN 模式（不會實際修改）")
    print("=" * 60)

    books = db.collection("books").stream()
    updated = 0
    skipped = 0

    for doc in books:
        data = doc.to_dict()
        title = data.get("title", "")
        current_type = data.get("type", "textbook")

        should_be_guideline = bool(GUIDELINE_PATTERN.search(title))

        if should_be_guideline and current_type != "guideline":
            print(f"  ✏️  {title}")
            print(f"      {current_type} → guideline")
            if not dry_run:
                doc.reference.update({"type": "guideline"})
            updated += 1
        else:
            skipped += 1

    print(f"\n{'=' * 60}")
    print(f"✅ 完成！更新 {updated} 本，跳過 {skipped} 本")
    if dry_run:
        print("（DRY RUN - 未實際修改，移除 --dry-run 執行）")
    print("=" * 60)

if __name__ == "__main__":
    main()
