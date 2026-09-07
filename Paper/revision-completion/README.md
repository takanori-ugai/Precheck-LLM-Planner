# ToDo 6項目の実施完了と残る研究上の限界

2026-09-07。TeXは実行せず、既存データ・実験結果・人手票を保持した。

全6項目はユーザーが承認した変更後の完了条件で完了した。項目2は照合通過4候補の評価と未再現4候補の明示、項目4は保有資料なしの確認と回収不能・比較上の限界の明示とする。全8件の状態復元、過去実験の完全再現、独立した説明品質評価の成功を意味しない。

## 成果物

- [違反説明全文の資料](../human-unmet-review/Review.md)と[著者再確認票](../human-unmet-review/semantic_review.csv)：別要求 `unmet` が対象。全8件の記入（正しい1・誤り7）と根拠全文を [著者確認付録](../appendix-human-review.tex) に掲載。AI支援後の確認であり、根拠の曖昧さと独立検証でない限界も開示した。
- [候補状態復元試行](../vh_aligned_replay/README.md)：候補実行直前に一致を検査する別実装。最初の接頭列3行動の後、グラフ復元がタイムアウトしたため候補未実行で停止した。
- [再起動後の直前照合付き再生](../vh_aligned_prefix/README.md)：8件の初期化と接頭列再生を完了。照合通過2件はVH成功、6件は不一致による候補未実行。途中グラフ転送・API要求なし。
- [人物なしシーンへの復元](../vh_clean_restore/README.md)：前方式で不一致の6件を検証し、他2件が照合通過・VH成功。両方式で異なる4候補を評価し、本手順で未再現だった4候補の範囲・理由も記録した。
- [資料回収の判断記録](Archive-Resolution.md)：著者保有資料なし、回収不能範囲と比較上の限界の明示を完了条件とする指示を記録した。
- [統計付録](../appendix-statistics.tex)：全手法の分布、失敗類型、長さ差・比、マクロSR・区間、検索別成績、全618件の組合せ。
- [実入力付録](../appendix-real-inputs.tex)：構成要素比較のtask6・task65、C1・GPT-4o・反復0の入力全文・関係・変化。
- [原典確認](Literature.md)：記号的監視・修復を含む比較。原稿・回答書と計画を同期した。

## 再生成と検証（VH・API不要）

```sh
python3 scripts/export_revision_completion.py
python3 scripts/export_revision_completion.py --check
python3 scripts/validate_unmet_review.py
python3 scripts/validate_unmet_review.py --semantic
python3 scripts/summarize_semantic_review.py
python3 scripts/summarize_semantic_review.py --check
python3 scripts/summarize_aligned_prefix.py
python3 scripts/summarize_clean_snapshot.py
/home/ugai/venv/bin/python -m unittest discover -s scripts -p 'test_*.py'
```

エクスポータは派生TeX・説明資料・空テンプレートを生成するが、記入用 `review.csv` と `semantic_review.csv` はそれぞれ初回だけ作成し、既存の記入内容を上書きしない。`export_manifest.json` に根拠CSV・イベント・グラフのハッシュを保存する。採点検証器は入力列・ラベル・根拠・評価者・日付を検査し、未記入を判断不能で自動補完しない。

全テストはinflection等を含む既存の仮想環境を使う。標準PythonのみではVHドライバのモックテスト2件で依存不足になる。テストは通信をモックしており、実際のAPI・VHは呼ばない。

最終検証は61テスト成功。原稿14入力ファイルの109ラベル・163参照を静的照合した。Gitの空白検査では、実際のプロンプト原文に含まれる18行の末尾空白とCSVのCRLFを意図的に保持し、それ以外の空白エラーがないことを確認した。これらを整形して保存入力を変えない。

## 著者資料の回収

ローカル履歴と通常のファイル一覧を再確認したが、新たな回収元は見つからなかった。著者から「保有資料なし」と確認したため、追加の著者保有アーカイブは今回利用できない。非公開アーカイブを検査したとしたり、他所に資料が存在しないと証明したりはしない。

Huang原著のTranslation LM・検索・停止規則は原典で確認したが、それは基本性能結果を生成した実装・設定の証明ではない。ユーザー指示で限界の明示を今回の完了条件とし、新規再実装は実施しない。完全な実験再現を達成したとはしない。

前提条件については、ローカルにある公式VHクライアントリポジトリ（コミット `58970fd80951c2eaa1af713e0917d1a105353ad8`）の `virtualhome/simulation/evolving_graph/execution.py` を確認し、実装付録に対応表を追加した。`WalkExecutor`、`GrabExecutor`、`SwitchExecutor.check_switchable`、`OpenExecutor.check_openable`、`_check_puttable` と操作登録を照合した。属性・空き手・OPENとnot CLOSED・PUTBACKとPUTの違いがある。ただし公開Pythonグラフ実行器は遠隔Unityの内部実装と同一とは確認できず、過去の辞書作成元・転記履歴を回収したわけではない。

## 著者確認記録の掲載完了と限界

著者による `unmet` 8件の採点記録を本文・付録・回答書へ反映した。旧票を保存し、基準説明と個別例照会をAI支援で行った経緯を開示した。根拠と未充足条件の列挙の対応に曖昧さが残るため、説明品質の確定正解率や独立検証の完了とはしない。[受領・確認記録](../human-unmet-review/Review-Status.md)を参照。自動エクスポータはラベル・根拠を変更せず、根拠ファイルと実装のハッシュを `recorded_results.json` に記録する。

## 今回の完了範囲外として明示する限界

1. 2方式でも未再現だった4候補の同一状態での実行と、未選択51候補の評価。観測グラフの一致も物理内部状態の完全同一性を保証しない。
2. 回収不能な実験時資料に基づく完全再現と、新しいベースライン再実装。
3. 著者の支援付き確認を越える、違反説明の意味的妥当性の独立検証。

全415タスクの反復比較、全候補実行、独立した人間性能実験は再追加しない。PDF生成・組版確認はユーザー指示により対象外。
