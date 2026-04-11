# Session Log

## 最近一次更新
- **日期**：2026-04-12
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
  1. **指引大腦 — 前端章節瀏覽器**（全部完成）：
     - `GuidelineContentViewer.vue`: 富內容章節瀏覽（markdown 渲染 + Mermaid 流程圖 + 建議等級 badge）
     - `GuidelineChapterNav.vue`: 章節側邊導航（桌面側欄 / 手機橫向 pills）
     - `RecommendationBadge.vue`: 建議等級色碼 (1A=綠, 1B=藍, 2A=琥珀, 2B=灰)
     - `useGuidelineChapters.js`: Firestore `guideline_chapters` 查詢 composable
     - `GuidelineDetail.vue` 新增「查看章節內容」主按鈕
     - `InsightPage.vue` 右欄條件渲染章節瀏覽器（桌面+手機版）
  2. **指引大腦 — 後端處理腳本**（全部完成）：
     - `process_guideline_content.py`: Gemini AI 逐章解析指引 PDF，生成繁中摘要、關鍵建議(含 grade)、治療流程圖(Mermaid)、版本差異分析
     - `download_kdoqi.py`: 下載 5 部 KDOQI 指引 PDF 並上傳 Firebase Storage
  3. **Firestore 配置**（全部完成）：
     - `guideline_chapters` collection 公開讀取規則
     - `(guideline_id, chapter_number)` 複合索引
  4. **Bug fix**：crawlers 改為 fallback 讀取 `backend/.env`（因為 GOOGLE_API_KEY 放在那）
- **目前狀態**：程式碼全部寫完並 push 到 `claude/review-project-code-mPLbL` branch，尚未 merge 到 main
- **使用者尚未在本地執行的**：
  - `firebase deploy --only firestore:rules,firestore:indexes`（部署 Firestore 規則+索引）
  - `python crawlers/process_guideline_content.py --limit 1`（先測試一部指引）
  - 確認 Gemini 輸出品質後 → `python crawlers/process_guideline_content.py --resume`（全部處理）
  - `python crawlers/download_kdoqi.py`（下載 KDOQI 指引 PDF）
- **下次待辦**：
  - 使用者回報 `process_guideline_content.py --limit 1` 的執行結果
  - 觀察 Gemini 生成的 Mermaid 流程圖品質，必要時調整 prompt
  - 確認前端 GuidelineContentViewer 能正確顯示章節資料
  - 需要 merge branch → main，讓 Vercel 部署前端
  - Phase 2: 版本差異分析（diff_from_previous，需上傳舊版 PDF）
  - 3 部較舊的 KDOQI (2003-2006) 可能需手動找 PDF
- **重要決策**：
  - 章節內容存在獨立的 `guideline_chapters` collection（非 subcollection），方便查詢
  - 每章發 3 次 Gemini 呼叫（content/recommendations/flowchart）而非 1 次大呼叫，提高穩定性
  - 使用 Gemini File API 整份 PDF 上傳（非逐頁），效率更高
  - 前端 GuidelineContentViewer 直接使用現有 renderMd + renderMermaidIn，零新增依賴
  - KDOQI 較舊指引(2003-2006) URL 需手動確認，download_kdoqi.py 中已註解
  - crawlers 的 `.env` 讀取順序：根目錄 `.env` → `backend/.env`（fallback）

## 2026-04-06（第一次更新）
- Consult → Insight 相關文獻推薦（純前端 keyword→topic 匹配）
- LandingPage Dashboard（即時統計 + 模組入口 grid）
- Insight 臨床指引區（KDIGO/KDOQI 目錄 + 篩選）
- seed_guidelines.py（26 部指引種子資料）
- 修正 3 筆 KDIGO URL 404（ANCA、ADPKD、IgAN）
- seed_guidelines.py 新增 --update 模式

## 歷史紀錄

### 2026-04-02（第二次更新）
- Insight 新文章 badge、本日快訊
- Consult 精選問答區
- Teach PPT 選項擴充（頁數 4 檔 + 自動配色）
- Assist 圖片貼上（Ctrl+V + 拖曳）
- 跨模組連動優化、PWA icons、Service Worker、re-tagging 腳本

### 2026-04-02（第一次更新）
- 跨模組連動優化
- 抽取 useTeachPicker composable
- PWA icon 生成 + vite-plugin-pwa 設定
- 文章 re-tagging 腳本

### 2026-03-30
- Insight 搜尋主題從 7 個擴充到 13 個
- Insight 三欄式佈局、手機版下拉選單
- 五個頁面統一高度、統一全寬佈局
- 行動版全面優化
- Claude Code 工作流程自動化設定
