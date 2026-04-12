# Session Log

## 最近一次更新
- **日期**：2026-04-13

- **完成事項**：
  1. **OpenEvidence Deep Research 整合**（全部完成，PR #91 已 merge）：
     - `backend/openevidence_client.py`: 新增 OE Cookie 管理（Firestore 儲存）+ API Client（cookie auth、polling、citation extraction）
     - `backend/api_server.py`: Deep Research 分支（三路並行 RAG+PubMed+OE → Gemini Pro 綜合）、`_assist_evidence()` 模式、3 個 admin OE endpoints
     - `backend/Dockerfile`: COPY openevidence_client.py
     - `firestore.rules`: system_config collection admin-only 規則
     - `src/composables/useConsultChat.js`: statusMessages ref、deep_research flag、SSE status 處理
     - `src/views/ConsultPage.vue`: Deep Research toggle 按鈕、漸進式 status 顯示（逐行更新）
     - `src/views/AssistPage.vue`: Evidence 查詢模式（直接查 OE）
     - `src/views/SettingsPage.vue`: OE Cookie 管理 UI（狀態燈號、上傳、驗證）
- **目前狀態**：程式碼已 merge 到 main，Vercel 前端應自動部署
- **使用者需要執行的**：
  - `firebase deploy --only firestore:rules`（部署 system_config 規則）
  - `gcloud run deploy nephro-brain-api --source ./backend --region asia-east1 --clear-base-image`（部署後端）
  - 在瀏覽器登入 OpenEvidence → 匯出 Cookie → Settings 頁面上傳
  - 測試 Deep Research 功能
- **重要決策**：
  - Deep Research 是 opt-in toggle（不影響現有 Normal mode）
  - OE Cookie 存 Firestore（不存 .env），支援 Cloud Run 無本地檔案環境
  - Deep Research 用 Gemini 2.5 Pro（成本較高但品質好），Normal mode 維持 Flash
  - OE 查詢用獨立 threading.Thread（不在 ThreadPoolExecutor 裡），避免 with block 提早 join
  - OE 失敗時 graceful fallback（只用 RAG + PubMed 繼續綜合）
  - Cookie 管理支援三種格式：JSON array、JSON object、raw string（name=val; name2=val2）

## 2026-04-06（第三次更新）
- **完成事項**：
  1. **知識庫全面擴充 — 三個 Phase 全部完成**：
     - **Phase 1: 擴大現有管道**
       - PubMed 期刊從 7 本擴充至 13 本（+AJT, Transplantation, NDT, AJKD, Kidney360, KI Reports）
       - MAX_ARTICLES_PER_RUN 從 80 提高到 150
       - 臨床指引從 26 部擴充至 40 部（+5 NICE + 9 ERBP/ERA-EDTA）
       - 前端 InsightPage 新增 NICE / ERBP org 篩選按鈕
       - 藥物資料庫從 20 種擴充至 72 種（+免疫抑制劑、透析藥物、CRRT 劑量、降壓藥、CKM 藥物、抗生素等）
     - **Phase 2: 新增高實證爬蟲**
       - `crawler_utils.py`：從 crawler_v2.py 抽取共用模組（Firebase init、PubMed API、AI 摘要、Firestore 儲存）
       - `crawler_cochrane.py`：Cochrane 系統性回顧爬蟲（透過 PubMed 搜尋 Cochrane Journal，全部 Level 1）
       - `crawler_clinicaltrials.py`：ClinicalTrials.gov REST API v2 爬蟲（含 `has_taiwan_site` 標記）
       - `backfill_pubmed.py`：歷史 12 個月 Level 1-2 文獻回溯腳本（按月分批）
       - `crawler_sr_weekly.py`：每週 SR/Meta-analysis 追蹤（不限期刊，全腎臟科）
       - 前端：新增「臨床試驗」tab、TrialCard.vue、useClinicalTrials.js
       - Firestore: clinical_trials collection + 公開讀取規則 + 複合索引
     - **Phase 3: 進階知識工程**
       - `nhi_database.json`：台灣健保給付結構化資料（21 項腎科常用藥物）
       - NHI API endpoints（`/nhi/search`, `/nhi/<drug>`）零 AI 成本直接查表
       - `_assist_nhi()` 改為結構化資料優先，找不到才 fallback Google Search + AI
       - `mesh_topic_map.json`：MeSH 本體論映射（13 topics, 123 descriptors）
       - `detect_topics()` 改為 MeSH-first 策略，keyword fallback
- **目前狀態**：程式碼已 commit 並 push 到 `feature/knowledge-base-expansion` branch
- **使用者需要做的**：
  - 在 GitHub 建立 PR 並 merge: https://github.com/toutsai/Nephro-brain-os/pull/new/feature/knowledge-base-expansion
  - `firebase deploy --only firestore:rules,firestore:indexes`（部署新的 Firestore 規則+索引）
  - `python crawlers/seed_guidelines.py`（seed 新的 NICE/ERBP 指引到 Firestore）
  - `python crawlers/crawler_cochrane.py --dry-run --limit 5`（測試 Cochrane 爬蟲）
  - `python crawlers/crawler_clinicaltrials.py --dry-run --limit 5`（測試 ClinicalTrials 爬蟲）
  - `python crawlers/backfill_pubmed.py --dry-run --limit 5 --months-back 1`（測試歷史回溯）
  - 重新部署 backend（Cloud Run）以載入新的 drug_database.json 和 nhi_database.json
- **月增 API 成本**：< $1 USD（PubMed/Cochrane/ClinicalTrials API 免費）
- **重要決策**：
  - Cochrane 爬蟲透過 PubMed 搜尋（無需 Cochrane 付費 API），存入 articles_v2 collection
  - ClinicalTrials.gov 用獨立 collection（schema 差異大），AI 僅用 Groq 翻譯
  - NHI 結構化資料優先於 AI 查詢（零成本 + 更準確）
  - MeSH-first topic detection 提升分類準確度，keyword 作為 fallback
  - crawler_utils.py 避免程式碼重複，所有新爬蟲共用

## 2026-04-06（第三次更新）
- 指引大腦 — 前端章節瀏覽器（全部完成）
- 指引大腦 — 後端處理腳本（全部完成）
- Firestore 配置（guideline_chapters）
- Bug fix：crawlers fallback 讀取 backend/.env

## 2026-04-06（第一次更新）
- Consult → Insight 相關文獻推薦
- LandingPage Dashboard
- Insight 臨床指引區（KDIGO/KDOQI）
- seed_guidelines.py（26 部指引）

## 歷史紀錄

### 2026-04-02（第二次更新）
- Insight 新文章 badge、本日快訊
- Consult 精選問答區
- Teach PPT 選項擴充
- Assist 圖片貼上
- 跨模組連動優化、PWA icons、Service Worker

### 2026-04-02（第一次更新）
- 跨模組連動優化
- 抽取 useTeachPicker composable
- PWA icon 生成 + vite-plugin-pwa 設定

### 2026-03-30
- Insight 搜尋主題擴充到 13 個
- 三欄式佈局、手機版全面優化
- Claude Code 工作流程自動化設定
