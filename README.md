# Nephro Brain OS

**The Intelligence Operating System for Nephrology**
腎臟科智慧中樞的作業系統

---

## 概述

Nephro Brain OS 是以 AI 強化的腎臟科知識基礎設施，整合文獻、證據與臨床推理，打造專科醫師可持續演化的智慧中樞平台。

## 核心模組

| 模組 | 說明 |
|------|------|
| **NB Insight** | 每日文獻智慧引擎 — 自動匯入 ESRD / AKI / CKD 最新文獻 |
| **NB Consult** | 證據合成問答引擎 — RAG 為基礎的臨床問答 |
| **NB Teach** | 教學內容生成引擎 — 投影片、心智圖、分眾教學素材 |
| **NB Assist** | 臨床決策輔助層 — 透析/CKD 決策邏輯 + 台灣健保規則 |

## 三層架構

1. **Knowledge Core** — Postgres + pgvector + Evidence Hierarchy + Taiwan NHI Rules
2. **Reasoning Layer** — PICO Structuring + Evidence Synthesis + Clinical Logic
3. **Presentation Layer** — LINE / Slides / Podcast / Mindmap / Web UI

## 本機預覽

```bash
python3 -m http.server 4173
```

開啟 <http://localhost:4173> 即可預覽 Landing Page。
