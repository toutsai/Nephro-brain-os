#!/usr/bin/env python3
"""
本地 PDF 處理器 (方案 A + C 優化版)
- 運行於本地電腦
- 解析 PDF -> 向量化 (FAISS) -> 文字上傳 Firestore (減少 RAM 消耗) -> 索引上傳 Storage
"""

import firebase_admin
from firebase_admin import credentials, firestore, storage
from google import genai
from google.genai import types
import faiss
import numpy as np
import pypdf
import fitz  # PyMuPDF
import requests
import base64
import os
import time
import tempfile
import pickle
import gc
import argparse
from dotenv import load_dotenv

# --- 設定 ---
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise EnvironmentError("請在 .env 中設定 GOOGLE_API_KEY")

# Firebase 初始化
if not firebase_admin._apps:
    firebase_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if firebase_json and firebase_json.strip().startswith("{"):
        import json
        cred = credentials.Certificate(json.loads(firebase_json))
    else:
        cred_path = firebase_json or "serviceAccountKey.json"
        if not os.path.exists(cred_path):
            raise FileNotFoundError(f"找不到 Firebase 憑證：{cred_path}")
        cred = credentials.Certificate(cred_path)

    storage_bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
    if storage_bucket:
        firebase_admin.initialize_app(cred, {'storageBucket': storage_bucket})
    else:
        firebase_admin.initialize_app(cred)

db = firestore.client()
storage_bucket_obj = storage.bucket()

gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
GEMINI_MODEL = "gemini-2.5-flash"

# 本地設定
PAGES_PER_BATCH = 100
DEEP_PAGES_PER_BATCH = 30
INDEX_FILE = "nephro_brain.index"
DATA_FILE = "nephro_data.pkl"

# 全域變數
index = None
stored_chunks = [] # 這裡現在只會存 Firestore ID (字串)，不存全文
processed_books = set()
deep_processed_books = set()

def get_embedding(text):
    try:
        result = gemini_client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        # 新版 SDK 返回 EmbedContentResponse 對象
        if hasattr(result, 'embeddings') and result.embeddings:
            return result.embeddings[0].values
        return None
    except Exception as e:
        print(f"⚠️ Embedding Error: {e}")
        return None

def get_embeddings_batch(texts, batch_size=20):
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        try:
            result = gemini_client.models.embed_content(
                model="gemini-embedding-001",
                contents=batch,
                config=types.EmbedContentConfig(output_dimensionality=768)
            )
            # 新版 SDK 返回 EmbedContentResponse 對象
            if hasattr(result, 'embeddings') and result.embeddings:
                for emb in result.embeddings:
                    all_embeddings.append(emb.values)
        except Exception as e:
            print(f"⚠️ Batch Error: {e}")
            for text in batch:
                v = get_embedding(text)
                if v:
                    all_embeddings.append(v)
        time.sleep(0.05)
    return all_embeddings

def download_memory():
    """從 Firebase Storage 下載記憶檔案"""
    global index, stored_chunks, processed_books, deep_processed_books

    try:
        print("☁️ 從 Firebase Storage 下載記憶...")

        blob_index = storage_bucket_obj.blob(f"brain_memory/{INDEX_FILE}")
        if blob_index.exists():
            blob_index.download_to_filename(INDEX_FILE)

        blob_data = storage_bucket_obj.blob(f"brain_memory/{DATA_FILE}")
        if blob_data.exists():
            blob_data.download_to_filename(DATA_FILE)

        if os.path.exists(INDEX_FILE) and os.path.exists(DATA_FILE):
            try:
                index = faiss.read_index(INDEX_FILE)
                with open(DATA_FILE, "rb") as f:
                    data = pickle.load(f)
                    stored_chunks = data.get("chunks", [])
                    processed_books = data.get("books", set())
                    deep_processed_books = data.get("deep_books", set())
                print(f"✅ 記憶載入！{len(stored_chunks)} chunks, {len(processed_books)} 本書")
                
                # 檢查舊格式兼容性 (如果 stored_chunks 裡存的是 dict，轉換為警告)
                if len(stored_chunks) > 0 and isinstance(stored_chunks[0], dict):
                    print("⚠️ 警告：檢測到舊版記憶格式 (含全文)。建議重新建立索引以節省空間。")
                    
                return True
            except Exception as e:
                print(f"⚠️ 讀取本地記憶檔案失敗 (可能格式不符): {e}")
                # 如果讀取失敗，重置
                index = None
                stored_chunks = []
                processed_books = set()
                deep_processed_books = set()
                return False
    except Exception as e:
        print(f"⚠️ 下載記憶失敗: {e}")
    return False

def upload_memory():
    """上傳記憶檔案到 Firebase Storage"""
    global index, stored_chunks, processed_books, deep_processed_books

    try:
        if index is not None:
            faiss.write_index(index, INDEX_FILE)
            with open(DATA_FILE, "wb") as f:
                pickle.dump({
                    "chunks": stored_chunks, # 這裡現在只存 ID 列表
                    "books": processed_books,
                    "deep_books": deep_processed_books
                }, f)

            blob_index = storage_bucket_obj.blob(f"brain_memory/{INDEX_FILE}")
            blob_index.upload_from_filename(INDEX_FILE)

            blob_data = storage_bucket_obj.blob(f"brain_memory/{DATA_FILE}")
            blob_data.upload_from_filename(DATA_FILE)

            print(f"☁️ 記憶已上傳至 Firebase Storage (優化版)")
            return True
    except Exception as e:
        print(f"❌ 上傳記憶失敗: {e}")
    return False

# 🔥 新增功能：將文字片段上傳到 Firestore
def upload_chunks_to_firestore(chunks):
    """
    將文字片段上傳到 Firestore 'knowledge_chunks' 集合
    回傳：上傳後的 Document ID 列表
    """
    batch = db.batch()
    ids = []
    count = 0
    
    print(f"      ☁️ 正在將 {len(chunks)} 個片段上傳至 Firestore...")
    
    for chunk in chunks:
        doc_ref = db.collection("knowledge_chunks").document()
        batch.set(doc_ref, chunk) # 寫入 text, source, book_id
        ids.append(doc_ref.id)
        count += 1
        
        # Firestore batch 限制為 500
        if count >= 400:
            batch.commit()
            batch = db.batch()
            count = 0
            print("         ...已上傳 400 筆")
            
    if count > 0:
        batch.commit()
    
    print(f"      ✅ Firestore 上傳完成")
    return ids

def process_pdf(doc_id, title, url, deep_read=False):
    """處理單一 PDF"""
    global index, stored_chunks, processed_books, deep_processed_books

    print(f"\n{'='*60}")
    print(f"📘 處理: {title}")
    print(f"{'='*60}")

    temp_path = None

    try:
        # 更新狀態
        db.collection("books").document(doc_id).update({"status": "processing"})

        # 下載 PDF
        print(f"⬇️ 下載中...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf:
            with requests.get(url, stream=True, timeout=300) as response:
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        tf.write(chunk)
            temp_path = tf.name
        print(f"✅ 下載完成")

        if deep_read:
            process_deep_read(doc_id, title, temp_path)
        else:
            process_quick_read(doc_id, title, temp_path)

    except Exception as e:
        print(f"❌ 處理失敗: {e}")
        db.collection("books").document(doc_id).update({
            "status": "error",
            "reason": str(e)[:200]
        })
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        gc.collect()

def process_quick_read(doc_id, title, temp_path):
    """快速閱讀 - 文字擷取 (優化版：存 Firestore)"""
    global index, stored_chunks, processed_books

    reader = pypdf.PdfReader(temp_path, strict=False)
    total_pages = len(reader.pages)
    print(f"📖 共 {total_pages} 頁")

    num_batches = (total_pages + PAGES_PER_BATCH - 1) // PAGES_PER_BATCH
    total_chunks = 0

    for batch_idx in range(num_batches):
        start_page = batch_idx * PAGES_PER_BATCH
        end_page = min((batch_idx + 1) * PAGES_PER_BATCH, total_pages)

        print(f"\n   📄 批次 {batch_idx + 1}/{num_batches} (頁 {start_page + 1}-{end_page})")

        # 讀取頁面
        text_parts = []
        for i in range(start_page, end_page):
            try:
                page = reader.pages[i]
                t = page.extract_text()
                if t:
                    text_parts.append(t)
            except:
                pass

        text = "\n".join(text_parts)
        del text_parts

        # 分段
        chunks = []
        chunk_size = 1000
        start = 0
        while start < len(text):
            chunk = text[start:start + chunk_size]
            chunks.append({
                "text": chunk,
                "source": f"教科書: {title} (頁 {start_page+1}-{end_page})",
                "book_id": doc_id,
                "created_at": firestore.SERVER_TIMESTAMP
            })
            start += 900
        del text

        if chunks:
            # 向量化
            print(f"      🧠 向量化 {len(chunks)} 片段...")
            texts = [c['text'] for c in chunks]
            embeddings = get_embeddings_batch(texts, batch_size=20)

            if embeddings and len(embeddings) == len(chunks):
                emb_np = np.array(embeddings).astype('float32')

                # 1. 上傳文字到 Firestore
                chunk_ids = upload_chunks_to_firestore(chunks)

                # 2. 更新本地 Index (FAISS)
                if index is None:
                    index = faiss.IndexFlatL2(emb_np.shape[1])
                index.add(emb_np)
                
                # 3. 本地只存 ID
                stored_chunks.extend(chunk_ids)

                total_chunks += len(chunks)
                del emb_np, embeddings

            del chunks, texts

        # 每批完成後上傳記憶
        upload_memory()
        gc.collect()

    # 完成
    del reader
    processed_books.add(doc_id)
    upload_memory()

    db.collection("books").document(doc_id).update({
        "status": "ready",
        "total_pages": total_pages
    })

    print(f"\n✅ {title} 處理完畢！共 {total_chunks} 片段")

def process_deep_read(doc_id, title, temp_path):
    """深度閱讀 - Gemini Vision (優化版：存 Firestore)"""
    global index, stored_chunks, deep_processed_books

    # 使用全域的 gemini_client

    pdf_doc = fitz.open(temp_path)
    total_pages = len(pdf_doc)
    print(f"📖 共 {total_pages} 頁 (深度閱讀)")

    num_batches = (total_pages + DEEP_PAGES_PER_BATCH - 1) // DEEP_PAGES_PER_BATCH
    total_chunks = 0

    for batch_idx in range(num_batches):
        start_page = batch_idx * DEEP_PAGES_PER_BATCH
        end_page = min((batch_idx + 1) * DEEP_PAGES_PER_BATCH, total_pages)

        print(f"\n   📄 批次 {batch_idx + 1}/{num_batches} (頁 {start_page + 1}-{end_page})")

        chunks = []
        for i in range(start_page, end_page):
            try:
                page = pdf_doc[i]
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                img_bytes = pix.tobytes("png")
                del pix

                prompt = """請詳細閱讀這一頁醫學教科書的內容... (同前)""" # 省略 prompt 以節省篇幅

                response = gemini_client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=[
                        prompt,
                        types.Part.from_bytes(data=img_bytes, mime_type="image/png")
                    ]
                )
                del img_bytes

                page_content = response.text if response.text else ""
                del response

                if page_content.strip():
                    chunks.append({
                        "text": page_content,
                        "source": f"教科書(深度): {title} - 第{i+1}頁",
                        "book_id": doc_id,
                        "created_at": firestore.SERVER_TIMESTAMP
                    })
                    print(f"      ✓ 頁 {i+1}")

                time.sleep(0.5)

            except Exception as e:
                print(f"      ⚠️ 頁 {i+1} 失敗: {e}")

        if chunks:
            print(f"      🧠 向量化 {len(chunks)} 片段...")
            texts = [c['text'][:2000] for c in chunks]
            embeddings = get_embeddings_batch(texts, batch_size=10)

            if embeddings and len(embeddings) == len(chunks):
                emb_np = np.array(embeddings).astype('float32')

                # 1. 上傳 Firestore
                chunk_ids = upload_chunks_to_firestore(chunks)

                # 2. 更新 Index
                if index is None:
                    index = faiss.IndexFlatL2(emb_np.shape[1])
                index.add(emb_np)
                
                # 3. 存 ID
                stored_chunks.extend(chunk_ids)

                total_chunks += len(chunks)
                del emb_np, embeddings

            del chunks, texts

        upload_memory()
        gc.collect()

    pdf_doc.close()
    deep_processed_books.add(doc_id)
    upload_memory()

    db.collection("books").document(doc_id).update({
        "status": "ready",
        "total_pages": total_pages,
        "deep_read": True
    })

    print(f"\n✅ {title} 深度閱讀完畢！共 {total_chunks} 片段")

def main():
    parser = argparse.ArgumentParser(description='本地 PDF 處理器')
    parser.add_argument('--deep', action='store_true', help='使用深度閱讀模式')
    parser.add_argument('--book-id', type=str, help='處理特定書籍 ID')
    parser.add_argument('--all', action='store_true', help='處理所有書籍（包括已處理的）')
    parser.add_argument('--reset', action='store_true', help='⚠️ 重置所有記憶 (清除 Index 和 stored_chunks)')
    args = parser.parse_args()

    print("="*60)
    print("🏠 本地 PDF 處理器 (方案 A+C: Firestore 儲存版)")
    print("="*60)

    # 邏輯修正：如果是重置模式，就不下載舊記憶
    if args.reset:
        print("⚠️ 正在重置本地記憶檔案...")
        if os.path.exists(INDEX_FILE): os.remove(INDEX_FILE)
        if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
        print("✅ 已刪除本地檔案。")
        print("🚫 跳過雲端下載，準備建立全新索引...")
        # 這裡不呼叫 download_memory()，讓變數保持為空
    else:
        # 正常模式才下載
        download_memory()

    if args.book_id:
        doc = db.collection("books").document(args.book_id).get()
        if doc.exists:
            data = doc.to_dict()
            process_pdf(doc.id, data.get('title', 'Unknown'), data.get('url'), args.deep)
        else:
            print(f"❌ 找不到書籍 ID: {args.book_id}")
    else:
        books = db.collection("books").stream()
        pending_books = []
        for doc in books:
            data = doc.to_dict()
            status = data.get("status", "")
            
            # 如果是 reset 模式，我們要重新處理所有 'ready' 的書，因為舊的索引被我們丟掉了
            # 或者您可以手動指定要處理哪些狀態
            target_statuses = ["pending", "processing", "needs_upgrade", "error", "partial"]
            if args.reset: 
                target_statuses.append("ready") # 重置時，連已完成的都要重做索引

            if args.all or status in target_statuses:
                pending_books.append({
                    "id": doc.id,
                    "title": data.get("title", "Unknown"),
                    "url": data.get("url"),
                    "status": status,
                    "size_mb": data.get("file_size_mb", 0)
                })

        if not pending_books:
            print("\n✅ 沒有需要處理的書籍！")
            return

        print(f"\n📚 找到 {len(pending_books)} 本書籍 (將重新建立索引):")
        for i, book in enumerate(pending_books):
            size_info = f" ({book['size_mb']}MB)" if book['size_mb'] else ""
            print(f"   {i+1}. [{book['status']}] {book['title']}{size_info}")

        print(f"\n開始處理...")
        for book in pending_books:
            process_pdf(book['id'], book['title'], book['url'], args.deep)

    print("\n" + "="*60)
    print("🎉 全部完成！")
    print(f"   總 chunks: {len(stored_chunks)} (ID 列表)")
    print(f"   快速閱讀: {len(processed_books)} 本")
    print(f"   深度閱讀: {len(deep_processed_books)} 本")
    print("="*60)

if __name__ == "__main__":
    main()