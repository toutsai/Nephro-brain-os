"""
Knowledge Graph Concept Seeder — Nephro Brain OS
==================================================
從既有資料源（topic taxonomy、guideline chapters、drug database、
guideline key_topics）收集候選 concepts，再透過 Gemini 進行
去重、分群、產生 canonical concept nodes，寫入 Firestore kg_concepts。

使用方式：
  python crawlers/kg_build_concepts.py              # 全量建構
  python crawlers/kg_build_concepts.py --dry-run     # 預覽，不寫入 Firestore
  python crawlers/kg_build_concepts.py --limit 10    # 只處理前 10 個 concepts（測試用）
"""

import argparse
import json
import logging
import os
import re
import time
from datetime import datetime, timezone

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from crawler_utils import db, gemini_client, gemini_types, GEMINI_DELAY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================
# 常數
# ============================================================

TOPIC_TAXONOMY = [
    "ESRD/HD", "AKI", "CKD", "GN", "Transplant", "Electrolyte",
    "PD", "CKM", "HTN", "PKD", "CKD-MBD", "Stone", "Onco-Nephro",
]

GEMINI_MODEL = "gemini-2.5-flash"
BATCH_SIZE = 50
MAX_RETRIES = 3

# ============================================================
# 1. 收集候選 concepts
# ============================================================


def collect_topic_candidates() -> list[dict]:
    """13 個頂層 topic taxonomy concepts"""
    candidates = []
    for topic in TOPIC_TAXONOMY:
        candidates.append({
            "raw_title": topic,
            "source": "topic_taxonomy",
            "suggested_topics": [topic],
        })
    logger.info("Topic taxonomy: %d candidates", len(candidates))
    return candidates


def collect_guideline_chapter_candidates() -> list[dict]:
    """從 Firestore guideline_chapters 取得唯一 chapter_title"""
    candidates = []
    seen_titles = set()
    try:
        docs = db.collection("guideline_chapters").stream()
        for doc in docs:
            data = doc.to_dict()
            title = data.get("chapter_title", "").strip()
            if title and title not in seen_titles:
                seen_titles.add(title)
                # 嘗試推測所屬 topic
                topics = data.get("topics", [])
                candidates.append({
                    "raw_title": title,
                    "source": "guideline_chapter",
                    "suggested_topics": topics if topics else [],
                })
    except Exception as e:
        logger.error("讀取 guideline_chapters 失敗: %s", e)
    logger.info("Guideline chapters: %d unique candidates", len(candidates))
    return candidates


def collect_drug_candidates() -> list[dict]:
    """從 drug_database.json 取得 drug classes 和個別 drugs"""
    candidates = []
    drug_db_path = os.path.join(
        os.path.dirname(__file__), "..", "backend", "drug_database.json"
    )
    if not os.path.exists(drug_db_path):
        logger.warning("drug_database.json 不存在: %s", drug_db_path)
        return candidates

    with open(drug_db_path, "r", encoding="utf-8") as f:
        drug_data = json.load(f)

    # Collect unique drug classes
    seen_classes = set()
    for drug_key, drug_info in drug_data.items():
        class_en = drug_info.get("class_en", "").strip()
        if class_en and class_en not in seen_classes:
            seen_classes.add(class_en)
            candidates.append({
                "raw_title": class_en,
                "source": "drug_class",
                "suggested_topics": [],
            })

    # Collect individual drugs (all have clinical significance in nephrology)
    for drug_key, drug_info in drug_data.items():
        drug_name = drug_info.get("drug_name_en", "").strip()
        if drug_name:
            candidates.append({
                "raw_title": drug_name,
                "source": "drug",
                "suggested_topics": [],
            })

    logger.info(
        "Drug database: %d classes + %d drugs = %d candidates",
        len(seen_classes), len(drug_data), len(candidates),
    )
    return candidates


def collect_key_topic_candidates() -> list[dict]:
    """從 Firestore guidelines collection 取得 key_topics[] 子主題"""
    candidates = []
    seen = set()
    try:
        docs = db.collection("guidelines").stream()
        for doc in docs:
            data = doc.to_dict()
            key_topics = data.get("key_topics", [])
            for kt in key_topics:
                kt_str = kt.strip() if isinstance(kt, str) else ""
                if kt_str and kt_str not in seen:
                    seen.add(kt_str)
                    topics = data.get("topics", [])
                    candidates.append({
                        "raw_title": kt_str,
                        "source": "guideline_key_topic",
                        "suggested_topics": topics if topics else [],
                    })
    except Exception as e:
        logger.error("讀取 guidelines 失敗: %s", e)
    logger.info("Guideline key_topics: %d unique candidates", len(candidates))
    return candidates


def collect_all_candidates() -> list[dict]:
    """收集所有來源的候選 concepts"""
    all_candidates = []
    all_candidates.extend(collect_topic_candidates())
    all_candidates.extend(collect_guideline_chapter_candidates())
    all_candidates.extend(collect_drug_candidates())
    all_candidates.extend(collect_key_topic_candidates())

    # Basic dedup by raw_title (case-insensitive)
    seen = {}
    deduped = []
    for c in all_candidates:
        key = c["raw_title"].lower().strip()
        if key not in seen:
            seen[key] = c
            deduped.append(c)
        else:
            # Merge sources/topics
            existing = seen[key]
            existing["source"] += f", {c['source']}"
            for t in c.get("suggested_topics", []):
                if t not in existing.get("suggested_topics", []):
                    existing["suggested_topics"].append(t)

    logger.info(
        "收集完成: %d raw candidates -> %d after basic dedup",
        len(all_candidates), len(deduped),
    )
    return deduped


# ============================================================
# 2. Gemini 叢集 / 去重 / 豐富化
# ============================================================

CLUSTERING_PROMPT = """你是腎臟科知識圖譜的 concept 建構專家。

以下是一批候選 concept 條目（來自文獻主題、guideline、藥物資料庫等）。
請進行以下處理：

1. **去重合併**：將同義或高度重疊的條目合併為一個 canonical concept
   （例如 "IgA nephropathy" 和 "IgAN" 合併為一個 concept）
2. **指定 concept_id**：用英文 slug 格式（kebab-case），如 "iga-nephropathy"
3. **指定 title**：英文正式名稱。藥物名稱一律維持英文。
4. **指定 title_zh**：繁體中文名稱
5. **指定 aliases**：所有同義詞 / 別名 / 縮寫（陣列）
6. **指定 topics**：對應的頂層 topic（從以下清單中選）：
   ESRD/HD, AKI, CKD, GN, Transplant, Electrolyte, PD, CKM, HTN, PKD, CKD-MBD, Stone, Onco-Nephro
   如果跨多個 topic 可以填多個。
7. **指定 parent_concept**：如果有明顯的上層 concept，填寫其 concept_id（slug）。
   頂層 topic 的 parent_concept 為 null。
   藥物的 parent 通常是其 drug class。
   疾病亞型的 parent 通常是其大分類。

回傳嚴格 JSON 陣列（不要加 markdown code block）：
[
  {{
    "concept_id": "iga-nephropathy",
    "title": "IgA Nephropathy",
    "title_zh": "IgA 腎病變",
    "aliases": ["IgAN", "Berger's disease"],
    "topics": ["GN"],
    "parent_concept": "glomerulonephritis"
  }},
  ...
]

候選條目：
{candidates_json}
"""


def slugify(text: str) -> str:
    """將文字轉為 kebab-case slug"""
    text = text.lower().strip()
    text = re.sub(r"[/\\]", "-", text)
    text = re.sub(r"[^a-z0-9\s\-]", "", text)
    text = re.sub(r"[\s]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def call_gemini_clustering(batch: list[dict]) -> list[dict]:
    """呼叫 Gemini 進行 concept 叢集化"""
    if not gemini_client:
        logger.error("Gemini client 未初始化")
        return []

    candidates_json = json.dumps(
        [{"raw_title": c["raw_title"], "source": c["source"],
          "suggested_topics": c.get("suggested_topics", [])}
         for c in batch],
        ensure_ascii=False, indent=2,
    )
    prompt = CLUSTERING_PROMPT.format(candidates_json=candidates_json)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=gemini_types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            result = json.loads(response.text)
            if isinstance(result, dict):
                # Sometimes Gemini wraps in {"concepts": [...]}
                for key in ("concepts", "results", "data"):
                    if key in result and isinstance(result[key], list):
                        result = result[key]
                        break
                else:
                    result = [result]
            if not isinstance(result, list):
                logger.warning("Gemini 回傳非陣列，attempt %d", attempt)
                continue

            # Validate and clean each concept
            cleaned = []
            for item in result:
                if not isinstance(item, dict):
                    continue
                concept_id = item.get("concept_id", "")
                if not concept_id:
                    concept_id = slugify(item.get("title", "unknown"))
                cleaned.append({
                    "concept_id": concept_id,
                    "title": item.get("title", ""),
                    "title_zh": item.get("title_zh", ""),
                    "aliases": item.get("aliases", []),
                    "topics": item.get("topics", []),
                    "parent_concept": item.get("parent_concept") or None,
                })
            return cleaned

        except json.JSONDecodeError as e:
            logger.warning("Gemini JSON 解析失敗 (attempt %d/%d): %s", attempt, MAX_RETRIES, e)
        except Exception as e:
            logger.warning("Gemini 呼叫失敗 (attempt %d/%d): %s", attempt, MAX_RETRIES, e)

        if attempt < MAX_RETRIES:
            time.sleep(GEMINI_DELAY)

    logger.error("Gemini clustering 全部重試失敗，回傳 fallback")
    # Fallback: 直接用 raw_title 產生基本 concept
    fallback = []
    for c in batch:
        cid = slugify(c["raw_title"])
        fallback.append({
            "concept_id": cid,
            "title": c["raw_title"],
            "title_zh": "",
            "aliases": [],
            "topics": c.get("suggested_topics", []),
            "parent_concept": None,
        })
    return fallback


def cluster_candidates(candidates: list[dict], limit: int | None = None) -> list[dict]:
    """分批送 Gemini 進行叢集化處理"""
    if limit:
        candidates = candidates[:limit]

    all_concepts = []
    total_batches = (len(candidates) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[i: i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        logger.info(
            "Gemini clustering batch %d/%d (%d candidates)...",
            batch_num, total_batches, len(batch),
        )
        concepts = call_gemini_clustering(batch)
        all_concepts.extend(concepts)
        logger.info("  -> %d concepts from this batch", len(concepts))

        if i + BATCH_SIZE < len(candidates):
            time.sleep(GEMINI_DELAY)

    # Final dedup by concept_id across batches
    seen = {}
    deduped = []
    for c in all_concepts:
        cid = c["concept_id"]
        if cid in seen:
            # Merge aliases
            existing = seen[cid]
            for alias in c.get("aliases", []):
                if alias not in existing["aliases"]:
                    existing["aliases"].append(alias)
            for topic in c.get("topics", []):
                if topic not in existing["topics"]:
                    existing["topics"].append(topic)
        else:
            seen[cid] = c
            deduped.append(c)

    logger.info(
        "Clustering 完成: %d raw -> %d unique concepts",
        len(all_concepts), len(deduped),
    )
    return deduped


# ============================================================
# 3. 寫入 Firestore
# ============================================================


def build_search_text(concept: dict) -> str:
    """產生用於全文搜尋的 search_text"""
    parts = [
        concept.get("title", "").lower(),
        concept.get("title_zh", ""),
        concept.get("concept_id", "").replace("-", " "),
    ]
    for alias in concept.get("aliases", []):
        parts.append(alias.lower())
    for topic in concept.get("topics", []):
        parts.append(topic.lower())
    return " ".join(p for p in parts if p)


def get_existing_concept_ids() -> set[str]:
    """取得已存在的 concept_ids"""
    existing = set()
    try:
        docs = db.collection("kg_concepts").stream()
        for doc in docs:
            existing.add(doc.id)
    except Exception as e:
        logger.warning("讀取現有 kg_concepts 失敗: %s", e)
    return existing


def write_concepts(concepts: list[dict], dry_run: bool = False) -> dict:
    """寫入 concepts 到 Firestore，回傳統計"""
    stats = {"total": len(concepts), "created": 0, "skipped_existing": 0, "errors": 0}

    existing_ids = get_existing_concept_ids()
    logger.info("Firestore 現有 %d 個 concepts", len(existing_ids))

    for concept in concepts:
        concept_id = concept["concept_id"]

        if concept_id in existing_ids:
            stats["skipped_existing"] += 1
            if dry_run:
                logger.info("[DRY RUN][SKIP] %s (already exists)", concept_id)
            continue

        doc_data = {
            "concept_id": concept_id,
            "title": concept["title"],
            "title_zh": concept.get("title_zh", ""),
            "aliases": concept.get("aliases", []),
            "topics": concept.get("topics", []),
            "parent_concept": concept.get("parent_concept"),
            "related_concepts": [],
            "synthesis_note": "",
            "synthesis_status": "draft",
            "link_counts": {
                "article": 0,
                "guideline": 0,
                "trial": 0,
                "drug": 0,
                "consult": 0,
            },
            "search_text": build_search_text(concept),
            "created_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP,
            "created_by": "system",
        }

        if dry_run:
            logger.info(
                "[DRY RUN] %s — %s (%s) topics=%s parent=%s aliases=%s",
                concept_id,
                concept["title"],
                concept.get("title_zh", ""),
                concept.get("topics", []),
                concept.get("parent_concept"),
                concept.get("aliases", []),
            )
            stats["created"] += 1
            continue

        try:
            db.collection("kg_concepts").document(concept_id).set(doc_data)
            stats["created"] += 1
        except Exception as e:
            logger.error("寫入 %s 失敗: %s", concept_id, e)
            stats["errors"] += 1

    return stats


# ============================================================
# 主程式
# ============================================================


def main():
    parser = argparse.ArgumentParser(
        description="Seed knowledge graph concept nodes into Firestore kg_concepts"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print concepts without writing to Firestore",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Only process first N candidates (for testing)",
    )
    args = parser.parse_args()

    logger.info("=== Knowledge Graph Concept Seeder ===")
    if args.dry_run:
        logger.info("DRY RUN 模式：不會寫入 Firestore")

    # Step 1: Collect raw candidates
    logger.info("--- Step 1: Collect candidates ---")
    candidates = collect_all_candidates()

    if not candidates:
        logger.warning("沒有找到任何候選 concepts，結束")
        return

    # Step 2: Gemini clustering
    logger.info("--- Step 2: Gemini clustering & enrichment ---")
    if not gemini_client:
        logger.error("Gemini client 未初始化，無法進行 clustering")
        logger.info("Fallback: 使用 raw candidates 直接建立 concepts")
        concepts = []
        for c in (candidates[:args.limit] if args.limit else candidates):
            cid = slugify(c["raw_title"])
            concepts.append({
                "concept_id": cid,
                "title": c["raw_title"],
                "title_zh": "",
                "aliases": [],
                "topics": c.get("suggested_topics", []),
                "parent_concept": None,
            })
    else:
        concepts = cluster_candidates(candidates, limit=args.limit)

    if not concepts:
        logger.warning("Clustering 後沒有 concepts，結束")
        return

    # Step 3: Write to Firestore
    logger.info("--- Step 3: Write to Firestore ---")
    stats = write_concepts(concepts, dry_run=args.dry_run)

    # Step 4: Log stats
    logger.info("=== 完成 ===")
    logger.info("  Total concepts processed: %d", stats["total"])
    logger.info("  Created: %d", stats["created"])
    logger.info("  Skipped (existing): %d", stats["skipped_existing"])
    logger.info("  Errors: %d", stats["errors"])

    # Log to crawler_runs_v2
    if not args.dry_run:
        try:
            db.collection("crawler_runs_v2").add({
                "timestamp": datetime.now(timezone.utc),
                "crawler": "kg_build_concepts",
                "status": "completed",
                **stats,
            })
            logger.info("已記錄執行結果到 crawler_runs_v2")
        except Exception as e:
            logger.warning("記錄 crawler run 失敗: %s", e)


if __name__ == "__main__":
    main()
