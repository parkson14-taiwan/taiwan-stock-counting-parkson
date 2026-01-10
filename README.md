# 台股 MA 回測 (Streamlit)

## 安裝

```bash
pip install -r requirements.txt
```

## 執行

```bash
streamlit run app.py
```

程式會自動讀取 `data/taiex.csv` 並顯示前 20 行資料與回測結果。

## GitHub Pages 部署（純前端）

1. 將 `index.html`、`app.js`、`style.css` 與 `data/taiex.csv` 保留在 repo 根目錄與 `data/` 目錄。
2. 進入 GitHub repo → Settings → Pages。
3. 在「Build and deployment」中選擇：
   - Source: Deploy from a branch
   - Branch: `main` / `/ (root)`
4. 儲存後等待部署完成，開啟 GitHub Pages 提供的網址即可使用。

此版本不需要安裝任何套件或執行任何 build 指令，直接開啟 GitHub Pages 網址即可使用。
