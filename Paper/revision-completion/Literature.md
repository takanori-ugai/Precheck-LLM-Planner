# 先行研究の原典確認

確認日：2026-09-07。原稿の共通軸比較に用いた原典と該当部分を記録する。性能値の直接比較や各方式の忠実な再実装は行っていない。

| 原典 | 確認箇所 | 原稿で区別した点 |
| --- | --- | --- |
| [Fikes, Technical Note 55 (1971)](https://www.researchgate.net/publication/23815496_Monitored_execution_of_robot_plans_produced_by_STRIPS) | 著者が公開した本文、Introduction、STRIPS Plans、Kernel Models | 計画・述語的状態と必要条件による監視、部分再実行・再計画。LLM以前の原理であり、本実装と同じ保証はない。SRIの旧PDFリンクは取得できず、著者公開全文を確認した。 |
| [Fox et al., ICAPS (2006)](https://cdn.aaai.org/ICAPS/2006/ICAPS06-022.pdf) | Sections 1, 4, 5.1 | 状態・ゴール変更下のLPGによる修復と再計画。評価軸は時間・品質・計画安定性。 |
| [Huang et al., ICML (2022)](https://proceedings.mlr.press/v162/huang22a/huang22a.pdf) | Sections 3.2–3.4, 4 | Translation LMで行動集合へ意味的に変換し、変換後履歴を利用する。Dynamic Exampleも埋め込み検索。行動形式への変換と現在状態での前提条件検証は異なる。 |
| [Raman et al., CAPE](https://arxiv.org/pdf/2211.09935) | Section III、Figure 2、実験節 | 環境側の前提条件エラーを修正プロンプトへ利用。C3はこの論文の忠実再現ではない。 |
| [Lin et al., AAAI (2023)](https://arxiv.org/pdf/2209.00465) | Sections 3.2, 3.3, 4.1 | 物体表は種・位置・姿勢・包含先を符号化。反復デコードと参照ベースKASを、オンラインの実行前検証・実行後修復と区別する。 |

対応先：第2章の記号的監視・修復節と6列比較表。表の本研究欄はローカルの実装・実験に基づく。原典にない優劣や安全性は補っていない。
