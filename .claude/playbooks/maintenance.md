# 制度檔案維護協議（maintenance.md）

管的是這些檔案：`CLAUDE.md`、`.claude/SESSION_LOG.md`、`.claude/SESSION_ARCHIVE.md`、`.claude/playbooks/*.md`、`.claude/agents/*.md`、`.claude/settings.json`。

## 1. 改之前：先備份

改任何上述既有檔案前，先複製一份到 `.claude/archive/<今天日期>-<簡述>/<原檔名>.bak`（目錄不存在就建）。
git 歷史不算備份——弱模型可能在錯誤 branch 上工作或 force 操作，實體副本才保險。

## 2. 權限分級：哪些可以自己改、哪些要先問

**可自行修改（不需問使用者）：**
- `SESSION_LOG.md`：每次 session 收尾更新（見第 4 節格式）。
- `SESSION_ARCHIVE.md`：從 SESSION_LOG 搬歷史進來。
- `judgment.md` / `dispatch.md` / `templates.md` 的**「教訓」附錄區**：踩坑後追加教訓（見第 3 節格式）。
- 明確的事實錯誤：路徑改了、工具改名了、指令參數變了——改正並在 commit message 說明。

**必須先問使用者（在線用 AskUserQuestion；不在線就開 draft PR 說明、不直接 merge）：**
- CLAUDE.md 的「不可違反的硬規則」與「品質底線」任何一字。
- 刪除或重寫任何 playbook 的整個章節。
- 調整 dispatch.md 的升降級門檻、judgment.md 的判準本身。
- `.claude/settings.json`（hooks）與 `.claude/agents/*.md`。
- 刪除任何備份或 archive 內容。

**判斷原則**：追加具體教訓＝可以；改變規則語意＝要問。分不清就當成要問。

## 3. 踩坑後：教訓寫回哪裡、什麼格式

踩了坑（返工、部署失敗、agent 產出報廢、被使用者糾正）→ 當次 session 收尾時寫回對應檔案的檔尾「## 教訓」區（沒有就新建該節）：

- 派工/模型選擇踩坑 → `dispatch.md`
- 判斷失誤（該問沒問、該停沒停、誤判完成）→ `judgment.md`
- prompt 寫法問題 → `templates.md`
- 專案事實（部署、指令、架構）→ CLAUDE.md 對應段落（若屬硬規則層級，先問使用者）

**格式（一條 3 行內，寫不進 3 行代表還沒想清楚）：**
```
- [YYYY-MM-DD] 症狀：<出了什麼事>。根因：<為什麼>。規則：<以後怎麼做，一句可執行的話>。
```

## 4. SESSION_LOG.md 的格式與容量

- **上限 80 行**。每次更新後檢查 `wc -l`，超了就把「最近一次 session」以外的舊 session 摘要搬到 SESSION_ARCHIVE.md 最上方。
- 固定四節：`最近一次 session`（≤10 行）／`系統目前狀態`／`待辦（依優先序）`／`重要架構決策`。
- 「重要架構決策」只增不刪；要刪或推翻必須先問使用者。其他節可自由改寫。
- 只寫「下個 session 需要知道的事」。過程、嘗試、失敗細節不寫這裡（有價值的進教訓區，其餘丟掉）。

## 5. 累積多長要精簡

每次 session 開場如果注意到以下任一情況，主動做精簡（這是「可自行修改」等級，但精簡＝合併與改寫，不是刪規則）：
- 任何單一 playbook 超過 **250 行** → 合併重複條目、把冷內容移到 archive。
- 任何「## 教訓」區超過 **15 條** → 把同類教訓合併成一條通則；若某教訓已升格為正式規則（要問使用者），原條目移除。
- `.claude/archive/` 超過 10 個目錄 → 問使用者能否清掉一年以上的。

## 6. 改完之後：驗證

- 改 `.md`：派 verifier read-back——引用的路徑、工具名、指令都真實存在；新舊規則無矛盾。
- 改 `settings.json`：`python -c "import json;json.load(open('.claude/settings.json'))"` 必過（settings 壞掉曾讓 hook 整個失效）。
- 改 CLAUDE.md：確認路由表指的檔案全部存在（`ls .claude/playbooks/`）。
- 一律走 feature branch + PR，不直接在 main 上改制度檔。
