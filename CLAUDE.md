# Nephro Brain OS

## 部署指令

GitHub Actions 部署 API 有 IAM 權限問題，改由手動部署：

```bash
gcloud run deploy nephro-brain-api --source ./backend --region asia-east1 --clear-base-image
```

當 backend 有更動時，需手動執行上述指令部署到 Cloud Run。
