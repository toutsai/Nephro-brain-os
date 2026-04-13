# Session Log

## 最近一次更新
- **日期**：2026-04-13（第二次更新）
- **完成事項**：

### 一、GitHub Actions 自動化
  1. `backfill-pubmed-monthly.yml` — 每月 1 日自動回溯上月 PubMed 高實證文章（手動可設 months_back/limit）
  2. `process-guidelines-monthly.yml` — 每月 15 日自動處理新指引 PDF（--resume 冪等執行）
  3. 兩者完成後皆自動執行 knowledge base index incremental update

### 二、Knowledge Graph Phase 1（feature/knowledge-graph-phase1 → merged to main）
  1. **概念種子腳本** `crawlers/kg_build_concepts.py`
     - 從 topic taxonomy（13 topics）、guideline chapters、drug database（72 drugs）、guideline key_topics 收集候選
     - Gemini 批次叢集：去重、slug 命名、中文翻譯、topic 分配、parent 階層
     - 寫入 Firestore `kg_concepts` collection
  2. **自動連結腳本** `crawlers/kg_auto_link.py`
     - Pass 1: 關鍵字/topic 比對（零 AI 成本）
     - Pass 2: Gemini 確認 relevance_score + reason
     - 寫入 `kg_links` collection，更新 concept link_counts
  3. **Backend API 端點**
     - `GET /kg/concepts` — 列出概念（topic/status 篩選）
     - `GET /kg/concepts/<id>` — 概念詳情 + 關聯資料
     - `POST /kg/concepts/<id>/review` — 審核摘要
     - `POST /kg/links/<id>/review` — 審核連結
     - `GET /kg/review-queue` — 待審核佇列
     - `GET /kg/gaps` — 缺口報告
  4. **Frontend `/knowledge` 頁面**
     - ConceptCard.vue — 概念卡片（topics badges, link counts, status badge）
     - ConceptDetail.vue — 詳情頁（synthesis note + tabbed sources: Articles/Guidelines/Trials/Drugs）
     - useKnowledgeGraph.js — Firestore real-time composables
     - 主題篩選 chips + 搜尋功能
     - NavBar 新增 Knowledge (🧠) 項目
  5. **Firestore rules + indexes**
     - 新增 kg_concepts、kg_links、kg_consult_extractions、kg_gap_reports 規則
     - 4 組複合索引

### 三、修復
  - `.claude/settings.local.json` JSON 格式修復

- **目前狀態**：程式碼全部在 main branch，已 push
- **使用者需要執行的**：
  - 首次跑概念種子：`python crawlers/kg_build_concepts.py`（本機，需 .env）
  - 概念建好後跑連結：`python crawlers/kg_auto_link.py`（本機，需 .env）
  - 部署後端：`gcloud run deploy nephro-brain-api --source ./backend --region asia-east1 --clear-base-image`
  - 手動觸發 GitHub Actions PubMed Monthly Backfill（months_back=12）做首次全量回溯
  - 部署 Firestore rules：`firebase deploy --only firestore:rules,firestore:indexes`
- **下次待辦**：
  - 確認 Knowledge 頁面前端顯示正確
  - 確認 kg_build_concepts.py 產生合理數量的概念節點
  - Phase 2: Consult 知識萃取（修改 ask_stream 持久化 sources_used）
  - Phase 2: kg_generate_synthesis.py 為概念生成整合摘要
  - Phase 3: Review tab + approve/reject 流程
  - Phase 3: kg_gap_analysis.py 缺口偵測週報

## 重要架構決策（新增）
- **Knowledge Graph 是 overlay，不替換三層搜尋**：RAG pipeline 保持不變，KG 提供瀏覽/審核/缺口偵測
- **AI 產出預設 pending**：所有 AI 生成的 synthesis/links 需人工審核後才正式生效
- **批次而非即時**：醫療領域需審核，batch processing 可控且可追蹤
- **Firestore 而非 Neo4j**：現有 stack，規模 ~500 concepts / ~10K links 足夠

---

## 上一次更新
- **日期**：2026-04-13
- **完成事項**：

### 一、知識庫全面擴充（feature/knowledge-base-expansion → merged to main）
  1. **Phase 1: 擴大現有管道**
     - PubMed 期刊 7→13 本（+AJT, Transplantation, NDT, AJKD, Kidney360, KI Reports）
     - MAX_ARTICLES_PER_RUN 80→150
     - 臨床指引 26→40 部（+5 NICE + 9 ERBP/ERA-EDTA）
     - 藥物資料庫 20→72 種（+免疫抑制劑、透析藥物、CRRT 劑量、降壓藥、CKM、抗生素等）
     - 前端 InsightPage 新增 NICE / ERBP org 篩選
  2. **Phase 2: 新增高實證爬蟲**
     - `crawlers/crawler_utils.py`：共用模組（Firebase init、PubMed API、AI 摘要、Firestore）
     - `crawlers/crawler_cochrane.py`：Cochrane SR 爬蟲（Level 1，透過 PubMed 搜尋）
     - `crawlers/crawler_clinicaltrials.py`：ClinicalTrials.gov REST API v2（含腫瘤過濾 + 台灣站點標記）
     - `crawlers/backfill_pubmed.py`：歷史 12 個月 Level 1-2 回溯
     - `crawlers/crawler_sr_weekly.py`：每週 SR/Meta-analysis 追蹤
     - 前端：臨床試驗 tab + TrialCard.vue + useClinicalTrials.js
     - Firestore: clinical_trials collection + 規則 + 索引
  3. **Phase 3: 進階知識工程**
     - `backend/nhi_database.json`：21 項腎科藥物健保給付結構化資料
     - NHI API：`/nhi/search`, `/nhi/<drug>`（零 AI 成本查表）
     - `_assist_nhi()` 改為結構化資料優先，找不到才 fallback AI
     - `crawlers/mesh_topic_map.json`：MeSH 本體論映射（13 topics, 123 descriptors）
     - `detect_topics()` 改為 MeSH-first 策略
  4. **GitHub Actions 排程**
     - `crawl-cochrane-weekly.yml`：每週日 UTC 23:00
     - `crawl-sr-weekly.yml`：每週日 UTC 22:00
     - `crawl-clinicaltrials-weekly.yml`：每週日 UTC 23:30

### 二、混合式 RAG 知識庫整合（Consult 三層搜尋）
  1. **Layer 1 — 結構化查表（<1ms）**
     - `get_drug_nhi_context()`：從問題偵測藥物 → drug_database + nhi_database
  2. **Layer 2 — 知識庫向量搜尋（新增）**
     - `crawlers/build_knowledge_index.py`：articles_v2 + guideline_chapters + clinical_trials → FAISS IndexFlatL2(768)
     - `download_knowledge_base()` / `search_knowledge_base()` / `fetch_kb_content()` in api_server.py
     - 索引已建構（392 vectors）並上傳 Firebase Storage
  3. **Layer 3 — 外部搜尋（不變）**
     - PubMed + Google Search + OpenEvidence
  4. **Prompt 改寫**
     - Normal mode: 2→3 並行（textbook + KB + pubmed）+ 藥物/健保 pre-check
     - Deep Research: 3→4 並行 + DEEP_RESEARCH_PROMPT 新增 {drug_nhi_section} + {kb_ctx}
     - 所有 prompt 加入「優先引用結構化藥物/健保資料」指示
  5. **自動化**
     - `crawl-daily.yml` 每日爬蟲後增量更新知識庫索引
     - `rebuild-knowledge-index.yml` 每週全量重建

### 三、其他修正
  - 統一藥物名稱一律維持英文（PROMPT_HEADER + 所有 crawler prompts）
  - ClinicalTrials 爬蟲排除純腫瘤試驗（ONCO_EXCLUDE_KEYWORDS + NEPHRO_INCLUDE_KEYWORDS）
  - 修正 `/ask-stream` f-string json.dumps dict 跳脫問題
  - `backend/.env` Big5→UTF-8 編碼修正
  - 臨床試驗中文翻譯已補完（patch_translate_trials.py，已刪除）

- **目前狀態**：程式碼全部在 main branch，已 push
- **使用者需要執行的**：
  - `gcloud run deploy nephro-brain-api --source ./backend --region asia-east1 --clear-base-image`（部署後端 — 最重要！72 藥物 + NHI + 三層 RAG 都需要此步驟生效）
  - 部署後到 Consult 測試三層搜尋效果
- **下次待辦**：
  - 確認 Cloud Run 部署後 Consult 三層搜尋正常運作
  - 確認前端 Insight 臨床試驗 tab 顯示正確
  - 確認 Assist 藥物搜尋顯示 72 種藥物
  - 觀察每週 GitHub Actions 排程是否正常觸發
  - 考慮：歷史回溯 backfill 跑完整 12 個月（目前只跑了部分）
  - 考慮：`process_guideline_content.py` 處理新增的 NICE/ERBP 指引 PDF

## 重要架構決策
- **Consult 三層搜尋**：結構化查表 → 本地向量搜尋 → 外部搜尋
- **雙 FAISS 索引**：教科書（nephro_brain.index）獨立於知識庫（knowledge_base.index），互不影響
- **藥物名稱英文規則**：所有 AI 翻譯和回答中藥物名稱一律維持英文
- **Cochrane 透過 PubMed 搜尋**：不需 Cochrane 付費 API，存入 articles_v2（同 schema）
- **ClinicalTrials 獨立 collection**：schema 差異大，用 Groq 翻譯（最低成本）
- **NHI 結構化優先**：_assist_nhi() 先查 JSON，找不到才走 AI + Google Search

## 歷史紀錄
### 2026-04-06（第三次更新）
- 指引大腦前端章節瀏覽器 + 後端處理腳本
### 2026-04-06（第一次更新）
- LandingPage Dashboard + Insight 臨床指引區 + seed_guidelines.py
### 2026-04-02
- Insight 新文章 badge、Consult 精選問答、Teach PPT、Assist 圖片貼上、PWA
### 2026-03-30
- Insight 13 主題、三欄式佈局、手機版優化、Claude Code 自動化
