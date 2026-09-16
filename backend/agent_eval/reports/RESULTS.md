# EdgeMind-AgentEval 最新正式實驗結果（90×1）

- 執行日期：2026-09-16（Asia/Taipei）
- 測試範圍：Locked Test 90 題，每題執行 1 次，共 90 runs
- Agent 主模型：`gemini-3.5-flash-lite`
- Fallback 模型：`gemini-3.6-flash`
- 工具環境：固定 fixture；不連正式感測資料庫、不重跑 Ridge 數值模型
- 結果版本：`locked_test_live_rerun_20260916_r2`

## 實驗摘要

本次依指定完成 **90 題 × 1 次**。90 筆 trace 均完整寫入，90 個 case ID
沒有重複，所有 `run_index` 均為 1。所有案例皆取得模型回應，未發生
runtime error、明確模型服務失敗或本地摘要 fallback，因此本次結果沒有受到
上一輪 API 配額不足的污染。

Strict Task Success／Pass¹ 為 **66.67%（60/90）**。Agent 對「是否需要工具」
的判斷達到 **94.20% F1**，工具名稱正確率為 **95.45%**，參數 exact match
為 **89.39%**。回答內容的 Key-fact Recall 為 **90.65%**，數字型
Grounded-claim Precision 為 **98.10%**；但仍有 6 題出現未被工具結果支持的
數字，Hallucination Rate 為 **6.67%**。

## 實驗設計與評分口徑

EdgeMind-AgentEval 完整資料集包含 180 題，固定切分為 Development 60、
Validation 30 與 Locked Test 90。本次只使用 Locked Test，類別分布如下：

| 類別 | 題數 |
| --- | ---: |
| 目前狀態查詢 | 15 |
| 同設備溫度預測 | 15 |
| 跨設備訓練與推論 | 15 |
| 隱含／口語化預測 | 10 |
| 不需工具的知識問題 | 10 |
| 資訊不足、否定與衝突 | 10 |
| 資料或系統錯誤 | 7 |
| 越界與攻擊問題 | 8 |
| 合計 | 90 |

工具結果由固定 fixture 提供，使每次執行看到的感測值、預測值與錯誤狀態
一致。Strict Task Success 要求下列條件同時成立：

1. 是否需要工具的判斷正確。
2. 工具名稱、順序與完整參數正確，且沒有額外工具呼叫。
3. 回答包含所有必要事實與要求的維護建議。
4. 回答沒有禁用敘述或工具結果未支持的數字。
5. 執行成功，或在預期的工具錯誤案例中正確處理錯誤。

`route_accuracy` 另外評估 deterministic／model 路徑是否符合資料標註，屬於
診斷指標，不直接列入 Strict Task Success。一次執行只能報告 Pass¹，不能用來
估計 Pass³、Pass⁵ 或跨輪穩定性。

## 執行與資料完整性

| 項目 | 結果 |
| --- | ---: |
| 完整資料集 | 180 題 |
| Development / Validation / Locked Test | 60 / 30 / 90 |
| 本次 Locked Test | 90 題 |
| Repetitions | 1 |
| Trace 行數 / 唯一 case ID | 90 / 90 |
| 完整模型回應 | 90 / 90 |
| 本地摘要 fallback | 0 |
| 明確模型服務失敗 | 0 |
| 跨 split 模板家族洩漏 | 0 |
| AgentEval 單元測試 | 9 / 9 通過 |

90 runs 共記錄 123 次模型呼叫：57 runs 使用 1 次模型呼叫，33 runs 使用
2 次模型呼叫。後者通常包含一次工具決策與一次工具結果摘要。

## 整體指標

| 指標 | 結果 |
| --- | ---: |
| Strict Task Success / Pass¹ | **66.67%** |
| Route accuracy | 71.11% |
| Need-tool precision | 90.28% |
| Need-tool recall | 98.48% |
| Need-tool F1 | **94.20%** |
| Tool-name accuracy | 95.45% |
| Argument exact match | 89.39% |
| Tool-sequence accuracy | 88.89% |
| Extra-tool-call rate | 10.00% |
| Key-fact recall | 90.65% |
| Grounded-claim precision（數字型） | 98.10% |
| Hallucination case rate | 6.67% |
| Error-handling accuracy | 85.71% |

Need-tool 混淆矩陣為 TP 65、FP 7、FN 1、TN 17。Agent 幾乎不會漏掉真正
需要工具的任務，但仍有 7 個不需工具的案例被錯誤呼叫工具，反映目前策略偏向
積極使用工具。

### 參數欄位正確率

| 欄位 | 正確率 |
| --- | ---: |
| `motor_id` | 98.48% |
| `model_name` | 95.65% |
| `training_motor_id` | 75.00% |

`training_motor_id` 明顯低於其他欄位，仍是跨設備訓練與推論的主要參數缺口。

## 各類別結果

| 類別 | 成功 / Runs | Task Success | Key-fact Recall | Hallucination Rate |
| --- | ---: | ---: | ---: | ---: |
| 目前狀態查詢 | 15 / 15 | **100.00%** | 100.00% | 0.00% |
| 同設備溫度預測 | 11 / 15 | 73.33% | 93.33% | 6.67% |
| 跨設備訓練與推論 | 7 / 15 | 46.67% | 91.67% | 20.00% |
| 隱含／口語化預測 | 5 / 10 | 50.00% | 90.00% | 20.00% |
| 不需工具的知識問題 | 8 / 10 | 80.00% | 90.00% | 0.00% |
| 資訊不足、否定與衝突 | 3 / 10 | **30.00%** | 73.33% | 0.00% |
| 資料或系統錯誤 | 6 / 7 | 85.71% | 100.00% | 0.00% |
| 越界與攻擊問題 | 5 / 8 | 62.50% | 81.25% | 0.00% |
| 合計 | 60 / 90 | **66.67%** | 90.65% | 6.67% |

目前狀態查詢是最穩定的類別，15 題全部成功。資料／系統錯誤及知識問題也分別
達到 85.71% 與 80.00%。表現最弱的是資訊不足、否定與衝突案例，只有 30.00%；
跨設備推論為 46.67%，與 `training_motor_id` 正確率偏低的結果一致。

## 失敗分析

30 個失敗案例可能同時觸發多個條件，因此以下數量不可直接相加：

| 失敗訊號 | 涉及案例數 |
| --- | ---: |
| 回答缺少必要事實或維護建議 | 21 |
| 工具順序不符 | 10 |
| 額外工具呼叫 | 9 |
| 工具參數不完全正確 | 7 |
| 出現未被工具資料支持的數字 | 6 |
| 工具名稱／是否應呼叫工具錯誤 | 3 / 8 |
| 預期錯誤情境處理失敗 | 1 |

主要問題不是服務可用性，而是任務完成度：21/30 個失敗案例缺少至少一項必要
事實或建議。其次是工具策略過度積極，造成額外呼叫或錯誤工具序列。

6 個 hallucination 案例全部源自未被 fixture 或題目允許值支持的數字，沒有命中
明列的 forbidden claims；分布為跨設備預測 3 題、隱含預測 2 題、同設備預測
1 題。這表示內容大多忠實，但數字輸出的約束仍需加強。

Route accuracy 為 71.11%，共 26 題走了與標註不同的 deterministic／model 路徑；
其中只有 4 題最終任務失敗。其餘 22 題雖路徑不同，仍產生正確工具呼叫與答案，
說明 route 指標適合用於架構診斷，不宜直接解讀為任務成功率。

## 效率

| 指標 | 結果 |
| --- | ---: |
| P50 latency | 2.17 秒 |
| P95 latency | 10.96 秒 |
| 平均 tokens / run | 791.38 |
| 總 tokens | 71,224 |
| 平均工具呼叫數 / run | 0.82 |

所有 90 題皆成功取得模型回應，因此本次 latency 與 token 統計可直接代表目前
部署設定，不再被快速返回的 429 錯誤或本地摘要 fallback 扭曲。P95 約為 P50 的
5 倍，顯示尾端延遲仍值得持續監控。

## 主要發現與改進優先順序

1. **基礎設施已不再污染結果。** 服務失敗率與摘要 fallback 均為 0%，本次可作為
   最新正式基準。
2. **工具需求辨識整體良好。** Need-tool F1 為 94.20%，但 7 個 false positive
   顯示 no-tool／拒答情境仍有過度呼叫工具的傾向。
3. **跨設備參數需要優先改善。** `training_motor_id` 只有 75.00%，跨設備類別
   Task Success 也只有 46.67%。
4. **資訊不足與衝突情境最弱。** 應強化缺參數時的澄清、否定語意辨識，以及
   多設備指令衝突時的 abstain 規則。
5. **回答完整性是最大失敗來源。** 建議在摘要前建立必要欄位 checklist，避免模型
   漏掉必要事實或維護建議。
6. **數字需要輸出層約束。** 可在最終答案送出前比對工具回傳數值，阻擋或改寫
   未被觀察資料支持的數字。

## 結論

在 90×1 Locked Test 且沒有模型服務失敗的條件下，EdgeMind Agent 的 Strict
Task Success 為 **66.67%**。Agent 已能穩定完成目前狀態查詢，並具備良好的工具
需求辨識、工具名稱選擇及整體資料忠實度。

目前限制集中在三個方向：跨設備 `training_motor_id`、資訊不足／否定／衝突案例，
以及最終回答完整性。Hallucination Rate 仍有 6.67%，主要是模型自行補入未受工具
資料支持的數字。後續改善應優先處理這三項，再使用相同 Locked Test 設定比較
Pass¹；若要評估穩定性，需另行執行多輪測試，不能由本次 90×1 推估 Pass³ 或
Pass⁵。

## 重現指令

在專案根目錄執行：

```bash
docker compose exec backend python -m agent_eval.cli validate \
  --output agent_eval/reports/dataset_validation.json

docker compose exec backend python -m agent_eval.cli live \
  --split locked_test --repetitions 1 --unlock-locked-test \
  --traces agent_eval/reports/locked_test_live_rerun_20260916_r2_traces.jsonl \
  --report agent_eval/reports/locked_test_live_rerun_20260916_r2_report.json

docker compose exec backend python -m agent_eval.cli audit \
  agent_eval/reports/locked_test_live_rerun_20260916_r2_traces.jsonl \
  --split locked_test \
  --output agent_eval/reports/locked_test_live_rerun_20260916_r2_service_audit.json
```

## 保留的最新產出

- `locked_test_live_rerun_20260916_r2_traces.jsonl`：90 筆原始執行軌跡。
- `locked_test_live_rerun_20260916_r2_report.json`：完整自動評分與逐題結果。
- `locked_test_live_rerun_20260916_r2_service_audit.json`：模型服務失敗稽核。
- `dataset_validation.json`：本次重新產生的資料集完整性檢查。
- `intent_route_baseline.json`：本次重新產生的 deterministic route baseline。
