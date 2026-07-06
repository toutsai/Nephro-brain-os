# Nephro Brain OS

## 部署指令

GitHub Actions 部署 API 有 IAM 權限問題，改由手動部署：

```bash
gcloud run deploy nephro-brain-api --source ./backend --region asia-east1 --clear-base-image
```

當 backend 有更動時，需手動執行上述指令部署到 Cloud Run。

## 工作流程

### 分析階段
- 收到需求時，先用 2-3 個 Explore agents 並行探索 codebase
- 整合各 agent 的發現，提出完整分析

### 規劃階段
- 用 Plan agent 設計實作方案
- 寫出 plan 讓使用者檢視確認
- 使用者確認前不得開始實作

### 實作階段
- 確認後盡量用多個 agents 並行完成獨立任務
- 每完成一個步驟標記 TODO 進度

### 完成階段
- 所有修改完成後，自動 commit、push、建立 PR、merge 到 main
- 確認 Vercel 部署不會失敗（檢查 Vue template 語法）

### 對話結束
- 對話結束前，將本次工作摘要寫入 `.claude/SESSION_LOG.md`
- 包含：完成了什麼、未完成的、下次待辦、重要決策紀錄
