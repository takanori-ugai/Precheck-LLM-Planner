# 過去の保存行動列の再生

4タスク（状態変化test_task1・test_task6、配置test_task1・test_task65）について、過去のMulti Promptsの2モデルの保存列、計8件をAPIなしで再生する。対象は追加比較と同じ4件として事前固定し、元の結果JSONのSHA-256をconfigに保存する。最新の実施件数と結果は、実行後の `completion.json` と `Report.md` を参照する。

現在のWindows VHと前回の固定位置参照グラフを用いる。過去実験の人物位置・全依存版は未回収なので、歴史的な実行環境の完全再現ではない。成功・失敗にかかわらず保存されたコマンドをそのまま送り、最初のVH失敗で停止する。自動ID変換・行動書換え・再計画は行わない。

過去のExecution FailureのJSONには最後の失敗行動が保存されていない。したがってここで測定するのは**保存済みの成功行動の接頭列**の再生可能性と最終グラフであり、元の失敗を起こした行動を復元するものではない。保存列を再生できても、元の失敗が否定されたとは解釈しない。

```bash
/home/ugai/venv/bin/python scripts/replay_saved_vh.py --phase prepare
# 240条件の比較が終了し、他のVH利用がないことを確認して実行：
/home/ugai/venv/bin/python scripts/replay_saved_vh.py --phase run
# オフライン再集計：
/home/ugai/venv/bin/python scripts/replay_saved_vh.py --phase summary
```

APIキーの読込み・LLM/API呼出しはない。VHの実行順序・初期照合・短い録画名は追加比較の補助実装を使用し、各実行のRPC・完全グラフ・ゴール変化を保存する。完了runは再実行せず、中断runは自動削除・再試行しない。TeX／LaTeXは実行しない。
