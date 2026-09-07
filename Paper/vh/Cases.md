# VHログからの代表ケース説明案

これはAIがデータと生ログを照合して作成し、2026-09-06にユーザーが内容を確認したケース説明である。確認者の氏名は未提供。人間性能評価ではない。4件は論点を示す目的選択であり、統計的代表標本ではない。必要な判断と参照手順を説明するが、最短性は主張しない。以下のLLM観測は特記以外 `fixed_initial/runs/` の新しい試行である。

## 1. 行動をしない判断：状態変化test_task1

- 指示：`Turn on all lightswitches`、scene 1、初期部屋livingroom。
- 初期条件とゴール：ID 71・173・261・427がすべてON。参照列は0行動。
- 必要な判断：対象全体が初期状態ですでにゴールを満たすことを確認して終了する。指示に動詞があるだけで不要な操作を始めない。
- 観測：参照と6条件すべてで最終ゴールを満たして終了した。元の計画ループの参照長0特例を保持しており、通常の行動上限と同一の処理とは説明しない。
- 難しい点：タスク名だけでは行動の要否が分からず、初期状態の照合が必要。ゼロ長に対して実行長／参照長を計算しない。
- 根拠：[入力JSON](../../dataset/state_change_task/test.json)、[固定位置C0・mini結果](fixed_initial/runs/state_change_task_test_task1_C0_no_precheck_gpt-4o-mini-2024-07-18/result.json)、同フォルダのeventsと完全グラフ。他条件はepisodes.csvから追跡できる。

## 2. 前提条件を満たす行動とゴール達成の違い：状態変化test_task6

- 指示：同じく `Turn on all lightswitches`、scene 1、初期部屋kitchen。
- 初期条件：71・261はON、173・427はOFF。必要な手順は173へ移動→ON、427へ移動→ON（参照4行動）。すでにONの対象を再操作する必要はない。
- 必要な判断：複数の対象IDを区別し、未達成の対象だけを追跡する。移動の前提条件が満たされていても、その移動がタスクを進めるとは限らない。
- 観測：C2・miniは `WALK 173 → SWITCHON 173 → WALK 261` の3行動をすべてVHで成功させた。ステップ4でLLMがEndを返したが、完全グラフのゴール充足は `[true, true, true, false]` で、427が未達。終了判定の誤りとして直接確認できる。
- 制約：この試行ではC2の前提条件検査は3候補すべてtrueで再生成していない。したがって「記号検証が誤終了を発生させた」とは言えない。1反復のLLM出力差を機構の安定した効果と解釈しない。
- 根拠：[C2・mini結果](fixed_initial/runs/state_change_task_test_task6_C2_symbolic_precheck_gpt-4o-mini-2024-07-18/result.json)、[各ステップのログ](fixed_initial/runs/state_change_task_test_task6_C2_symbolic_precheck_gpt-4o-mini-2024-07-18/events.jsonl)。該当完全グラフはログのgraph_fileを参照。

## 3. 条件辞書とシミュレータ実行可能性の違い：配置test_task1

- 指示：`Put all cupcakes on the kitchencounter`、scene 1、初期部屋bathroom。
- ゴール：cupcake 195・196の両方からkitchencounter 238へのON関係。参照は各物体について移動→把持→配置先へ移動→PUT、計8行動。
- 必要な判断：2個を別々に追跡し、把持・配置先への近接・物体を扱える操作かを確認する。指示の「all」を1個の配置だけで満たしたと判断しない。
- 参照再生の観測：元の部屋指定・固定位置の両方で最初の3行動は成功し、4手目のPUT 195→238でVHが実行失敗を返した。元の試行の診断ではPUTBACKも同じ物体・配置先で失敗した。保持・近接の関係は確認できるが、失敗の物理的原因はVHの一般的なエラーだけから特定しない。PUTの名称だけが原因とも断定しない。
- LLMの観測：固定位置C1・miniは `WALK desk 108` の後、候補 `OPEN desk 108` をNoと判定し、`OPEN cupcake 195` へ再生成した。後者のJSON条件はunknownで、VHはcupcakeを操作対象として選択できない旨を返して失敗した。元実装どおり再生成後の再検証は行っていない。候補のJSON条件がtrueでも、物体の操作適合性まで証明されたわけではないため、NoをVHに対する誤棄却とは呼ばない。
- 制約：参照再生失敗例を含むため、参照成功3件のみの集計と全4件の診断集計を区別する。失敗した元候補は同一状態のコピーで実行していない。PUTBACK試行も直前の失敗で姿勢等が変化し得るため厳密な同一状態対照ではない。
- 根拠：[固定位置参照結果](fixed_initial/runs/placement_task_test_task1_reference_reference/result.json)、[C1・miniログ](fixed_initial/runs/placement_task_test_task1_C1_llm_precheck_gpt-4o-mini-2024-07-18/events.jsonl)、[操作名の診断ログ](diagnostics/put_alias_after_reference_failure/)。

## 4. 容器操作と残り対象の管理：配置test_task65

- 指示：`Put all plums in the fridge`、scene 4、初期部屋bedroom。fridge 103は初期CLOSED。
- ゴール：plum 53・54の両方からfridge 103へのINSIDE関係。参照は53へ移動→把持→冷蔵庫へ移動→OPEN→PUTIN、54へ移動→把持→冷蔵庫へ移動→PUTINの9行動で、両方の初期化方式で再生成功した。
- 必要な判断：対象の位置、現在の保持物、容器の開閉、まだ入れていない対象を分けて追跡する。最後に冷蔵庫を閉めることはこのJSONゴールには含まれない。参照にない制約を評価時だけ追加しない。
- LLMの観測：固定位置C0・miniは7行動後にEndを返した。plum 53は冷蔵庫内だが、54は右手で保持したままで、最終ゴールは `[true, false]`。終了判定に渡した自然言語にも54を保持している旨が残っており、このケースを「必要な保持情報がすべて抽出段階で消えた」とは説明できない。
- 実行ラベルの注意：同じC0試行ではOPENを行わずPUTIN 53がVHで成功し、後続グラフで53のINSIDEが確認された一方、103の状態はCLOSEDだった。条件辞書の「容器がCLOSEDでない」とVHの返す成功ラベルは同一の判定ではない。全操作・全シーンに一般化せず、このログでの相違として扱う。
- 根拠：[入力JSON](../../dataset/placement_task/test.json)、[C0・mini結果](fixed_initial/runs/placement_task_test_task65_C0_no_precheck_gpt-4o-mini-2024-07-18/result.json)、[終了時入力・実行前後グラフへの参照](fixed_initial/runs/placement_task_test_task65_C0_no_precheck_gpt-4o-mini-2024-07-18/events.jsonl)。

## 内容確認の記録

2026-09-06、確認者：ユーザー（氏名未提供）。本会話で「Cases.mdの内容確認しました。」との確認を受けた。対象は上記4ケースの内容。修正指摘はなかったため、ケース本文は変更していない。これは説明内容の確認であり、ユーザー自身がVHを再実行した、動画を全件確認した、または人間の成功率を測定したとは解釈しない。本文・回答書への反映は別途追跡する。
