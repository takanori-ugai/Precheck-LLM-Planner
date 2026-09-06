# 既存実験結果の再集計（手順2）

本資料は既存JSONの分析と検索のオフライン再構成である。新しいタスク実行実験ではない。

## データセット

| タスク | 集合 | 件数 | タスク名数 | 参照長0 | 参照平均長 | 中央値 | 最小 | 最大 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| state_change_task | test | 312 | 6 | 27 | 3.872 | 4.000 | 0 | 10 |
| state_change_task | example | 152 | 6 | 32 | 2.368 | 2.000 | 0 | 8 |
| placement_task | test | 103 | 38 | 2 | 9.175 | 8.000 | 0 | 25 |
| placement_task | example | 51 | 19 | 0 | 13.471 | 8.000 | 4 | 53 |

## 論文表1・表2の再現

全18行×5指標（90値）が本文と小数第3位で一致。詳細は `paper_table_checks.csv`。

| タスク | 手法 | N | 成功数 | SR | AEFR | FRRMA | ETFR | Average Steps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| state_change_task | baseline/gpt-4o | 312 | 10 | 0.032 | 0.000 | 0.535 | 0.433 | 10.481 |
| state_change_task | single-prompt/gpt-4o-mini/precheck | 312 | 195 | 0.625 | 0.026 | 0.231 | 0.119 | 4.747 |
| state_change_task | single-prompt/gpt-4o/precheck | 312 | 246 | 0.788 | 0.016 | 0.173 | 0.022 | 4.381 |
| state_change_task | multi-prompts/gpt-4o-mini/precheck | 312 | 234 | 0.750 | 0.045 | 0.183 | 0.022 | 4.917 |
| state_change_task | multi-prompts/gpt-4o/precheck | 312 | 279 | 0.894 | 0.019 | 0.000 | 0.087 | 3.391 |
| state_change_task | single-prompt/gpt-4o-mini/no-precheck | 312 | 192 | 0.615 | 0.003 | 0.253 | 0.128 | 4.872 |
| state_change_task | single-prompt/gpt-4o/no-precheck | 312 | 237 | 0.760 | 0.016 | 0.189 | 0.035 | 4.449 |
| state_change_task | multi-prompts/gpt-4o-mini/no-precheck | 312 | 217 | 0.696 | 0.016 | 0.253 | 0.035 | 5.080 |
| state_change_task | multi-prompts/gpt-4o/no-precheck | 312 | 272 | 0.872 | 0.010 | 0.016 | 0.103 | 3.478 |
| placement_task | baseline/gpt-4o | 103 | 0 | 0.000 | 0.010 | 0.573 | 0.417 | 15.398 |
| placement_task | single-prompt/gpt-4o-mini/precheck | 103 | 48 | 0.466 | 0.146 | 0.029 | 0.359 | 7.282 |
| placement_task | single-prompt/gpt-4o/precheck | 103 | 76 | 0.738 | 0.117 | 0.029 | 0.117 | 8.078 |
| placement_task | multi-prompts/gpt-4o-mini/precheck | 103 | 42 | 0.408 | 0.117 | 0.029 | 0.447 | 6.447 |
| placement_task | multi-prompts/gpt-4o/precheck | 103 | 84 | 0.816 | 0.117 | 0.019 | 0.049 | 8.272 |
| placement_task | single-prompt/gpt-4o-mini/no-precheck | 103 | 49 | 0.476 | 0.117 | 0.019 | 0.388 | 6.592 |
| placement_task | single-prompt/gpt-4o/no-precheck | 103 | 70 | 0.680 | 0.165 | 0.029 | 0.126 | 7.320 |
| placement_task | multi-prompts/gpt-4o-mini/no-precheck | 103 | 45 | 0.437 | 0.126 | 0.010 | 0.427 | 6.136 |
| placement_task | multi-prompts/gpt-4o/no-precheck | 103 | 82 | 0.796 | 0.117 | 0.029 | 0.058 | 7.767 |

## 成功・失敗別の行動列長

参照平均も同じ成功／失敗集合で計算。空集合は「—」。全ての分位点・標準偏差・比率は `lengths_by_outcome.csv`。

| タスク | 手法 | 集合 | N | 保存平均長 | 参照平均長 | 平均差 |
| --- | --- | --- | --- | --- | --- | --- |
| state_change_task | baseline/gpt-4o | success | 10 | 0 | 0 | 0 |
| state_change_task | baseline/gpt-4o | failure | 302 | 10.828 | 4 | 6.828 |
| state_change_task | single-prompt/gpt-4o-mini/precheck | success | 195 | 3.969 | 3.662 | 0.308 |
| state_change_task | single-prompt/gpt-4o-mini/precheck | failure | 117 | 6.043 | 4.222 | 1.821 |
| state_change_task | single-prompt/gpt-4o/precheck | success | 246 | 3.923 | 3.927 | -0.004 |
| state_change_task | single-prompt/gpt-4o/precheck | failure | 66 | 6.091 | 3.667 | 2.424 |
| state_change_task | multi-prompts/gpt-4o-mini/precheck | success | 234 | 4.179 | 3.735 | 0.444 |
| state_change_task | multi-prompts/gpt-4o-mini/precheck | failure | 78 | 7.128 | 4.282 | 2.846 |
| state_change_task | multi-prompts/gpt-4o/precheck | success | 279 | 3.584 | 3.878 | -0.294 |
| state_change_task | multi-prompts/gpt-4o/precheck | failure | 33 | 1.758 | 3.818 | -2.061 |
| state_change_task | single-prompt/gpt-4o-mini/no-precheck | success | 192 | 4.203 | 3.792 | 0.411 |
| state_change_task | single-prompt/gpt-4o-mini/no-precheck | failure | 120 | 5.942 | 4 | 1.942 |
| state_change_task | single-prompt/gpt-4o/no-precheck | success | 237 | 3.979 | 3.932 | 0.046 |
| state_change_task | single-prompt/gpt-4o/no-precheck | failure | 75 | 5.933 | 3.680 | 2.253 |
| state_change_task | multi-prompts/gpt-4o-mini/no-precheck | success | 217 | 4.558 | 4.028 | 0.530 |
| state_change_task | multi-prompts/gpt-4o-mini/no-precheck | failure | 95 | 6.274 | 3.516 | 2.758 |
| state_change_task | multi-prompts/gpt-4o/no-precheck | success | 272 | 3.673 | 3.882 | -0.210 |
| state_change_task | multi-prompts/gpt-4o/no-precheck | failure | 40 | 2.150 | 3.800 | -1.650 |
| placement_task | baseline/gpt-4o | success | 0 | — | — | — |
| placement_task | baseline/gpt-4o | failure | 103 | 15.398 | 9.175 | 6.223 |
| placement_task | single-prompt/gpt-4o-mini/precheck | success | 48 | 8.625 | 8.771 | -0.146 |
| placement_task | single-prompt/gpt-4o-mini/precheck | failure | 55 | 6.109 | 9.527 | -3.418 |
| placement_task | single-prompt/gpt-4o/precheck | success | 76 | 8.868 | 9.329 | -0.461 |
| placement_task | single-prompt/gpt-4o/precheck | failure | 27 | 5.852 | 8.741 | -2.889 |
| placement_task | multi-prompts/gpt-4o-mini/precheck | success | 42 | 7.929 | 8.548 | -0.619 |
| placement_task | multi-prompts/gpt-4o-mini/precheck | failure | 61 | 5.426 | 9.607 | -4.180 |
| placement_task | multi-prompts/gpt-4o/precheck | success | 84 | 8.976 | 9.333 | -0.357 |
| placement_task | multi-prompts/gpt-4o/precheck | failure | 19 | 5.158 | 8.474 | -3.316 |
| placement_task | single-prompt/gpt-4o-mini/no-precheck | success | 49 | 7.490 | 8.286 | -0.796 |
| placement_task | single-prompt/gpt-4o-mini/no-precheck | failure | 54 | 5.778 | 9.981 | -4.204 |
| placement_task | single-prompt/gpt-4o/no-precheck | success | 70 | 8.671 | 9.029 | -0.357 |
| placement_task | single-prompt/gpt-4o/no-precheck | failure | 33 | 4.455 | 9.485 | -5.030 |
| placement_task | multi-prompts/gpt-4o-mini/no-precheck | success | 45 | 7.578 | 8.400 | -0.822 |
| placement_task | multi-prompts/gpt-4o-mini/no-precheck | failure | 58 | 5.017 | 9.776 | -4.759 |
| placement_task | multi-prompts/gpt-4o/no-precheck | success | 82 | 8.390 | 9.305 | -0.915 |
| placement_task | multi-prompts/gpt-4o/no-precheck | failure | 21 | 5.333 | 8.667 | -3.333 |

## 前提条件検証の対応比較

| タスク | 提示 | モデル | 失敗→成功 | 成功→失敗 | SR差 pp | 95%区間下限 | 95%区間上限 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| state_change_task | single-prompt | gpt-4o-mini | 34 | 31 | 0.962 | -4.545 | 5.593 |
| state_change_task | single-prompt | gpt-4o | 26 | 17 | 2.885 | 0.658 | 10.000 |
| state_change_task | multi-prompts | gpt-4o-mini | 48 | 31 | 5.449 | -5.000 | 14.706 |
| state_change_task | multi-prompts | gpt-4o | 12 | 5 | 2.244 | 0.938 | 6.944 |
| placement_task | single-prompt | gpt-4o-mini | 6 | 7 | -0.971 | -8.547 | 7.059 |
| placement_task | single-prompt | gpt-4o | 12 | 6 | 5.825 | -2.858 | 13.979 |
| placement_task | multi-prompts | gpt-4o-mini | 6 | 9 | -2.913 | -9.303 | 4.651 |
| placement_task | multi-prompts | gpt-4o | 6 | 4 | 1.942 | -4.168 | 7.619 |

## 検索類似度（新しく再構成した検索）

| タスク | 重み | N | 平均cosine | 最小 | 最大 | 対象一致率 | 操作一致率 | 配置先一致率 | 同点件数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| state_change_task | task_name | 6 | 0.678 | 0.499 | 0.910 | 0.333 | 0.667 | 1 | 0 |
| state_change_task | instance | 312 | 0.624 | 0.499 | 0.910 | 0.103 | 0.897 | 1 | 0 |
| placement_task | task_name | 38 | 0.782 | 0.640 | 0.901 | 0.868 | 0.711 | 0.132 | 0 |
| placement_task | instance | 103 | 0.781 | 0.640 | 0.901 | 0.893 | 0.544 | 0.107 | 0 |

状態変化の配置先は両方空欄のため一致率1となるが、配置先検索の性能指標ではない。

### 再構成された検索の具体例

| テスト指示 | 採択事例 | 事例ID | cosine | 事例列長 | 操作一致 |
| --- | --- | --- | --- | --- | --- |
| Turn off all computers | Turn on all computers | example_task12 | 0.859 | 4 | False |
| Turn off all lightswitches | Turn off all candles | example_task81 | 0.585 | 6 | True |
| Turn off all tablelamps | Turn on all tablelamps | example_task76 | 0.910 | 6 | False |
| Turn off all tvs | Turn off all cellphones | example_task21 | 0.499 | 8 | True |
| Turn on all lightswitches | Turn on all tablelamps | example_task76 | 0.611 | 6 | True |
| Turn on all tvs | Turn on all computers | example_task12 | 0.602 | 4 | True |
| Put all bananas in the fridge | Put all bananas on the kitchentable | example_task2 | 0.776 | 12 | False |
| Put all cupcakes on the kitchencounter | Put all cupcakes on the kitchentable | example_task1 | 0.854 | 8 | True |
| Put all plums in the fridge | Put all plums on the kitchentable | example_task4 | 0.761 | 8 | False |

状態変化では `Turn off all computers` と `Turn off all tablelamps` に、同じ対象をONにする事例が選ばれた。高いcosineは操作の一致を保証しない。配置ではテスト件数で重み付けすると対象一致率は約89.3%だが、配置先一致率は約10.7%。これらは検索の正解率ではなく、選択事例と共有する構造の記述である。

## 集計の定義と解釈

- 分母は状態変化312件、配置103件。SRと3失敗率は全件を分母とする。保存の全タスクID・ラベル・score・列長の整合性を検証した。
- `attempts` は全保存結果で行動列長と等しい。公開提案実装では成功した実行のみが列に追加される。最後の失敗試行、再生成、LLM呼び出し数を含まない。ベースラインの保存規則の詳細は未回収。
- 参照列は最短解ではない。失敗時は早期終了で短くなるため、短さを効率の改善と解釈しない。差・比は成功集合での解釈を主とする。
- `length_ratio` は参照長が正のときのみ定義する。参照長0の状態変化27件、配置2件は独立集計。初期充足は参照長0からの代理分類で、完全な初期グラフによる再検証ではない。
- ベースラインの状態変化成功10件はすべて参照長0。非ゼロ285件の成功は0。配置ベースライン成功は0。
- 分位点は線形補間（type 7）、標準偏差は標本標準偏差（n−1）。n=0の統計量とn<2の標準偏差は空欄。比の分母数もCSVに保存する。
- 手法間の共通成功集合を全組合せで比較し `common_success_comparisons.csv` に出力した。選択バイアスを完全には除けない。
- 信頼区間はタスク名を単位とするクラスター・ブートストラップ4000回、seed=20260906、百分位法95%。抽出された各クラスターの全インスタンスを保持してmicro SRを計算。対応比較では条件間で同じタスクを再標本化する。
- 同じシーンによる依存、少数クラスター（状態変化6名）、反復実験の欠如はこの区間では解消しない。モデルの実行間変動は推定していない。p値や因果効果は主張しない。タスク名マクロ平均は `metrics.csv`。
- 同名タスクは両集合で重複0だが、シーン1～7・操作構造は共有する。未知家屋汎化を測る評価ではない。網羅表は観測された組合せのみ。
- 検索は元のエンコーダ名とcosineを使い、名前ごとの上位1件→同名の最長列（長さ同点はJSONの先頭）を選択。候補名はソートして同点時の選択を決定的にした。元コードのset順序、実験時の重み版・実行依存関係は不明。
- `retrieval_scores.json` に重みハッシュ・版・依存関係と全候補スコアを保存。これは過去の検索ログではない。検索条件別SRも再構成結果との記述的な関連で、検索の正解率や因果的寄与ではない。
- `repeated_action_occurrences` は同一文字列の2回目以降の数であり、必要な反復も含む。冗長行動の正解ラベルではない。

個別事例は [Cases.md](Cases.md)、来歴・未回収項目は [Evidence.md](Evidence.md)、再実行手順は [README.md](README.md)。
