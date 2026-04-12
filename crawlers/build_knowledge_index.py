"""
Knowledge Base Index Builder — Nephro Brain OS
================================================
建構知識庫 FAISS 索引，將 articles_v2、guideline_chapters、clinical_trials
的結構化內容向量化，供 Consult 模組搜尋使用。

使用方式：
  python crawlers/build_knowledge_index.py              # 全量建構
  python crawlers/build_knowledge_index.py --incremental # 增量更新（只處理新文件）
  python crawlers/build_knowledge_index.py --dry-run     # 預覽，不寫入
"""

import argparse
import json
import logging
import os
import pickle
import time
from datetime import datetime, timezone

import numpy as np

from crawler_utils import db, gemini_client, gemini_types

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================
# 設定
# ============================================================

KB_INDEX_FILE = "knowledge_base.index"
KB_DATA_FILE = "knowledge_base_data.pkl"
EMBEDDING_DIM = 768
BATCH_SIZE = 20

# ============================================================
# Firebase Storage
# ============================================================

try:
    from firebase_admin import storage
    bucket = storage.bucket()
except Exception:
    bucket = None
    logger.warning("Firebase Storage 未設定，將只存本地檔案")


# ============================================================
# Embedding 函式（與 local_pdf_processor.py 相同模式）
# ============================================================

def get_embedding(text):
    try:
        result = gemini_client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config=gemini_types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
        )
        if hasattr(result, "embeddings") and result.embeddings:
            return result.embeddings[0].values
        return None
    except Exception as e:
        logger.warning("Embedding 失敗: %s", e)
        return None


def get_embeddings_batch(texts, batch_size=BATCH_SIZE):
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        try:
            result = gemini_client.models.embed_content(
                model="gemini-embedding-001",
                contents=batch,
                config=gemini_types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
            )
            if hasattr(result, "embeddings") and result.embeddings:
                for emb in result.embeddings:
                    all_embeddings.append(emb.values)
        except Exception as e:
            logger.warning("Batch embedding 失敗，逐筆重試: %s", e)
            for text in batch:
                v = get_embedding(text)
                if v:
                    all_embeddings.append(v)
                else:
                    all_embeddings.append([0.0] * EMBEDDING_DIM)
        time.sleep(0.05)
    return all_embeddings


# ============================================================
# 從 Firestore 讀取資料
# ============================================================

def compose_article_text(doc: dict) -> str:
    """組合 articles_v2 的 embedding 文字"""
    parts = [doc.get("title", "")]
    takeaways = doc.get("clinical_takeaways", [])
    if takeaways:
        parts.append(" ".join(takeaways))
    pico = doc.get("pico", {})
    if pico:
        pico_text = f"P: {pico.get('P', '')} I: {pico.get('I', '')} C: {pico.get('C', '')} O: {pico.get('O', '')}"
        parts.append(pico_text)
    return "\n".join(parts)


def compose_guideline_text(doc: dict) -> str:
    """組合 guideline_chapters 的 embedding 文字"""
    parts = [
        doc.get("guideline_title", ""),
        doc.get("chapter_title", ""),
        doc.get("chapter_title_zh", ""),
    ]
    recs = doc.get("key_recommendations", [])
    if recs:
        for r in recs[:10]:
            if isinstance(r, dict):
                parts.append(f"{r.get('grade', '')} {r.get('text', '')}")
            elif isinstance(r, str):
                parts.append(r)
    return "\n".join(p for p in parts if p)


def compose_trial_text(doc: dict) -> str:
    """組合 clinical_trials 的 embedding 文字"""
    parts = [doc.get("title", "")]
    if doc.get("summary_zh"):
        parts.append(doc["summary_zh"])
    if doc.get("conditions"):
        parts.append("Conditions: " + ", ".join(doc["conditions"]))
    interventions = doc.get("interventions", [])
    if interventions:
        iv_names = [iv.get("name", "") for iv in interventions if isinstance(iv, dict)]
        if iv_names:
            parts.append("Interventions: " + ", ".join(iv_names))
    return "\n".join(p for p in parts if p)


def fetch_articles(since_timestamp=None) -> list:
    """讀取 articles_v2"""
    q = db.collection("articles_v2").where("process_status", "==", "completed")
    if since_timestamp:
        q = q.where("created_at", ">", since_timestamp)
    docs = list(q.stream())
    results = []
    for doc in docs:
        data = doc.to_dict()
        text = compose_article_text(data)
        if len(text) > 20:
            results.append({
                "doc_id": doc.id,
                "doc_type": "article",
                "text": text,
            })
    return results


def fetch_guideline_chapters(since_timestamp=None) -> list:
    """讀取 guideline_chapters"""
    q = db.collection("guideline_chapters").where("processing_status", "==", "ready")
    if since_timestamp:
        q = q.where("created_at", ">", since_timestamp)
    docs = list(q.stream())
    results = []
    for doc in docs:
        data = doc.to_dict()
        text = compose_guideline_text(data)
        if len(text) > 20:
            results.append({
                "doc_id": doc.id,
                "doc_type": "guideline",
                "text": text,
            })
    return results


def fetch_clinical_trials(since_timestamp=None) -> list:
    """讀取 clinical_trials"""
    q = db.collection("clinical_trials")
    if since_timestamp:
        q = q.where("created_at", ">", since_timestamp)
    docs = list(q.stream())
    results = []
    for doc in docs:
        data = doc.to_dict()
        text = compose_trial_text(data)
        if len(text) > 20:
            results.append({
                "doc_id": doc.id,
                "doc_type": "trial",
                "text": text,
            })
    return results


# ============================================================
# 索引建構
# ============================================================

def build_index(items: list, dry_run: bool = False) -> tuple:
    """建構 FAISS 索引，回傳 (index, metadata_dict)"""
    import faiss

    if not items:
        logger.warning("沒有資料可建構索引")
        return None, None

    texts = [item["text"] for item in items]
    doc_ids = [item["doc_id"] for item in items]
    doc_types = [item["doc_type"] for item in items]

    logger.info("開始 embedding %d 筆文件...", len(texts))

    if dry_run:
        logger.info("[DRY RUN] 會 embed %d 筆，跳過實際 embedding", len(texts))
        return None, None

    embeddings = get_embeddings_batch(texts, batch_size=BATCH_SIZE)

    if len(embeddings) != len(texts):
        logger.error("Embedding 數量不符: %d vs %d", len(embeddings), len(texts))
        return None, None

    emb_np = np.array(embeddings).astype("float32")
    logger.info("Embedding 完成: shape=%s", emb_np.shape)

    index = faiss.IndexFlatL2(EMBEDDING_DIM)
    index.add(emb_np)
    logger.info("FAISS 索引建構完成: %d vectors", index.ntotal)

    # 統計
    type_counts = {}
    for dt in doc_types:
        type_counts[dt] = type_counts.get(dt, 0) + 1

    metadata = {
        "doc_ids": doc_ids,
        "doc_types": doc_types,
        "build_timestamp": datetime.now(timezone.utc).isoformat(),
        "counts": type_counts,
    }

    return index, metadata


def save_index(index, metadata, upload: bool = True):
    """儲存索引到本地 + 上傳 Firebase Storage"""
    import faiss

    faiss.write_index(index, KB_INDEX_FILE)
    with open(KB_DATA_FILE, "wb") as f:
        pickle.dump(metadata, f)
    logger.info("本地儲存完成: %s + %s", KB_INDEX_FILE, KB_DATA_FILE)

    if upload and bucket:
        try:
            blob_idx = bucket.blob(f"brain_memory/{KB_INDEX_FILE}")
            blob_idx.upload_from_filename(KB_INDEX_FILE)
            blob_data = bucket.blob(f"brain_memory/{KB_DATA_FILE}")
            blob_data.upload_from_filename(KB_DATA_FILE)
            logger.info("已上傳到 Firebase Storage: brain_memory/")
        except Exception as e:
            logger.error("上傳失敗: %s", e)
    elif not bucket:
        logger.warning("Firebase Storage 未設定，跳過上傳")


def load_existing_metadata() -> dict | None:
    """載入現有的 metadata（用於 incremental mode）"""
    if bucket:
        try:
            blob = bucket.blob(f"brain_memory/{KB_DATA_FILE}")
            if blob.exists():
                blob.download_to_filename(KB_DATA_FILE)
        except Exception:
            pass
    if os.path.exists(KB_DATA_FILE):
        with open(KB_DATA_FILE, "rb") as f:
            return pickle.load(f)
    return None


# ============================================================
# 主程式
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="建構 Nephro Brain 知識庫 FAISS 索引")
    parser.add_argument("--dry-run", action="store_true", help="預覽模式，不實際 embed/寫入")
    parser.add_argument("--incremental", action="store_true", help="增量模式，只處理新文件")
    args = parser.parse_args()

    since_timestamp = None
    if args.incremental:
        existing = load_existing_metadata()
        if existing and existing.get("build_timestamp"):
            ts = existing["build_timestamp"]
            logger.info("增量模式：只處理 %s 之後的文件", ts)
            since_timestamp = datetime.fromisoformat(ts)
        else:
            logger.info("找不到現有索引，改為全量建構")

    # 讀取資料
    logger.info("=== 讀取 Firestore 資料 ===")
    articles = fetch_articles(since_timestamp)
    logger.info("articles_v2: %d 筆", len(articles))

    chapters = fetch_guideline_chapters(since_timestamp)
    logger.info("guideline_chapters: %d 筆", len(chapters))

    trials = fetch_clinical_trials(since_timestamp)
    logger.info("clinical_trials: %d 筆", len(trials))

    all_items = articles + chapters + trials
    logger.info("合計: %d 筆待處理", len(all_items))

    if not all_items:
        logger.info("沒有新資料需要處理")
        return

    if args.incremental and since_timestamp:
        # 增量模式：載入現有索引，append 新資料
        import faiss

        existing = load_existing_metadata()
        existing_index_path = KB_INDEX_FILE
        if bucket:
            try:
                blob = bucket.blob(f"brain_memory/{KB_INDEX_FILE}")
                if blob.exists():
                    blob.download_to_filename(KB_INDEX_FILE)
            except Exception:
                pass

        if os.path.exists(existing_index_path) and existing:
            logger.info("載入現有索引 (%d vectors)，append %d 筆新資料",
                        len(existing.get("doc_ids", [])), len(all_items))
            old_index = faiss.read_index(existing_index_path)

            if args.dry_run:
                logger.info("[DRY RUN] 會 append %d 筆到現有索引", len(all_items))
                return

            texts = [item["text"] for item in all_items]
            embeddings = get_embeddings_batch(texts)
            if len(embeddings) == len(texts):
                emb_np = np.array(embeddings).astype("float32")
                old_index.add(emb_np)

                new_metadata = {
                    "doc_ids": existing["doc_ids"] + [item["doc_id"] for item in all_items],
                    "doc_types": existing["doc_types"] + [item["doc_type"] for item in all_items],
                    "build_timestamp": datetime.now(timezone.utc).isoformat(),
                    "counts": {},
                }
                for dt in new_metadata["doc_types"]:
                    new_metadata["counts"][dt] = new_metadata["counts"].get(dt, 0) + 1

                save_index(old_index, new_metadata)
                logger.info("增量更新完成: 索引現有 %d vectors", old_index.ntotal)
            return
        else:
            logger.info("現有索引不存在，改為全量建構")

    # 全量建構
    index, metadata = build_index(all_items, dry_run=args.dry_run)

    if index and metadata and not args.dry_run:
        save_index(index, metadata)
        logger.info("=== 建構完成 ===")
        for dtype, count in metadata["counts"].items():
            logger.info("  %s: %d 筆", dtype, count)


if __name__ == "__main__":
    main()
