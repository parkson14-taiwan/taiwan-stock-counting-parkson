# 台股 MA 回測 (Streamlit)

這個專案是本機可直接執行的 Streamlit 回測工具，請先在你的電腦上安裝 Python 以及套件，再啟動網頁介面。

## 安裝

```bash
python -m pip install -r requirements.txt
```

## 執行

```bash
python -m streamlit run app.py
```

執行後瀏覽器會自動開啟，或手動開啟 `http://localhost:8501`。

程式會自動讀取 `data/taiex.csv` 並顯示前 20 行資料與回測結果。

## 常見問題

- **畫面完全不會動**：請確認你是在本機執行上述指令，並且命令列顯示 Streamlit 已啟動。
- **找不到 `streamlit` 指令**：請使用 `python -m streamlit run app.py`，避免 PATH 沒有設定成功。
