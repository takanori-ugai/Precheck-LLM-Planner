# 手順1・2の成果物と再実行

入口は [Evidence.md](Evidence.md)（来歴・設定・未回収資料）と [Report.md](Report.md)（掲載用集計表・定義）。本文のTeXと過去の実験コードは変更していない。

## 再集計

リポジトリのルートで実行する。保存済みの検索スコアを利用する再集計はPython 3.10以上の標準ライブラリのみで動作する。OpenAI API・VH・ネット接続は不要。

```bash
python3 scripts/revision_analysis.py
python3 -m unittest discover -s scripts -p 'test_revision_analysis.py' -v
```

スクリプトは `Paper/analysis/` に派生ファイルを生成する。元データ・Notebook・論文本体は書き換えない。新しい分析時に入力のSHA-256が検索スコア内の記録と異なれば、古い検索スコアの使用を拒否する。

## 検索スコアも再計算する場合

今回利用した環境：`/home/ugai/venv/bin/python`、sentence-transformers 5.2.0、transformers 4.57.6、torch 2.9.1、numpy 1.26.4。CPU、1文ずつのエンコード、ローカルのモデル重みを使用した。追加インストール・ダウンロードは実施していない。

```bash
/home/ugai/venv/bin/python scripts/reconstruct_retrieval.py \
  --model-dir /home/ugai/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/c9745ed1d9f207416be6d2e6f8de32d1f16199bf
python3 scripts/revision_analysis.py
```

別環境では `--model-dir` に同じrevisionのローカルsnapshotを指定する。`HF_HUB_OFFLINE=1` と `TRANSFORMERS_OFFLINE=1` をスクリプト内で設定し、ネットから取得しない。重みと全設定ファイルのSHA-256、実行ライブラリ版は [retrieval_scores.json](retrieval_scores.json) のmetadataで照合できる。

元requirementsの依存版とは異なるため、これは「元コードの検索方式の再構成」であり、当時と完全に同一な検索結果の証明ではない。元のモデルrevisionと候補setの順序も保存されていない。同点の場合はタスク名辞書順、同名の最長列の同点はJSON順で決定する。類似度は全候補分を保存し、最近傍の差・同点も報告する。

## 成果物一覧

| ファイル | 内容 |
| --- | --- |
| `source_manifest.csv`, `local_history.json`, `upstream_check.json` | 元ファイルのハッシュ、Git履歴、公開側の調査結果。公開側の記録は当日の読み取り結果で、自動更新しない。 |
| `result_file_mapping.csv`, `settings.csv`, `unrecovered.csv` | 結果と条件の対応、設定の根拠、未回収資料8項目。 |
| `task_inventory.csv` | 全618件のタスク名・対象・操作・配置先・シーン・初期条件・ゴール・参照行動列。 |
| `dataset_summary.csv`, `dataset_coverage.csv`, `dataset_dimension_counts.csv`, `split_overlap.csv` | 分割別の件数・長さ、観測組合せ、対象・配置先・シーン等の全種類別件数、タスク名やシーン・対象の重複。 |
| `results_per_task.csv` | 全18条件・3735行のタスク単位の成功・失敗・長さ差・比率・保存行動列。 |
| `metrics.csv`, `paper_table_checks.csv` | SR・失敗率・平均長、マクロ平均・信頼区間、本文18行×5指標との照合。 |
| `lengths_by_outcome.csv` | 全件／成功／失敗／失敗3類型／参照長0／非ゼロ別の長さ・差・比の統計。 |
| `performance_by_task_properties.csv` | タスク名・シーン・対象・配置先・ゴール数・必要状態変更数・参照長別の性能。 |
| `precheck_paired_comparison.csv`, `precheck_transitions.csv` | 検証有無の成功差・対応遷移・クラスター信頼区間。 |
| `common_success_comparisons.csv` | 各種別の全手法組合せについて、共通成功タスク上の長さ比較。 |
| `retrieval_scores.json` | 全候補のcosineと検索再構成の来歴。 |
| `retrieval_by_task_name.csv`, `retrieval_by_instance.csv`, `retrieval_summary.csv` | 再構成した最近傍・採択事例・類似度・共有構造・初期条件と参照列の比較。 |
| `performance_by_retrieval.csv` | 類似度の固定区間・対象／操作／配置先一致別のSRと成功時の長さ差。因果効果ではない。 |
| `case_candidates.csv`, `Cases.md` | 6つの掲載候補と参照／実行行動列。 |
| `Report.md`, `tables.tex` | 掲載用の表と定義。TeXは確認後に取り込めるtabular断片。 |
| `analysis_receipt.json` | 分析種別、スクリプト・入力のハッシュ、チェック件数。 |

CSVはUTF-8。配列・グラフ等はJSON文字列として格納する。統計量の空欄は未定義／該当なしで、0とは異なる。`same_destination` は状態変化では両方空文字列のため常に真となり、評価指標として解釈しない。

成功数は保存ラベルによる。前提条件判定の正解率・失敗した最後の試行・環境グラフによる成功の再検証・実行コスト・反復間変動は、元ファイルからは計算できない。

## 検証結果（2026-09-06）

7件の単体テストが成功。全18条件・90指標値の一致、全3,735結果のタスクID・ラベル・列長・比率の分母、検証有無の対応数、72組の共通成功比較、検索44名／415事例の網羅性、入力ハッシュと相対リンクを確認した。同じ保存検索スコアによる再集計を繰り返し、生成物がバイト単位で一致することも確認した。元のデータ・結果・NotebookはHEADの内容と一致している。
