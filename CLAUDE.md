# Nephro Brain OS

腎臟科知識管理系統。前端 Vue 3 + Vite + Tailwind（Vercel 自動部署 main）；後端 Python Flask（Cloud Run，手動部署）；資料 Firestore + FAISS；爬蟲在 `crawlers/`。

## 不可違反的硬規則

1. **main 就是 production**。merge 前必須通過品質底線驗證（見下方「品質底線」）。
2. **藥物名稱一律維持英文**——所有 AI 翻譯、摘要、回答中不得把藥名譯成中文。
3. **AI 生成的醫療內容預設 pending**，需人工審核才生效（synthesis、links 等）。不得加入任何 auto-approve 邏輯。
4. **改 `.claude/` 下任何既有檔案前，先照 `.claude/playbooks/maintenance.md` 的規則做**（含備份與是否需使用者同意）。

## 品質底線（merge 前必跑）

- 前端有改動：`npm run build` 必須成功（Vue template 語法錯誤會讓 Vercel 部署失敗）。
- 後端/爬蟲有改動：`python -m py_compile <改過的每個 .py>` 必須通過。
- Firestore rules/indexes 有改動：session 結尾提醒使用者執行 `firebase deploy --only firestore`。
- 本 repo 沒有測試套件，以上是唯一的機器驗證，不可跳過。

## 部署

- **後端**：GitHub Actions 部署 API 有 IAM 權限問題，只能由使用者在本機手動執行：
  `gcloud run deploy nephro-brain-api --source ./backend --region asia-east1 --clear-base-image`
  backend 有更動時，session 結尾必須明確提醒使用者跑這行，並在 SESSION_LOG 標記「已 merge 未部署」。
- **前端**：merge 到 main 後 Vercel 自動部署，無需動作。

## 工作流程

1. **開場**：SessionStart hook 已自動載入 `.claude/SESSION_LOG.md`。用 1-2 句告知使用者上次進度，若有「未完成/未部署」項目先點名。
2. **分析**：探索 codebase 一律派 subagent，主對話不自己大量讀檔。派工規則見 `.claude/playbooks/dispatch.md`，prompt 直接套 `.claude/playbooks/templates.md`。
3. **規劃**：大小改動的判準見 judgment.md 第 3 條。小改動不需 plan，直接做。大改動先寫 plan：
   - 使用者在線（會回覆訊息）：plan 經確認後才實作。
   - 使用者不在線（遠端自主 session、排程觸發）：只交 plan 與 draft PR 說明，不實作。
4. **實作**：獨立檔案的修改可派多個 agents 並行；會衝突的依序做。用 TODO/task 追進度。
5. **完成**：commit 用清楚的中文訊息 → push feature branch → 建 PR。
   - 使用者在線：小改動通過品質底線即可 merge；大改動須 plan 已被確認才可 merge。
   - 使用者不在線：**建 draft PR，不 merge**，等使用者處理。
   - 遠端 session 沒有 `gh` CLI，用 GitHub MCP tools（`mcp__github__create_pull_request` 等）。
6. **收尾**：把工作摘要更新進 `.claude/SESSION_LOG.md`（格式與容量上限見 maintenance.md）。

## 深入指引（需要時才讀，不用預先全讀）

| 情境 | 讀這個檔 |
|---|---|
| 要派 subagent（選 model、寫驗收、收回報） | `.claude/playbooks/dispatch.md` |
| 派工 prompt 怎麼寫（搜尋/實作/重構/研究/審查） | `.claude/playbooks/templates.md` |
| 拿不準：該不該升級模型／算不算完成／該不該問使用者／要不要換方向 | `.claude/playbooks/judgment.md` |
| 要修改 CLAUDE.md、SESSION_LOG、playbooks 本身 | `.claude/playbooks/maintenance.md` |
| 新環境第一次跑，或想了解這套制度的由來 | `.claude/playbooks/letter-to-future-sessions.md`、`.claude/playbooks/DIAGNOSIS.md` |
| 想查更早的歷史工作紀錄 | `.claude/SESSION_ARCHIVE.md` |
