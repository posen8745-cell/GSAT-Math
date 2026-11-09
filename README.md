# GSAT-Math｜學測數學逐題原題練習網站

這一版修正了之前「只有逐題答題卡，沒有顯示題目」的問題。

## 這次有什麼不同？

1. 在「歷屆試卷」選擇學測年度／考科，**直接在作答欄上方顯示這一題的原題**，而不是空白 PDF 框。
2. 正式題圖由大考中心官方 PDF **裁切成每題一張 WebP 圖**，保留原本圖形、矩陣、根號與分數。切到下一題，題圖和選項都一起切換。
3. 「學測原題・單元抽題」分頁也使用相同的題圖資源。
4. 保留原本的計時、答案自動儲存、批改、錯題紀錄，以及名校段考自編題練習。
5. 不再預設載入那個在某些瀏覽器出現空白的整份 PDF 預覽框。

## 重要：要看到全部題圖，必須執行圖片建立流程

ZIP 內 `index.html` 提供 115 年數 A 第 1–4 題的文字版預覽，方便你立刻確認逐題顯示有作用。**其餘年度與題號不是已經全部做好了**；需按以下步驟擷取題圖。

### 上傳到 GitHub（已有 `posen8745-cell/GSAT-Math` 專案）

1. 解壓縮 ZIP。
2. 到你的 `GSAT-Math` 專案，上傳 ZIP 裡的檔案／資料夾，保留目錄位置：
   - `index.html`
   - `scripts/build_question_images.py`
   - `.github/workflows/build-question-images.yml`
   - `README.md`
3. 提交 `Commit changes`。
4. 到 GitHub 專案上方 **Actions**，選 **Build original math question images**，點 **Run workflow**。
5. 等工作流程跑完，Actions 會把 `assets/questions/` 裡生成的題目圖片提交到同一個 GitHub 專案。
6. 打開 `https://posen8745-cell.github.io/GSAT-Math/`，重新整理。先檢查 **115 年數學 A 第 1 題**能否顯示官方原題圖片，再測下一題。

若無法從 GitHub Actions 自動提交檔案，到 Repository **Settings → Actions → General → Workflow permissions** 檢查是否允許 **Read and write permissions**。若 PDF 連結失效，會在 Actions 紀錄中顯示錯誤；不能當作已收錄成功。

### 檢查裁切品質（重要）

**自動裁切可能出錯**，例如題目跨頁、選項位於下一頁、題組共用敘述與圖形。Action 完成後，請開啟：

`https://posen8745-cell.github.io/GSAT-Math/assets/questions/review.html`

逐題檢查是否有題幹缺頭、截斷結尾、圖片漏抓或把下一題混進同一張圖的情況；如果某題有問題，應依官方 PDF 人工重新擷取，不能直接宣稱全部官方題圖均已核對。

## 計分說明

本網站仍只記錄「完全答對」的結果；多選題的正式部分給分、非選擇題人工評分沒有模擬，也不等同正式學測原始分數或級分。

## 資料來源

大學入學考試中心 108–115 學年度官方數學試卷及答案，題目 PDF 原卷連結寫於網站中的 `EXAMS` 資料；依第三方資料分類的學期／單元標籤不是官方單元標籤。專案非大考中心官方服務。
