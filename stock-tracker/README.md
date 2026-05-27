# 📊 台股投資組合監控

自動追蹤台灣股市持倉，每個交易日收盤後抓取股價、檢查警示並在 GitHub Issues 建立通知。

## 功能

| 功能 | 說明 |
|---|---|
| ⏰ 自動抓取股價 | GitHub Actions 每個交易日 14:40 自動執行 |
| 🛑 停損 / 🎯 目標價警示 | 觸發時自動開 GitHub Issue |
| 📊 視覺化儀表板 | GitHub Pages 展示持倉、損益、圖表 |

## 快速開始

### 1. 設定持倉（`portfolio.json`）

編輯 `stock-tracker/portfolio.json`，填入您實際持有的股票：

```json
{
  "holdings": [
    {
      "symbol": "2330",     // 股票代號
      "name": "台積電",
      "market": "TSE",      // TSE = 上市，OTC = 上櫃
      "shares": 100,        // 持股張數 × 1000（或股數）
      "avg_cost": 800.0,    // 平均買入成本
      "alerts": {
        "target_price": 1100.0,   // 目標價（達到時開 Issue）
        "stop_loss": 700.0         // 停損價（跌破時開 Issue）
      }
    }
  ]
}
```

### 2. 啟用 GitHub Pages

1. 進入 **Settings → Pages**
2. Source 選 **Deploy from a branch**
3. Branch 選 `main`，Folder 選 `/stock-tracker/docs`
4. 儲存後即可在 `https://<username>.github.io/<repo>/` 看到儀表板

### 3. 給 Actions 寫入權限

1. 進入 **Settings → Actions → General**
2. 找到 **Workflow permissions**
3. 選 **Read and write permissions**
4. 儲存

### 4. 觸發執行

- **自動**：每個週一至週五 14:40 (台灣時間) 執行
- **手動**：進入 **Actions → 📈 抓取台股股價 → Run workflow**

## 目錄結構

```
stock-tracker/
├── portfolio.json              # ← 在此設定您的持倉與警示
├── data/
│   └── prices.json             # 自動更新（每日）
├── docs/
│   └── index.html              # GitHub Pages 儀表板
├── scripts/
│   ├── fetch_prices.py         # 抓取 TWSE 股價
│   ├── check_alerts.py         # 檢查警示，建立 Issue
│   └── requirements.txt
└── .github/
    └── workflows/
        └── fetch_prices.yml    # GitHub Actions 排程
```

## GitHub Issue 警示範例

達到目標價時：
> **🎯 [2330] 台積電 達到目標價 $1100**

觸發停損時：
> **🛑 [2330] 台積電 觸發停損 $700**

每個 Issue 包含：目前股價、成本、損益、持倉張數等詳細資訊。

## 本機測試

```bash
cd stock-tracker
pip install -r scripts/requirements.txt
python scripts/fetch_prices.py
python scripts/check_alerts.py   # 需設定 GITHUB_TOKEN 環境變數
```
