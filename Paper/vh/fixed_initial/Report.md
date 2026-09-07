# VH小規模比較実験の結果

比較エピソードは予定24件中24件完了。対象4件、2モデル、3条件、各1反復。

## 参照行動列の再生

| 種別 | ID | 参照長 | 成功行動数 | 結果 | 最終ゴール |
| --- | --- | ---: | ---: | --- | --- |
| placement_task | test_task1 | 8 | 3 | Reference Failure | False |
| placement_task | test_task65 | 9 | 9 | Reference Success | True |
| state_change_task | test_task1 | 0 | 0 | Reference Success | True |
| state_change_task | test_task6 | 4 | 4 | Reference Success | True |

配置test_task1の参照列は4手目のPUTで失敗。元の位置指定の予備実験では別途PUTBACKも同じ物体・配置先で失敗した。保持・近接を満たすだけではこの配置が実行できると保証できない。
この例は除外して隠さず診断対象として残す。参照列が全件再現できたとは主張せず、参照再生成功3件のみの集計も分ける。

## 比較（全4件、参照失敗例を含む診断集計）

| モデル | 条件 | n | 元の成功判定 | 最終ゴール充足 | 平均保存行動数 | 失敗実行数 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| gpt-4o-2024-08-06 | C0_no_precheck | 4 | 3 | 3 | 4.25 | 1 |
| gpt-4o-mini-2024-07-18 | C0_no_precheck | 4 | 2 | 2 | 3.50 | 1 |
| gpt-4o-2024-08-06 | C1_llm_precheck | 4 | 3 | 3 | 4.25 | 1 |
| gpt-4o-mini-2024-07-18 | C1_llm_precheck | 4 | 3 | 3 | 3.25 | 1 |
| gpt-4o-2024-08-06 | C2_symbolic_precheck | 4 | 3 | 3 | 5.00 | 1 |
| gpt-4o-mini-2024-07-18 | C2_symbolic_precheck | 4 | 1 | 1 | 3.25 | 2 |

平均保存行動数は成功・失敗を含み、失敗した最後の実行は含まない。短い失敗を効率改善と解釈しない。
状態変化test_task1は参照長0の終了判定例。単一試行の小標本であり、統計的有意差や全415タスクへの一般化は主張しない。

## 初期条件の照合

C0との記号状態一致は24/24件（C0自身を含む）。
完全グラフ一致は22/24件。
initial_comparability.csvに全対象・モデル・条件の一致判定と全ノード位置の最大差を保存した。記号状態の一致だけでは物理状態の同一性は保証しない。
この追加試行は人物位置を指定し直した新しい設定であり、過去実験や元の部屋指定の試行を置き換えない。各条件はAPI呼出前に参照の記号状態一致・全ノード位置差0.001以下・四元数距離0.0001以下を検査した。物理エンジンやLLM応答の完全決定性は保証しない。
C0以外の条件で位置・向き・記号状態の基準を満たす比較は16/16件。

## 判定・実行ログ

precondition_labels.csvは実際のC1候補に対する、抽出知識上のJSON条件ラベルとLLM応答。unknownは二値精度から除く。
termination_labels.csvは各時点の完全グラフと元のEnd完全一致判定を照合する。execution_labels.csvは実行した行動に限ったVHラベルであり、棄却した候補の実行可能性を捏造しない。
C2のラベル生成器と同じ規則を診断に使うため、C2自身の正解率によって規則の妥当性を立証しない。

precondition_metrics.csvにC1の混同行列・適合率・再現率・誤受理率・誤棄却率、termination_metrics.csvに全途中時点の終了判定の混同行列相当の件数を保存した。
changed_action_metrics.csvは候補と異なる行動を実行した場合だけの集計であり、同じ文字列を返した再生成は含まない。違反説明の意味的正しさや棄却候補の反実仮想実行は未評価。

## 費用・範囲

API成功要求274件、失敗0件。入力87434tokens、出力1726tokens。
成功要求の通常単価による推定費用は0.136771米ドル（キャッシュ割引を適用しない推定、請求確定額ではない）。
通信障害で中断した試行のAPI要求も費用に含む。episodes.csvのapi_requests_in_prior_incomplete_attemptsで完了試行以前の要求を区別する。中断したVH要求は実行成否が未確定のため実行ラベルの分母に含めない。
[GPT-4o料金](https://developers.openai.com/api/docs/models/gpt-4o)、[GPT-4o mini料金](https://developers.openai.com/api/docs/models/gpt-4o-mini)。

原稿のモデルID、元のMulti計画ループ・プロンプト・上限判定を使用するが、現在の依存版とWindows VHによる新しい試行であり、過去結果の完全再現ではない。
C3/C4/C5、検索条件を変えた実行比較、全件・複数反復、人間評価は未実施。TeXは実行していない。詳細は[README.md](../README.md)。ケース説明案は[Cases.md](../Cases.md)。
