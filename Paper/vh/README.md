# VHログ付き小規模実験

## 現在の状態

2026-09-06にWindows側の起動済みVH（WSLホスト `172.26.224.1:8080`）で実施。**元の部屋指定による参照4件と比較24件は完了**した。参照列は3/4成功、比較のAPI成功要求は240件、推定費用0.1038423米ドル。結果は [Report.md](Report.md)。人物の初期位置が条件ごとに異なったため、この試行だけで機構の因果効果を主張しない。

**固定位置の参照4件・比較24件も完了**し、別設定の試行として `fixed_initial/` に保存した。24条件すべて開始状態の照合基準を通過した。完了件数は [fixed_initial/completion.json](fixed_initial/completion.json)、結果は [fixed_initial/Report.md](fixed_initial/Report.md)。両試行は合算して1つの性能値にはしない。本文の過去結果は変更していない。

VH関連の合計は比較48件・参照8件、API成功514要求・失敗0要求、入力165,418tokens・出力3,373tokens。推定費用0.24061365米ドル（通常単価、キャッシュ割引なし、中断試行の2要求を含む）。以前の非VH評価の費用は含めない。48件のオフラインテストが成功した。

4件の必要な判断・参照手順・難しい点と、実行ログから確認できた事象は [Cases.md](Cases.md)。2026-09-06にユーザーが説明内容を確認済み。確認者の氏名は未提供であり、[確認記録](author_confirmation.json)に範囲と確認対象のハッシュを保存した。人間性能実験とは扱わない。

## 接続・録画の障害と復旧記録

最初はシーン初期化前のグラフ取得でVH内部の `NullReferenceException` が発生し、後続のシーンリセットも応答しなくなった。ユーザーによる再起動後に参照再生・比較を実施した。この通信障害はタスク失敗率として数えない。

最初の接続確認の順序に問題があった。`scripts/vh_experiment.py` のprobeをidleだけに修正し、グラフ取得は `reset(scene - 1)` による初期化成功後にのみ行う。失敗した要求は `probe/simulator_rpc.jsonl.gz` と各runのログに保存し、再試行時も削除しない。

WindowsのVHログ `C:/Users/ugai/AppData/LocalLow/VirtualHome/VirtualHome/Player.log` で確認した例外箇所：

```text
Received request: {"id": "1788702265.7193089", "action": "environment_graph"}
NullReferenceException: Object reference not set to an instance of an object
  at StoryGenerator.Utilities.EnvironmentGraphCreator.UpdateGraphNodes (...)
  at StoryGenerator.Utilities.EnvironmentGraphCreator.CreateGraph (...)
  at StoryGenerator.TestDriver+<ProcessNetworkRequest>d__39.MoveNext ()
```

同ログに `windows_exec.v2.3.0/VirtualHome_Data` とDirect3D 11 / NVIDIA GeForce RTX 2060が記録されていた。ローカルのLinux実行ファイルは起動していない。Windowsの実行ファイル・UnityPlayer.dll・Assembly-CSharp.dllのSHA-256と版の確認範囲は [runtime_receipt.json](runtime_receipt.json)。フォルダ名だけでビルド版を独立に証明したとは扱わない。

固定位置比較では録画名をさらに長くしたことで、状態変化test_task6・C0・miniの最初の行動要求で `Recorder.CreateTextualGTs` 内に `DirectoryNotFoundException` が生じ、応答が90秒でタイムアウトした。Windowsの当該ログを圧縮保存した（runtime_receipt参照）。録画名を25文字の一意名へ短縮し、対応を各runの `recording_name` イベントに記録するよう修正した。再起動前の試行は `fixed_initial/interrupted/` に保存し、2件の成功API要求も費用に含める。VHでの当該行動の成否は未確定で、失敗ラベルに変換しない。変更履歴は `fixed_initial/recording_patch.json`。学術的な条件と元のconfigは上書きしない。

## 固定した試験計画

- 入力：状態変化 `test_task1`（参照長0）、`test_task6`、配置 `test_task1`、`test_task65`。
- 前提試験：4件の参照列をAPIなしで再生し、全行動の実行成否と最終ゴールを確認した。配置test_task1の4手目PUTが失敗したため一度停止し、PUTBACKも同じ物体・配置先で失敗することを診断した。その後、全4件を保持する診断試行へ明示的に変更して `comparison_policy.json` を最初のAPI要求前に保存した。操作名の自動変換は行っていない。参照成功3件の集計も別に出す。
- 比較：4件×2モデル×3条件×1反復＝24エピソード。`gpt-4o-mini-2024-07-18` と `gpt-4o-2024-08-06`、C0検証なし・C1既存LLM検証・C2記号的検証。
- Multiの元 `run()` をASTから抽出し、停止条件と分岐は書き換えない。前提条件・生成・再生成のメッセージは照合済み仕様に従う。API応答上限256tokensとログ追加は新設定として区別する。
- C2は同じ抽出知識と条件辞書を使用する。未抽出物体への距離や状態の欠落はunknownとし、1回再生成する。JSON条件充足はVH実行可能性の完全な判定ではない。
- `find_solution=False`、`recording=True`、`camera_mode=['PERSON_FROM_BACK']` を保持する。録画の接頭辞をエピソード・ステップごとに変えて、Windows側の録画を上書きしない。
- 各条件で元の初期化を行い、完全グラフ・順序を正規化した記号状態のハッシュ・エージェント位置を保存する。**同一初期状態で比較できたかは実行後の照合が必要**。不一致なら同一条件と主張しない。
- 検索は凍結済みのMiniLM再構成結果を使用する。当時の検索ログが回収できたわけではない。spaCy 3.7.5 / en_core_web_sm 3.7.1など、現在の依存版をconfigに保存し、過去の未回収環境と区別する。
- 元の試行のAPI推定費用上限は2米ドル、固定位置の追加試行は1米ドル（再開前の消費を含む）。キーは許可済み `.env.local` を読み、ログには含めない。APIとVHの状態変更要求は自動リトライしない。

本試験は動作確認と事例分析用の小規模試行であり、全415タスクや3反復の本評価ではない。C3/C4/C5、未知環境評価、人間評価はこの試行に含めない。

## 固定位置の追加試行

`scripts/vh_fixed_initial.py` は元の試行とは別のconfig・ログを使う。各タスクの元の参照初期位置を、結果が良くなる位置の探索をせず、そのまま採用した。新しい参照再生4件を行い、各計画器の開始時に参照との記号状態の一致、全ノード位置差0.001以下、回転四元数距離0.0001以下を検査する。不一致はAPI要求前に停止する。位置固定は新しい条件であり、過去実験の初期化仕様を置き換えない。初期状態が一致しても実行やモデルの決定性・複数反復での安定性は保証しない。

## 実行・再集計手順

クライアントは `.vh-deps/virtualhome` の公式リポジトリのコミット `58970fd80951c2eaa1af713e0917d1a105353ad8` を使う。依存版・入力ハッシュはconfig参照。probeはシーンを読み取らず接続確認だけを行う。以下のオンラインコマンドはVHのシーンをリセットするため、他の実験と同時実行しない。完了runは再実行しない。

```bash
/home/ugai/venv/bin/python scripts/vh_experiment.py --phase probe --host 172.26.224.1
/home/ugai/venv/bin/python scripts/vh_experiment.py --phase reference --host 172.26.224.1 --retry-incomplete
/home/ugai/venv/bin/python scripts/vh_experiment.py --phase compare --host 172.26.224.1 --allow-reference-failure
/home/ugai/venv/bin/python scripts/vh_fixed_initial.py --phase reference
/home/ugai/venv/bin/python scripts/vh_fixed_initial.py --phase compare --retry-incomplete
```

`--retry-incomplete` は**VHの再起動後に限って**指定し、インフラ失敗記録のある未完了runだけを `interrupted/` へ移動して保存し、シーンリセットからやり直す。元のreferenceコマンドは参照失敗時に停止する。本試行では残りの配置test_task65も個別に再生して4件をそろえ、明示的な `--allow-reference-failure` で比較した。固定位置版は参照失敗を保持する診断方針をconfigに記録している。VH自体の起動・終了はスクリプトでは行わない。

集計・検証はAPI・VH不要：

```bash
/home/ugai/venv/bin/python scripts/summarize_vh.py
/home/ugai/venv/bin/python scripts/summarize_vh.py --fixed-initial
/home/ugai/venv/bin/python -m unittest discover -s scripts -p 'test_*.py'
/home/ugai/venv/bin/python scripts/verify_vh.py --include-fixed
```

最後の検証は両試行完了後に実施する。キー混入検査だけは `.env.local` の値をメモリ上で照合するが送信・表示しない。

## 保存する証拠

- `config.json`：モデル・条件・対象、公式Pythonクライアントのコミットとファイルハッシュ、依存版、元データハッシュ。
- `runs/<run_id>/simulator_rpc.jsonl.gz`：VHへの完全な要求・応答・時間・通信エラー。
- `runs/<run_id>/graph_*.json.gz`：各時点の完全グラフ。
- `runs/<run_id>/events.jsonl`：初期化、抽出知識、検索、各判定・行動・修正、実行前後のゴール充足。
- `runs/<run_id>/result.json`：完了時の結果。元の成功判定と最終グラフ上のゴール充足を別欄にする。
- `runs/<run_id>/infrastructure_error.json`：通信・初期化等の異常。タスク失敗とは別に扱う。
- `api_log.jsonl`：実際にAPIを呼んだ場合のみ作成。全入力・生応答・usage・時間・推定費用。失敗分の費用予約は実請求と区別する。
- `episodes.csv` / `metrics.csv`：全4件・参照成功3件を分けた集計。費用には同じrunの中断試行も含み、該当要求数を別列にする。
- `precondition_labels.csv` / `termination_labels.csv` / `execution_labels.csv`：JSON条件、完全グラフの終了判定、実行した行動のVH応答を分離したラベル。
- `initial_comparability.csv`：条件間の開始状態・位置・向きの照合。
- `sources/` / `manifest.json` / `verification.json`：実行コードの保存可能な版、成果物ハッシュ、照合結果。初期参照の1版はハッシュのみで編集前ソース未保存と明記する。

録画は要求したWindows側の `Output/` に残るが、全フレームの完全性は監査していない。比較・ケース分析の一次証拠は保存したRPC、完全グラフ、API生応答であり、動画の見た目を著者が確認したとは記載しない。

既存の `result/`、`Paper/analysis/`、`Paper/nonvh/` は上書きしない。TeX/LaTeXは実行しない。
