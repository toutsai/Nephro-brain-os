# 工作流程規則

## 新對話啟動
1. 先讀取 `.claude/SESSION_LOG.md` 了解上次進度
2. 簡要告知使用者上次的工作摘要
3. 詢問是否繼續未完成的工作或開始新任務

## 分析與規劃
- 探索性問題：啟動 2-3 個 Explore agents 並行搜尋
- 寫 plan 到 plan file，使用 ExitPlanMode 讓使用者確認
- 使用者未確認前，絕對不開始實作

## 實作
- 獨立的檔案修改用 agents 並行處理
- 會互相衝突的修改必須依序處理
- 每個 agent 完成後更新 TODO 狀態

## 完成
- Commit 用清楚的中文訊息
- Push 到 feature branch → 建 PR → merge 到 main
- 確認 build 不會失敗（Vue template 語法檢查）

## 對話結束
- 將工作摘要更新到 `.claude/SESSION_LOG.md`
