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
import re
import json
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
deleted_chunks = set()  # 已刪除的 chunk IDs（版本替換時標記，搜尋時跳過）


# --- Guideline helpers ---

def derive_guideline_id(title):
    """'KDIGO AKI 2024' -> 'KDIGO-AKI-2024'"""
    gid = re.sub(r'[\s_]+', '-', title.strip())
    gid = re.sub(r'[^A-Za-z0-9\-\u4e00-\u9fff]', '', gid)
    return gid

def extract_version(title):
    """從 title 提取版本號或年份"""
    match = re.search(r'v(\d+\.?\d*)', title, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r'(20\d{2})', title)
    if match:
        return match.group(1)
    return "1.0"

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
    global index, stored_chunks, processed_books, deep_processed_books, deleted_chunks

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
                    deleted_chunks = data.get("deleted_chunks", set())
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
                deleted_chunks = set()
                return False
    except Exception as e:
        print(f"⚠️ 下載記憶失敗: {e}")
    return False

def upload_memory(local_only=False):
    """上傳記憶檔案到 Firebase Storage（含重試機制）"""
    global index, stored_chunks, processed_books, deep_processed_books, deleted_chunks

    try:
        if index is not None:
            faiss.write_index(index, INDEX_FILE)
            with open(DATA_FILE, "wb") as f:
                pickle.dump({
                    "chunks": stored_chunks,
                    "books": processed_books,
                    "deep_books": deep_processed_books,
                    "deleted_chunks": deleted_chunks
                }, f)

            if local_only:
                return True

            # 上傳至 Firebase Storage，含重試機制
            MAX_RETRIES = 3
            for attempt in range(MAX_RETRIES):
                try:
                    blob_index = storage_bucket_obj.blob(f"brain_memory/{INDEX_FILE}")
                    blob_index.upload_from_filename(INDEX_FILE, timeout=300)

                    blob_data = storage_bucket_obj.blob(f"brain_memory/{DATA_FILE}")
                    blob_data.upload_from_filename(DATA_FILE, timeout=300)

                    print(f"☁️ 記憶已上傳至 Firebase Storage (優化版)")
                    return True
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        wait = 2 ** (attempt + 1)
                        print(f"⚠️ 上傳記憶失敗 (第 {attempt+1} 次)，{wait}s 後重試: {e}")
                        time.sleep(wait)
                    else:
                        print(f"❌ 上傳記憶失敗 (已重試 {MAX_RETRIES} 次): {e}")
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

def process_pdf(doc_id, title, url, deep_read=False, guideline_mode=False):
    """處理單一 PDF"""
    global index, stored_chunks, processed_books, deep_processed_books

    print(f"\n{'='*60}")
    mode_label = "📋 指引" if guideline_mode else "📘 教科書"
    print(f"{mode_label} 處理: {title}")
    print(f"{'='*60}")

    temp_path = None

    try:
        # 更新狀態
        db.collection("books").document(doc_id).update({"status": "processing"})

        # 如果是 guideline 模式，補上 guideline 欄位
        if guideline_mode:
            gid = derive_guideline_id(title)
            ver = extract_version(title)
            db.collection("books").document(doc_id).update({
                "type": "guideline",
                "guideline_id": gid,
                "version": ver
            })
            print(f"   guideline_id: {gid}, version: {ver}")

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

        if guideline_mode:
            process_guideline(doc_id, title, temp_path)
        elif deep_read:
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

        # 每批先存本地，避免頻繁上傳大檔案超時
        upload_memory(local_only=True)
        gc.collect()

    # 完成後才上傳雲端
    del reader
    processed_books.add(doc_id)
    upload_memory()

    db.collection("books").document(doc_id).update({
        "status": "ready",
        "total_pages": total_pages
    })

    print(f"\n✅ {title} 處理完畢！共 {total_chunks} 片段")

# ============================================================
# Guideline 智慧切片功能
# ============================================================

def extract_toc_from_pdf(temp_path):
    """用 PyMuPDF 提取 PDF 內建目錄，回傳 [(level, title, page), ...] 或 None"""
    try:
        doc = fitz.open(temp_path)
        toc = doc.get_toc()  # [[level, title, page], ...]
        doc.close()
        if toc and len(toc) >= 3:
            return [(entry[0], entry[1], entry[2]) for entry in toc]
    except Exception as e:
        print(f"⚠️ PDF ToC 提取失敗: {e}")
    return None

def extract_toc_via_gemini(temp_path):
    """用 Gemini Vision 分析前幾頁，提取章節結構 JSON"""
    try:
        doc = fitz.open(temp_path)
        pages_to_send = min(8, len(doc))

        image_parts = []
        for i in range(pages_to_send):
            pix = doc[i].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            img_bytes = pix.tobytes("png")
            image_parts.append(
                types.Part.from_bytes(data=img_bytes, mime_type="image/png")
            )
            del pix
        doc.close()

        prompt = """Analyze these pages from a medical guideline PDF.
Extract the chapter/section structure (table of contents).
Return ONLY a JSON array, each element: {"level": 1, "title": "Chapter name", "page": 5}
- level 1 = main chapter, level 2 = sub-section, level 3 = sub-sub-section
- "page" is the PDF page number (1-indexed)
- Include ALL chapters and major sections you can identify
- Keep titles in their original language
- If you see a table of contents page, use it. Otherwise infer from headings.
Return ONLY the JSON array, no markdown fences."""

        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[prompt] + image_parts
        )
        text = response.text.strip()
        # 清理 markdown code fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3].strip()
        entries = json.loads(text)
        result = [(e["level"], e["title"], e["page"]) for e in entries]
        print(f"   Gemini 提取到 {len(result)} 個章節")
        return result
    except Exception as e:
        print(f"⚠️ Gemini ToC 提取失敗: {e}")
        return None

def split_by_chapters(temp_path, toc_entries):
    """根據 ToC 頁碼範圍切割 PDF 文字，回傳 [(chapter_name, text), ...]"""
    reader = pypdf.PdfReader(temp_path, strict=False)
    total_pages = len(reader.pages)

    # 只取 level 1-2 的章節做切割點；若太少則逐步放寬
    main_entries = [(lvl, title, page) for lvl, title, page in toc_entries if lvl <= 2]
    if len(main_entries) < 3:
        main_entries = [(lvl, title, page) for lvl, title, page in toc_entries if lvl <= 3]
    if len(main_entries) < 3:
        main_entries = toc_entries[:]  # 全部使用

    main_entries.sort(key=lambda x: x[2])

    chapters = []
    for i, (level, title, start_page) in enumerate(main_entries):
        # 決定結束頁碼
        if i + 1 < len(main_entries):
            end_page = main_entries[i + 1][2] - 1
        else:
            end_page = total_pages

        # ToC 頁碼是 1-indexed，reader 是 0-indexed
        sp = max(0, start_page - 1)
        ep = min(total_pages, end_page)

        text_parts = []
        for p in range(sp, ep):
            try:
                t = reader.pages[p].extract_text()
                if t:
                    text_parts.append(t)
            except:
                pass

        full_text = "\n".join(text_parts)
        if full_text.strip():
            chapters.append((title, full_text))

    return chapters

def process_guideline(doc_id, title, temp_path):
    """指引智慧切片 - 按章節切割"""
    global index, stored_chunks, processed_books

    print(f"📋 指引模式: {title}")

    # Step 1: 提取目錄
    toc = extract_toc_from_pdf(temp_path)
    if toc is None:
        print("   PDF 無內建目錄，嘗試 Gemini 分析...")
        toc = extract_toc_via_gemini(temp_path)

    if toc is None:
        print("   ⚠️ 無法提取章節結構，退回固定切片模式")
        process_quick_read(doc_id, title, temp_path)
        return

    print(f"   找到 {len(toc)} 個目錄項目")

    # Step 2: 按章節切割文字
    chapters = split_by_chapters(temp_path, toc)
    if not chapters:
        print("   ⚠️ 無法提取章節內容，退回固定切片模式")
        process_quick_read(doc_id, title, temp_path)
        return

    print(f"   切割出 {len(chapters)} 個章節")

    # Step 3: 建立 chunks
    total_chunks_count = 0
    MAX_CHUNK_SIZE = 3000
    SUB_CHUNK_SIZE = 1500
    SUB_OVERLAP = 200

    for chapter_name, chapter_text in chapters:
        source_label = f"{title} - {chapter_name}"
        chunks = []

        if len(chapter_text) <= MAX_CHUNK_SIZE:
            chunks.append({
                "text": chapter_text,
                "source": source_label,
                "book_id": doc_id,
                "created_at": firestore.SERVER_TIMESTAMP
            })
        else:
            # 長章節子切割
            start = 0
            part = 1
            while start < len(chapter_text):
                sub_text = chapter_text[start:start + SUB_CHUNK_SIZE]
                chunks.append({
                    "text": sub_text,
                    "source": f"{source_label} (Part {part})",
                    "book_id": doc_id,
                    "created_at": firestore.SERVER_TIMESTAMP
                })
                start += SUB_CHUNK_SIZE - SUB_OVERLAP
                part += 1

        if chunks:
            print(f"      🧠 {chapter_name}: {len(chunks)} 片段")
            texts = [c['text'][:2000] for c in chunks]
            embeddings = get_embeddings_batch(texts, batch_size=20)

            if embeddings and len(embeddings) == len(chunks):
                emb_np = np.array(embeddings).astype('float32')
                chunk_ids = upload_chunks_to_firestore(chunks)

                if index is None:
                    index = faiss.IndexFlatL2(emb_np.shape[1])
                index.add(emb_np)
                stored_chunks.extend(chunk_ids)
                total_chunks_count += len(chunks)
                del emb_np, embeddings

            del chunks, texts

        # 每章只存本地，避免大檔案頻繁上傳 Storage 超時
        upload_memory(local_only=True)
        gc.collect()

    reader = pypdf.PdfReader(temp_path, strict=False)
    processed_books.add(doc_id)
    # 整本處理完畢才上傳雲端
    upload_memory()

    db.collection("books").document(doc_id).update({
        "status": "ready",
        "total_pages": len(reader.pages),
    })

    print(f"\n✅ {title} 指引處理完畢！共 {total_chunks_count} 片段")

def replace_guideline(guideline_id):
    """替換舊版指引：刪除舊 chunks，處理新版"""
    global deleted_chunks

    # 1. 找到同 guideline_id 的所有 books（可能有舊版和新版 pending）
    query = db.collection("books").where("guideline_id", "==", guideline_id)
    docs = list(query.stream())

    if not docs:
        print(f"❌ 找不到 guideline_id: {guideline_id}")
        return

    # 分出 ready（舊版）和 pending（新版）
    old_docs = [d for d in docs if d.to_dict().get("status") == "ready"]
    new_docs = [d for d in docs if d.to_dict().get("status") in ("pending", "processing")]

    if not new_docs:
        print(f"❌ 沒有 pending 的新版指引。請先上傳新版 PDF。")
        return

    # 2. 刪除舊版 chunks
    for old_doc in old_docs:
        old_doc_id = old_doc.id
        old_data = old_doc.to_dict()
        print(f"🗑️ 刪除舊版: {old_data.get('title', '?')} v{old_data.get('version', '?')}")

        old_chunks_query = db.collection("knowledge_chunks").where("book_id", "==", old_doc_id)
        old_chunk_docs = list(old_chunks_query.stream())

        batch = db.batch()
        count = 0
        for chunk_doc in old_chunk_docs:
            deleted_chunks.add(chunk_doc.id)
            batch.delete(chunk_doc.reference)
            count += 1
            if count >= 400:
                batch.commit()
                batch = db.batch()
                count = 0
        if count > 0:
            batch.commit()

        print(f"   已刪除 {len(old_chunk_docs)} 個 chunks")

        # 標記舊 book 為 replaced
        db.collection("books").document(old_doc_id).update({
            "status": "replaced",
            "replaced_at": firestore.SERVER_TIMESTAMP
        })

    upload_memory()

    # 3. 處理新版
    for new_doc in new_docs:
        new_data = new_doc.to_dict()
        print(f"\n📋 處理新版: {new_data.get('title', '?')}")
        process_pdf(new_doc.id, new_data.get('title', 'Unknown'),
                    new_data.get('url'), guideline_mode=True)


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

        upload_memory(local_only=True)
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
    parser.add_argument('--guideline', action='store_true', help='使用指引智慧章節切片模式')
    parser.add_argument('--replace', type=str, metavar='GUIDELINE_ID',
                        help='替換舊版指引 (例: --replace KDIGO-AKI-2024)')
    parser.add_argument('--migrate-types', action='store_true',
                        help='一次性為現有書籍補上 type 欄位')
    args = parser.parse_args()

    print("="*60)
    print("🏠 本地 PDF 處理器 (方案 A+C: Firestore 儲存版)")
    print("="*60)

    # --- migrate-types 一次性遷移 ---
    if args.migrate_types:
        print("🔄 為現有書籍補上 type 欄位...")
        books = db.collection("books").stream()
        count = 0
        for doc in books:
            data = doc.to_dict()
            if "type" not in data:
                doc.reference.update({"type": "textbook"})
                print(f"   ✅ {data.get('title', doc.id)} -> type: textbook")
                count += 1
        print(f"✅ 已遷移 {count} 本書")
        return

    # 邏輯修正：如果是重置模式，就不下載舊記憶
    if args.reset:
        print("⚠️ 正在重置本地記憶檔案...")
        if os.path.exists(INDEX_FILE): os.remove(INDEX_FILE)
        if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
        print("✅ 已刪除本地檔案。")
        print("🚫 跳過雲端下載，準備建立全新索引...")
    else:
        download_memory()

    # --- replace 版本替換 ---
    if args.replace:
        replace_guideline(args.replace)
        print("\n" + "="*60)
        print("🎉 版本替換完成！")
        print("="*60)
        return

    if args.book_id:
        doc = db.collection("books").document(args.book_id).get()
        if doc.exists:
            data = doc.to_dict()
            is_guideline = args.guideline or data.get('type') == 'guideline'
            process_pdf(doc.id, data.get('title', 'Unknown'), data.get('url'),
                        args.deep, guideline_mode=is_guideline)
        else:
            print(f"❌ 找不到書籍 ID: {args.book_id}")
    else:
        books = db.collection("books").stream()
        pending_books = []
        for doc in books:
            data = doc.to_dict()
            status = data.get("status", "")

            target_statuses = ["pending", "processing", "needs_upgrade", "error", "partial"]
            if args.reset:
                target_statuses.append("ready")

            if args.all or status in target_statuses:
                pending_books.append({
                    "id": doc.id,
                    "title": data.get("title", "Unknown"),
                    "url": data.get("url"),
                    "status": status,
                    "size_mb": data.get("file_size_mb", 0),
                    "type": data.get("type", "textbook")
                })

        if not pending_books:
            print("\n✅ 沒有需要處理的書籍！")
            return

        print(f"\n📚 找到 {len(pending_books)} 本書籍:")
        for i, book in enumerate(pending_books):
            size_info = f" ({book['size_mb']}MB)" if book['size_mb'] else ""
            type_info = f" [{book['type']}]" if book.get('type') else ""
            print(f"   {i+1}. [{book['status']}]{type_info} {book['title']}{size_info}")

        print(f"\n開始處理...")
        for book in pending_books:
            # 自動根據 type 欄位決定是否用 guideline 模式（命令列 --guideline 可覆蓋）
            is_guideline = args.guideline or book.get('type') == 'guideline'
            process_pdf(book['id'], book['title'], book['url'],
                        args.deep, guideline_mode=is_guideline)

    print("\n" + "="*60)
    print("🎉 全部完成！")
    print(f"   總 chunks: {len(stored_chunks)} (ID 列表)")
    print(f"   快速閱讀: {len(processed_books)} 本")
    print(f"   深度閱讀: {len(deep_processed_books)} 本")
    print("="*60)

if __name__ == "__main__":
    main()