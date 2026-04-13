"""
Knowledge Graph Auto-Linker — Nephro Brain OS
===============================================
自動連結 kg_concepts 概念節點到各資料來源（文獻、指引、臨床試驗、藥物），
產出 kg_links 文件以建構知識圖譜。

兩段式策略：
  Pass 1: 關鍵字/主題比對（無 AI，快速）
  Pass 2: Gemini 確認（AI，處理模糊匹配）

使用方式：
  python crawlers/kg_auto_link.py                     # 全量執行
  python crawlers/kg_auto_link.py --dry-run            # 預覽，不寫入
  python crawlers/kg_auto_link.py --limit 5            # 只處理前 5 個概念
  python crawlers/kg_auto_link.py --skip-ai            # 跳過 Gemini 確認
  python crawlers/kg_auto_link.py --dry-run --limit 3  # 預覽前 3 個概念
"""

import argparse
import json
import logging
import os
import re
import time
from datetime import datetime

from google.cloud import firestore as gc_firestore

from crawler_utils import db, gemini_client, gemini_types, GEMINI_DELAY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================
# 資料載入
# ============================================================

def load_concepts(limit: int = 0) -> list:
    """從 kg_concepts 載入所有概念節點"""
    q = db.collection("kg_concepts")
    docs = list(q.stream())
    concepts = []
    for doc in docs:
        data = doc.to_dict()
        data["_id"] = doc.id
        concepts.append(data)
    if limit > 0:
        concepts = concepts[:limit]
    logger.info("載入 %d 個概念節點", len(concepts))
    return concepts


def load_articles() -> list:
    """從 articles_v2 載入文獻"""
    docs = list(db.collection("articles_v2").stream())
    articles = []
    for doc in docs:
        data = doc.to_dict()
        data["_id"] = doc.id
        articles.append(data)
    logger.info("載入 %d 篇文獻", len(articles))
    return articles


def load_guidelines() -> list:
    """從 guideline_chapters 載入指引章節"""
    docs = list(db.collection("guideline_chapters").stream())
    chapters = []
    for doc in docs:
        data = doc.to_dict()
        data["_id"] = doc.id
        chapters.append(data)
    logger.info("載入 %d 個指引章節", len(chapters))
    return chapters


def load_trials() -> list:
    """從 clinical_trials 載入臨床試驗"""
    docs = list(db.collection("clinical_trials").stream())
    trials = []
    for doc in docs:
        data = doc.to_dict()
        data["_id"] = doc.id
        trials.append(data)
    logger.info("載入 %d 筆臨床試驗", len(trials))
    return trials


def load_drugs() -> dict:
    """從 backend/drug_database.json 載入藥物資料"""
    drug_path = os.path.join(
        os.path.dirname(__file__), "..", "backend", "drug_database.json"
    )
    if not os.path.exists(drug_path):
        logger.warning("找不到藥物資料庫: %s", drug_path)
        return {}
    with open(drug_path, "r", encoding="utf-8") as f:
        drugs = json.load(f)
    logger.info("載入 %d 筆藥物", len(drugs))
    return drugs


# ============================================================
# Pass 1: 關鍵字比對
# ============================================================

def _normalize(text: str) -> str:
    """正規化文字供比對用"""
    return text.lower().strip()


def _get_concept_terms(concept: dict) -> list:
    """取得概念的所有比對用詞（title + aliases），全部小寫"""
    terms = []
    title = concept.get("title", "")
    if title:
        terms.append(_normalize(title))
    aliases = concept.get("aliases", [])
    for alias in aliases:
        n = _normalize(alias)
        if n and n not in terms:
            terms.append(n)
    return terms


def _text_contains_any(text: str, terms: list) -> bool:
    """檢查 text（已小寫）是否包含任何一個 term"""
    text_lower = _normalize(text)
    for term in terms:
        if term in text_lower:
            return True
    return False


def match_articles(concept: dict, articles: list) -> list:
    """比對概念與文獻"""
    terms = _get_concept_terms(concept)
    concept_topics = set(_normalize(t) for t in concept.get("topics", []))
    matches = []

    for art in articles:
        matched = False

        # 方法 1: topics 交集
        if concept_topics:
            art_topics = set(_normalize(t) for t in art.get("topics", []))
            if concept_topics & art_topics:
                matched = True

        # 方法 2: 概念名稱出現在文獻標題
        if not matched:
            art_title = art.get("title", "")
            if _text_contains_any(art_title, terms):
                matched = True

        if matched:
            # 建構 source_snapshot
            pubdate = art.get("pubdate", "")
            if isinstance(pubdate, datetime):
                pubdate = pubdate.strftime("%Y-%m")
            elif isinstance(pubdate, str) and len(pubdate) > 7:
                pubdate = pubdate[:7]

            matches.append({
                "source_type": "article",
                "source_id": art["_id"],
                "source_collection": "articles_v2",
                "source_snapshot": {
                    "title": art.get("title", ""),
                    "title_zh": art.get("title_zh", ""),
                    "journal": art.get("journal", ""),
                    "evidence_level": art.get("evidence_level", ""),
                    "date": pubdate,
                },
            })

    return matches


def match_guidelines(concept: dict, guidelines: list) -> list:
    """比對概念與指引章節"""
    terms = _get_concept_terms(concept)
    matches = []

    for gl in guidelines:
        chapter_title = gl.get("chapter_title", "")
        guideline_title = gl.get("guideline_title", "")
        combined = f"{chapter_title} {guideline_title}"

        if _text_contains_any(combined, terms):
            matches.append({
                "source_type": "guideline",
                "source_id": gl["_id"],
                "source_collection": "guideline_chapters",
                "source_snapshot": {
                    "title": chapter_title,
                    "guideline_title": guideline_title,
                    "org": gl.get("org", ""),
                },
            })

    return matches


def match_trials(concept: dict, trials: list) -> list:
    """比對概念與臨床試驗"""
    terms = _get_concept_terms(concept)
    matches = []

    for trial in trials:
        matched = False

        # 檢查 conditions
        conditions = trial.get("conditions", [])
        for cond in conditions:
            if _text_contains_any(cond, terms):
                matched = True
                break

        # 檢查 interventions
        if not matched:
            interventions = trial.get("interventions", [])
            for iv in interventions:
                iv_name = iv.get("name", "") if isinstance(iv, dict) else str(iv)
                if _text_contains_any(iv_name, terms):
                    matched = True
                    break

        # 檢查標題
        if not matched:
            trial_title = trial.get("title", "")
            if _text_contains_any(trial_title, terms):
                matched = True

        if matched:
            matches.append({
                "source_type": "trial",
                "source_id": trial["_id"],
                "source_collection": "clinical_trials",
                "source_snapshot": {
                    "title": trial.get("title", ""),
                    "title_zh": trial.get("title_zh", ""),
                    "phase": trial.get("phase", ""),
                    "status": trial.get("status", ""),
                },
            })

    return matches


def match_drugs(concept: dict, drugs: dict) -> list:
    """比對概念與藥物"""
    terms = _get_concept_terms(concept)
    matches = []

    for drug_key, drug_data in drugs.items():
        matched = False
        drug_name = drug_data.get("drug_name_en", "")
        class_en = drug_data.get("class_en", "")

        # 方法 1: 藥物 class 出現在概念 terms
        if class_en:
            class_lower = _normalize(class_en)
            for term in terms:
                if term in class_lower or class_lower in term:
                    matched = True
                    break

        # 方法 2: 藥物名稱出現在概念 aliases
        if not matched and drug_name:
            drug_lower = _normalize(drug_name)
            for term in terms:
                if drug_lower in term or term in drug_lower:
                    matched = True
                    break

        # 方法 3: drug_key 出現在概念 terms
        if not matched:
            key_lower = _normalize(drug_key)
            for term in terms:
                if key_lower in term or term == key_lower:
                    matched = True
                    break

        if matched:
            matches.append({
                "source_type": "drug",
                "source_id": drug_key,
                "source_collection": "drug_database",
                "source_snapshot": {
                    "drug_name_en": drug_name,
                    "class_en": class_en,
                    "class_zh": drug_data.get("class_zh", ""),
                },
            })

    return matches


# ============================================================
# Pass 2: Gemini 確認
# ============================================================

GEMINI_CONFIRM_PROMPT = """你是一位腎臟科知識圖譜專家。以下是一組「概念 → 資料來源」的候選連結，
請判斷每個連結的相關性。

概念：{concept_title}
概念別名：{concept_aliases}

候選連結（JSON 陣列）：
{candidates_json}

請以嚴格 JSON 陣列格式回傳（不要加 markdown code block），每個元素包含：
{{
  "index": 0,
  "relevant": true,
  "relevance_score": 0.92,
  "relevance_reason": "一句話說明相關性原因"
}}

評分標準：
- 1.0: 直接針對此概念的研究/指引
- 0.8-0.9: 高度相關（同疾病不同面向）
- 0.6-0.7: 中等相關（同類疾病或治療）
- 0.3-0.5: 低相關（間接提及）
- <0.3: 不相關，設 relevant=false

只回傳 JSON，不要加任何其他文字。"""


def confirm_with_gemini(concept: dict, candidates: list) -> list:
    """用 Gemini 確認候選連結的相關性"""
    if not gemini_client:
        logger.warning("Gemini 未設定，跳過 AI 確認")
        return _default_scores(candidates)

    if not candidates:
        return []

    # 組合簡化的候選資訊供 Gemini 判斷
    simplified = []
    for i, c in enumerate(candidates):
        snap = c.get("source_snapshot", {})
        simplified.append({
            "index": i,
            "source_type": c["source_type"],
            "source_id": c["source_id"],
            "title": snap.get("title", snap.get("drug_name_en", "")),
        })

    # 每次最多處理 20 個候選
    BATCH_SIZE = 20
    all_results = []

    for batch_start in range(0, len(simplified), BATCH_SIZE):
        batch = simplified[batch_start:batch_start + BATCH_SIZE]
        prompt = GEMINI_CONFIRM_PROMPT.format(
            concept_title=concept.get("title", ""),
            concept_aliases=", ".join(concept.get("aliases", [])),
            candidates_json=json.dumps(batch, ensure_ascii=False, indent=2),
        )

        try:
            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=gemini_types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
            results = json.loads(response.text)
            if isinstance(results, dict):
                results = [results]
            all_results.extend(results)
            time.sleep(GEMINI_DELAY)
        except Exception as e:
            logger.warning("Gemini 確認失敗: %s — 使用預設分數", e)
            for item in batch:
                all_results.append({
                    "index": item["index"],
                    "relevant": True,
                    "relevance_score": 0.7,
                    "relevance_reason": "AI 確認失敗，使用預設分數",
                })

    # 將 Gemini 結果合併回候選
    score_map = {}
    for r in all_results:
        idx = r.get("index", -1)
        if 0 <= idx < len(candidates):
            score_map[idx] = r

    confirmed = []
    for i, c in enumerate(candidates):
        info = score_map.get(i, {})
        if info.get("relevant", True):
            c["relevance_score"] = info.get("relevance_score", 0.7)
            c["relevance_reason"] = info.get("relevance_reason", "")
            confirmed.append(c)
        else:
            logger.debug(
                "  排除: %s (%s) — score %.2f",
                c["source_id"],
                c["source_type"],
                info.get("relevance_score", 0),
            )

    return confirmed


def _default_scores(candidates: list) -> list:
    """跳過 AI 時，給所有候選預設分數"""
    for c in candidates:
        c["relevance_score"] = 0.7
        c["relevance_reason"] = "Keyword match (AI confirmation skipped)"
    return candidates


# ============================================================
# 重複檢查與寫入
# ============================================================

def link_exists(concept_id: str, source_id: str) -> bool:
    """檢查 kg_links 中是否已存在此連結"""
    existing = (
        db.collection("kg_links")
        .where("concept_id", "==", concept_id)
        .where("source_id", "==", source_id)
        .limit(1)
        .stream()
    )
    return any(True for _ in existing)


def write_link(concept_id: str, link: dict, dry_run: bool = False) -> bool:
    """寫入一筆 kg_links 文件，回傳是否成功寫入"""
    if link_exists(concept_id, link["source_id"]):
        logger.debug("  已存在: %s -> %s，跳過", concept_id, link["source_id"])
        return False

    doc_data = {
        "concept_id": concept_id,
        "source_type": link["source_type"],
        "source_id": link["source_id"],
        "source_collection": link["source_collection"],
        "relevance_score": link.get("relevance_score", 0.7),
        "relevance_reason": link.get("relevance_reason", ""),
        "source_snapshot": link.get("source_snapshot", {}),
        "status": "pending",
        "created_at": gc_firestore.SERVER_TIMESTAMP,
        "created_by": "system",
    }

    if dry_run:
        logger.info(
            "  [DRY RUN] 會建立連結: %s -> %s (%s, score=%.2f)",
            concept_id,
            link["source_id"],
            link["source_type"],
            link.get("relevance_score", 0.7),
        )
        return True

    db.collection("kg_links").add(doc_data)
    return True


def count_links_for_concept(concept_id: str) -> dict:
    """查詢某概念的實際連結數量（按 source_type）"""
    counts = {"article": 0, "guideline": 0, "trial": 0, "drug": 0, "consult": 0}
    links = db.collection("kg_links").where("concept_id", "==", concept_id).stream()
    for link in links:
        stype = link.to_dict().get("source_type", "other")
        if stype in counts:
            counts[stype] += 1
    return counts


def update_link_counts(concept_id: str, counts: dict, dry_run: bool = False):
    """更新 kg_concepts 文件的 link_counts 欄位"""
    if dry_run:
        logger.info("  [DRY RUN] 會更新 link_counts: %s", counts)
        return

    doc_ref = db.collection("kg_concepts").document(concept_id)
    doc_ref.update({"link_counts": counts, "links_updated_at": gc_firestore.SERVER_TIMESTAMP})


# ============================================================
# 主程式
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Knowledge Graph Auto-Linker — 自動連結概念到資料來源"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="預覽模式，不寫入 Firestore"
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="只處理前 N 個概念（0=全部）"
    )
    parser.add_argument(
        "--skip-ai", action="store_true", help="跳過 Gemini 確認，直接用關鍵字比對"
    )
    args = parser.parse_args()

    logger.info("=== Knowledge Graph Auto-Linker 開始 ===")
    logger.info("模式: dry_run=%s, limit=%d, skip_ai=%s", args.dry_run, args.limit, args.skip_ai)

    # Step 1: 載入所有資料
    logger.info("--- Step 1: 載入資料 ---")
    concepts = load_concepts(args.limit)
    if not concepts:
        logger.warning("沒有概念節點，結束")
        return

    articles = load_articles()
    guidelines = load_guidelines()
    trials = load_trials()
    drugs = load_drugs()

    # 統計
    stats = {
        "concepts_processed": 0,
        "links_created": 0,
        "links_skipped_duplicate": 0,
        "links_rejected_ai": 0,
        "by_type": {"article": 0, "guideline": 0, "trial": 0, "drug": 0},
    }

    # Step 2-6: 逐概念處理
    for i, concept in enumerate(concepts, 1):
        concept_id = concept["_id"]
        concept_title = concept.get("title", concept_id)
        logger.info(
            "--- [%d/%d] 處理概念: %s ---", i, len(concepts), concept_title
        )

        # Pass 1: 關鍵字比對
        candidates = []
        art_matches = match_articles(concept, articles)
        gl_matches = match_guidelines(concept, guidelines)
        trial_matches = match_trials(concept, trials)
        drug_matches = match_drugs(concept, drugs)

        candidates = art_matches + gl_matches + trial_matches + drug_matches
        logger.info(
            "  Pass 1 候選: %d (文獻=%d, 指引=%d, 試驗=%d, 藥物=%d)",
            len(candidates),
            len(art_matches),
            len(gl_matches),
            len(trial_matches),
            len(drug_matches),
        )

        if not candidates:
            logger.info("  無候選連結，跳過")
            stats["concepts_processed"] += 1
            continue

        # Pass 2: Gemini 確認（或跳過）
        if args.skip_ai:
            confirmed = _default_scores(candidates)
        else:
            before_count = len(candidates)
            confirmed = confirm_with_gemini(concept, candidates)
            rejected = before_count - len(confirmed)
            stats["links_rejected_ai"] += rejected
            if rejected > 0:
                logger.info("  Pass 2: AI 排除 %d 筆，確認 %d 筆", rejected, len(confirmed))

        # Step 5: 寫入 kg_links
        link_counts = {"article": 0, "guideline": 0, "trial": 0, "drug": 0}
        for link in confirmed:
            written = write_link(concept_id, link, dry_run=args.dry_run)
            if written:
                stats["links_created"] += 1
                stype = link["source_type"]
                stats["by_type"][stype] = stats["by_type"].get(stype, 0) + 1
                link_counts[stype] = link_counts.get(stype, 0) + 1
            else:
                stats["links_skipped_duplicate"] += 1

        # Step 6: 更新 link_counts（查詢實際總數，避免重複執行時計數不準）
        if any(v > 0 for v in link_counts.values()):
            actual_counts = count_links_for_concept(concept_id)
            update_link_counts(concept_id, actual_counts, dry_run=args.dry_run)

        stats["concepts_processed"] += 1

    # Step 7: 輸出統計
    logger.info("=== 執行完成 ===")
    logger.info("概念處理: %d", stats["concepts_processed"])
    logger.info("連結建立: %d", stats["links_created"])
    logger.info("  文獻: %d", stats["by_type"]["article"])
    logger.info("  指引: %d", stats["by_type"]["guideline"])
    logger.info("  試驗: %d", stats["by_type"]["trial"])
    logger.info("  藥物: %d", stats["by_type"]["drug"])
    logger.info("重複跳過: %d", stats["links_skipped_duplicate"])
    logger.info("AI 排除: %d", stats["links_rejected_ai"])


if __name__ == "__main__":
    main()
