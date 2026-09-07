# 代表候補8件：違反説明の人手レビュー票

## 目的と範囲

前提条件チェックの説明文が、説明対象時点のVH状態と対応しているかを確認する。これは人間性能実験ではなく、著者による少数ケースの内容確認である。候補の選定情報や機械ラベルを先に見ず、まずログの状態と説明文を確認してから採点する。

## 手順

1. `selection.csv` の `run_id` と `step` から対象の `events.jsonl` を開く。
2. 対象stepの `precondition` イベントで、LLMの説明文（`response`）を読む。
3. 同じstepの `extracted_knowledge` グラフと、直前の完全グラフを確認する。必要なら `execution_labels.csv` の前後グラフも参照する。
4. 説明文の各主張を、状態グラフにある事実・条件辞書と照合する。推測で補わない。
5. 次のラベルを1つ選び、根拠を記入する。

## ラベル

- `正しい`: 主要な違反／充足主張が状態と一致し、重要な見落としがない。
- `一部正しい`: 一部の主張は一致するが、重要な条件の誤り・見落としがある。
- `誤り`: 中心となる理由が状態と反対、または存在しない事実に基づく。
- `判断不能`: 応答が短すぎる、状態情報が不足する、または主張を検証できない。

## 記入欄

| No. | run_id | step | action | ラベル | 状態と照合した根拠 | 評価者 | 評価日 |
|---:|---|---:|---|---|---|---|---|
| 1 | state_change_task_test_task6_C1_llm_precheck_gpt-4o-2024-08-06_r0 | 4 | SWITCHON lightswitch 261 |  |  |  |  |
| 2 | state_change_task_test_task6_C1_llm_precheck_gpt-4o-mini-2024-07-18_r0 | 4 | SWITCHON lightswitch 261 |  |  |  |  |
| 3 | state_change_task_test_task6_R_fixed_gpt-4o-2024-08-06_r0 | 1 | SWITCHON lightswitch 261 |  |  |  |  |
| 4 | placement_task_test_task1_R_fixed_gpt-4o-mini-2024-07-18_r1 | 7 | PUTIN cupcake 195 → kitchencounter 238 |  |  |  |  |
| 5 | placement_task_test_task1_R_random_gpt-4o-mini-2024-07-18_r2 | 2 | OPEN desk 108 |  |  |  |  |
| 6 | placement_task_test_task65_C1_llm_precheck_gpt-4o-2024-08-06_r0 | 2 | OPEN fridge 103 |  |  |  |  |
| 7 | placement_task_test_task65_C1_llm_precheck_gpt-4o-mini-2024-07-18_r0 | 1 | WALK kitchencounter 92 |  |  |  |  |
| 8 | placement_task_test_task65_R_fixed_gpt-4o-2024-08-06_r0 | 2 | OPEN fridge 103 |  |  |  |  |

採点後、この表を `human_review_completed.csv` として保存し、評価者名（または匿名表記）と日付を記入する。未記入欄は未評価として扱う。
