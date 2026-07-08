# 派工 prompt 模板（templates.md）

用法：選任務型態 → 複製模板 → 填 `【】` 空格 → 依 `dispatch.md` 第 2 節選 subagent_type 與 model → 派出。
每個模板已內建三件套（目標與動機／驗收條件／回報格式），**不要刪掉任何一節**，可以加料不可減料。

---

## 1. 搜尋／探索（subagent_type: Explore，model: sonnet）

```
目標：找出【要找什麼，例如：所有呼叫 search_knowledge_base() 的位置】。
動機：【上游任務，例如：我要改它的回傳格式，需要知道影響面】。
範圍：【目錄或檔案類型，例如：backend/ 與 crawlers/；quick / medium / very thorough 三選一】。

驗收條件：
- 每個結果附 檔案路徑:行號。
- 明說搜尋過哪些關鍵字/pattern，讓我能判斷有沒有漏。
- 找不到也要回報「用了哪些方式找、確定不存在」。
【可選：我預期至少會在 XX 檔案找到，若沒有請特別註明。】

回報格式：結論先行（一句話總結數量與分布）→ 條列 檔案:行號＋每項一句說明。不要貼大段程式碼。超過 30 行寫入 scratchpad 檔案回傳路徑。
```

## 2. 實作（subagent_type: general-purpose，model: sonnet；已有明確 pattern 可套→haiku）

```
目標：【做什麼，例如：在 src/views/InsightPage.vue 的 org 篩選加入新組織選項（假設未來要加 "ISN"）】。
動機：【為什麼／使用者要什麼效果】。
作法約束：
- 比照現有寫法：【參考位置，例如：src/views/InsightPage.vue 裡現有 NICE/ERBP 選項的寫法】。
- 不要動：【禁區，例如：api_server.py 的 prompt 字串、任何審核流程邏輯】。
- 硬規則：藥物名稱一律英文；AI 醫療內容預設 pending，不得加 auto-approve。

驗收條件：
- 【功能上可判定的結果，例如：Insight 頁 org 篩選出現 ISN 且點選後只顯示該組織的指引】。
- 改動的每個前端檔：npm run build 通過；每個 .py：python -m py_compile 通過。
- 改動範圍不超出上述目標（不順手重構）。

回報格式：結論先行（做了/沒做成）→ 改了哪些檔（檔案:行號）→ 驗證指令與結果原文（最後幾行）→ 沒做或不確定的部分明列。
```

## 3. 重構（subagent_type: general-purpose，model: sonnet；跨模組大重構先派 Plan agent 出方案）

```
目標：把【現況】重構成【目標形狀】，行為不得改變。
動機：【為什麼值得重構】。
範圍：只動【檔案清單】。範圍外發現的問題記下來回報，不要動手。

驗收條件：
- 對外行為不變：【怎麼證明，例如：該模組所有 public 函式簽名不變；npm run build / py_compile 通過】。
- 【量化目標，例如：重複的 Firebase init 程式碼只剩一份，在 crawlers/crawler_utils.py】。
- diff 裡沒有與重構無關的改動。

回報格式：結論先行 → 改動摘要（每檔一句）→ 驗證結果原文 → 「行為可能改變的風險點」清單（沒有就明說沒有）。
```

## 4. 研究（subagent_type: general-purpose，model: sonnet；要下結論做取捨→opus）

```
題目：【要回答的問題，例如：ClinicalTrials.gov API v2 的 rate limit 與分頁上限是多少】。
動機：【這個答案會決定什麼】。
來源要求：優先官方文件/官方 repo；每個關鍵結論附來源 URL；區分「文件明說」與「你的推論」。

驗收條件：
- 直接回答題目，有數字給數字。
- 每個結論可追溯到來源。
- 查不到的部分明說查不到，不准編。

回報格式：結論先行（3 句內）→ 關鍵事實條列（每條附來源）→ 不確定事項。全文 ≤30 行，長版報告落檔回傳路徑。
```

## 5. 審查（subagent_type: verifier；一般 code review 用 general-purpose + model: sonnet）

```
目標：驗收【誰的什麼產出，例如：feature branch X 的 diff / .claude/playbooks/ 全部檔案】。
背景：【這份產出宣稱做到什麼】。

驗收條件清單（逐條檢查）：
1.【條件一，例如：所有引用的檔案路徑真實存在】
2.【條件二，例如：npm run build 通過】
3.【條件三，例如：規則之間沒有互相矛盾】
…

回報格式：第一行 PASS 或 FAIL（N 條）→ 逐條 [PASS/FAIL/UNVERIFIABLE]＋證據（檔案:行號 或指令輸出）→ FAIL 條目附一句修法建議。≤40 行。
```

---

## 派工後的收工檢查（主對話自己做）

1. 回報符合回報合約嗎？（結論先行、檔案:行號、長產物落檔）不符 → 退回要求照格式重報，不要自己去翻。
2. 驗收條件每條都有著落嗎？有 FAIL → 交回修，修完**再驗一次**。
3. 只把結論留在主對話。細節去讀落檔產物。
