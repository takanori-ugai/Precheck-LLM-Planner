# アクション前提条件の公式資料との照合

確認日：2026-09-08。論文の既存 `precondition.json` に含まれる8操作・16条件の説明と出典の確認に、指定された公式資料を利用した。今回の照合結果を第4章「公式資料と前提条件辞書の対応」と回答書B-3-2に反映した。

## 参照資料と役割

- [VirtualHome v2.3 Actions](http://virtual-home.org/documentation/master/kb/actions.html)：操作の引数、前提条件、実行後の変化。ページの表示版はv2.3。HTMLと、同ページの「View page source」から取得できる[reStructuredText原文](http://virtual-home.org/documentation/master/_sources/kb/actions.rst.txt)を確認した。
- [公式resources](https://github.com/xavierpuigf/virtualhome/tree/master/virtualhome/resources)：物体属性・可能な状態の定義。READMEの説明に従い、Unity用 `properties_data_unity.json`、Pythonグラフ実行器用 `properties_data.json`、状態の `object_states.json` を区別した。
- [固定版execution.py](https://github.com/xavierpuigf/virtualhome/blob/58970fd80951c2eaa1af713e0917d1a105353ad8/virtualhome/simulation/evolving_graph/execution.py)：GRABの重複把持の拒否と、文書・実装間の条件表現の差を補足確認した。

GitHubのmasterを取得した時点のコミットは `58970fd80951c2eaa1af713e0917d1a105353ad8`。resourcesとexecution.pyはこのコミットのファイルを取得した。公式文書のmasterは別の公開先であり、確認日と取得内容のSHA-256で識別する。

## 判断

Actions文書は、既存辞書の16条件中15条件に対応する記述を含む。GRABの残り1条件（対象を左右の手に保持していない）は、同文書のGrabの前提条件一覧に明記されていない。公開Pythonコードの `GrabExecutor.check_grabbable` は実行履歴の把持記録から重複把持を拒否するため、この項目の補足照合に使用した。辞書は保持関係、同コードは履歴を検査しており、対応付けたのは重複把持を避ける条件の意味である。

したがって、指定2資料は採用条件の説明の中心資料として利用でき、GRABの非保持条件には公開コードの補足を付ける。resources自体は物体属性・状態の辞書であり、近接・保持などの動的前提条件はActions文書と実行コードで確認する。本文では「前提条件の説明と条件文の照合に利用した」と記述した。今回の確認手順は、既存JSONの条件を操作別に読み取り、公式文書とコードへ対応付ける手順である。

## 8操作の対応

| 操作 | 既存JSONの条件（要約） | 対応する公式資料 | 公式文書で併記される条件・補足 |
| --- | --- | --- | --- |
| WALK | 非保持 | [Walk](http://virtual-home.org/documentation/master/kb/actions.html#walk) | 非座位、到達可能性。 |
| GRAB | 近接、非保持 | [Grab](http://virtual-home.org/documentation/master/kb/actions.html#grab) は近接、execution.pyの349–372行は重複把持拒否 | 把持可能属性、到達可能性、空いた手。履歴に基づく重複把持判定と、JSONの左右の保持関係の判定を区別。 |
| SWITCHON | 近接、OFF | [SwitchOn](http://virtual-home.org/documentation/master/kb/actions.html#switchon) | スイッチ属性。 |
| SWITCHOFF | 近接、ON | [SwitchOff](http://virtual-home.org/documentation/master/kb/actions.html#switchoff) | スイッチ属性。 |
| OPEN | 近接、CLOSED | [Open](http://virtual-home.org/documentation/master/kb/actions.html#open) | 開閉可能属性、到達可能性、空いた手。 |
| CLOSE | 近接、OPEN | [Close](http://virtual-home.org/documentation/master/kb/actions.html#close) | 開閉可能属性、到達可能性、空いた手。 |
| PUT | 対象物の保持、配置先への近接 | [Put](http://virtual-home.org/documentation/master/kb/actions.html#put) | 文書のプログラム構造例ではput、Put節の例とPython実行器の登録名ではputback。 |
| PUTIN | 対象物の保持、配置先への近接、配置先がCLOSEDでない | [PutIn](http://virtual-home.org/documentation/master/kb/actions.html#putin) | not CLOSEDは公式Actions文書に直接対応。Pythonの `_check_puttable` は開閉可能属性のある配置先にOPENを要求する。 |

## resourcesで確認した具体例

`properties_data_unity.json` にはlightswitchの `HAS_SWITCH`、fridgeの `CAN_OPEN`・`CONTAINERS`、plumとcupcakeの `GRABBABLE`、deskとkitchencounterの `SURFACES` がある。`object_states.json` にはlightswitchのon/offとfridgeのopen/closedがある。これは可能な属性・状態の確認であり、各試行の現在状態は実行時グラフから取得する。

Python用とUnity用では定義が異なる。例えばPython用のfridgeには `HAS_SWITCH`・`HAS_PLUG` もあるが、Unity用では `CAN_OPEN`・`CONTAINERS`。deskもPython用には `CAN_OPEN` がある一方、Unity用には `SURFACES` がある。このため論文ではファイルの役割を明記した。

## 取得内容のSHA-256

| 資料 | SHA-256 |
| --- | --- |
| Actions HTML | `46bf689a4439ce4955e7173ddf4f4b150410c2798aa51b0f3b2ee2673dfa826c` |
| Actions RST | `44b545a6d9bcba0763b76456da68760575a17e1c277ea2ce61fe3c58ff858086` |
| properties_data.json | `d0ce21fdeb9d48839aa2c887c48c524b37677b8f8d8337e799632a66b1f738a4` |
| properties_data_unity.json | `029d3ea44a4634f19ec513c96a731032984b08a239237692aa481b5b409ebece` |
| object_states.json | `c517dca88abe741d7dfcb2ff1cc05f21d5e24d0f80b184a954e505e6a15e7807` |
| execution.py | `2f591e135b47649f2ebee5e8f3e634e4c8dc4b8f04866235690e0d846a446aa4` |
| 論文のprecondition.json | `427e1bec1a52df0f59f024335dc4bba8bd41dd8cab966694ba53fe606d19018d` |
