# APPENDIX：公開補足資料

対象論文：**家庭環境知識に基づく行動前提条件の検証を伴うLLMエージェントの逐次的行動計画生成**

更新日：2026年9月8日

旧付録の仕様、実験条件、詳細結果、コード、実入力例をまとめた公開補足資料です。全30表、12件のコード・入力ブロック、知識抽出の擬似コードを掲載しています。データ網羅表には全618件を収録しています。表・Listing・Algorithmの番号は本資料内の通し番号です。

論文本文との対応は[構成変更の記録](revision-completion/Appendix-Removal.md)、ビルド方法は[README](README.md)を参照してください。

## 目次

- [公開実装のプロンプトと知識変換](#app-implementation)
- [実験条件と詳細結果](#app-evaluation)
- [分布・対応比較・データ網羅の詳細](#app-statistics)
- [実シーンでの入力と行動前後の変化](#app-real-inputs)

<details>
<summary>表一覧（30表）</summary>

- [表A1：各呼び出しの役割・入力・履歴と分岐](#tab-prompt-calls)
- [表A2：8操作の前提条件辞書と公式資料の対応](#tab-condition-source-scope)
- [表A3：シーン・初期部屋別のインスタンス数](#tab-coverage-internal)
- [表A4：全18条件の成功・失敗別行動列長（参照平均も各行と同じ集合で計算）](#tab-all-outcome-lengths)
- [表A5：検証あり／なしの共通成功集合における平均行動列長](#tab-common-success-internal)
- [表A6：固定した人物位置（VH座標）](#tab-fixed-positions-internal)
- [表A7：反復別の成功数と参照成功タスクに限定した成功数](#tab-repeat-internal)
- [表A8：意味類似検索で選択した事例](#tab-semantic-internal)
- [表A9：ランダム検索で選択した指示（両モデル共通）](#tab-random-internal)
- [表A10：棄却候補8件の再実行と状態照合（○：一致または成功，×：不一致または失敗）](#tab-replay-internal)
- [表A11：実行直前照合を条件とした代表候補評価（番号は表A10に対応）](#tab-replay-gated)
- [表A12：代表候補の判定応答と未充足条件応答（番号は表A10と共通）](#tab-unmet-internal)
- [表A13：人物のいないシーンへの候補時点グラフ復元（番号は表A10と共通）](#tab-clean-restore)
- [表A14：未充足条件応答への著者記入ラベルと根拠（番号は表A12と共通）](#tab-author-unmet-review)
- [表A15：記録行動列8本の再生と最終ゴール（全列の再生は成功）](#tab-saved-replay-internal)
- [表A16：詳細集計に用いる条件番号](#tab-method-dictionary)
- [表A17：成功・失敗別の列長分布](#tab-length-distribution)
- [表A18：失敗類型別の列長](#tab-failure-lengths)
- [表A19：同一IDでの列長差と比](#tab-length-ratios)
- [表A20：マクロ成功率とタスク名クラスター区間（%）](#tab-macro-intervals)
- [表A21：検証なしからありへの対応変化とSR差（percentage points）](#tab-paired-intervals)
- [表A22：検索類似度の分布](#tab-retrieval-distribution)
- [表A23：検索類似度・共有構造別の成功率と成功時列長差](#tab-retrieval-strata)
- [表A24：タスク指示の辞書](#tab-instruction-dictionary)
- [表A25：初期状態の辞書（ID:状態配列）](#tab-initial-state-dictionary)
- [表A26：全インスタンスの組合せ（ID:初期部屋）](#tab-joint-coverage)
- [表A27：初期グラフの対象・人物からの関係抜粋](#tab-real-edges-test-task6)
- [表A28：行動と状態・関係の変化](#tab-real-changes-test-task6)
- [表A29：初期グラフの対象・人物からの関係抜粋](#tab-real-edges-test-task65)
- [表A30：行動と状態・関係の変化](#tab-real-changes-test-task65)

</details>

<a id="app-implementation"></a>

## 公開実装のプロンプトと知識変換

本資料は，提案手法の公開Notebookに対応する入力と処理の仕様を示す．テンプレートと実際の送信ログを区別し，比較条件による入力の違いは[過程別の記録と状態照合](#app-evidence)，実行資料の確認範囲は[実験資料と再現性](#app-reproducibility)に示す．以下のPython表記では`\n`を改行とし，roleと文字列の組を順に並べたものをメッセージ配列とする．英語表現・空白は実装と一致させている．

<a id="app-prompts"></a>

### 全メッセージの組立て

Listing [A1](#lst-prompt-spec)に，終了判定，行動生成，前提条件判定，違反条件特定，再生成の全入力を構成する関数を示す．`mode`はsingleまたはmulti，`env`は[知識抽出と自然言語化](#app-knowledge)の変換結果全文，`history`は成功実行した行動の列である．`example`は`example_text`で得た選択事例の文字列であり，`pc`は[前提条件辞書と代入規則](#app-conditions)の辞書とする．プロンプトにゴールJSONを渡す引数はない．

<a id="tab-prompt-calls"></a>

**表A1：各呼び出しの役割・入力・履歴と分岐**

| 呼び出し | 入力メッセージ | 出力の利用 |
|:---|:---|:---|
| 完了判定 | system（末尾空白なし），user（環境＋判定指示＋タスク） | Endとの完全一致．参照列長0ではContinueとの完全一致も確認． |
| 行動生成Single | system（末尾空白なし），user（5要素を連結） | 生成した1行動を検証または実行． |
| 行動生成Multi | system（末尾空白あり），5個のuser（役割指示，許可操作・形式，事例，環境，タスク・成功履歴・次ステップ） | 1回の呼び出しから1行動を得る． |
| 前提条件判定 | user（環境＋判定文＋対象を代入した条件） | 部分文字列Yesを含めば充足． |
| 違反条件特定 | system（末尾空白あり），直前の判定入力userと出力assistant，追加問い合わせuser | 違反理由のフィードバックを作る． |
| 再生成 | system（末尾空白あり），行動生成時のuser群，候補assistant，理由user，再生成指示user | 1回だけ生成し，再検証せず実行． |

通常の未完了周回では，検証なしは完了判定と生成の2回，条件を充足する検証ありは3回，違反条件特定と再生成を行う場合は5回のLLM呼び出しとなる．操作名が条件辞書にない形式不正では，条件判定・違反特定を呼ばず再生成を行うため3回である．最初の完了判定で終了する周回は1回である．これはコードの呼び出し経路から数えた値であり，通信層の再試行や個々のエピソードの実測費用を含まない．

本文のListing [タスク完了判定](sec4.tex#L58)～[行動再生成](sec4.tex#L149)は構成要素を説明する表示である．正確なメッセージ境界・改行・単語は以下を参照する．特に違反理由と再生成指示は別々のuserメッセージとなり，前提条件の違反特定には行動生成時の履歴を渡していない．

<a id="lst-prompt-spec"></a>

**Listing A1：公開コードと照合した完全なプロンプト組立て仕様**

ソース：[listings/prompt_spec.py](listings/prompt_spec.py)

```python
"""Message specification of the published notebooks (no LLM calls).

mode: 'single' or 'multi'; env: exact return_nlp output;
history: successfully executed actions; pc: original precondition.json.
Whitespace and grammatical errors of the original prompts are preserved.
"""

SYSTEM = "You are a life support robot."
CHAT_SYSTEM = "You are a life support robot. "
INSTRUCTION = "You need to generate a next action step for completing a household task.\n"
ALLOWED = """
Allowed actions: 
Walk, Grab, Switch on, Switch off, Open, Close, Put, Put in
Output Format: 
[WALK] <Object> (ID)
[GRAB] <Object> (ID)
[SWITCHON] <Object> (ID)
[SWITCHOFF] <Object> (ID)
[OPEN] <Object> (ID)
[CLOSE] <Object> (ID)
[PUT] <Object1> (ID) <Object2> (ID)
[PUTIN] <Object1> (ID) <Object2> (ID)

"""
CHECK = '\nIf the current status satisfies the preconditions, output "Yes"; otherwise, output "No".\n'
UNMET = 'Which the preconditions are not satisfied?\nOutput only that.'


def example_text(name, script):
    text = f"Example Task: {name}\n"
    for step, action in enumerate(script, 1):
        text += f"Step{step}: {action}\n"
    return text + "\n"


def task_text(mode, task, history):
    if mode == 'single':
        text = "\nGenerate a next action step to complete the following task and output only that.\n"
    else:
        text = "Generate a only next action step to complete the following task and output only that.\n"
    text += f"Task: {task}\n"
    for step, action in enumerate(history, 1):
        text += f"Step{step}: {action}\n"
    return text + f"Step{len(history) + 1}: "


def end_messages(mode, task, env):
    if mode == 'single':
        text = '\nOutput "End" if the following task has already completed based on the current status, otherwise output "Continue".\n'
    else:
        text = '\nIf the following task has already completed based on the current status, output "End"; otherwise, output "Continue".\n'
    return [('system', SYSTEM), ('user', env + text + f'Task: {task}\n')]


def generation_messages(mode, task, env, example, history):
    blocks = [INSTRUCTION, ALLOWED, example, env, task_text(mode, task, history)]
    if mode == 'single':
        return [('system', SYSTEM), ('user', ''.join(blocks))]
    return [('system', CHAT_SYSTEM)] + [('user', block) for block in blocks]


def bind_conditions(action, pc):
    parts = action.split(' ')
    operation = parts[0][1:-1]
    if operation not in pc:
        return None
    text = pc[operation]
    if len(parts) == 5:
        return text.replace('<Object1>', f'{parts[1]} {parts[2]}').replace('<Object2>', f'{parts[3]} {parts[4]}')
    return text.replace('<Object>', f'{parts[1]} {parts[2]}')


def check_messages(env, conditions):
    return [('user', env + CHECK + conditions)]


def unmet_messages(env, conditions, check_output):
    return [('system', CHAT_SYSTEM),
            ('user', env + CHECK + conditions),
            ('assistant', check_output),
            ('user', UNMET + conditions)]


def feedback(action, unmet_output=None):
    if unmet_output is None:
        return f"'{action}' is incorrect output format."
    return f"'{action}' can not execute, because it is not satisfied the following precondition.\n{unmet_output}"


def regeneration_messages(mode, task, env, example, history, action, reason):
    messages = generation_messages(mode, task, env, example, history)
    messages[0] = ('system', CHAT_SYSTEM)
    return messages + [('assistant', action), ('user', reason),
                       ('user', task_text(mode, task, history).replace('Generate', 'Regenerate'))]
```

<a id="app-conditions"></a>

### 前提条件辞書と代入規則

Listing [A2](#lst-conditions)は公開JSONそのものである．操作文字列を空白で分割し，先頭の角括弧を除いた操作名で辞書を参照する．トークン数が5ならObject1とObject2へ対象名・IDの組を代入し，それ以外ではObjectへ最初の対象名・IDを代入する．未定義の操作名なら形式不正の再生成へ進むが，必要なトークンがない場合等の例外を捕捉して必ず修正する処理はない．

この辞書の条件は固定した自然言語表現である．公式Actions文書の各操作の条件を，近接，保持，対象状態の項目ごとに照合した．条件文中のObject，Object1，Object2は対象名・IDを代入する箇所に対応する．

<a id="lst-conditions"></a>

**Listing A2：公開されている8操作の前提条件辞書**

ソース：[../precondition.json](../precondition.json)

```json
{
    "WALK": "Preconditions:\n<Object> is not held in your right hand or left hand.\n",
    "GRAB": "Preconditions:\nYou are close to <Object>.\n<Object> is not held in your right hand or left hand.\n",
    "SWITCHON": "Preconditions:\nYou are close to <Object>.\n<Object> is OFF.\n",
    "SWITCHOFF": "Preconditions:\nYou are close to <Object>.\n<Object> is ON.\n",
    "OPEN": "Preconditions:\nYou are close to <Object>.\n<Object> is CLOSED.\n",
    "CLOSE": "Preconditions:\nYou are close to <Object>.\n<Object> is OPEN.\n",
    "PUT": "Preconditions:\nYou are holding <Object1> in your right hand or left hand.\nYou are close to <Object2>.\n",
    "PUTIN": "Preconditions:\nYou are holding <Object1> in your right hand or left hand.\nYou are close to <Object2>.\n<Object2> is not CLOSED.\n"
}
```

<a id="section-4"></a>

#### 公式資料と前提条件辞書の対応

VH v2.3の[公式Actions文書](http://virtual-home.org/documentation/master/kb/actions.html)と[`resources`](https://github.com/xavierpuigf/virtualhome/tree/58970fd80951c2eaa1af713e0917d1a105353ad8/virtualhome/resources)を，前提条件の説明・照合に利用した．2026年9月8日に確認したリポジトリのコミットは`58970fd80951c2eaa1af713e0917d1a105353ad8`である．Actions文書はWalk，Grab，Open，Close，Put，PutIn，SwitchOn，SwitchOffの各項を参照した．表[A2](#tab-condition-source-scope)に，現在の辞書が採用する条件と，公式資料で確認できる条件を整理する．

<a id="tab-condition-source-scope"></a>

**表A2：8操作の前提条件辞書と公式資料の対応**

| 操作 | 辞書が採用する条件 | 公式Actions文書および公開コードとの対応 |
|:---|:---|:---|
| WALK | 対象を左右どちらの手にも保持していない | Walkの非把持条件に対応．同項には非座位と到達可能性も記載されている． |
| GRAB | 対象に近接し，対象を保持していない | Grabに近接条件が記載されている．非保持は公開コードの`GrabExecutor.check_grabbable`による重複把持の拒否と対応付けた．同項には把持可能属性，到達可能性，空いた手も記載されている． |
| SWITCHON | 対象に近接し，対象がOFF | SwitchOnの近接・OFF条件に対応．同項にはスイッチ属性も記載されている． |
| SWITCHOFF | 対象に近接し，対象がON | SwitchOffの近接・ON条件に対応．同項にはスイッチ属性も記載されている． |
| OPEN | 対象に近接し，対象がCLOSED | Openの近接・CLOSED条件に対応．同項には開閉可能属性，到達可能性，空いた手も記載されている． |
| CLOSE | 対象に近接し，対象がOPEN | Closeの近接・OPEN条件に対応．同項には開閉可能属性，到達可能性，空いた手も記載されている． |
| PUT | 対象物を保持し，配置先に近接 | Putの2条件に対応．文書のプログラム構造では`put`，同項の例とPython実行器では`putback`という表記を用いる． |
| PUTIN | 対象物を保持し，配置先に近接し，配置先がCLOSEDでない | PutInの3条件に対応．Python実行器の`_check_puttable`では，開閉可能属性のある配置先にOPENを要求する． |

`resources/properties_data_unity.json`でUnity側の物体属性を，`properties_data.json`でPythonグラフ実行器側の属性を，`object_states.json`で物体が取り得る状態を確認した．例えばUnity側ではlightswitchに`HAS_SWITCH`，fridgeに`CAN_OPEN`と`CONTAINERS`，plumに`GRABBABLE`が定義されている．状態資料にはlightswitchのON／OFFとfridgeのOPEN／CLOSEDが含まれる．各試行の現在状態と保持・近接関係は，実行時に取得する環境グラフから抽出する．

表の採用条件を自然言語で固定してLLMへ渡す処理と，候補の実行をVHに要求する処理を分けて実装している．公式文書には物体属性，到達可能性，空いた手などの条件もあり，実行成否はVHの応答で評価する．GRABの補足照合には，公開Pythonグラフ実行器の`execution.py`[^1]を用いた．同コードは実行履歴の把持記録を検査し，本辞書は左右の保持関係を条件に用いる．資料の取得日，固定版，各条件の対応は[Paper/revision-completion/Precondition-Sources.md](revision-completion/Precondition-Sources.md)に記録した．

<a id="app-knowledge"></a>

### 知識抽出と自然言語化

抽出の処理順はAlgorithm [A1](#alg-extract)に示す．物体記録は状態配列，単一の支持物・容器・所属部屋，保持対象のリストを持つ．グラフのnodes・edgesの順序で走査し，単一値の欄は後から見つかった辺で上書きする．追加ノードが元の抽出集合にある場合にも，その記録を初期化して再走査する．エージェントの保持物は名前・IDの取得対象となるが，保持物を新たな抽出の起点として再帰展開するわけではない．

<a id="alg-extract"></a>

**Algorithm A1：公開コードの知識抽出**

```text
入力：現在のグラフ G，指示から得た名詞・単数形候補 R
O ← クラス名が R に含まれるノードの記録
A ← 空集合
for G の各辺 (u, r, v) を格納順に:
    if u ∈ O:
        ON なら支持物を記録し v を A へ追加（walk，floor は除外）
        INSIDE なら4部屋クラスへの辺を所属部屋として記録
        部屋以外への INSIDE なら容器を記録し v を A へ追加
    u, v ∈ O かつ r ∈ {ON, INSIDE} なら v の保持対象に u を追加
nodes 順に A のノードを O へ追加（既存の記録も初期化）
for G の各辺 (u, r, v) を格納順に:
    u ∈ A について支持物・容器・所属部屋を記録（A は追加拡張しない）
    v ∈ A, u ∈ O かつ r ∈ {ON, INSIDE} なら v の保持対象に u を追加
ID 1 の出辺から左右の保持物，4部屋クラスへの INSIDE，O への CLOSE を取得して B とする
return O, B
```

自然言語化の全関数をListing [A6](#lst-serialization)に示す．`objId_dic`はIDからクラス名への辞書，`objProp_dic`はIDから属性配列への辞書であり，初期化後のグラフから作成する．Listing [状態変化タスクのデータセット例](sec5.tex#L22)・[配置タスクのデータセット例](sec5.tex#L50)のタスクJSONだけでは，例えばID 173の所属部屋を確定できず，実行時のグラフが必要となる．基本性能評価には各時刻の完全グラフ・プロンプトの記録がないため，構成要素比較やケース分析のグラフを，基本性能評価の個別試行の入力として代用しない．

Listing [A4](#lst-knowledge-state)・[A5](#lst-knowledge-placement)は，変換関数の振る舞いを示す**説明用の合成入力**に対する出力である．実際のVHシーンの観測ではなく，IDも9000番台の仮の値を用いる．入力全文はListing [A3](#lst-knowledge-inputs)に示す．状態例はキッチンのOFFのスイッチへの近接を，配置例はキッチンのテーブル上のplumと閉じたfridge，エージェントの近接関係を仮定する．ここには座標・壁面・同じ床面といった追加情報はない．出力中の重複した“and”等も変換関数の出力をそのまま保持した．

<a id="lst-knowledge-inputs"></a>

**Listing A3：知識変換の説明用合成入力の全文**

ソース：[listings/knowledge_example_inputs.json](listings/knowledge_example_inputs.json)

```json
{
  "kind": "synthetic_serialization_example_not_VH_graph_or_experiment_log",
  "object_names": {
    "9001": "kitchen",
    "9002": "lightswitch",
    "9012": "plum",
    "9013": "kitchentable",
    "9014": "fridge"
  },
  "properties": {
    "9002": [],
    "9012": [],
    "9013": [],
    "9014": [
      "CONTAINERS"
    ]
  },
  "state_objects": {
    "9002": {
      "states": [
        "OFF"
      ],
      "on": null,
      "inside": null,
      "location": 9001,
      "hold": []
    }
  },
  "placement_objects": {
    "9012": {
      "states": [],
      "on": 9013,
      "inside": null,
      "location": 9001,
      "hold": []
    },
    "9013": {
      "states": [],
      "on": null,
      "inside": null,
      "location": 9001,
      "hold": [
        9012
      ]
    },
    "9014": {
      "states": [
        "CLOSED"
      ],
      "on": null,
      "inside": null,
      "location": 9001,
      "hold": []
    }
  },
  "state_agent": {
    "close_to": [
      9002
    ],
    "hold_rh": null,
    "hold_lh": null,
    "location": 9001
  },
  "placement_agent": {
    "close_to": [
      9012,
      9013
    ],
    "hold_rh": null,
    "hold_lh": null,
    "location": 9001
  }
}
```

<a id="lst-knowledge-state"></a>

**Listing A4：説明用の状態知識の出力（実験ログではない）**

ソース：[listings/knowledge_example_state.txt](listings/knowledge_example_state.txt)

```text
The current states in the home are as follows: 
The lightswitch (9002) is OFF and and is INSIDE the kitchen (9001).
You are INSIDE the kitchen (9001).
You are close to the lightswitch (9002).
```

<a id="lst-knowledge-placement"></a>

**Listing A5：説明用の配置知識の出力（実験ログではない）**

ソース：[listings/knowledge_example_placement.txt](listings/knowledge_example_placement.txt)

```text
The current states in the home are as follows: 
The plum (9012) is ON the kitchentable (9013) and and is INSIDE the kitchen (9001).
The kitchentable (9013) and is INSIDE the kitchen (9001).
plum (9012) is ON the kitchentable (9013).
The fridge (9014) is CLOSED and and is INSIDE the kitchen (9001).
You are INSIDE the kitchen (9001).
You are close to the plum (9012) and the kitchentable (9013).
```

<a id="lst-serialization"></a>

**Listing A6：両Notebookで共通する自然言語化関数の全文**

ソース：[listings/knowledge_serialization.py](listings/knowledge_serialization.py)

```python
def return_nlp(a, b):

    env_prompt = "The current states in the home are as follows: \n"
    for id, knowledge in a.items():
        text = "The " + objId_dic[id] + f" ({id})"
    
        if knowledge["states"]:
            text += f" is {knowledge['states'][0]} and"
            if knowledge["on"]:
                text += f" is ON the {objId_dic[knowledge['on']]} ({knowledge['on']}) and"

            elif knowledge["inside"]:
                text += f" is INSIDE the {objId_dic[knowledge['inside']]} ({knowledge['inside']}) and"

        else:
            if knowledge["on"]:
                text += f" is ON the {objId_dic[knowledge['on']]} ({knowledge['on']}) and"

            elif knowledge["inside"]:
                text += f" is INSIDE the {objId_dic[knowledge['inside']]} ({knowledge['inside']}) and"

        if knowledge["location"]:
            text += f" and is INSIDE the {objId_dic[knowledge['location']]} ({knowledge['location']}).\n"
        else:
            text = ""

        if knowledge["hold"]:
            receptacle_type = "INSIDE" if "CONTAINERS" in objProp_dic[id] else "ON"
            text += f"{objId_dic[knowledge['hold'][0]]} ({knowledge['hold'][0]})"
            if len(knowledge["hold"]) > 1:
                for ho in knowledge["hold"][1:]:
                    text += f" and {objId_dic[ho]} ({ho})"
                text += f" are {receptacle_type} the {objId_dic[id]} ({id}).\n"
            else:
                text += f" is {receptacle_type} the {objId_dic[id]} ({id}).\n"

        env_prompt += text


    agent_prompt = f"You are INSIDE the {objId_dic[b['location']]} ({b['location']}).\n"
    if b["hold_rh"] and b["hold_lh"]:
        agent_prompt += f"You are holding the {objId_dic[b['hold_rh']]} ({b['hold_rh']}) in your right hand and the {objId_dic[b['hold_lh']]} ({b['hold_lh']}) in your left hand.\n"
    elif b["hold_rh"]:
        agent_prompt += f"You are holding the {objId_dic[b['hold_rh']]} ({b['hold_rh']}) in your right hand.\n"
    elif b["hold_lh"]:
        agent_prompt += f"You are holding the {objId_dic[b['hold_lh']]} ({b['hold_lh']}) in your left hand.\n"

    if b["close_to"]:
        agent_prompt += f"You are close to the {objId_dic[b['close_to'][0]]} ({b['close_to'][0]})"
        if len(b['close_to']) > 1:
            for c in b['close_to'][1:]:
                agent_prompt += f" and the {objId_dic[c]} ({c})"
        agent_prompt += ".\n"
    
    env_prompt += agent_prompt

    return env_prompt
```

<a id="app-evidence"></a>

### 過程別の記録と状態照合

実シーンでの状態変化task6と配置task65の環境知識全文，物体の所属部屋，人物位置，行動前後の状態・関係差分は[実シーンでの入力と行動前後の変化](#app-real-inputs)に示す．構成要素比較のC1・GPT-4o・反復0に対応する例であり，合成例や基本性能評価の未保存入力とは区別する． 構成要素比較では，候補判定に使う完全グラフと抽出辞書，前提条件判定の入力・応答，別要求の未充足条件，再生成の入力・応答，実行前後のグラフとVH応答を，タスク・モデル・条件・反復・ステップに対応付けて記録した．C1-budget等の条件に固有のメッセージ構成は[比較条件固有のプロンプト](#app-comparison-prompts)に示す．

棄却候補の状態照合では，候補判定時のグラフと，再実行イベントに付随する候補実行直前のグラフを比較した．結果要約の前状態欄は実装上，候補実行後の最後のグラフ取得を指していたため，照合対象として用いなかった．照合はノードID・クラス・状態・属性と関係辺の一致を確認した上で，全ノードの位置差と四元数距離を評価する．具体的な距離の定義と候補別結果は[棄却候補の状態照合と人手確認](#app-review-conditions)に示す．VH成否や人手ラベルはこの照合によって変更していない．

<a id="app-reproducibility"></a>

### 実験資料と再現性

基本性能評価に関する提案手法の公開コード・データ・結果JSONはGitコミット`2761158`に含まれ，READMEのみが異なる`de1fc8d`を照合対象とした．各結果とテスト集合のIDは一致し，結果JSONから計算した全18条件のSR・3失敗率・平均列長の90値は掲載値と小数第3位まで一致する．ただし，実行ごとのコード版・日時・API応答メタデータは記録されていない．

公開Notebookは`gpt-4o-mini`というモデル別名とtemperature 0.0を指定する．Multiの評価ループは1件で停止する`break`を含み，Notebookの出力キーは`action_script`，基本性能評価の結果JSONのキーは`action script`である．したがって，Notebookの無変更実行で全モデル・全条件の結果を再生成できるとはいえない．本文の処理仕様はこのコードに基づくもので，各試行の実装との完全な一致は確認できない．

基本性能評価の各タスク種別には，ベースライン1条件とSingle／Multi・2モデル・検証あり／なしの8条件の結果が対応する．ベースラインはHuangら [(2022)](https://proceedings.mlr.press/v162/huang22a.html)の著者公開実装（<https://github.com/huangwl18/language-planner>）を本研究のデータセットで実行したものである．この出所と実行対象は著者による確認に基づく．状態変化312件・配置103件のタスク別結果JSONは本研究のテスト集合に対応する．一方，実験時に使用した公開実装のコミット，変更差分，GPT-4oへの接続処理，Action Translation・Dynamic Exampleの具体的なモデル・候補集合・設定，自動探索・停止・結果記録処理の詳細は確認できない．公開リポジトリの現在のコードが入手可能であることと，実験時の実行コード・設定を特定できることは区別する．VHのバイナリ・シーンの実験時の固定版には記録がない．前提条件の各文と現在参照できる公式資料の対応は表[A2](#tab-condition-source-scope)に示す．現在の公開実装の既定値，構成要素比較の設定や提案実装の検索・停止規則を，これらの不明な設定の代わりに用いない．構成要素比較で確認できる実行設定は[構成要素比較の実行設定](#app-execution-conditions)に示す．

著者への確認でも，これらの未確認事項を補う実験時の追加保有資料はなかった．利用できない範囲は，ベースラインの実験時コードの版・変更差分と詳細設定，各試行とコード版・日時の対応，モデル・生成設定・依存環境の実行記録，データの構築・除外・分割履歴，前提条件辞書の作成時の転記・整形記録，途中候補・判定・グラフ，検索の実採択・重み版・候補順序，実験時VHバイナリ・シーン・プラットフォームの対応である．著者公開実装を用いて得た結果と確認不能な範囲を開示する．

<a id="app-evaluation"></a>

## 実験条件と詳細結果

本資料では，S1・S6を状態変化のtest_task1・test_task6，P1・P65を配置のtest_task1・test_task65の略記とする．miniはGPT-4o mini，4oはGPT-4oを表す．

<a id="section-9"></a>

### データの分布と行動列長

表[A3](#tab-coverage-internal)にシーン・初期部屋の周辺分布を示す．各区分の合計は状態変化のテスト312・事例152，配置のテスト103・事例51となる．部屋は人物の初期配置先であり，物体検索の範囲ではない．

<a id="tab-coverage-internal"></a>

**表A3：シーン・初期部屋別のインスタンス数**

| 区分     | 値         | 状態テスト | 状態事例 | 配置テスト | 配置事例 |
|:---------|:-----------|-----------:|---------:|-----------:|---------:|
| シーン   | 1          |         48 |       36 |         25 |       14 |
| シーン   | 2          |         40 |       28 |         17 |        8 |
| シーン   | 3          |         72 |       28 |         14 |        7 |
| シーン   | 4          |         32 |       12 |         18 |       12 |
| シーン   | 5          |         44 |       16 |          8 |        4 |
| シーン   | 6          |         40 |       12 |          5 |        3 |
| シーン   | 7          |         36 |       20 |         16 |        3 |
| 初期部屋 | bathroom   |         69 |       34 |         26 |        8 |
| 初期部屋 | bedroom    |         72 |       52 |         24 |       13 |
| 初期部屋 | kitchen    |         86 |       35 |         29 |       17 |
| 初期部屋 | livingroom |         85 |       31 |         24 |       13 |

表[A4](#tab-all-outcome-lengths)では成功集合と失敗集合を分け，参照平均も各行と同じ集合から計算した．件数0の平均は「–」とする．表[A5](#tab-common-success-internal)は検証あり／なしの両条件で成功したインスタンスだけを対応付けた平均である．成功集合の違いを除く記述的比較である．

<a id="tab-all-outcome-lengths"></a>

**表A4：全18条件の成功・失敗別行動列長（参照平均も各行と同じ集合で計算）**

| タスク | 提示     | モデル | 検証 | 成功数 | 成功平均 | 参照平均 | 失敗数 | 失敗平均 | 参照平均 |
|:-------|:---------|:-------|:-----|-------:|---------:|---------:|-------:|---------:|---------:|
| 状態   | Baseline | 4o     | –    |     10 |    0.000 |    0.000 |    302 |   10.828 |    4.000 |
| 状態   | Single   | mini   | あり |    195 |    3.969 |    3.662 |    117 |    6.043 |    4.222 |
| 状態   | Single   | 4o     | あり |    246 |    3.923 |    3.927 |     66 |    6.091 |    3.667 |
| 状態   | Multi    | mini   | あり |    234 |    4.179 |    3.735 |     78 |    7.128 |    4.282 |
| 状態   | Multi    | 4o     | あり |    279 |    3.584 |    3.878 |     33 |    1.758 |    3.818 |
| 状態   | Single   | mini   | なし |    192 |    4.203 |    3.792 |    120 |    5.942 |    4.000 |
| 状態   | Single   | 4o     | なし |    237 |    3.979 |    3.932 |     75 |    5.933 |    3.680 |
| 状態   | Multi    | mini   | なし |    217 |    4.558 |    4.028 |     95 |    6.274 |    3.516 |
| 状態   | Multi    | 4o     | なし |    272 |    3.673 |    3.882 |     40 |    2.150 |    3.800 |
| 配置   | Baseline | 4o     | –    |      0 |        – |        – |    103 |   15.398 |    9.175 |
| 配置   | Single   | mini   | あり |     48 |    8.625 |    8.771 |     55 |    6.109 |    9.527 |
| 配置   | Single   | 4o     | あり |     76 |    8.868 |    9.329 |     27 |    5.852 |    8.741 |
| 配置   | Multi    | mini   | あり |     42 |    7.929 |    8.548 |     61 |    5.426 |    9.607 |
| 配置   | Multi    | 4o     | あり |     84 |    8.976 |    9.333 |     19 |    5.158 |    8.474 |
| 配置   | Single   | mini   | なし |     49 |    7.490 |    8.286 |     54 |    5.778 |    9.981 |
| 配置   | Single   | 4o     | なし |     70 |    8.671 |    9.029 |     33 |    4.455 |    9.485 |
| 配置   | Multi    | mini   | なし |     45 |    7.578 |    8.400 |     58 |    5.017 |    9.776 |
| 配置   | Multi    | 4o     | なし |     82 |    8.390 |    9.305 |     21 |    5.333 |    8.667 |

<a id="tab-common-success-internal"></a>

**表A5：検証あり／なしの共通成功集合における平均行動列長**

| タスク | 提示   | モデル | 共通成功数 | 検証あり | 検証なし |  参照 |
|:-------|:-------|:-------|-----------:|---------:|---------:|------:|
| 状態   | Single | mini   |        161 |    3.826 |    3.919 | 3.627 |
| 状態   | Single | 4o     |        220 |    3.777 |    3.886 | 3.909 |
| 状態   | Multi  | mini   |        186 |    4.027 |    4.220 | 3.796 |
| 状態   | Multi  | 4o     |        267 |    3.584 |    3.678 | 3.888 |
| 配置   | Single | mini   |         42 |    8.119 |    7.571 | 8.333 |
| 配置   | Single | 4o     |         64 |    8.734 |    8.703 | 9.078 |
| 配置   | Multi  | mini   |         36 |    7.694 |    7.306 | 8.000 |
| 配置   | Multi  | 4o     |         78 |    8.872 |    8.397 | 9.346 |

<a id="app-execution-conditions"></a>

### 構成要素比較の実行設定

実行制御側はPython 3.12.3，spaCy 3.7.5，en_core_web_sm 3.7.1，inflection 0.5.1，NumPy 1.26.4，requests 2.32.4を用いた．Windows上のVHへ接続し，シーン番号から1を引いて初期化し，タスクの状態配列を上書きした後，表[A6](#tab-fixed-positions-internal)の座標に人物を配置した．同じ位置の参照列実行を比較基準とし，API要求前に記号状態と全ノードの位置・姿勢を照合した．通信クライアントのコミットは`58970fd80951c2eaa1af713e0917d1a105353ad8`である．接続先VHのバイナリ版は独立には確認できておらず，シーン・IDの互換性と状態照合を確認した範囲の評価である．

実行時には`find_solution=False`，録画あり，カメラは`PERSON_FROM_BACK`とした．アニメーション省略と実行順ランダム化は要求の引数に指定せず，通信APIの既定設定を用いた．インフラ障害をタスク失敗と区別し，API・VH要求の自動再試行は行わない．構成要素比較の240件には通信失敗はなかった．参照列長の2倍を実行予算とし，C3では失敗実行も消費する．C3の失敗後修復は予算が残る場合に限り1回行い，修復後の再失敗では終了する．

モデルIDは`gpt-4o-mini-2024-07-18`と`gpt-4o-2024-08-06`，temperatureは0，要求ごとの出力上限は256トークンである．反復ごとにタスク・モデルの8ブロックを並べ替え，各ブロック内の10条件も並べ替える．Pythonの疑似乱数生成器をseed 20260907で初期化し，同じ生成器を3反復にわたって用いる．並べ替え前の列挙順はS1，S6，P1，P65，モデルはmini，4o，条件はC0，C1，C2，C3，C1-budget，C4-budget，C5，R-random，R-fixed，R-noneである．

費用は入力・出力トークン数に記録時点の通常単価を掛けて計算した．100万トークン当たりminiは入力0.15・出力0.60米ドル，4oは入力2.50・出力10.00米ドルで，キャッシュ割引を適用しない推定値である．240件の合計は入力1052576・出力30594トークン，1.681766米ドルである．

<a id="tab-fixed-positions-internal"></a>

**表A6：固定した人物位置（VH座標）**

| タスク |          x |     y |           z |
|:-------|-----------:|------:|------------:|
| S1     | 2.90539312 |  1.25 | -5.62809753 |
| S6     |   -2.41545 |  1.25 | -7.44353151 |
| P1     |  -6.287474 | 1.247 |   0.1396097 |
| P65    |   9.582918 |  1.25 | -4.21981239 |

表[A7](#tab-repeat-internal)の各反復の分母は4である．参照成功集合の分母9はP1を除く3タスクの各3反復からなる．各モデル・条件について，反復別成功数の和は本文の分母12の成功数と一致する．

<a id="tab-repeat-internal"></a>

**表A7：反復別の成功数と参照成功タスクに限定した成功数**

| 条件      | mini r0 |  r1 |  r2 | 参照成功/9 | 4o r0 |  r1 |  r2 | 参照成功/9 |
|:----------|--------:|----:|----:|-----------:|------:|----:|----:|-----------:|
| C0        |       2 |   3 |   3 |          8 |     3 |   3 |   3 |          9 |
| C1        |       3 |   3 |   3 |          9 |     3 |   3 |   3 |          9 |
| C2        |       1 |   1 |   2 |          4 |     3 |   4 |   3 |          9 |
| C3        |       2 |   2 |   1 |          5 |     3 |   3 |   3 |          9 |
| C1-budget |       2 |   1 |   1 |          4 |     4 |   3 |   4 |          9 |
| C4-budget |       2 |   2 |   2 |          6 |     4 |   3 |   3 |          9 |
| C5        |       1 |   2 |   2 |          5 |     3 |   3 |   3 |          9 |
| R-random  |       3 |   2 |   3 |          5 |     3 |   3 |   3 |          9 |
| R-fixed   |       2 |   2 |   3 |          6 |     3 |   3 |   3 |          9 |
| R-none    |       1 |   1 |   1 |          3 |     1 |   1 |   1 |          3 |

<a id="app-retrieval-conditions"></a>

### 検索条件と選択事例

意味類似検索はMiniLMによるタスク名のコサイン類似度を用い，選択名に属する事例のうち最長の行動列を採用する．長さ同点ではデータの格納順で先の事例を選ぶ．表[A8](#tab-semantic-internal)の上位差は第1位と第2位のコサイン類似度の差である．固定検索は候補名を辞書順に並べた最初の名前を使い，状態変化では「Turn off all candles」，配置では「Put all apples in the fridge」となる．noneは事例のuserメッセージを空文字列にする．

ランダム検索は異なる候補名から一様に1名選び，その名前の最長列を採用する．反復別に，文字列 `20260906/種別/タスクID/反復` のUTF-8バイト列のSHA-256の先頭16桁を16進整数としてseedにする．種別は`state_change_task`または`placement_task`，タスクIDは`test_task1`等，反復は0，1，2である．Pythonの`random.Random(seed).choice`を辞書順の候補名リストへ適用する．選択は両モデルで共通とし，表[A9](#tab-random-internal)に具体的な名前を示す．

<a id="tab-semantic-internal"></a>

**表A8：意味類似検索で選択した事例**

| タスク | 選択した指示                         | 類似度 | 上位差 | 列長 |
|:-------|:-------------------------------------|-------:|-------:|-----:|
| S1     | Turn on all tablelamps               |  0.611 |  0.066 |    6 |
| S6     | Turn on all tablelamps               |  0.611 |  0.066 |    6 |
| P1     | Put all cupcakes on the kitchentable |  0.854 |  0.049 |    8 |
| P65    | Put all plums on the kitchentable    |  0.761 |  0.098 |    8 |

<a id="tab-random-internal"></a>

**表A9：ランダム検索で選択した指示（両モデル共通）**

| タスク | 反復0 | 反復1 | 反復2 |
|:---|:---|:---|:---|
| S1 | Turn on all tablelamps | Turn off all faucets | Turn off all faucets |
| S6 | Turn on all computers | Turn off all faucets | Turn on all tablelamps |
| P1 | Put all bananas on the kitchentable | Put all crackers on the coffeetable | Put all plums on the coffeetable |
| P65 | Put all plums on the coffeetable | Put all bananas on the kitchentable | Put all chips on the coffeetable |

<a id="app-symbolic-rules"></a>

### 記号判定とラベルの定義

条件辞書の8操作を原子条件に分解する．WALKは非保持，GRABは近接と非保持，SWITCHONは近接とOFF，SWITCHOFFは近接とON，OPENは近接とCLOSED，CLOSEは近接とOPEN，PUTは対象の保持と配置先への近接，PUTINはそれらと配置先がCLOSEDでないことを要求する．いずれかの原子がfalseならfalse，falseがなくunknownがあればunknown，全原子がtrueならtrueとする．

C2は抽出辞書を入力とする．近接は抽出対象にIDがなければunknown，保持は左右の手のIDとの一致，状態は配列が空または欠落ならunknownとして判定する．C5は全ノードと人物ID 1のCLOSE・HOLDS_RH・HOLDS_LH関係を使う．完全グラフの空状態集合は既知の空集合として扱うため，例えばCLOSEDでないという否定条件をtrueとできる点がC2と異なる．形式不正と条件の情報不足は区別する．

C2／C5はtrueのみを受理し，それ以外は1回の再生成へ進む．C2ではfalseの条件文に続けてunknownの条件を`Cannot determine from the available knowledge: `という接頭辞付きで列挙する．C5はfalseとunknownの条件文をそのまま列挙する．その文字列をListing [行動再生成](sec4.tex#L149)の理由へ代入する．

LLMの正答数はYesを含む受理と上記true／falseの一致を数え，unknownを分母から除く．誤受理はfalseに対する受理，誤棄却はtrueに対する棄却である．終了判定は厳密なEndとゴール充足を照合し，非EndとEnd/Continue以外の書式違反も区別する．

<a id="app-comparison-prompts"></a>

### 比較条件固有のプロンプト

C0・C1・C2・C5および検索条件の生成・終了・再生成メッセージは[全メッセージの組立て](#app-prompts)を基礎とする．C3は失敗後のグラフを再抽出して生成時の環境メッセージを置換し，次の固定文，改行，VHが返した失敗応答のJSON文字列を理由として再生成へ渡す．

<a id="lst-inline7"></a>

**Listing A7：C3の失敗後再生成の理由**

```text
The simulator returned failure for this action. The environment knowledge has been refreshed. Revise once.
```

C1-budgetは候補生成の後，Listing [前提条件判定](sec4.tex#L117)のuser入力だけで条件をレビューする．操作が条件辞書にない場合はsystemを付け，環境文，改行，`Candidate: `と候補，改行，`Check the output format. Reply Yes or No.`をuser入力にする．続いて，レビュー時のメッセージ，そのassistant応答，次のuser文を送る．

<a id="lst-inline8"></a>

**Listing A8：C1-budgetの条件説明指示**

```text
Briefly explain the satisfied, violated or unknown conditions. If all are satisfied, say so.
```

C4-budgetはsystemを付け，環境文に続けて改行ごとに`Task: `と指示，`Candidate: `と候補，次のレビュー文をuser入力とする．

<a id="lst-inline9"></a>

**Listing A9：C4-budgetの候補レビュー指示**

```text
Review whether this candidate is a sensible next step for the task. Reply Yes or No. Do not use a supplied precondition checklist.
```

そのメッセージとassistantの応答に，次のuser文を追加する．

<a id="lst-inline10"></a>

**Listing A10：C4-budgetの候補説明指示**

```text
Briefly explain whether to retain or revise this candidate based on the task and current knowledge.
```

両budget条件はレビューがYesでも再生成する．再生成はsystem，生成時の5個のuser，候補assistant，説明応答をそのまま入れたuser，最後の生成指示のGenerateをRegenerateへ置換したuserの順とする．レビューのsystemはListing [A1](#lst-prompt-spec)のSYSTEM，再生成のsystemは末尾空白付きのCHAT_SYSTEMを用いる．条件違反を断定する追加文は説明に付けない．生成・レビュー・説明・再生成の4要求を各256トークン上限とし，終了判定の要求は別に数える．

<a id="app-static-conditions"></a>

### 固定入力による前提条件評価

静的評価は8操作の充足例各1件と，16原子条件を一つずつ違反させた16件の計24入力を用いる．さらにSWITCHON，SWITCHOFF，OPEN，CLOSEについて対象の状態を欠落させた4入力を用い，unknownとして精度の分母から除く．各入力を2モデルで3反復し，temperature 0，出力上限160トークン，自動再試行なしで問い合わせる．既知ラベルは各モデル72判定，除外は12判定となる．

物体はapple 101，fridge 102，lightswitch 103，kitchentable 104，部屋はkitchen 900とする．基本状態は全物体に近接，両手は空，fridgeはCLOSED，lightswitchはOFF，appleとkitchentableの状態配列は空で，すべてkitchenに所属する．fridgeだけにCONTAINERS属性を与える．充足例ではSWITCHOFFのみlightswitchをON，CLOSEとPUTINではfridgeをOPEN，PUTとPUTINではappleを保持に変更する．対象はWALK・GRABではapple，SWITCHON・SWITCHOFFではlightswitch，OPEN・CLOSEではfridge，PUTではappleとkitchentable，PUTINではappleとfridgeとする．

各違反例は対応する充足例から，非保持違反ならappleを保持，保持違反なら保持を空，近接違反なら近接集合を空，状態違反ならON/OFFまたはOPEN/CLOSEDを反転する．unknown例では対象状態を欠落させ，自然言語化では状態を述べない．支持・包含関係は付与しない．[知識抽出と自然言語化](#app-knowledge)の変換とListing [前提条件判定](sec4.tex#L117)の要求を用いる．既知の正解はtrue 8入力・false 16入力であり，3反復の正答はminiでtrue 24・false 27の51/72，4oでtrue 24・false 29の53/72だった．

<a id="app-review-conditions"></a>

### 棄却候補の状態照合と人手確認

表[A10](#tab-replay-internal)のrは反復番号，stepは候補を判定したステップを表す．C1はLLM検証，RfはR-fixed，RrはR-randomである．同じID集合の各ノードについてクラス・状態・属性と関係辺を比較し，順序だけの違いを除いた一致を記号一致とする．位置差は全ノードのユークリッド距離の最大，姿勢差は四元数の符号同値を考慮した $`\min(\|q_1-q_2\|,\|q_1+q_2\|)`$ の全ノード最大である．全ノードに位置・姿勢があり，記号一致，位置差0.001以下，姿勢差0.0001以下の場合だけ状態一致とする．距離は表示桁へ丸める前に判定する．候補実行前にこの検査を行ったものではなく，記録グラフの事後比較である．

<a id="tab-replay-internal"></a>

**表A10：棄却候補8件の再実行と状態照合（○：一致または成功，×：不一致または失敗）**

| 番号 | タスク | モデル | 条件 | r | step | 候補 | 記号 | 位置差 | 姿勢差 | 状態 | VH |
|---:|:---|:---|:---|:---|:---|:---|:---|---:|---:|:---|:---|
| 1 | S6 | 4o | C1 | 0 | 4 | \[SWITCHON\] \<lightswitch\> (261) | × | 0.506386 | 0.076625 | × | ○ |
| 2 | S6 | mini | C1 | 0 | 4 | \[SWITCHON\] \<lightswitch\> (261) | × | 0.119574 | 0.007552 | × | ○ |
| 3 | S6 | 4o | Rf | 0 | 1 | \[SWITCHON\] \<lightswitch\> (261) | ○ | 0.000000 | 0.000000 | ○ | ○ |
| 4 | P1 | mini | Rf | 1 | 7 | \[PUTIN\] \<cupcake\> (195) \<kitchencounter\> (238) | ○ | 0.010881 | 0.003474 | × | × |
| 5 | P1 | mini | Rr | 2 | 2 | \[OPEN\] \<desk\> (108) | ○ | 0.074607 | 0.042299 | × | × |
| 6 | P65 | 4o | C1 | 0 | 2 | \[OPEN\] \<fridge\> (103) | ○ | 0.037343 | 1.297491 | × | ○ |
| 7 | P65 | mini | C1 | 0 | 1 | \[WALK\] \<kitchencounter\> (92) | ○ | 0.000000 | 0.000000 | ○ | ○ |
| 8 | P65 | 4o | Rf | 0 | 2 | \[OPEN\] \<fridge\> (103) | ○ | 0.095187 | 0.543762 | × | ○ |

実行直前照合を条件とする評価を表[A11](#tab-replay-gated)に示す．候補の番号・行動・モデル・条件・反復は表[A10](#tab-replay-internal)と同じである．各候補につき1回だけ初期化と成功接頭列の再生を行い，記号一致・位置差0.001以下・姿勢差0.0001以下を実行の条件とした．候補判定に用いたグラフの取得を実行前の最後のRPCとし，通過時だけ候補を実行して実行後グラフを取得した．人物追加後の途中グラフ転送や自動再試行は行わない．全8件で初期化照合が通過し，接頭列の計15行動はすべて成功した．候補は2件だけ実行し，6件は状態不一致のため未実行だった．通信エラーとAPI要求は0件で，API費用は0米ドルである．照合通過した2件は接頭行動数0の候補である．

<a id="tab-replay-gated"></a>

**表A11：実行直前照合を条件とした代表候補評価（番号は表[A10](#tab-replay-internal)に対応）**

| 番号 | 接頭数 | 記号 |   位置差 |   姿勢差 | 候補結果 |
|-----:|-------:|:-----|---------:|---------:|:---------|
|    1 |      3 | ×    | 0.419929 | 0.035789 | 未実行   |
|    2 |      3 | ○    | 0.091742 | 0.020617 | 未実行   |
|    3 |      0 | ○    | 0.000000 | 0.000000 | 成功     |
|    4 |      6 | ○    | 0.247181 | 0.045965 | 未実行   |
|    5 |      1 | ○    | 0.041228 | 0.025620 | 未実行   |
|    6 |      1 | ○    | 0.101502 | 0.920426 | 未実行   |
|    7 |      0 | ○    | 0.000000 | 0.000000 | 成功     |
|    8 |      1 | ○    | 0.058573 | 0.206024 | 未実行   |

判定応答の人手確認では，上記8候補について同じステップの抽出知識・完全グラフ・条件辞書と判定応答を照合するよう依頼した．ラベルは，主要主張が状態と一致し重要な見落としがない場合を「正しい」，一部は一致するが重要な誤り・見落としがある場合を「一部正しい」，中心的理由が状態と反対または存在しない事実に基づく場合を「誤り」，応答・状態情報が不足して検証できない場合を「判断不能」とした．著者ugaiによる2026年9月7日のこの票への記入は全8件「判断不能」，根拠「情報が不十分」である．未充足条件応答の確認記録とは区別する．

表[A12](#tab-unmet-internal)は判定応答と，別要求で得られた未充足条件の応答を区別して示す．4番の判定応答は，cupcakeの保持が入力から確認できない一方，配置先への近接とOPENは確認できると述べ，最後にNoと結論する文章だった．表の「条件別説明付きNo」はこの応答の要約である．他7件の判定はNoまたはNo.のみだった．未充足条件応答は全文を示し，この応答を対象とする著者の確認記録とその制約を[未充足条件応答に対する著者の確認記録](#app-author-unmet-review)に示す．

<a id="tab-unmet-internal"></a>

**表A12：代表候補の判定応答と未充足条件応答（番号は表[A10](#tab-replay-internal)と共通）**

| 番号 | 判定応答 | 別要求の未充足条件応答（全文） |
|---:|:---|:---|
| 1 | No. | \<lightswitch\> (261) is OFF. |
| 2 | No | \<lightswitch\> (261) is ON. |
| 3 | No | \<lightswitch\> (261) is OFF. |
| 4 | 条件別説明付きNo | You are holding \<cupcake\> (195) in your right hand or left hand. |
| 5 | No | \<desk\> (108) is CLOSED. |
| 6 | No. | You are close to \<fridge\> (103). |
| 7 | No | The precondition that \<kitchencounter\> (92) is not held in your right hand or left hand is not satisfied. |
| 8 | No. | You are close to \<fridge\> (103). |

接頭列方式で不一致だった6件を対象とする，人物のいないシーンへの保存グラフ復元を表[A13](#tab-clean-restore)に示す．元タスクのシーンへリセットし，人物がいないことを確認してから，候補時点の完全グラフを`animate_character=True, transfer_transform=True, randomize=False`で1回だけ転送した．実行直前の最後のグラフ取得で表[A11](#tab-replay-gated)と同じ照合を行い，通過時だけ候補を実行した．全6件の初期化と転送要求は応答成功で，通信エラー・API要求は0件だった．4件は状態不一致のため候補未実行である．

<a id="tab-clean-restore"></a>

**表A13：人物のいないシーンへの候補時点グラフ復元（番号は表[A10](#tab-replay-internal)と共通）**

| 番号 | 記号 | 最大位置差 | 最大姿勢差 | 候補結果 | 不一致の観測 |
|---:|:---|---:|---:|:---|:---|
| 1 | × | $`1.910\times10^{-6}`$ | 0 | 未実行 | 保存グラフにあったFACING辺7本が欠落 |
| 2 | × | $`1.910\times10^{-6}`$ | 0 | 未実行 | 保存グラフにあったFACING辺14本が欠落 |
| 4 | × | 1.237802 | 0.910223 | 未実行 | cupcake 195の位置・姿勢とON desk 108関係が不一致 |
| 5 | × | $`2.000\times10^{-6}`$ | $`3.000\times10^{-8}`$ | 未実行 | FACING辺1本が追加 |
| 6 | ○ | 0 | 0 | 成功 | 許容差内で一致 |
| 8 | ○ | 0 | $`7.021\times10^{-8}`$ | 成功 | 許容差内で一致 |

接頭列方式で通過した3・7番と復元方式で通過した6・8番を合わせ，異なる4候補で実行直前の照合が通過し，4件ともVH成功だった．8件の接頭列方式と不一致6件の復元方式は同じ候補を含む段階的な診断であり，14件の独立試行として合算しない．試行結果の確認後に，評価範囲を照合通過4件と本手順で未再現だった1・2・4・5番の開示に限定した．接頭列方式では，同じ行動列の再生時に人物の位置・姿勢が変化した例があった．グラフに現れない内部状態の一致は未確認である．

<a id="app-author-unmet-review"></a>

#### 未充足条件応答に対する著者の確認記録

表[A14](#tab-author-unmet-review)は，表[A12](#tab-unmet-internal)の未充足条件応答そのものを対象とした著者ugaiによる2026年9月7日の記入である．同じ8候補について要求メッセージ全文，応答全文，抽出辞書，関連する完全グラフの状態・関係を提示した．採点基準は，未充足条件の列挙と網羅が妥当なら「正しい」，妥当な部分と誤り・欠落があれば「一部正しい」，主要な説明が不適切なら「誤り」，資料でも判断できなければ「判断不能」とした．根拠・評価者・日付も記録した．表の根拠は著者記入のまま示し，AIによる修正文や正解ラベルへ置き換えていない．

評価者は最初に応答文と現在状態の一致で採点したと申告したため，その票（正しい2件・誤り6件）と未充足条件としての再確認票を分けた．再確認ではAI支援による採点基準の説明と個別例の整合性照会を複数回行い，著者がラベル・根拠を修正した．これは同一著者の支援付き事例確認である．判定応答を対象にした全8件「判断不能」の票とも合算しない． 著者の最終記入は正しい1件，一部正しい0件，誤り7件，判断不能0件である．

<a id="tab-author-unmet-review"></a>

**表A14：未充足条件応答への著者記入ラベルと根拠（番号は表[A12](#tab-unmet-internal)と共通）**

| 番号 | 著者ラベル | 著者記入の根拠 |
|---:|:---|:---|
| 1 | 正しい | The lightswitch (261) is ON and and is INSIDE the kitchen (205). |
| 2 | 誤り | The lightswitch (261) is ON and and is INSIDE the kitchen (205). Both conditions are required |
| 3 | 誤り | The lightswitch (261) is ON and and is INSIDE the kitchen (205). Both conditions are required |
| 4 | 誤り | cupcake (196) and cupcake (195) are ON the desk (108). |
| 5 | 誤り | The desk (108) is CLOSED |
| 6 | 誤り | You are INSIDE the kitchen (11). しかし、冷蔵庫に近いも必要 |
| 7 | 誤り | The precondition that \<kitchencounter\> (92) is not held in your right hand or left hand is not satisfied. ではなく、プラムがキッチンにあるのでキッチンに歩く |
| 8 | 誤り | You are INSIDE the kitchen (11).だが冷蔵庫に近いも必要 |

例えば4番は非保持を示す根拠，6・8番は近接が必要という根拠を記しているが，それだけでは保持・近接を未充足条件として列挙した応答を誤りとする理由を十分に説明しない．評価対象の読み方と根拠の対応に曖昧さが残り，第三者による裁定も行っていない．この記入結果を著者の判断記録として提示する．

<a id="section-17"></a>

### 記録行動列の再生

表[A15](#tab-saved-replay-internal)は，基本性能評価のMulti・検証ありで得た8列の固定位置再生である．表[A10](#tab-replay-internal)の未実行候補の再実行とは区別する．列長0の2件も行動を要しない再生として含め，8列すべてを末尾まで再生できた．失敗した最後の未記録行動と生成時の人物位置は再生対象に含めない．

<a id="tab-saved-replay-internal"></a>

**表A15：記録行動列8本の再生と最終ゴール（全列の再生は成功）**

| タスク | モデル | 列長 | 最終ゴール |
|:-------|:-------|-----:|:-----------|
| P1     | mini   |    1 | 未達       |
| P1     | 4o     |    4 | 未達       |
| P65    | mini   |    5 | 未達       |
| P65    | 4o     |   10 | 充足       |
| S1     | mini   |    0 | 充足       |
| S1     | 4o     |    0 | 充足       |
| S6     | mini   |    5 | 充足       |
| S6     | 4o     |    4 | 充足       |

<a id="app-statistics"></a>

## 分布・対応比較・データ網羅の詳細

本資料の数値は基本性能評価の同じ結果ラベルと記録列から求めた．M1–M18は表[A16](#tab-method-dictionary)の条件，S/Fは成功／失敗，E/R/TはExecution Failure／Reaching Maximum Attempts／Erroneous Terminateを表す．SDは標本標準偏差，IQRは第3四分位点と第1四分位点の差で，四分位点はソート後の位置$`(n-1)p`$を線形補間した．空集合の統計と1件以下のSDは未定義（–）であり，0ではない．

<a id="tab-method-dictionary"></a>

**表A16：詳細集計に用いる条件番号**

| 番号 | タスク | 提示     | モデル | 検証 |
|:-----|:-------|:---------|:-------|:-----|
| M1   | 状態   | Baseline | 4o     | –    |
| M2   | 状態   | Single   | mini   | あり |
| M3   | 状態   | Single   | 4o     | あり |
| M4   | 状態   | Multi    | mini   | あり |
| M5   | 状態   | Multi    | 4o     | あり |
| M6   | 状態   | Single   | mini   | なし |
| M7   | 状態   | Single   | 4o     | なし |
| M8   | 状態   | Multi    | mini   | なし |
| M9   | 状態   | Multi    | 4o     | なし |
| M10  | 配置   | Baseline | 4o     | –    |
| M11  | 配置   | Single   | mini   | あり |
| M12  | 配置   | Single   | 4o     | あり |
| M13  | 配置   | Multi    | mini   | あり |
| M14  | 配置   | Multi    | 4o     | あり |
| M15  | 配置   | Single   | mini   | なし |
| M16  | 配置   | Single   | 4o     | なし |
| M17  | 配置   | Multi    | mini   | なし |
| M18  | 配置   | Multi    | 4o     | なし |

<a id="tab-length-distribution"></a>

**表A17：成功・失敗別の列長分布**

| 条件 | 結果 | $`n`$ | 記録中央値 | SD     | IQR    | 参照中央値 | SD    | IQR   |
|:-----|:-----|:------|:-----------|:-------|:-------|:-----------|:------|:------|
| M1   | S    | 10    | 0.000      | 0.000  | 0.000  | 0.000      | 0.000 | 0.000 |
| M1   | F    | 302   | 20.000     | 9.816  | 20.000 | 4.000      | 2.088 | 4.000 |
| M2   | S    | 195   | 4.000      | 2.568  | 4.000  | 4.000      | 2.194 | 4.000 |
| M2   | F    | 117   | 4.000      | 4.780  | 6.000  | 4.000      | 2.097 | 4.000 |
| M3   | S    | 246   | 4.000      | 2.447  | 3.750  | 4.000      | 2.216 | 4.000 |
| M3   | F    | 66    | 4.000      | 4.488  | 4.000  | 4.000      | 2.003 | 2.000 |
| M4   | S    | 234   | 4.000      | 2.507  | 4.000  | 4.000      | 2.157 | 4.000 |
| M4   | F    | 78    | 8.000      | 4.924  | 9.000  | 4.000      | 2.180 | 4.000 |
| M5   | S    | 279   | 3.000      | 2.122  | 3.000  | 4.000      | 2.238 | 4.000 |
| M5   | F    | 33    | 1.000      | 2.062  | 2.000  | 4.000      | 1.530 | 2.000 |
| M6   | S    | 192   | 4.000      | 2.775  | 4.000  | 4.000      | 2.297 | 4.000 |
| M6   | F    | 120   | 4.000      | 4.314  | 4.000  | 4.000      | 1.958 | 4.000 |
| M7   | S    | 237   | 3.000      | 2.645  | 4.000  | 4.000      | 2.276 | 4.000 |
| M7   | F    | 75    | 8.000      | 4.147  | 6.000  | 4.000      | 1.802 | 2.000 |
| M8   | S    | 217   | 4.000      | 2.965  | 5.000  | 4.000      | 2.305 | 4.000 |
| M8   | F    | 95    | 5.000      | 3.945  | 4.000  | 4.000      | 1.792 | 2.000 |
| M9   | S    | 272   | 3.000      | 2.250  | 3.000  | 4.000      | 2.197 | 4.000 |
| M9   | F    | 40    | 2.000      | 1.929  | 3.000  | 4.000      | 2.015 | 2.000 |
| M10  | S    | 0     | –          | –      | –      | –          | –     | –     |
| M10  | F    | 103   | 20.000     | 7.198  | 9.500  | 8.000      | 3.451 | 1.000 |
| M11  | S    | 48    | 8.000      | 2.655  | 1.250  | 8.000      | 2.528 | 1.000 |
| M11  | F    | 55    | 5.000      | 3.680  | 4.000  | 8.000      | 4.082 | 1.000 |
| M12  | S    | 76    | 8.000      | 2.282  | 2.000  | 8.000      | 3.130 | 1.000 |
| M12  | F    | 27    | 5.000      | 4.605  | 5.500  | 8.000      | 4.266 | 1.000 |
| M13  | S    | 42    | 8.000      | 2.213  | 2.000  | 8.000      | 3.102 | 1.000 |
| M13  | F    | 61    | 5.000      | 3.339  | 3.000  | 9.000      | 3.634 | 1.000 |
| M14  | S    | 84    | 8.000      | 2.464  | 2.000  | 8.000      | 3.031 | 1.000 |
| M14  | F    | 19    | 3.000      | 9.161  | 4.500  | 8.000      | 4.948 | 1.000 |
| M15  | S    | 49    | 8.000      | 1.816  | 1.000  | 8.000      | 1.720 | 1.000 |
| M15  | F    | 54    | 4.500      | 3.790  | 3.000  | 9.000      | 4.342 | 3.250 |
| M16  | S    | 70    | 8.000      | 2.749  | 1.750  | 8.000      | 2.576 | 1.000 |
| M16  | F    | 33    | 3.000      | 4.206  | 4.000  | 8.000      | 4.848 | 1.000 |
| M17  | S    | 45    | 8.000      | 2.210  | 1.000  | 8.000      | 2.016 | 1.000 |
| M17  | F    | 58    | 4.000      | 2.711  | 2.750  | 8.000      | 4.164 | 1.000 |
| M18  | S    | 82    | 8.000      | 2.308  | 2.000  | 8.000      | 3.054 | 1.000 |
| M18  | F    | 21    | 2.000      | 10.155 | 4.000  | 8.000      | 4.757 | 1.000 |

<a id="tab-failure-lengths"></a>

**表A18：失敗類型別の列長**

| 条件 | 類型 | $`n`$ | 記録平均 | 中央値 | SD     | IQR    | 参照平均 |
|:-----|:-----|:------|:---------|:-------|:-------|:-------|:---------|
| M1   | E    | 0     | –        | –      | –      | –      | –        |
| M1   | R    | 167   | 19.329   | 20.000 | 2.999  | 0.000  | 3.677    |
| M1   | T    | 135   | 0.311    | 0.000  | 1.953  | 0.000  | 4.400    |
| M2   | E    | 8     | 0.875    | 1.000  | 0.835  | 1.250  | 3.000    |
| M2   | R    | 72    | 8.500    | 8.000  | 4.399  | 8.000  | 4.250    |
| M2   | T    | 37    | 2.378    | 2.000  | 1.876  | 4.000  | 4.432    |
| M3   | E    | 5     | 1.000    | 1.000  | 0.707  | 0.000  | 4.800    |
| M3   | R    | 54    | 7.259    | 8.000  | 4.117  | 7.000  | 3.630    |
| M3   | T    | 7     | 0.714    | 1.000  | 0.756  | 1.000  | 3.143    |
| M4   | E    | 14    | 2.000    | 1.500  | 1.519  | 1.750  | 4.000    |
| M4   | R    | 57    | 9.123    | 8.000  | 4.192  | 4.000  | 4.561    |
| M4   | T    | 7     | 1.143    | 1.000  | 1.069  | 1.000  | 2.571    |
| M5   | E    | 6     | 2.333    | 1.000  | 3.777  | 0.000  | 3.667    |
| M5   | R    | 0     | –        | –      | –      | –      | –        |
| M5   | T    | 27    | 1.630    | 1.000  | 1.548  | 2.000  | 3.852    |
| M6   | E    | 1     | 5.000    | 5.000  | –      | 0.000  | 4.000    |
| M6   | R    | 79    | 7.747    | 8.000  | 4.068  | 8.000  | 3.873    |
| M6   | T    | 40    | 2.400    | 2.000  | 2.048  | 4.000  | 4.250    |
| M7   | E    | 5     | 1.200    | 1.000  | 0.447  | 0.000  | 5.200    |
| M7   | R    | 59    | 7.254    | 8.000  | 3.675  | 4.000  | 3.627    |
| M7   | T    | 11    | 1.000    | 1.000  | 0.775  | 1.000  | 3.273    |
| M8   | E    | 5     | 3.000    | 3.000  | 1.414  | 0.000  | 3.200    |
| M8   | R    | 79    | 7.139    | 8.000  | 3.717  | 4.000  | 3.570    |
| M8   | T    | 11    | 1.545    | 1.000  | 1.368  | 2.000  | 3.273    |
| M9   | E    | 3     | 0.667    | 1.000  | 0.577  | 0.500  | 2.000    |
| M9   | R    | 5     | 4.000    | 4.000  | 0.000  | 0.000  | 2.000    |
| M9   | T    | 32    | 2.000    | 2.000  | 1.967  | 1.500  | 4.250    |
| M10  | E    | 1     | 13.000   | 13.000 | –      | 0.000  | 8.000    |
| M10  | R    | 59    | 19.678   | 20.000 | 1.345  | 0.000  | 7.915    |
| M10  | T    | 43    | 9.581    | 9.000  | 7.926  | 19.000 | 10.930   |
| M11  | E    | 15    | 5.000    | 5.000  | 2.976  | 3.000  | 8.467    |
| M11  | R    | 3     | 5.333    | 0.000  | 9.238  | 8.000  | 2.667    |
| M11  | T    | 37    | 6.622    | 6.000  | 3.361  | 4.000  | 10.514   |
| M12  | E    | 12    | 4.417    | 4.000  | 2.778  | 4.000  | 8.333    |
| M12  | R    | 3     | 5.333    | 0.000  | 9.238  | 8.000  | 2.667    |
| M12  | T    | 12    | 7.417    | 7.000  | 4.680  | 5.250  | 10.667   |
| M13  | E    | 12    | 3.083    | 2.500  | 2.466  | 4.000  | 9.417    |
| M13  | R    | 3     | 10.667   | 16.000 | 9.238  | 8.000  | 5.333    |
| M13  | T    | 46    | 5.696    | 5.000  | 2.493  | 3.000  | 9.935    |
| M14  | E    | 12    | 2.500    | 2.000  | 2.276  | 3.000  | 8.250    |
| M14  | R    | 2     | 0.000    | 0.000  | 0.000  | 0.000  | 0.000    |
| M14  | T    | 5     | 13.600   | 8.000  | 15.485 | 2.000  | 12.400   |
| M15  | E    | 12    | 4.500    | 5.000  | 1.883  | 1.250  | 8.583    |
| M15  | R    | 2     | 8.000    | 8.000  | 11.314 | 8.000  | 4.000    |
| M15  | T    | 40    | 6.050    | 4.000  | 3.796  | 3.250  | 10.700   |
| M16  | E    | 17    | 2.529    | 2.000  | 2.211  | 2.000  | 9.471    |
| M16  | R    | 3     | 5.333    | 0.000  | 9.238  | 8.000  | 2.667    |
| M16  | T    | 13    | 6.769    | 6.000  | 3.898  | 4.000  | 11.077   |
| M17  | E    | 13    | 3.692    | 3.000  | 3.521  | 4.000  | 8.308    |
| M17  | R    | 1     | 0.000    | 0.000  | –      | 0.000  | 0.000    |
| M17  | T    | 44    | 5.523    | 5.000  | 2.215  | 3.250  | 10.432   |
| M18  | E    | 12    | 2.000    | 2.000  | 1.477  | 1.250  | 8.583    |
| M18  | R    | 3     | 16.000   | 0.000  | 27.713 | 24.000 | 8.000    |
| M18  | T    | 6     | 6.667    | 7.000  | 1.862  | 2.250  | 9.167    |

<a id="section-19"></a>

### 参照列との差と比

差$`D=L_{exec}-L_{ref}`$は同一IDごとに計算する．比$`Q=L_{exec}/L_{ref}`$は参照長が正のIDだけを用い，表の$`n_Q`$を分母とする．状態変化27件・配置2件の参照長0は比から除く．成功・失敗ごとに平均の比ではなく各IDの比を平均する．手法間で成功集合が異なるため，表[A5](#tab-common-success-internal)の共通成功集合による比較も併用する．

<a id="tab-length-ratios"></a>

**表A19：同一IDでの列長差と比**

| 条件 | 結果 | $`n_D`$ | D平均  | 中央値 | SD     | IQR    | $`n_Q`$ | Q平均 | 中央値 | SD    | IQR   |
|:-----|:-----|:--------|:-------|:-------|:-------|:-------|:--------|:------|:-------|:------|:------|
| M1   | S    | 10      | 0.000  | 0.000  | 0.000  | 0.000  | 0       | –     | –      | –     | –     |
| M1   | F    | 302     | 6.828  | 12.000 | 10.259 | 20.000 | 285     | 3.087 | 2.500  | 3.540 | 5.000 |
| M2   | S    | 195     | 0.308  | 0.000  | 1.009  | 0.000  | 172     | 1.081 | 1.000  | 0.231 | 0.000 |
| M2   | F    | 117     | 1.821  | 2.000  | 3.708  | 5.000  | 113     | 1.395 | 2.000  | 0.778 | 1.333 |
| M3   | S    | 246     | -0.004 | 0.000  | 1.024  | 1.000  | 223     | 0.994 | 1.000  | 0.255 | 0.167 |
| M3   | F    | 66      | 2.424  | 2.000  | 3.239  | 2.000  | 62      | 1.653 | 2.000  | 0.719 | 0.000 |
| M4   | S    | 234     | 0.444  | 0.000  | 1.084  | 1.000  | 209     | 1.127 | 1.000  | 0.248 | 0.250 |
| M4   | F    | 78      | 2.846  | 4.000  | 3.476  | 6.000  | 76      | 1.586 | 2.000  | 0.698 | 1.042 |
| M5   | S    | 279     | -0.294 | 0.000  | 0.678  | 1.000  | 252     | 0.929 | 1.000  | 0.193 | 0.167 |
| M5   | F    | 33      | -2.061 | -2.000 | 1.298  | 1.000  | 33      | 0.370 | 0.250  | 0.345 | 0.500 |
| M6   | S    | 192     | 0.411  | 0.000  | 1.089  | 0.000  | 167     | 1.093 | 1.000  | 0.233 | 0.167 |
| M6   | F    | 120     | 1.942  | 2.000  | 3.252  | 5.250  | 118     | 1.476 | 2.000  | 0.753 | 1.250 |
| M7   | S    | 237     | 0.046  | 0.000  | 1.266  | 1.000  | 214     | 1.005 | 1.000  | 0.300 | 0.167 |
| M7   | F    | 75      | 2.253  | 4.000  | 3.180  | 4.000  | 71      | 1.610 | 2.000  | 0.733 | 0.000 |
| M8   | S    | 217     | 0.530  | 0.000  | 1.371  | 1.000  | 194     | 1.109 | 1.000  | 0.275 | 0.250 |
| M8   | F    | 95      | 2.758  | 2.000  | 2.517  | 2.000  | 91      | 1.749 | 2.000  | 0.571 | 0.000 |
| M9   | S    | 272     | -0.210 | 0.000  | 0.853  | 1.000  | 245     | 0.942 | 1.000  | 0.227 | 0.167 |
| M9   | F    | 40      | -1.650 | -2.000 | 1.642  | 2.000  | 40      | 0.590 | 0.500  | 0.602 | 0.417 |
| M10  | S    | 0       | –      | –      | –      | –      | 0       | –     | –      | –     | –     |
| M10  | F    | 103     | 6.223  | 11.000 | 7.863  | 11.000 | 101     | 1.742 | 2.222  | 0.905 | 1.375 |
| M11  | S    | 48      | -0.146 | 0.000  | 1.052  | 1.000  | 48      | 0.990 | 1.000  | 0.159 | 0.111 |
| M11  | F    | 55      | -3.418 | -4.000 | 3.023  | 1.000  | 53      | 0.637 | 0.556  | 0.313 | 0.192 |
| M12  | S    | 76      | -0.461 | 0.000  | 2.068  | 1.000  | 76      | 0.969 | 1.000  | 0.160 | 0.111 |
| M12  | F    | 27      | -2.889 | -4.000 | 3.274  | 2.500  | 25      | 0.651 | 0.615  | 0.403 | 0.250 |
| M13  | S    | 42      | -0.619 | 0.000  | 1.821  | 1.000  | 41      | 0.941 | 1.000  | 0.135 | 0.125 |
| M13  | F    | 61      | -4.180 | -4.000 | 3.413  | 1.000  | 60      | 0.564 | 0.528  | 0.340 | 0.222 |
| M14  | S    | 84      | -0.357 | 0.000  | 2.098  | 1.000  | 84      | 0.976 | 1.000  | 0.168 | 0.111 |
| M14  | F    | 19      | -3.316 | -4.000 | 5.598  | 5.000  | 17      | 0.481 | 0.444  | 0.424 | 0.567 |
| M15  | S    | 49      | -0.796 | -1.000 | 0.790  | 1.000  | 48      | 0.902 | 0.889  | 0.097 | 0.125 |
| M15  | F    | 54      | -4.204 | -4.000 | 2.616  | 1.000  | 53      | 0.562 | 0.500  | 0.255 | 0.125 |
| M16  | S    | 70      | -0.357 | 0.000  | 2.200  | 1.000  | 70      | 0.965 | 1.000  | 0.194 | 0.125 |
| M16  | F    | 33      | -5.030 | -5.000 | 4.864  | 2.000  | 31      | 0.472 | 0.375  | 0.388 | 0.335 |
| M17  | S    | 45      | -0.822 | -1.000 | 0.886  | 1.000  | 44      | 0.898 | 0.889  | 0.103 | 0.125 |
| M17  | F    | 58      | -4.759 | -4.000 | 3.289  | 1.000  | 57      | 0.516 | 0.500  | 0.250 | 0.171 |
| M18  | S    | 82      | -0.915 | -0.500 | 1.874  | 1.750  | 82      | 0.916 | 0.971  | 0.147 | 0.147 |
| M18  | F    | 21      | -3.333 | -5.000 | 6.938  | 3.000  | 19      | 0.511 | 0.375  | 0.532 | 0.375 |

<a id="section-20"></a>

### タスク名の依存を考慮した成功率

マクロSRはタスク名ごとのSRを等重み平均する．95%区間はタスク名をクラスターとして復元抽出し，選んだ名前の全インスタンスを保持した4000回の再標本化の2.5・97.5百分位点である（seed 20260906）．区間内のSRはインスタンス重みであり，マクロSRの区間ではない．検証有無の差では同じIDの成功差を保持して再標本化する．家屋の共有による名前間の依存は除去できず，状態変化の6名では区間推定自体が不安定になり得る．

<a id="tab-macro-intervals"></a>

**表A20：マクロ成功率とタスク名クラスター区間（%）**

| 条件 | 名前数 | SR     | マクロSR | SR下限 | SR上限 |
|:-----|:-------|:-------|:---------|:-------|:-------|
| M1   | 6      | 3.205  | 5.078    | 0.000  | 8.333  |
| M2   | 6      | 62.500 | 57.448   | 47.727 | 76.872 |
| M3   | 6      | 78.846 | 84.523   | 60.981 | 97.340 |
| M4   | 6      | 75.000 | 70.929   | 61.275 | 89.474 |
| M5   | 6      | 89.423 | 84.193   | 68.182 | 99.013 |
| M6   | 6      | 61.538 | 57.613   | 43.750 | 79.276 |
| M7   | 6      | 75.962 | 79.983   | 57.243 | 95.714 |
| M8   | 6      | 69.551 | 68.568   | 47.436 | 92.763 |
| M9   | 6      | 87.179 | 79.505   | 64.773 | 96.711 |
| M10  | 38     | 0.000  | 0.000    | 0.000  | 0.000  |
| M11  | 38     | 46.602 | 38.377   | 34.065 | 58.333 |
| M12  | 38     | 73.786 | 63.377   | 64.102 | 82.302 |
| M13  | 38     | 40.777 | 42.281   | 30.000 | 52.223 |
| M14  | 38     | 81.553 | 63.487   | 71.111 | 89.051 |
| M15  | 38     | 47.573 | 41.996   | 35.632 | 58.825 |
| M16  | 38     | 67.961 | 54.232   | 55.262 | 78.626 |
| M17  | 38     | 43.689 | 39.978   | 32.999 | 54.623 |
| M18  | 38     | 79.612 | 64.803   | 69.663 | 87.736 |

<a id="tab-paired-intervals"></a>

**表A21：検証なしからありへの対応変化とSR差（percentage points）**

| あり条件 | $`n`$ | 改善数 | 悪化数 | 両成功 | 両失敗 | SR差   | 下限   | 上限   |
|:---------|:------|:-------|:-------|:-------|:-------|:-------|:-------|:-------|
| M2       | 312   | 34     | 31     | 161    | 86     | 0.962  | -4.545 | 5.593  |
| M3       | 312   | 26     | 17     | 220    | 49     | 2.885  | 0.658  | 10.000 |
| M4       | 312   | 48     | 31     | 186    | 47     | 5.449  | -5.000 | 14.706 |
| M5       | 312   | 12     | 5      | 267    | 28     | 2.244  | 0.938  | 6.944  |
| M11      | 103   | 6      | 7      | 42     | 48     | -0.971 | -8.547 | 7.059  |
| M12      | 103   | 12     | 6      | 64     | 21     | 5.825  | -2.858 | 13.979 |
| M13      | 103   | 6      | 9      | 36     | 52     | -2.913 | -9.303 | 4.651  |
| M14      | 103   | 6      | 4      | 78     | 15     | 1.942  | -4.168 | 7.619  |

<a id="section-21"></a>

### 検索類似度と成績の関係

検索の構成と候補名順序は[検索条件と選択事例](#app-retrieval-conditions)に従う．表[A22](#tab-retrieval-distribution)では名前等重みとインスタンス等重みを区別する．表[A23](#tab-retrieval-strata)のO/A/Dは対象クラス／操作／配置先の一致，1/0は一致／不一致を表す．同じ試行を複数軸で分けた記述的集計であり，各行を合算しない．列長差はその行の成功IDのみを分母とする．状態変化には配置先がないためDは解釈対象から外す．空の層は成績表に行を設けていない．

<a id="tab-retrieval-distribution"></a>

**表A22：検索類似度の分布**

| タスク | 重み | $`n`$ | 平均  | 中央値 | Q1    | Q3    | 最小  | 最大  |
|:-------|:-----|:------|:------|:-------|:------|:------|:------|:------|
| 状態   | 名前 | 6     | 0.678 | 0.606  | 0.589 | 0.797 | 0.499 | 0.910 |
| 状態   | 事例 | 312   | 0.624 | 0.611  | 0.585 | 0.611 | 0.499 | 0.910 |
| 配置   | 名前 | 38    | 0.782 | 0.781  | 0.736 | 0.829 | 0.640 | 0.901 |
| 配置   | 事例 | 103   | 0.781 | 0.792  | 0.761 | 0.809 | 0.640 | 0.901 |

<a id="tab-retrieval-strata"></a>

**表A23：検索類似度・共有構造別の成功率と成功時列長差**

| 条件 | 層      | $`n`$ | 成功数 | SR (%)  | 成功時D平均 |
|:-----|:--------|:------|:-------|:--------|:------------|
| M8   | \<0.8   | 280   | 201    | 71.786  | 0.577       |
| M8   | O0      | 280   | 201    | 71.786  | 0.577       |
| M8   | A1      | 280   | 201    | 71.786  | 0.577       |
| M8   | \>=0.9  | 20    | 9      | 45.000  | 0.000       |
| M8   | O1      | 32    | 16     | 50.000  | -0.062      |
| M8   | A0      | 32    | 16     | 50.000  | -0.062      |
| M8   | 0.8–0.9 | 12    | 7      | 58.333  | -0.143      |
| M4   | \<0.8   | 280   | 214    | 76.429  | 0.481       |
| M4   | O0      | 280   | 214    | 76.429  | 0.481       |
| M4   | A1      | 280   | 214    | 76.429  | 0.481       |
| M4   | \>=0.9  | 20    | 11     | 55.000  | 0.182       |
| M4   | O1      | 32    | 20     | 62.500  | 0.050       |
| M4   | A0      | 32    | 20     | 62.500  | 0.050       |
| M4   | 0.8–0.9 | 12    | 9      | 75.000  | -0.111      |
| M9   | \<0.8   | 280   | 253    | 90.357  | -0.209      |
| M9   | O0      | 280   | 253    | 90.357  | -0.209      |
| M9   | A1      | 280   | 253    | 90.357  | -0.209      |
| M9   | \>=0.9  | 20    | 9      | 45.000  | -0.222      |
| M9   | O1      | 32    | 19     | 59.375  | -0.211      |
| M9   | A0      | 32    | 19     | 59.375  | -0.211      |
| M9   | 0.8–0.9 | 12    | 10     | 83.333  | -0.200      |
| M5   | \<0.8   | 280   | 258    | 92.143  | -0.314      |
| M5   | O0      | 280   | 258    | 92.143  | -0.314      |
| M5   | A1      | 280   | 258    | 92.143  | -0.314      |
| M5   | \>=0.9  | 20    | 9      | 45.000  | -0.111      |
| M5   | O1      | 32    | 21     | 65.625  | -0.048      |
| M5   | A0      | 32    | 21     | 65.625  | -0.048      |
| M5   | 0.8–0.9 | 12    | 12     | 100.000 | 0.000       |
| M6   | \<0.8   | 280   | 180    | 64.286  | 0.444       |
| M6   | O0      | 280   | 180    | 64.286  | 0.444       |
| M6   | A1      | 280   | 180    | 64.286  | 0.444       |
| M6   | \>=0.9  | 20    | 7      | 35.000  | -0.143      |
| M6   | O1      | 32    | 12     | 37.500  | -0.083      |
| M6   | A0      | 32    | 12     | 37.500  | -0.083      |
| M6   | 0.8–0.9 | 12    | 5      | 41.667  | 0.000       |
| M2   | \<0.8   | 280   | 180    | 64.286  | 0.328       |
| M2   | O0      | 280   | 180    | 64.286  | 0.328       |
| M2   | A1      | 280   | 180    | 64.286  | 0.328       |
| M2   | \>=0.9  | 20    | 8      | 40.000  | 0.125       |
| M2   | O1      | 32    | 15     | 46.875  | 0.067       |
| M2   | A0      | 32    | 15     | 46.875  | 0.067       |
| M2   | 0.8–0.9 | 12    | 7      | 58.333  | 0.000       |
| M7   | \<0.8   | 280   | 218    | 77.857  | 0.041       |
| M7   | O0      | 280   | 218    | 77.857  | 0.041       |
| M7   | A1      | 280   | 218    | 77.857  | 0.041       |
| M7   | \>=0.9  | 20    | 9      | 45.000  | 0.111       |
| M7   | O1      | 32    | 19     | 59.375  | 0.105       |
| M7   | A0      | 32    | 19     | 59.375  | 0.105       |
| M7   | 0.8–0.9 | 12    | 10     | 83.333  | 0.100       |
| M3   | \<0.8   | 280   | 222    | 79.286  | -0.014      |
| M3   | O0      | 280   | 222    | 79.286  | -0.014      |
| M3   | A1      | 280   | 222    | 79.286  | -0.014      |
| M3   | \>=0.9  | 20    | 12     | 60.000  | 0.333       |
| M3   | O1      | 32    | 24     | 75.000  | 0.083       |
| M3   | A0      | 32    | 24     | 75.000  | 0.083       |
| M3   | 0.8–0.9 | 12    | 12     | 100.000 | -0.167      |
| M17  | 0.8–0.9 | 44    | 19     | 43.182  | -0.684      |
| M17  | O1      | 92    | 43     | 46.739  | -0.860      |
| M17  | A1      | 56    | 25     | 44.643  | -0.480      |
| M17  | D0      | 92    | 43     | 46.739  | -0.860      |
| M17  | \<0.8   | 57    | 25     | 43.860  | -0.920      |
| M17  | A0      | 47    | 20     | 42.553  | -1.250      |
| M17  | O0      | 11    | 2      | 18.182  | 0.000       |
| M17  | D1      | 11    | 2      | 18.182  | 0.000       |
| M17  | \>=0.9  | 2     | 1      | 50.000  | -1.000      |
| M13  | 0.8–0.9 | 44    | 15     | 34.091  | -0.667      |
| M13  | O1      | 92    | 38     | 41.304  | -0.605      |
| M13  | A1      | 56    | 27     | 48.214  | -1.037      |
| M13  | D0      | 92    | 38     | 41.304  | -0.605      |
| M13  | \<0.8   | 57    | 26     | 45.614  | -0.577      |
| M13  | A0      | 47    | 15     | 31.915  | 0.133       |
| M13  | O0      | 11    | 4      | 36.364  | -0.750      |
| M13  | D1      | 11    | 4      | 36.364  | -0.750      |
| M13  | \>=0.9  | 2     | 1      | 50.000  | -1.000      |
| M18  | 0.8–0.9 | 44    | 36     | 81.818  | -0.528      |
| M18  | O1      | 92    | 72     | 78.261  | -0.986      |
| M18  | A1      | 56    | 44     | 78.571  | -1.159      |
| M18  | D0      | 92    | 72     | 78.261  | -0.986      |
| M18  | \<0.8   | 57    | 45     | 78.947  | -1.244      |
| M18  | A0      | 47    | 38     | 80.851  | -0.632      |
| M18  | O0      | 11    | 10     | 90.909  | -0.400      |
| M18  | D1      | 11    | 10     | 90.909  | -0.400      |
| M18  | \>=0.9  | 2     | 1      | 50.000  | 0.000       |
| M14  | 0.8–0.9 | 44    | 35     | 79.545  | 0.229       |
| M14  | O1      | 92    | 74     | 80.435  | -0.392      |
| M14  | A1      | 56    | 43     | 76.786  | -0.465      |
| M14  | D0      | 92    | 74     | 80.435  | -0.392      |
| M14  | \<0.8   | 57    | 48     | 84.211  | -0.771      |
| M14  | A0      | 47    | 41     | 87.234  | -0.244      |
| M14  | O0      | 11    | 10     | 90.909  | -0.100      |
| M14  | D1      | 11    | 10     | 90.909  | -0.100      |
| M14  | \>=0.9  | 2     | 1      | 50.000  | -1.000      |
| M15  | 0.8–0.9 | 44    | 20     | 45.455  | -0.550      |
| M15  | O1      | 92    | 47     | 51.087  | -0.809      |
| M15  | A1      | 56    | 26     | 46.429  | -0.423      |
| M15  | D0      | 92    | 47     | 51.087  | -0.809      |
| M15  | \<0.8   | 57    | 28     | 49.123  | -0.964      |
| M15  | A0      | 47    | 23     | 48.936  | -1.217      |
| M15  | O0      | 11    | 2      | 18.182  | -0.500      |
| M15  | D1      | 11    | 2      | 18.182  | -0.500      |
| M15  | \>=0.9  | 2     | 1      | 50.000  | -1.000      |
| M11  | 0.8–0.9 | 44    | 16     | 36.364  | -0.250      |
| M11  | O1      | 92    | 46     | 50.000  | -0.152      |
| M11  | A1      | 56    | 26     | 46.429  | -0.115      |
| M11  | D0      | 92    | 46     | 50.000  | -0.152      |
| M11  | \<0.8   | 57    | 31     | 54.386  | -0.194      |
| M11  | A0      | 47    | 22     | 46.809  | -0.182      |
| M11  | O0      | 11    | 2      | 18.182  | 0.000       |
| M11  | D1      | 11    | 2      | 18.182  | 0.000       |
| M11  | \>=0.9  | 2     | 1      | 50.000  | 3.000       |
| M16  | 0.8–0.9 | 44    | 30     | 68.182  | 0.133       |
| M16  | O1      | 92    | 63     | 68.478  | -0.349      |
| M16  | A1      | 56    | 39     | 69.643  | -0.641      |
| M16  | D0      | 92    | 63     | 68.478  | -0.349      |
| M16  | \<0.8   | 57    | 39     | 68.421  | -0.718      |
| M16  | A0      | 47    | 31     | 65.957  | 0.000       |
| M16  | O0      | 11    | 7      | 63.636  | -0.429      |
| M16  | D1      | 11    | 7      | 63.636  | -0.429      |
| M16  | \>=0.9  | 2     | 1      | 50.000  | -1.000      |
| M12  | 0.8–0.9 | 44    | 31     | 70.455  | -0.032      |
| M12  | O1      | 92    | 67     | 72.826  | -0.537      |
| M12  | A1      | 56    | 43     | 76.786  | -0.558      |
| M12  | D0      | 92    | 67     | 72.826  | -0.537      |
| M12  | \<0.8   | 57    | 44     | 77.193  | -0.750      |
| M12  | A0      | 47    | 33     | 70.213  | -0.333      |
| M12  | O0      | 11    | 9      | 81.818  | 0.111       |
| M12  | D1      | 11    | 9      | 81.818  | 0.111       |
| M12  | \>=0.9  | 2     | 1      | 50.000  | -1.000      |

<a id="app-coverage-joint"></a>

### 全インスタンスの組合せ網羅表

指示Nと初期状態Iは後続の辞書に完全に展開する．状態変化の指示はTurn on/off all，配置の指示はPut all ... in/on the ...で，対象・目標状態／配置先を指示辞書から一意に読める．S/Pは状態変化／配置，T/Eはテスト／事例用，部屋B/D/K/Lはbathroom／bedroom／kitchen／livingroomである．ID欄の整数はtest_taskまたはexample_taskに続く番号で，各IDの後の文字がinitial_roomとなる．同一指示・シーン・初期状態の行をまとめただけであり，全618件を重複なく列挙する．物体位置はシーンに依存し，Iはノード状態配列の上書きである．観測した組合せを列挙する．

<a id="tab-instruction-dictionary"></a>

**表A24：タスク指示の辞書**

| 番号 | 指示全文                                  |
|:-----|:------------------------------------------|
| N1   | Put all alcohols in the microwave         |
| N2   | Put all alcohols on the kitchentable      |
| N3   | Put all apples in the fridge              |
| N4   | Put all apples in the microwave           |
| N5   | Put all apples on the kitchencounter      |
| N6   | Put all apples on the kitchentable        |
| N7   | Put all bananas in the fridge             |
| N8   | Put all bananas in the microwave          |
| N9   | Put all bananas on the coffeetable        |
| N10  | Put all bananas on the desk               |
| N11  | Put all bananas on the kitchencounter     |
| N12  | Put all bananas on the kitchentable       |
| N13  | Put all bananas on the oventray           |
| N14  | Put all bellpeppers in the fridge         |
| N15  | Put all bellpeppers in the microwave      |
| N16  | Put all bellpeppers on the kitchencounter |
| N17  | Put all bellpeppers on the kitchentable   |
| N18  | Put all chips in the fridge               |
| N19  | Put all chips in the microwave            |
| N20  | Put all chips on the coffeetable          |
| N21  | Put all chips on the kitchentable         |
| N22  | Put all crackers in the fridge            |
| N23  | Put all crackers in the microwave         |
| N24  | Put all crackers on the coffeetable       |
| N25  | Put all crackers on the kitchentable      |
| N26  | Put all creamybuns in the fridge          |
| N27  | Put all creamybuns in the microwave       |
| N28  | Put all creamybuns on the kitchentable    |
| N29  | Put all cupcakes in the fridge            |
| N30  | Put all cupcakes in the microwave         |
| N31  | Put all cupcakes on the coffeetable       |
| N32  | Put all cupcakes on the desk              |
| N33  | Put all cupcakes on the kitchencounter    |
| N34  | Put all cupcakes on the kitchentable      |
| N35  | Put all juices in the fridge              |
| N36  | Put all juices in the microwave           |
| N37  | Put all juices on the coffeetable         |
| N38  | Put all milks in the fridge               |
| N39  | Put all milks in the microwave            |
| N40  | Put all milks on the coffeetable          |
| N41  | Put all milks on the cuttingboard         |
| N42  | Put all milks on the desk                 |
| N43  | Put all milks on the kitchencounter       |
| N44  | Put all milks on the kitchentable         |
| N45  | Put all peaches in the fridge             |
| N46  | Put all peaches in the microwave          |
| N47  | Put all peaches on the coffeetable        |
| N48  | Put all peaches on the kitchencounter     |
| N49  | Put all peaches on the kitchentable       |
| N50  | Put all peaches on the oventray           |
| N51  | Put all plums in the fridge               |
| N52  | Put all plums in the fryingpan            |
| N53  | Put all plums in the microwave            |
| N54  | Put all plums on the coffeetable          |
| N55  | Put all plums on the kitchencounter       |
| N56  | Put all plums on the kitchentable         |
| N57  | Put all plums on the oventray             |
| N58  | Turn off all candles                      |
| N59  | Turn off all cellphones                   |
| N60  | Turn off all computers                    |
| N61  | Turn off all faucets                      |
| N62  | Turn off all lightswitches                |
| N63  | Turn off all tablelamps                   |
| N64  | Turn off all tvs                          |
| N65  | Turn on all computers                     |
| N66  | Turn on all faucets                       |
| N67  | Turn on all lightswitches                 |
| N68  | Turn on all tablelamps                    |
| N69  | Turn on all tvs                           |

<a id="tab-initial-state-dictionary"></a>

**表A25：初期状態の辞書（ID:状態配列）**

| 番号 | 状態上書き                                 |
|:-----|:-------------------------------------------|
| I1   | (empty)                                    |
| I2   | 101:OFF; 187:OFF                           |
| I3   | 101:OFF; 187:ON                            |
| I4   | 101:ON; 187:OFF                            |
| I5   | 101:ON; 187:ON                             |
| I6   | 102:OFF; 103:OFF                           |
| I7   | 102:OFF; 103:ON                            |
| I8   | 102:ON; 103:OFF                            |
| I9   | 102:ON; 103:ON                             |
| I10  | 103:CLOSED                                 |
| I11  | 103:OFF; 201:OFF; 249:OFF; 366:OFF         |
| I12  | 103:OFF; 201:OFF; 249:OFF; 366:ON          |
| I13  | 103:OFF; 201:OFF; 249:ON; 366:OFF          |
| I14  | 103:OFF; 201:OFF; 249:ON; 366:ON           |
| I15  | 103:OFF; 201:ON; 249:OFF; 366:OFF          |
| I16  | 103:OFF; 201:ON; 249:OFF; 366:ON           |
| I17  | 103:OFF; 201:ON; 249:ON; 366:OFF           |
| I18  | 103:OFF; 201:ON; 249:ON; 366:ON            |
| I19  | 103:ON; 201:OFF; 249:OFF; 366:OFF          |
| I20  | 103:ON; 201:OFF; 249:OFF; 366:ON           |
| I21  | 103:ON; 201:OFF; 249:ON; 366:OFF           |
| I22  | 103:ON; 201:OFF; 249:ON; 366:ON            |
| I23  | 103:ON; 201:ON; 249:OFF; 366:OFF           |
| I24  | 103:ON; 201:ON; 249:OFF; 366:ON            |
| I25  | 103:ON; 201:ON; 249:ON; 366:OFF            |
| I26  | 103:ON; 201:ON; 249:ON; 366:ON             |
| I27  | 103:OPEN                                   |
| I28  | 108:OFF; 200:OFF                           |
| I29  | 108:OFF; 200:ON                            |
| I30  | 108:ON; 200:OFF                            |
| I31  | 108:ON; 200:ON                             |
| I32  | 109:CLOSED,OFF                             |
| I33  | 109:OPEN,OFF                               |
| I34  | 111:OFF; 185:OFF; 318:OFF                  |
| I35  | 111:OFF; 185:OFF; 318:ON                   |
| I36  | 111:OFF; 185:ON; 318:OFF                   |
| I37  | 111:OFF; 185:ON; 318:ON                    |
| I38  | 111:ON; 185:OFF; 318:OFF                   |
| I39  | 111:ON; 185:OFF; 318:ON                    |
| I40  | 111:ON; 185:ON; 318:OFF                    |
| I41  | 111:ON; 185:ON; 318:ON                     |
| I42  | 120:OFF; 274:OFF                           |
| I43  | 120:OFF; 274:ON                            |
| I44  | 120:ON; 274:OFF                            |
| I45  | 120:ON; 274:ON                             |
| I46  | 124:OFF; 125:OFF                           |
| I47  | 124:OFF; 125:ON                            |
| I48  | 124:OFF; 127:OFF                           |
| I49  | 124:OFF; 127:ON                            |
| I50  | 124:OFF; 216:OFF; 314:OFF                  |
| I51  | 124:OFF; 216:OFF; 314:ON                   |
| I52  | 124:OFF; 216:ON; 314:OFF                   |
| I53  | 124:OFF; 216:ON; 314:ON                    |
| I54  | 124:ON; 125:OFF                            |
| I55  | 124:ON; 125:ON                             |
| I56  | 124:ON; 127:OFF                            |
| I57  | 124:ON; 127:ON                             |
| I58  | 124:ON; 216:OFF; 314:OFF                   |
| I59  | 124:ON; 216:OFF; 314:ON                    |
| I60  | 124:ON; 216:ON; 314:OFF                    |
| I61  | 124:ON; 216:ON; 314:ON                     |
| I62  | 152:OFF; 300:OFF                           |
| I63  | 152:OFF; 300:ON                            |
| I64  | 152:ON; 300:OFF                            |
| I65  | 152:ON; 300:ON                             |
| I66  | 156:OFF; 327:OFF                           |
| I67  | 156:OFF; 327:ON                            |
| I68  | 156:ON; 327:OFF                            |
| I69  | 156:ON; 327:ON                             |
| I70  | 157:CLOSED                                 |
| I71  | 157:OFF; 249:OFF                           |
| I72  | 157:OFF; 249:ON                            |
| I73  | 157:ON; 249:OFF                            |
| I74  | 157:ON; 249:ON                             |
| I75  | 157:OPEN                                   |
| I76  | 162:CLOSED,OFF                             |
| I77  | 162:CLOSED                                 |
| I78  | 162:OPEN,OFF                               |
| I79  | 162:OPEN                                   |
| I80  | 166:CLOSED,OFF                             |
| I81  | 166:OPEN,OFF                               |
| I82  | 169:OFF; 209:OFF; 218:OFF; 300:OFF         |
| I83  | 169:OFF; 209:OFF; 218:OFF; 300:ON          |
| I84  | 169:OFF; 209:OFF; 218:ON; 300:OFF          |
| I85  | 169:OFF; 209:OFF; 218:ON; 300:ON           |
| I86  | 169:OFF; 209:ON; 218:OFF; 300:OFF          |
| I87  | 169:OFF; 209:ON; 218:OFF; 300:ON           |
| I88  | 169:OFF; 209:ON; 218:ON; 300:OFF           |
| I89  | 169:OFF; 209:ON; 218:ON; 300:ON            |
| I90  | 169:ON; 209:OFF; 218:OFF; 300:OFF          |
| I91  | 169:ON; 209:OFF; 218:OFF; 300:ON           |
| I92  | 169:ON; 209:OFF; 218:ON; 300:OFF           |
| I93  | 169:ON; 209:OFF; 218:ON; 300:ON            |
| I94  | 169:ON; 209:ON; 218:OFF; 300:OFF           |
| I95  | 169:ON; 209:ON; 218:OFF; 300:ON            |
| I96  | 169:ON; 209:ON; 218:ON; 300:OFF            |
| I97  | 169:ON; 209:ON; 218:ON; 300:ON             |
| I98  | 171:CLOSED,OFF                             |
| I99  | 171:OPEN,OFF                               |
| I100 | 174:OFF; 433:OFF                           |
| I101 | 174:OFF; 433:ON                            |
| I102 | 174:ON; 433:OFF                            |
| I103 | 174:ON; 433:ON                             |
| I104 | 188:OFF; 202:OFF; 448:OFF; 449:OFF         |
| I105 | 188:OFF; 202:OFF; 448:OFF; 449:ON          |
| I106 | 188:OFF; 202:OFF; 448:ON; 449:OFF          |
| I107 | 188:OFF; 202:OFF; 448:ON; 449:ON           |
| I108 | 188:OFF; 202:ON; 448:OFF; 449:OFF          |
| I109 | 188:OFF; 202:ON; 448:OFF; 449:ON           |
| I110 | 188:OFF; 202:ON; 448:ON; 449:OFF           |
| I111 | 188:OFF; 202:ON; 448:ON; 449:ON            |
| I112 | 188:ON; 202:OFF; 448:OFF; 449:OFF          |
| I113 | 188:ON; 202:OFF; 448:OFF; 449:ON           |
| I114 | 188:ON; 202:OFF; 448:ON; 449:OFF           |
| I115 | 188:ON; 202:OFF; 448:ON; 449:ON            |
| I116 | 188:ON; 202:ON; 448:OFF; 449:OFF           |
| I117 | 188:ON; 202:ON; 448:OFF; 449:ON            |
| I118 | 188:ON; 202:ON; 448:ON; 449:OFF            |
| I119 | 188:ON; 202:ON; 448:ON; 449:ON             |
| I120 | 194:OFF; 197:OFF                           |
| I121 | 194:OFF; 197:ON                            |
| I122 | 194:ON; 197:OFF                            |
| I123 | 194:ON; 197:ON                             |
| I124 | 207:OFF; 314:OFF                           |
| I125 | 207:OFF; 314:ON                            |
| I126 | 207:ON; 314:OFF                            |
| I127 | 207:ON; 314:ON                             |
| I128 | 223:OFF; 323:OFF                           |
| I129 | 223:OFF; 323:ON                            |
| I130 | 223:ON; 323:OFF                            |
| I131 | 223:ON; 323:ON                             |
| I132 | 225:CLOSED                                 |
| I133 | 225:OPEN                                   |
| I134 | 234:CLOSED,OFF                             |
| I135 | 234:OPEN,OFF                               |
| I136 | 235:CLOSED                                 |
| I137 | 235:OPEN                                   |
| I138 | 239:CLOSED,OFF                             |
| I139 | 239:OPEN,OFF                               |
| I140 | 256:OFF; 376:OFF; 377:OFF                  |
| I141 | 256:OFF; 376:OFF; 377:ON                   |
| I142 | 256:OFF; 376:ON; 377:OFF                   |
| I143 | 256:OFF; 376:ON; 377:ON                    |
| I144 | 256:ON; 376:OFF; 377:OFF                   |
| I145 | 256:ON; 376:OFF; 377:ON                    |
| I146 | 256:ON; 376:ON; 377:OFF                    |
| I147 | 256:ON; 376:ON; 377:ON                     |
| I148 | 264:OFF; 426:OFF                           |
| I149 | 264:OFF; 426:ON                            |
| I150 | 264:ON; 426:OFF                            |
| I151 | 264:ON; 426:ON                             |
| I152 | 268:OFF; 271:OFF                           |
| I153 | 268:OFF; 271:ON                            |
| I154 | 268:ON; 271:OFF                            |
| I155 | 268:ON; 271:ON                             |
| I156 | 274:OFF; 324:OFF                           |
| I157 | 274:OFF; 324:ON                            |
| I158 | 274:ON; 324:OFF                            |
| I159 | 274:ON; 324:ON                             |
| I160 | 29:OFF; 220:OFF                            |
| I161 | 29:OFF; 220:ON                             |
| I162 | 29:ON; 220:OFF                             |
| I163 | 29:ON; 220:ON                              |
| I164 | 30:OFF; 149:OFF                            |
| I165 | 30:OFF; 149:ON                             |
| I166 | 30:ON; 149:OFF                             |
| I167 | 30:ON; 149:ON                              |
| I168 | 305:CLOSED                                 |
| I169 | 305:OPEN                                   |
| I170 | 313:CLOSED,OFF                             |
| I171 | 313:OPEN,OFF                               |
| I172 | 38:OFF; 199:OFF                            |
| I173 | 38:OFF; 199:ON                             |
| I174 | 38:ON; 199:OFF                             |
| I175 | 38:ON; 199:ON                              |
| I176 | 48:OFF; 97:OFF; 157:OFF; 302:OFF           |
| I177 | 48:OFF; 97:OFF; 157:OFF; 302:ON            |
| I178 | 48:OFF; 97:OFF; 157:ON; 302:OFF            |
| I179 | 48:OFF; 97:OFF; 157:ON; 302:ON             |
| I180 | 48:OFF; 97:ON; 157:OFF; 302:OFF            |
| I181 | 48:OFF; 97:ON; 157:OFF; 302:ON             |
| I182 | 48:OFF; 97:ON; 157:ON; 302:OFF             |
| I183 | 48:OFF; 97:ON; 157:ON; 302:ON              |
| I184 | 48:ON; 97:OFF; 157:OFF; 302:OFF            |
| I185 | 48:ON; 97:OFF; 157:OFF; 302:ON             |
| I186 | 48:ON; 97:OFF; 157:ON; 302:OFF             |
| I187 | 48:ON; 97:OFF; 157:ON; 302:ON              |
| I188 | 48:ON; 97:ON; 157:OFF; 302:OFF             |
| I189 | 48:ON; 97:ON; 157:OFF; 302:ON              |
| I190 | 48:ON; 97:ON; 157:ON; 302:OFF              |
| I191 | 48:ON; 97:ON; 157:ON; 302:ON               |
| I192 | 50:OFF; 248:OFF                            |
| I193 | 50:OFF; 248:ON                             |
| I194 | 50:ON; 248:OFF                             |
| I195 | 50:ON; 248:ON                              |
| I196 | 54:OFF; 85:OFF; 277:OFF; 332:OFF           |
| I197 | 54:OFF; 85:OFF; 277:OFF; 332:ON            |
| I198 | 54:OFF; 85:OFF; 277:ON; 332:OFF            |
| I199 | 54:OFF; 85:OFF; 277:ON; 332:ON             |
| I200 | 54:OFF; 85:ON; 277:OFF; 332:OFF            |
| I201 | 54:OFF; 85:ON; 277:OFF; 332:ON             |
| I202 | 54:OFF; 85:ON; 277:ON; 332:OFF             |
| I203 | 54:OFF; 85:ON; 277:ON; 332:ON              |
| I204 | 54:ON; 85:OFF; 277:OFF; 332:OFF            |
| I205 | 54:ON; 85:OFF; 277:OFF; 332:ON             |
| I206 | 54:ON; 85:OFF; 277:ON; 332:OFF             |
| I207 | 54:ON; 85:OFF; 277:ON; 332:ON              |
| I208 | 54:ON; 85:ON; 277:OFF; 332:OFF             |
| I209 | 54:ON; 85:ON; 277:OFF; 332:ON              |
| I210 | 54:ON; 85:ON; 277:ON; 332:OFF              |
| I211 | 54:ON; 85:ON; 277:ON; 332:ON               |
| I212 | 58:OFF; 239:OFF; 278:OFF; 344:OFF; 402:OFF |
| I213 | 58:OFF; 239:OFF; 278:OFF; 344:OFF; 402:ON  |
| I214 | 58:OFF; 239:OFF; 278:OFF; 344:ON; 402:OFF  |
| I215 | 58:OFF; 239:OFF; 278:OFF; 344:ON; 402:ON   |
| I216 | 58:OFF; 239:OFF; 278:ON; 344:OFF; 402:OFF  |
| I217 | 58:OFF; 239:OFF; 278:ON; 344:OFF; 402:ON   |
| I218 | 58:OFF; 239:OFF; 278:ON; 344:ON; 402:OFF   |
| I219 | 58:OFF; 239:OFF; 278:ON; 344:ON; 402:ON    |
| I220 | 58:OFF; 239:ON; 278:OFF; 344:OFF; 402:OFF  |
| I221 | 58:OFF; 239:ON; 278:OFF; 344:OFF; 402:ON   |
| I222 | 58:OFF; 239:ON; 278:OFF; 344:ON; 402:OFF   |
| I223 | 58:OFF; 239:ON; 278:OFF; 344:ON; 402:ON    |
| I224 | 58:OFF; 239:ON; 278:ON; 344:OFF; 402:OFF   |
| I225 | 58:OFF; 239:ON; 278:ON; 344:OFF; 402:ON    |
| I226 | 58:OFF; 239:ON; 278:ON; 344:ON; 402:OFF    |
| I227 | 58:OFF; 239:ON; 278:ON; 344:ON; 402:ON     |
| I228 | 58:ON; 239:OFF; 278:OFF; 344:OFF; 402:OFF  |
| I229 | 58:ON; 239:OFF; 278:OFF; 344:OFF; 402:ON   |
| I230 | 58:ON; 239:OFF; 278:OFF; 344:ON; 402:OFF   |
| I231 | 58:ON; 239:OFF; 278:OFF; 344:ON; 402:ON    |
| I232 | 58:ON; 239:OFF; 278:ON; 344:OFF; 402:OFF   |
| I233 | 58:ON; 239:OFF; 278:ON; 344:OFF; 402:ON    |
| I234 | 58:ON; 239:OFF; 278:ON; 344:ON; 402:OFF    |
| I235 | 58:ON; 239:OFF; 278:ON; 344:ON; 402:ON     |
| I236 | 58:ON; 239:ON; 278:OFF; 344:OFF; 402:OFF   |
| I237 | 58:ON; 239:ON; 278:OFF; 344:OFF; 402:ON    |
| I238 | 58:ON; 239:ON; 278:OFF; 344:ON; 402:OFF    |
| I239 | 58:ON; 239:ON; 278:OFF; 344:ON; 402:ON     |
| I240 | 58:ON; 239:ON; 278:ON; 344:OFF; 402:OFF    |
| I241 | 58:ON; 239:ON; 278:ON; 344:OFF; 402:ON     |
| I242 | 58:ON; 239:ON; 278:ON; 344:ON; 402:OFF     |
| I243 | 58:ON; 239:ON; 278:ON; 344:ON; 402:ON      |
| I244 | 67:OFF; 110:OFF; 205:OFF; 315:OFF          |
| I245 | 67:OFF; 110:OFF; 205:OFF; 315:ON           |
| I246 | 67:OFF; 110:OFF; 205:ON; 315:OFF           |
| I247 | 67:OFF; 110:OFF; 205:ON; 315:ON            |
| I248 | 67:OFF; 110:ON; 205:OFF; 315:OFF           |
| I249 | 67:OFF; 110:ON; 205:OFF; 315:ON            |
| I250 | 67:OFF; 110:ON; 205:ON; 315:OFF            |
| I251 | 67:OFF; 110:ON; 205:ON; 315:ON             |
| I252 | 67:ON; 110:OFF; 205:OFF; 315:OFF           |
| I253 | 67:ON; 110:OFF; 205:OFF; 315:ON            |
| I254 | 67:ON; 110:OFF; 205:ON; 315:OFF            |
| I255 | 67:ON; 110:OFF; 205:ON; 315:ON             |
| I256 | 67:ON; 110:ON; 205:OFF; 315:OFF            |
| I257 | 67:ON; 110:ON; 205:OFF; 315:ON             |
| I258 | 67:ON; 110:ON; 205:ON; 315:OFF             |
| I259 | 67:ON; 110:ON; 205:ON; 315:ON              |
| I260 | 69:OFF; 181:OFF                            |
| I261 | 69:OFF; 181:ON                             |
| I262 | 69:ON; 181:OFF                             |
| I263 | 69:ON; 181:ON                              |
| I264 | 71:OFF; 173:OFF; 261:OFF; 427:OFF          |
| I265 | 71:OFF; 173:OFF; 261:OFF; 427:ON           |
| I266 | 71:OFF; 173:OFF; 261:ON; 427:OFF           |
| I267 | 71:OFF; 173:OFF; 261:ON; 427:ON            |
| I268 | 71:OFF; 173:ON; 261:OFF; 427:OFF           |
| I269 | 71:OFF; 173:ON; 261:OFF; 427:ON            |
| I270 | 71:OFF; 173:ON; 261:ON; 427:OFF            |
| I271 | 71:OFF; 173:ON; 261:ON; 427:ON             |
| I272 | 71:ON; 173:OFF; 261:OFF; 427:OFF           |
| I273 | 71:ON; 173:OFF; 261:OFF; 427:ON            |
| I274 | 71:ON; 173:OFF; 261:ON; 427:OFF            |
| I275 | 71:ON; 173:OFF; 261:ON; 427:ON             |
| I276 | 71:ON; 173:ON; 261:OFF; 427:OFF            |
| I277 | 71:ON; 173:ON; 261:OFF; 427:ON             |
| I278 | 71:ON; 173:ON; 261:ON; 427:OFF             |
| I279 | 71:ON; 173:ON; 261:ON; 427:ON              |
| I280 | 78:OFF; 229:OFF                            |
| I281 | 78:OFF; 229:ON                             |
| I282 | 78:ON; 229:OFF                             |
| I283 | 78:ON; 229:ON                              |
| I284 | 91:OFF; 195:OFF                            |
| I285 | 91:OFF; 195:ON                             |
| I286 | 91:ON; 195:OFF                             |
| I287 | 91:ON; 195:ON                              |
| I288 | 94:OFF; 295:OFF                            |
| I289 | 94:OFF; 295:ON                             |
| I290 | 94:ON; 295:OFF                             |
| I291 | 94:ON; 295:ON                              |

<a id="tab-joint-coverage"></a>

**表A26：全インスタンスの組合せ（ID:初期部屋）**

| 種別 | 分割 | 指示 | シーン | 初期状態 | 件数 | ID:部屋 |
|:-----|:-----|:-----|-------:|:---------|-----:|:--------|
| P    | E    | N3   |      1 | I168     |    1 | 12:K    |
| P    | E    | N3   |      1 | I169     |    1 | 11:D    |
| P    | E    | N3   |      2 | I132     |    1 | 18:K    |
| P    | E    | N3   |      2 | I133     |    1 | 17:D    |
| P    | E    | N4   |      1 | I170     |    1 | 14:L    |
| P    | E    | N4   |      1 | I171     |    1 | 13:D    |
| P    | E    | N4   |      2 | I134     |    1 | 20:D    |
| P    | E    | N4   |      2 | I135     |    1 | 19:K    |
| P    | E    | N6   |      1 | I1       |    1 | 3:B     |
| P    | E    | N6   |      2 | I1       |    1 | 15:K    |
| P    | E    | N6   |      7 | I1       |    1 | 49:L    |
| P    | E    | N12  |      1 | I1       |    1 | 2:D     |
| P    | E    | N12  |      5 | I1       |    1 | 43:B    |
| P    | E    | N15  |      1 | I170     |    1 | 8:K     |
| P    | E    | N15  |      1 | I171     |    1 | 7:D     |
| P    | E    | N18  |      1 | I168     |    1 | 10:K    |
| P    | E    | N18  |      1 | I169     |    1 | 9:L     |
| P    | E    | N18  |      2 | I132     |    1 | 22:B    |
| P    | E    | N18  |      2 | I133     |    1 | 21:K    |
| P    | E    | N18  |      4 | I10      |    1 | 39:D    |
| P    | E    | N18  |      4 | I27      |    1 | 38:L    |
| P    | E    | N20  |      4 | I1       |    1 | 35:D    |
| P    | E    | N24  |      4 | I1       |    1 | 36:D    |
| P    | E    | N29  |      1 | I168     |    1 | 6:B     |
| P    | E    | N29  |      1 | I169     |    1 | 5:L     |
| P    | E    | N29  |      3 | I77      |    1 | 29:L    |
| P    | E    | N29  |      3 | I79      |    1 | 28:K    |
| P    | E    | N29  |      4 | I10      |    1 | 41:K    |
| P    | E    | N29  |      4 | I27      |    1 | 40:L    |
| P    | E    | N29  |      5 | I70      |    1 | 45:D    |
| P    | E    | N29  |      5 | I75      |    1 | 44:L    |
| P    | E    | N34  |      1 | I1       |    1 | 1:D     |
| P    | E    | N34  |      4 | I1       |    1 | 37:K    |
| P    | E    | N34  |      5 | I1       |    1 | 42:L    |
| P    | E    | N34  |      7 | I1       |    1 | 51:K    |
| P    | E    | N36  |      3 | I98      |    1 | 25:K    |
| P    | E    | N36  |      3 | I99      |    1 | 24:D    |
| P    | E    | N37  |      3 | I1       |    1 | 23:L    |
| P    | E    | N38  |      3 | I77      |    1 | 27:L    |
| P    | E    | N38  |      3 | I79      |    1 | 26:D    |
| P    | E    | N38  |      6 | I136     |    1 | 48:K    |
| P    | E    | N38  |      6 | I137     |    1 | 47:K    |
| P    | E    | N44  |      6 | I1       |    1 | 46:B    |
| P    | E    | N47  |      4 | I1       |    1 | 31:B    |
| P    | E    | N50  |      4 | I1       |    1 | 30:K    |
| P    | E    | N54  |      4 | I1       |    1 | 34:K    |
| P    | E    | N56  |      1 | I1       |    1 | 4:L     |
| P    | E    | N56  |      2 | I1       |    1 | 16:L    |
| P    | E    | N56  |      4 | I1       |    1 | 32:B    |
| P    | E    | N56  |      7 | I1       |    1 | 50:K    |
| P    | E    | N57  |      4 | I1       |    1 | 33:B    |
| P    | T    | N1   |      7 | I80      |    1 | 97:L    |
| P    | T    | N1   |      7 | I81      |    1 | 96:D    |
| P    | T    | N2   |      7 | I1       |    1 | 90:K    |
| P    | T    | N5   |      1 | I1       |    1 | 6:K     |
| P    | T    | N7   |      1 | I168     |    1 | 13:B    |
| P    | T    | N7   |      1 | I169     |    1 | 12:L    |
| P    | T    | N7   |      3 | I77      |    1 | 52:L    |
| P    | T    | N7   |      3 | I79      |    1 | 51:K    |
| P    | T    | N7   |      5 | I70      |    1 | 80:B    |
| P    | T    | N7   |      5 | I75      |    1 | 79:K    |
| P    | T    | N8   |      1 | I170     |    1 | 15:D    |
| P    | T    | N8   |      1 | I171     |    1 | 14:D    |
| P    | T    | N8   |      3 | I98      |    1 | 54:L    |
| P    | T    | N8   |      3 | I99      |    1 | 53:D    |
| P    | T    | N8   |      5 | I76      |    1 | 82:K    |
| P    | T    | N8   |      5 | I78      |    1 | 81:L    |
| P    | T    | N9   |      3 | I1       |    1 | 45:K    |
| P    | T    | N10  |      5 | I1       |    1 | 76:K    |
| P    | T    | N11  |      1 | I1       |    1 | 2:L     |
| P    | T    | N13  |      3 | I1       |    1 | 44:K    |
| P    | T    | N14  |      1 | I168     |    1 | 17:D    |
| P    | T    | N14  |      1 | I169     |    1 | 16:D    |
| P    | T    | N16  |      1 | I1       |    1 | 4:B     |
| P    | T    | N17  |      1 | I1       |    1 | 3:K     |
| P    | T    | N19  |      2 | I134     |    1 | 42:K    |
| P    | T    | N19  |      2 | I135     |    1 | 41:D    |
| P    | T    | N19  |      7 | I80      |    1 | 95:D    |
| P    | T    | N19  |      7 | I81      |    1 | 94:K    |
| P    | T    | N21  |      1 | I1       |    1 | 5:K     |
| P    | T    | N21  |      2 | I1       |    1 | 28:L    |
| P    | T    | N21  |      7 | I1       |    1 | 89:D    |
| P    | T    | N22  |      4 | I10      |    1 | 70:D    |
| P    | T    | N22  |      4 | I27      |    1 | 69:D    |
| P    | T    | N23  |      4 | I32      |    1 | 72:K    |
| P    | T    | N23  |      4 | I33      |    1 | 71:K    |
| P    | T    | N25  |      4 | I1       |    1 | 58:D    |
| P    | T    | N26  |      2 | I132     |    1 | 38:K    |
| P    | T    | N26  |      2 | I133     |    1 | 37:B    |
| P    | T    | N27  |      2 | I134     |    1 | 40:B    |
| P    | T    | N27  |      2 | I135     |    1 | 39:K    |
| P    | T    | N27  |      7 | I80      |    1 | 93:L    |
| P    | T    | N27  |      7 | I81      |    1 | 92:K    |
| P    | T    | N28  |      2 | I1       |    1 | 27:L    |
| P    | T    | N28  |      7 | I1       |    1 | 88:B    |
| P    | T    | N30  |      1 | I170     |    1 | 11:D    |
| P    | T    | N30  |      1 | I171     |    1 | 10:K    |
| P    | T    | N30  |      3 | I98      |    1 | 56:B    |
| P    | T    | N30  |      3 | I99      |    1 | 55:D    |
| P    | T    | N30  |      4 | I32      |    1 | 74:L    |
| P    | T    | N30  |      4 | I33      |    1 | 73:L    |
| P    | T    | N30  |      5 | I76      |    1 | 78:L    |
| P    | T    | N30  |      5 | I78      |    1 | 77:L    |
| P    | T    | N30  |      7 | I80      |    1 | 103:D   |
| P    | T    | N30  |      7 | I81      |    1 | 102:D   |
| P    | T    | N31  |      3 | I1       |    1 | 46:B    |
| P    | T    | N31  |      4 | I1       |    1 | 59:D    |
| P    | T    | N32  |      5 | I1       |    1 | 75:D    |
| P    | T    | N33  |      1 | I1       |    1 | 1:B     |
| P    | T    | N35  |      3 | I77      |    1 | 48:K    |
| P    | T    | N35  |      3 | I79      |    1 | 47:B    |
| P    | T    | N39  |      3 | I98      |    1 | 50:D    |
| P    | T    | N39  |      3 | I99      |    1 | 49:B    |
| P    | T    | N39  |      6 | I138     |    1 | 87:L    |
| P    | T    | N39  |      6 | I139     |    1 | 86:L    |
| P    | T    | N40  |      3 | I1       |    1 | 43:B    |
| P    | T    | N41  |      6 | I1       |    1 | 84:B    |
| P    | T    | N42  |      6 | I1       |    1 | 85:D    |
| P    | T    | N43  |      6 | I1       |    1 | 83:K    |
| P    | T    | N45  |      1 | I168     |    1 | 19:L    |
| P    | T    | N45  |      1 | I169     |    1 | 18:K    |
| P    | T    | N45  |      2 | I132     |    1 | 30:K    |
| P    | T    | N45  |      2 | I133     |    1 | 29:B    |
| P    | T    | N45  |      4 | I10      |    1 | 61:L    |
| P    | T    | N45  |      4 | I27      |    1 | 60:L    |
| P    | T    | N46  |      1 | I170     |    1 | 21:K    |
| P    | T    | N46  |      1 | I171     |    1 | 20:D    |
| P    | T    | N46  |      2 | I134     |    1 | 32:K    |
| P    | T    | N46  |      2 | I135     |    1 | 31:B    |
| P    | T    | N46  |      4 | I32      |    1 | 63:L    |
| P    | T    | N46  |      4 | I33      |    1 | 62:D    |
| P    | T    | N46  |      7 | I80      |    1 | 99:K    |
| P    | T    | N46  |      7 | I81      |    1 | 98:L    |
| P    | T    | N48  |      1 | I1       |    1 | 8:K     |
| P    | T    | N49  |      1 | I1       |    1 | 7:D     |
| P    | T    | N49  |      2 | I1       |    1 | 26:B    |
| P    | T    | N49  |      4 | I1       |    1 | 57:L    |
| P    | T    | N49  |      7 | I1       |    1 | 91:B    |
| P    | T    | N51  |      1 | I168     |    1 | 23:B    |
| P    | T    | N51  |      1 | I169     |    1 | 22:L    |
| P    | T    | N51  |      2 | I132     |    1 | 34:B    |
| P    | T    | N51  |      2 | I133     |    1 | 33:L    |
| P    | T    | N51  |      4 | I10      |    1 | 65:D    |
| P    | T    | N51  |      4 | I27      |    1 | 64:K    |
| P    | T    | N52  |      4 | I1       |    1 | 68:B    |
| P    | T    | N53  |      1 | I170     |    1 | 25:B    |
| P    | T    | N53  |      1 | I171     |    1 | 24:B    |
| P    | T    | N53  |      2 | I134     |    1 | 36:L    |
| P    | T    | N53  |      2 | I135     |    1 | 35:B    |
| P    | T    | N53  |      4 | I32      |    1 | 67:B    |
| P    | T    | N53  |      4 | I33      |    1 | 66:B    |
| P    | T    | N53  |      7 | I80      |    1 | 101:K   |
| P    | T    | N53  |      7 | I81      |    1 | 100:B   |
| P    | T    | N55  |      1 | I1       |    1 | 9:K     |
| S    | E    | N58  |      1 | I260     |    1 | 20:L    |
| S    | E    | N58  |      1 | I261     |    1 | 19:K    |
| S    | E    | N58  |      1 | I262     |    1 | 18:D    |
| S    | E    | N58  |      1 | I263     |    1 | 17:B    |
| S    | E    | N58  |      2 | I120     |    1 | 64:K    |
| S    | E    | N58  |      2 | I121     |    1 | 63:D    |
| S    | E    | N58  |      2 | I122     |    1 | 62:D    |
| S    | E    | N58  |      2 | I123     |    1 | 61:B    |
| S    | E    | N58  |      3 | I50      |    1 | 88:L    |
| S    | E    | N58  |      3 | I51      |    1 | 87:L    |
| S    | E    | N58  |      3 | I52      |    1 | 86:B    |
| S    | E    | N58  |      3 | I53      |    1 | 85:K    |
| S    | E    | N58  |      3 | I58      |    1 | 84:D    |
| S    | E    | N58  |      3 | I59      |    1 | 83:L    |
| S    | E    | N58  |      3 | I60      |    1 | 82:K    |
| S    | E    | N58  |      3 | I61      |    1 | 81:K    |
| S    | E    | N58  |      7 | I48      |    1 | 148:D   |
| S    | E    | N58  |      7 | I49      |    1 | 147:B   |
| S    | E    | N58  |      7 | I56      |    1 | 146:D   |
| S    | E    | N58  |      7 | I57      |    1 | 145:K   |
| S    | E    | N59  |      1 | I104     |    1 | 36:B    |
| S    | E    | N59  |      1 | I105     |    1 | 35:L    |
| S    | E    | N59  |      1 | I106     |    1 | 34:D    |
| S    | E    | N59  |      1 | I107     |    1 | 33:D    |
| S    | E    | N59  |      1 | I108     |    1 | 32:B    |
| S    | E    | N59  |      1 | I109     |    1 | 31:B    |
| S    | E    | N59  |      1 | I110     |    1 | 30:K    |
| S    | E    | N59  |      1 | I111     |    1 | 29:L    |
| S    | E    | N59  |      1 | I112     |    1 | 28:D    |
| S    | E    | N59  |      1 | I113     |    1 | 27:K    |
| S    | E    | N59  |      1 | I114     |    1 | 26:B    |
| S    | E    | N59  |      1 | I115     |    1 | 25:B    |
| S    | E    | N59  |      1 | I116     |    1 | 24:L    |
| S    | E    | N59  |      1 | I117     |    1 | 23:D    |
| S    | E    | N59  |      1 | I118     |    1 | 22:K    |
| S    | E    | N59  |      1 | I119     |    1 | 21:B    |
| S    | E    | N59  |      2 | I34      |    1 | 60:K    |
| S    | E    | N59  |      2 | I35      |    1 | 59:B    |
| S    | E    | N59  |      2 | I36      |    1 | 58:K    |
| S    | E    | N59  |      2 | I37      |    1 | 57:D    |
| S    | E    | N59  |      2 | I38      |    1 | 56:D    |
| S    | E    | N59  |      2 | I39      |    1 | 55:D    |
| S    | E    | N59  |      2 | I40      |    1 | 54:D    |
| S    | E    | N59  |      2 | I41      |    1 | 53:D    |
| S    | E    | N59  |      3 | I42      |    1 | 80:L    |
| S    | E    | N59  |      3 | I43      |    1 | 79:K    |
| S    | E    | N59  |      3 | I44      |    1 | 78:D    |
| S    | E    | N59  |      3 | I45      |    1 | 77:D    |
| S    | E    | N59  |      4 | I71      |    1 | 104:K   |
| S    | E    | N59  |      4 | I72      |    1 | 103:K   |
| S    | E    | N59  |      4 | I73      |    1 | 102:D   |
| S    | E    | N59  |      4 | I74      |    1 | 101:D   |
| S    | E    | N59  |      5 | I2       |    1 | 116:K   |
| S    | E    | N59  |      5 | I3       |    1 | 115:B   |
| S    | E    | N59  |      5 | I4       |    1 | 114:D   |
| S    | E    | N59  |      5 | I5       |    1 | 113:D   |
| S    | E    | N59  |      6 | I128     |    1 | 132:B   |
| S    | E    | N59  |      6 | I129     |    1 | 131:L   |
| S    | E    | N59  |      6 | I130     |    1 | 130:D   |
| S    | E    | N59  |      6 | I131     |    1 | 129:D   |
| S    | E    | N59  |      7 | I152     |    1 | 152:L   |
| S    | E    | N59  |      7 | I153     |    1 | 151:K   |
| S    | E    | N59  |      7 | I154     |    1 | 150:B   |
| S    | E    | N59  |      7 | I155     |    1 | 149:D   |
| S    | E    | N61  |      1 | I192     |    1 | 16:D    |
| S    | E    | N61  |      1 | I193     |    1 | 15:B    |
| S    | E    | N61  |      1 | I194     |    1 | 14:B    |
| S    | E    | N61  |      1 | I195     |    1 | 13:L    |
| S    | E    | N61  |      2 | I160     |    1 | 52:L    |
| S    | E    | N61  |      2 | I161     |    1 | 51:D    |
| S    | E    | N61  |      2 | I162     |    1 | 50:K    |
| S    | E    | N61  |      2 | I163     |    1 | 49:B    |
| S    | E    | N61  |      3 | I66      |    1 | 92:K    |
| S    | E    | N61  |      3 | I67      |    1 | 91:K    |
| S    | E    | N61  |      3 | I68      |    1 | 90:K    |
| S    | E    | N61  |      3 | I69      |    1 | 89:B    |
| S    | E    | N61  |      4 | I284     |    1 | 100:D   |
| S    | E    | N61  |      4 | I285     |    1 | 99:D    |
| S    | E    | N61  |      4 | I286     |    1 | 98:L    |
| S    | E    | N61  |      4 | I287     |    1 | 97:B    |
| S    | E    | N61  |      5 | I62      |    1 | 120:L   |
| S    | E    | N61  |      5 | I63      |    1 | 119:B   |
| S    | E    | N61  |      5 | I64      |    1 | 118:B   |
| S    | E    | N61  |      5 | I65      |    1 | 117:B   |
| S    | E    | N61  |      6 | I172     |    1 | 128:B   |
| S    | E    | N61  |      6 | I173     |    1 | 127:D   |
| S    | E    | N61  |      6 | I174     |    1 | 126:K   |
| S    | E    | N61  |      6 | I175     |    1 | 125:B   |
| S    | E    | N61  |      7 | I164     |    1 | 144:L   |
| S    | E    | N61  |      7 | I165     |    1 | 143:D   |
| S    | E    | N61  |      7 | I166     |    1 | 142:L   |
| S    | E    | N61  |      7 | I167     |    1 | 141:D   |
| S    | E    | N65  |      1 | I100     |    1 | 12:L    |
| S    | E    | N65  |      1 | I101     |    1 | 11:K    |
| S    | E    | N65  |      1 | I102     |    1 | 10:D    |
| S    | E    | N65  |      1 | I103     |    1 | 9:L     |
| S    | E    | N65  |      2 | I288     |    1 | 44:D    |
| S    | E    | N65  |      2 | I289     |    1 | 43:D    |
| S    | E    | N65  |      2 | I290     |    1 | 42:K    |
| S    | E    | N65  |      2 | I291     |    1 | 41:B    |
| S    | E    | N65  |      7 | I156     |    1 | 140:K   |
| S    | E    | N65  |      7 | I157     |    1 | 139:D   |
| S    | E    | N65  |      7 | I158     |    1 | 138:D   |
| S    | E    | N65  |      7 | I159     |    1 | 137:K   |
| S    | E    | N66  |      1 | I192     |    1 | 4:D     |
| S    | E    | N66  |      1 | I193     |    1 | 3:D     |
| S    | E    | N66  |      1 | I194     |    1 | 2:D     |
| S    | E    | N66  |      1 | I195     |    1 | 1:B     |
| S    | E    | N66  |      2 | I160     |    1 | 40:L    |
| S    | E    | N66  |      2 | I161     |    1 | 39:D    |
| S    | E    | N66  |      2 | I162     |    1 | 38:D    |
| S    | E    | N66  |      2 | I163     |    1 | 37:K    |
| S    | E    | N66  |      3 | I66      |    1 | 68:L    |
| S    | E    | N66  |      3 | I67      |    1 | 67:L    |
| S    | E    | N66  |      3 | I68      |    1 | 66:D    |
| S    | E    | N66  |      3 | I69      |    1 | 65:D    |
| S    | E    | N66  |      4 | I284     |    1 | 96:L    |
| S    | E    | N66  |      4 | I285     |    1 | 95:L    |
| S    | E    | N66  |      4 | I286     |    1 | 94:B    |
| S    | E    | N66  |      4 | I287     |    1 | 93:D    |
| S    | E    | N66  |      5 | I62      |    1 | 112:L   |
| S    | E    | N66  |      5 | I63      |    1 | 111:B   |
| S    | E    | N66  |      5 | I64      |    1 | 110:B   |
| S    | E    | N66  |      5 | I65      |    1 | 109:K   |
| S    | E    | N66  |      6 | I172     |    1 | 124:K   |
| S    | E    | N66  |      6 | I173     |    1 | 123:D   |
| S    | E    | N66  |      6 | I174     |    1 | 122:D   |
| S    | E    | N66  |      6 | I175     |    1 | 121:K   |
| S    | E    | N66  |      7 | I164     |    1 | 136:L   |
| S    | E    | N66  |      7 | I165     |    1 | 135:L   |
| S    | E    | N66  |      7 | I166     |    1 | 134:L   |
| S    | E    | N66  |      7 | I167     |    1 | 133:D   |
| S    | E    | N68  |      1 | I6       |    1 | 8:L     |
| S    | E    | N68  |      1 | I7       |    1 | 7:K     |
| S    | E    | N68  |      1 | I8       |    1 | 6:D     |
| S    | E    | N68  |      1 | I9       |    1 | 5:K     |
| S    | E    | N68  |      2 | I46      |    1 | 48:B    |
| S    | E    | N68  |      2 | I47      |    1 | 47:B    |
| S    | E    | N68  |      2 | I54      |    1 | 46:B    |
| S    | E    | N68  |      2 | I55      |    1 | 45:L    |
| S    | E    | N68  |      3 | I140     |    1 | 76:K    |
| S    | E    | N68  |      3 | I141     |    1 | 75:D    |
| S    | E    | N68  |      3 | I142     |    1 | 74:L    |
| S    | E    | N68  |      3 | I143     |    1 | 73:L    |
| S    | E    | N68  |      3 | I144     |    1 | 72:B    |
| S    | E    | N68  |      3 | I145     |    1 | 71:D    |
| S    | E    | N68  |      3 | I146     |    1 | 70:D    |
| S    | E    | N68  |      3 | I147     |    1 | 69:K    |
| S    | E    | N68  |      5 | I280     |    1 | 108:K   |
| S    | E    | N68  |      5 | I281     |    1 | 107:K   |
| S    | E    | N68  |      5 | I282     |    1 | 106:B   |
| S    | E    | N68  |      5 | I283     |    1 | 105:D   |
| S    | T    | N60  |      1 | I100     |    1 | 44:B    |
| S    | T    | N60  |      1 | I101     |    1 | 43:L    |
| S    | T    | N60  |      1 | I102     |    1 | 42:K    |
| S    | T    | N60  |      1 | I103     |    1 | 41:D    |
| S    | T    | N60  |      2 | I288     |    1 | 84:B    |
| S    | T    | N60  |      2 | I289     |    1 | 83:D    |
| S    | T    | N60  |      2 | I290     |    1 | 82:K    |
| S    | T    | N60  |      2 | I291     |    1 | 81:K    |
| S    | T    | N60  |      7 | I156     |    1 | 312:L   |
| S    | T    | N60  |      7 | I157     |    1 | 311:L   |
| S    | T    | N60  |      7 | I158     |    1 | 310:D   |
| S    | T    | N60  |      7 | I159     |    1 | 309:L   |
| S    | T    | N62  |      1 | I264     |    1 | 36:L    |
| S    | T    | N62  |      1 | I265     |    1 | 35:B    |
| S    | T    | N62  |      1 | I266     |    1 | 34:D    |
| S    | T    | N62  |      1 | I267     |    1 | 33:K    |
| S    | T    | N62  |      1 | I268     |    1 | 32:L    |
| S    | T    | N62  |      1 | I269     |    1 | 31:D    |
| S    | T    | N62  |      1 | I270     |    1 | 30:D    |
| S    | T    | N62  |      1 | I271     |    1 | 29:L    |
| S    | T    | N62  |      1 | I272     |    1 | 28:L    |
| S    | T    | N62  |      1 | I273     |    1 | 27:K    |
| S    | T    | N62  |      1 | I274     |    1 | 26:L    |
| S    | T    | N62  |      1 | I275     |    1 | 25:B    |
| S    | T    | N62  |      1 | I276     |    1 | 24:L    |
| S    | T    | N62  |      1 | I277     |    1 | 23:L    |
| S    | T    | N62  |      1 | I278     |    1 | 22:L    |
| S    | T    | N62  |      1 | I279     |    1 | 21:L    |
| S    | T    | N62  |      2 | I176     |    1 | 80:D    |
| S    | T    | N62  |      2 | I177     |    1 | 79:B    |
| S    | T    | N62  |      2 | I178     |    1 | 78:D    |
| S    | T    | N62  |      2 | I179     |    1 | 77:L    |
| S    | T    | N62  |      2 | I180     |    1 | 76:B    |
| S    | T    | N62  |      2 | I181     |    1 | 75:K    |
| S    | T    | N62  |      2 | I182     |    1 | 74:B    |
| S    | T    | N62  |      2 | I183     |    1 | 73:K    |
| S    | T    | N62  |      2 | I184     |    1 | 72:B    |
| S    | T    | N62  |      2 | I185     |    1 | 71:B    |
| S    | T    | N62  |      2 | I186     |    1 | 70:L    |
| S    | T    | N62  |      2 | I187     |    1 | 69:D    |
| S    | T    | N62  |      2 | I188     |    1 | 68:D    |
| S    | T    | N62  |      2 | I189     |    1 | 67:D    |
| S    | T    | N62  |      2 | I190     |    1 | 66:L    |
| S    | T    | N62  |      2 | I191     |    1 | 65:L    |
| S    | T    | N62  |      3 | I212     |    1 | 152:L   |
| S    | T    | N62  |      3 | I213     |    1 | 151:L   |
| S    | T    | N62  |      3 | I214     |    1 | 150:K   |
| S    | T    | N62  |      3 | I215     |    1 | 149:D   |
| S    | T    | N62  |      3 | I216     |    1 | 148:D   |
| S    | T    | N62  |      3 | I217     |    1 | 147:K   |
| S    | T    | N62  |      3 | I218     |    1 | 146:B   |
| S    | T    | N62  |      3 | I219     |    1 | 145:L   |
| S    | T    | N62  |      3 | I220     |    1 | 144:K   |
| S    | T    | N62  |      3 | I221     |    1 | 143:B   |
| S    | T    | N62  |      3 | I222     |    1 | 142:D   |
| S    | T    | N62  |      3 | I223     |    1 | 141:L   |
| S    | T    | N62  |      3 | I224     |    1 | 140:D   |
| S    | T    | N62  |      3 | I225     |    1 | 139:K   |
| S    | T    | N62  |      3 | I226     |    1 | 138:L   |
| S    | T    | N62  |      3 | I227     |    1 | 137:D   |
| S    | T    | N62  |      3 | I228     |    1 | 136:L   |
| S    | T    | N62  |      3 | I229     |    1 | 135:D   |
| S    | T    | N62  |      3 | I230     |    1 | 134:D   |
| S    | T    | N62  |      3 | I231     |    1 | 133:B   |
| S    | T    | N62  |      3 | I232     |    1 | 132:B   |
| S    | T    | N62  |      3 | I233     |    1 | 131:B   |
| S    | T    | N62  |      3 | I234     |    1 | 130:B   |
| S    | T    | N62  |      3 | I235     |    1 | 129:L   |
| S    | T    | N62  |      3 | I236     |    1 | 128:B   |
| S    | T    | N62  |      3 | I237     |    1 | 127:B   |
| S    | T    | N62  |      3 | I238     |    1 | 126:L   |
| S    | T    | N62  |      3 | I239     |    1 | 125:B   |
| S    | T    | N62  |      3 | I240     |    1 | 124:B   |
| S    | T    | N62  |      3 | I241     |    1 | 123:K   |
| S    | T    | N62  |      3 | I242     |    1 | 122:B   |
| S    | T    | N62  |      3 | I243     |    1 | 121:K   |
| S    | T    | N62  |      4 | I82      |    1 | 192:L   |
| S    | T    | N62  |      4 | I83      |    1 | 191:B   |
| S    | T    | N62  |      4 | I84      |    1 | 190:L   |
| S    | T    | N62  |      4 | I85      |    1 | 189:D   |
| S    | T    | N62  |      4 | I86      |    1 | 188:D   |
| S    | T    | N62  |      4 | I87      |    1 | 187:K   |
| S    | T    | N62  |      4 | I88      |    1 | 186:B   |
| S    | T    | N62  |      4 | I89      |    1 | 185:B   |
| S    | T    | N62  |      4 | I90      |    1 | 184:L   |
| S    | T    | N62  |      4 | I91      |    1 | 183:K   |
| S    | T    | N62  |      4 | I92      |    1 | 182:L   |
| S    | T    | N62  |      4 | I93      |    1 | 181:B   |
| S    | T    | N62  |      4 | I94      |    1 | 180:K   |
| S    | T    | N62  |      4 | I95      |    1 | 179:L   |
| S    | T    | N62  |      4 | I96      |    1 | 178:K   |
| S    | T    | N62  |      4 | I97      |    1 | 177:L   |
| S    | T    | N62  |      5 | I11      |    1 | 232:L   |
| S    | T    | N62  |      5 | I12      |    1 | 231:K   |
| S    | T    | N62  |      5 | I13      |    1 | 230:K   |
| S    | T    | N62  |      5 | I14      |    1 | 229:B   |
| S    | T    | N62  |      5 | I15      |    1 | 228:D   |
| S    | T    | N62  |      5 | I16      |    1 | 227:L   |
| S    | T    | N62  |      5 | I17      |    1 | 226:B   |
| S    | T    | N62  |      5 | I18      |    1 | 225:L   |
| S    | T    | N62  |      5 | I19      |    1 | 224:L   |
| S    | T    | N62  |      5 | I20      |    1 | 223:K   |
| S    | T    | N62  |      5 | I21      |    1 | 222:L   |
| S    | T    | N62  |      5 | I22      |    1 | 221:B   |
| S    | T    | N62  |      5 | I23      |    1 | 220:B   |
| S    | T    | N62  |      5 | I24      |    1 | 219:K   |
| S    | T    | N62  |      5 | I25      |    1 | 218:K   |
| S    | T    | N62  |      5 | I26      |    1 | 217:D   |
| S    | T    | N62  |      6 | I244     |    1 | 272:L   |
| S    | T    | N62  |      6 | I245     |    1 | 271:L   |
| S    | T    | N62  |      6 | I246     |    1 | 270:D   |
| S    | T    | N62  |      6 | I247     |    1 | 269:B   |
| S    | T    | N62  |      6 | I248     |    1 | 268:K   |
| S    | T    | N62  |      6 | I249     |    1 | 267:K   |
| S    | T    | N62  |      6 | I250     |    1 | 266:L   |
| S    | T    | N62  |      6 | I251     |    1 | 265:L   |
| S    | T    | N62  |      6 | I252     |    1 | 264:K   |
| S    | T    | N62  |      6 | I253     |    1 | 263:D   |
| S    | T    | N62  |      6 | I254     |    1 | 262:K   |
| S    | T    | N62  |      6 | I255     |    1 | 261:K   |
| S    | T    | N62  |      6 | I256     |    1 | 260:D   |
| S    | T    | N62  |      6 | I257     |    1 | 259:K   |
| S    | T    | N62  |      6 | I258     |    1 | 258:B   |
| S    | T    | N62  |      6 | I259     |    1 | 257:B   |
| S    | T    | N62  |      7 | I196     |    1 | 308:D   |
| S    | T    | N62  |      7 | I197     |    1 | 307:L   |
| S    | T    | N62  |      7 | I198     |    1 | 306:L   |
| S    | T    | N62  |      7 | I199     |    1 | 305:B   |
| S    | T    | N62  |      7 | I200     |    1 | 304:B   |
| S    | T    | N62  |      7 | I201     |    1 | 303:D   |
| S    | T    | N62  |      7 | I202     |    1 | 302:B   |
| S    | T    | N62  |      7 | I203     |    1 | 301:D   |
| S    | T    | N62  |      7 | I204     |    1 | 300:L   |
| S    | T    | N62  |      7 | I205     |    1 | 299:L   |
| S    | T    | N62  |      7 | I206     |    1 | 298:D   |
| S    | T    | N62  |      7 | I207     |    1 | 297:L   |
| S    | T    | N62  |      7 | I208     |    1 | 296:K   |
| S    | T    | N62  |      7 | I209     |    1 | 295:K   |
| S    | T    | N62  |      7 | I210     |    1 | 294:D   |
| S    | T    | N62  |      7 | I211     |    1 | 293:L   |
| S    | T    | N63  |      1 | I6       |    1 | 40:K    |
| S    | T    | N63  |      1 | I7       |    1 | 39:K    |
| S    | T    | N63  |      1 | I8       |    1 | 38:D    |
| S    | T    | N63  |      1 | I9       |    1 | 37:L    |
| S    | T    | N63  |      2 | I46      |    1 | 88:B    |
| S    | T    | N63  |      2 | I47      |    1 | 87:K    |
| S    | T    | N63  |      2 | I54      |    1 | 86:B    |
| S    | T    | N63  |      2 | I55      |    1 | 85:K    |
| S    | T    | N63  |      3 | I140     |    1 | 160:K   |
| S    | T    | N63  |      3 | I141     |    1 | 159:L   |
| S    | T    | N63  |      3 | I142     |    1 | 158:D   |
| S    | T    | N63  |      3 | I143     |    1 | 157:B   |
| S    | T    | N63  |      3 | I144     |    1 | 156:D   |
| S    | T    | N63  |      3 | I145     |    1 | 155:K   |
| S    | T    | N63  |      3 | I146     |    1 | 154:L   |
| S    | T    | N63  |      3 | I147     |    1 | 153:B   |
| S    | T    | N63  |      5 | I280     |    1 | 216:K   |
| S    | T    | N63  |      5 | I281     |    1 | 215:K   |
| S    | T    | N63  |      5 | I282     |    1 | 214:K   |
| S    | T    | N63  |      5 | I283     |    1 | 213:K   |
| S    | T    | N64  |      1 | I148     |    1 | 48:K    |
| S    | T    | N64  |      1 | I149     |    1 | 47:K    |
| S    | T    | N64  |      1 | I150     |    1 | 46:D    |
| S    | T    | N64  |      1 | I151     |    1 | 45:L    |
| S    | T    | N64  |      5 | I28      |    1 | 236:K   |
| S    | T    | N64  |      5 | I29      |    1 | 235:D   |
| S    | T    | N64  |      5 | I30      |    1 | 234:K   |
| S    | T    | N64  |      5 | I31      |    1 | 233:D   |
| S    | T    | N64  |      6 | I124     |    1 | 276:L   |
| S    | T    | N64  |      6 | I125     |    1 | 275:K   |
| S    | T    | N64  |      6 | I126     |    1 | 274:B   |
| S    | T    | N64  |      6 | I127     |    1 | 273:L   |
| S    | T    | N67  |      1 | I264     |    1 | 16:D    |
| S    | T    | N67  |      1 | I265     |    1 | 15:B    |
| S    | T    | N67  |      1 | I266     |    1 | 14:B    |
| S    | T    | N67  |      1 | I267     |    1 | 13:B    |
| S    | T    | N67  |      1 | I268     |    1 | 12:B    |
| S    | T    | N67  |      1 | I269     |    1 | 11:D    |
| S    | T    | N67  |      1 | I270     |    1 | 10:D    |
| S    | T    | N67  |      1 | I271     |    1 | 9:D     |
| S    | T    | N67  |      1 | I272     |    1 | 8:K     |
| S    | T    | N67  |      1 | I273     |    1 | 7:K     |
| S    | T    | N67  |      1 | I274     |    1 | 6:K     |
| S    | T    | N67  |      1 | I275     |    1 | 5:B     |
| S    | T    | N67  |      1 | I276     |    1 | 4:K     |
| S    | T    | N67  |      1 | I277     |    1 | 3:K     |
| S    | T    | N67  |      1 | I278     |    1 | 2:B     |
| S    | T    | N67  |      1 | I279     |    1 | 1:L     |
| S    | T    | N67  |      2 | I176     |    1 | 64:D    |
| S    | T    | N67  |      2 | I177     |    1 | 63:L    |
| S    | T    | N67  |      2 | I178     |    1 | 62:K    |
| S    | T    | N67  |      2 | I179     |    1 | 61:K    |
| S    | T    | N67  |      2 | I180     |    1 | 60:B    |
| S    | T    | N67  |      2 | I181     |    1 | 59:B    |
| S    | T    | N67  |      2 | I182     |    1 | 58:D    |
| S    | T    | N67  |      2 | I183     |    1 | 57:K    |
| S    | T    | N67  |      2 | I184     |    1 | 56:D    |
| S    | T    | N67  |      2 | I185     |    1 | 55:K    |
| S    | T    | N67  |      2 | I186     |    1 | 54:B    |
| S    | T    | N67  |      2 | I187     |    1 | 53:D    |
| S    | T    | N67  |      2 | I188     |    1 | 52:L    |
| S    | T    | N67  |      2 | I189     |    1 | 51:B    |
| S    | T    | N67  |      2 | I190     |    1 | 50:K    |
| S    | T    | N67  |      2 | I191     |    1 | 49:D    |
| S    | T    | N67  |      3 | I212     |    1 | 120:D   |
| S    | T    | N67  |      3 | I213     |    1 | 119:B   |
| S    | T    | N67  |      3 | I214     |    1 | 118:D   |
| S    | T    | N67  |      3 | I215     |    1 | 117:L   |
| S    | T    | N67  |      3 | I216     |    1 | 116:D   |
| S    | T    | N67  |      3 | I217     |    1 | 115:L   |
| S    | T    | N67  |      3 | I218     |    1 | 114:K   |
| S    | T    | N67  |      3 | I219     |    1 | 113:L   |
| S    | T    | N67  |      3 | I220     |    1 | 112:D   |
| S    | T    | N67  |      3 | I221     |    1 | 111:D   |
| S    | T    | N67  |      3 | I222     |    1 | 110:D   |
| S    | T    | N67  |      3 | I223     |    1 | 109:K   |
| S    | T    | N67  |      3 | I224     |    1 | 108:D   |
| S    | T    | N67  |      3 | I225     |    1 | 107:D   |
| S    | T    | N67  |      3 | I226     |    1 | 106:K   |
| S    | T    | N67  |      3 | I227     |    1 | 105:D   |
| S    | T    | N67  |      3 | I228     |    1 | 104:B   |
| S    | T    | N67  |      3 | I229     |    1 | 103:K   |
| S    | T    | N67  |      3 | I230     |    1 | 102:B   |
| S    | T    | N67  |      3 | I231     |    1 | 101:K   |
| S    | T    | N67  |      3 | I232     |    1 | 100:K   |
| S    | T    | N67  |      3 | I233     |    1 | 99:L    |
| S    | T    | N67  |      3 | I234     |    1 | 98:L    |
| S    | T    | N67  |      3 | I235     |    1 | 97:K    |
| S    | T    | N67  |      3 | I236     |    1 | 96:L    |
| S    | T    | N67  |      3 | I237     |    1 | 95:B    |
| S    | T    | N67  |      3 | I238     |    1 | 94:K    |
| S    | T    | N67  |      3 | I239     |    1 | 93:K    |
| S    | T    | N67  |      3 | I240     |    1 | 92:K    |
| S    | T    | N67  |      3 | I241     |    1 | 91:L    |
| S    | T    | N67  |      3 | I242     |    1 | 90:D    |
| S    | T    | N67  |      3 | I243     |    1 | 89:L    |
| S    | T    | N67  |      4 | I82      |    1 | 176:K   |
| S    | T    | N67  |      4 | I83      |    1 | 175:B   |
| S    | T    | N67  |      4 | I84      |    1 | 174:L   |
| S    | T    | N67  |      4 | I85      |    1 | 173:K   |
| S    | T    | N67  |      4 | I86      |    1 | 172:B   |
| S    | T    | N67  |      4 | I87      |    1 | 171:D   |
| S    | T    | N67  |      4 | I88      |    1 | 170:B   |
| S    | T    | N67  |      4 | I89      |    1 | 169:L   |
| S    | T    | N67  |      4 | I90      |    1 | 168:D   |
| S    | T    | N67  |      4 | I91      |    1 | 167:B   |
| S    | T    | N67  |      4 | I92      |    1 | 166:K   |
| S    | T    | N67  |      4 | I93      |    1 | 165:K   |
| S    | T    | N67  |      4 | I94      |    1 | 164:D   |
| S    | T    | N67  |      4 | I95      |    1 | 163:L   |
| S    | T    | N67  |      4 | I96      |    1 | 162:B   |
| S    | T    | N67  |      4 | I97      |    1 | 161:D   |
| S    | T    | N67  |      5 | I11      |    1 | 208:D   |
| S    | T    | N67  |      5 | I12      |    1 | 207:K   |
| S    | T    | N67  |      5 | I13      |    1 | 206:K   |
| S    | T    | N67  |      5 | I14      |    1 | 205:L   |
| S    | T    | N67  |      5 | I15      |    1 | 204:D   |
| S    | T    | N67  |      5 | I16      |    1 | 203:K   |
| S    | T    | N67  |      5 | I17      |    1 | 202:B   |
| S    | T    | N67  |      5 | I18      |    1 | 201:D   |
| S    | T    | N67  |      5 | I19      |    1 | 200:B   |
| S    | T    | N67  |      5 | I20      |    1 | 199:D   |
| S    | T    | N67  |      5 | I21      |    1 | 198:L   |
| S    | T    | N67  |      5 | I22      |    1 | 197:L   |
| S    | T    | N67  |      5 | I23      |    1 | 196:L   |
| S    | T    | N67  |      5 | I24      |    1 | 195:K   |
| S    | T    | N67  |      5 | I25      |    1 | 194:B   |
| S    | T    | N67  |      5 | I26      |    1 | 193:L   |
| S    | T    | N67  |      6 | I244     |    1 | 252:D   |
| S    | T    | N67  |      6 | I245     |    1 | 251:B   |
| S    | T    | N67  |      6 | I246     |    1 | 250:D   |
| S    | T    | N67  |      6 | I247     |    1 | 249:D   |
| S    | T    | N67  |      6 | I248     |    1 | 248:L   |
| S    | T    | N67  |      6 | I249     |    1 | 247:B   |
| S    | T    | N67  |      6 | I250     |    1 | 246:L   |
| S    | T    | N67  |      6 | I251     |    1 | 245:B   |
| S    | T    | N67  |      6 | I252     |    1 | 244:K   |
| S    | T    | N67  |      6 | I253     |    1 | 243:B   |
| S    | T    | N67  |      6 | I254     |    1 | 242:L   |
| S    | T    | N67  |      6 | I255     |    1 | 241:K   |
| S    | T    | N67  |      6 | I256     |    1 | 240:K   |
| S    | T    | N67  |      6 | I257     |    1 | 239:D   |
| S    | T    | N67  |      6 | I258     |    1 | 238:L   |
| S    | T    | N67  |      6 | I259     |    1 | 237:K   |
| S    | T    | N67  |      7 | I196     |    1 | 292:K   |
| S    | T    | N67  |      7 | I197     |    1 | 291:L   |
| S    | T    | N67  |      7 | I198     |    1 | 290:L   |
| S    | T    | N67  |      7 | I199     |    1 | 289:K   |
| S    | T    | N67  |      7 | I200     |    1 | 288:D   |
| S    | T    | N67  |      7 | I201     |    1 | 287:K   |
| S    | T    | N67  |      7 | I202     |    1 | 286:D   |
| S    | T    | N67  |      7 | I203     |    1 | 285:L   |
| S    | T    | N67  |      7 | I204     |    1 | 284:K   |
| S    | T    | N67  |      7 | I205     |    1 | 283:K   |
| S    | T    | N67  |      7 | I206     |    1 | 282:B   |
| S    | T    | N67  |      7 | I207     |    1 | 281:L   |
| S    | T    | N67  |      7 | I208     |    1 | 280:L   |
| S    | T    | N67  |      7 | I209     |    1 | 279:K   |
| S    | T    | N67  |      7 | I210     |    1 | 278:L   |
| S    | T    | N67  |      7 | I211     |    1 | 277:D   |
| S    | T    | N69  |      1 | I148     |    1 | 20:K    |
| S    | T    | N69  |      1 | I149     |    1 | 19:K    |
| S    | T    | N69  |      1 | I150     |    1 | 18:D    |
| S    | T    | N69  |      1 | I151     |    1 | 17:B    |
| S    | T    | N69  |      5 | I28      |    1 | 212:B   |
| S    | T    | N69  |      5 | I29      |    1 | 211:B   |
| S    | T    | N69  |      5 | I30      |    1 | 210:L   |
| S    | T    | N69  |      5 | I31      |    1 | 209:D   |
| S    | T    | N69  |      6 | I124     |    1 | 256:K   |
| S    | T    | N69  |      6 | I125     |    1 | 255:L   |
| S    | T    | N69  |      6 | I126     |    1 | 254:L   |
| S    | T    | N69  |      6 | I127     |    1 | 253:L   |

<a id="app-real-inputs"></a>

## 実シーンでの入力と行動前後の変化

構成要素比較のC1・GPT-4o・反復0から，状態変化task6と配置task65を固定して示す．結果の良否による選び直しは行わない．これは基本性能評価の未保存入力を復元したものではなく，付録の合成例とも異なる実際の観測である．以下の環境文は最初の終了判定へ送信した全文から末尾の判定指示のみを除いたもので，重複したand等も保持した．

<a id="section-24"></a>

### 状態変化task6

人物の初期位置は\[-2.41545, 1.25, -7.44353151\]である．

<a id="lst-inline11"></a>

**Listing A11：最初の判定へ送信した環境知識全文**

```text
The current states in the home are as follows: 
The lightswitch (71) is ON and and is INSIDE the bathroom (11).
The lightswitch (173) is OFF and and is INSIDE the bedroom (73).
The lightswitch (261) is ON and and is INSIDE the kitchen (205).
The lightswitch (427) is OFF and and is INSIDE the livingroom (335).
You are INSIDE the kitchen (205).

```

<a id="tab-real-edges-test-task6"></a>

**表A27：初期グラフの対象・人物からの関係抜粋**

| 始点ID | クラス      | 関係   | 終点ID | クラス          |
|:-------|:------------|:-------|:-------|:----------------|
| 71     | lightswitch | INSIDE | 11     | bathroom        |
| 173    | lightswitch | INSIDE | 73     | bedroom         |
| 261    | lightswitch | INSIDE | 205    | kitchen         |
| 427    | lightswitch | INSIDE | 335    | livingroom      |
| 1      | character   | INSIDE | 205    | kitchen         |
| 1      | character   | CLOSE  | 175    | cpuscreen       |
| 1      | character   | CLOSE  | 230    | tvstand         |
| 1      | character   | CLOSE  | 232    | bench           |
| 1      | character   | CLOSE  | 249    | bookshelf       |
| 1      | character   | CLOSE  | 253    | rug             |
| 1      | character   | CLOSE  | 260    | orchid          |
| 1      | character   | CLOSE  | 264    | tv              |
| 1      | character   | CLOSE  | 286    | clothespile     |
| 1      | character   | CLOSE  | 287    | box             |
| 1      | character   | CLOSE  | 288    | dishbowl        |
| 1      | character   | CLOSE  | 289    | book            |
| 1      | character   | CLOSE  | 290    | book            |
| 1      | character   | CLOSE  | 291    | book            |
| 1      | character   | CLOSE  | 292    | book            |
| 1      | character   | CLOSE  | 293    | book            |
| 1      | character   | CLOSE  | 294    | condimentbottle |
| 1      | character   | CLOSE  | 295    | condimentbottle |
| 1      | character   | CLOSE  | 296    | condimentshaker |
| 1      | character   | CLOSE  | 297    | condimentshaker |
| 1      | character   | CLOSE  | 298    | wineglass       |
| 1      | character   | CLOSE  | 302    | paper           |
| 1      | character   | CLOSE  | 303    | paper           |
| 1      | character   | CLOSE  | 315    | bananas         |
| 1      | character   | CLOSE  | 316    | bananas         |
| 1      | character   | CLOSE  | 317    | dishbowl        |

関係変化の$`+`$/$`-`$は追加／削除を表し，対象辞書内の物体と人物を始点とするON・INSIDE・保持・CLOSEに限定する．座標変化そのものや無関係な辺は省略する．

<a id="tab-real-changes-test-task6"></a>

**表A28：行動と状態・関係の変化**

| step | 実行行動 | VH | 変化 |
|---:|:---|:---|:---|
| 1 | \[WALK\] \<lightswitch\> (173) | 成功 | \- (1, ’CLOSE’, 230); - (1, ’CLOSE’, 232); - (1, ’CLOSE’, 253); - (1, ’CLOSE’, 260); - (1, ’CLOSE’, 264); - (1, ’CLOSE’, 287); - (1, ’CLOSE’, 298); - (1, ’CLOSE’, 303); - (1, ’CLOSE’, 315); - (1, ’CLOSE’, 316); - (1, ’CLOSE’, 317); - (1, ’INSIDE’, 205); + (1, ’CLOSE’, 107); + (1, ’CLOSE’, 108); + (1, ’CLOSE’, 172); + (1, ’CLOSE’, 173); + (1, ’CLOSE’, 174); + (1, ’CLOSE’, 193); + (1, ’CLOSE’, 194); + (1, ’CLOSE’, 195); + (1, ’CLOSE’, 196); + (1, ’CLOSE’, 261); + (1, ’CLOSE’, 262); + (1, ’CLOSE’, 263); + (1, ’CLOSE’, 265); + (1, ’INSIDE’, 73); + (173, ’CLOSE’, 1); + (261, ’CLOSE’, 1) |
| 2 | \[SWITCHON\] \<lightswitch\> (173) | 成功 | 173: OFF -\> ON |
| 3 | \[WALK\] \<lightswitch\> (261) | 成功 | \- (1, ’CLOSE’, 107); - (1, ’CLOSE’, 108); - (1, ’CLOSE’, 172); - (1, ’CLOSE’, 174); - (1, ’CLOSE’, 175); - (1, ’CLOSE’, 193); - (1, ’CLOSE’, 194); - (1, ’CLOSE’, 195); - (1, ’CLOSE’, 196); - (1, ’CLOSE’, 249); - (1, ’CLOSE’, 286); - (1, ’CLOSE’, 288); - (1, ’CLOSE’, 289); - (1, ’CLOSE’, 290); - (1, ’CLOSE’, 291); - (1, ’CLOSE’, 292); - (1, ’CLOSE’, 293); - (1, ’CLOSE’, 294); - (1, ’CLOSE’, 295); - (1, ’CLOSE’, 296); - (1, ’CLOSE’, 297); - (1, ’CLOSE’, 302); - (1, ’INSIDE’, 73); + (1, ’CLOSE’, 178); + (1, ’CLOSE’, 229); + (1, ’CLOSE’, 231); + (1, ’CLOSE’, 233); + (1, ’CLOSE’, 252); + (1, ’CLOSE’, 253); + (1, ’CLOSE’, 254); + (1, ’CLOSE’, 255); + (1, ’CLOSE’, 256); + (1, ’CLOSE’, 268); + (1, ’CLOSE’, 270); + (1, ’CLOSE’, 271); + (1, ’CLOSE’, 272); + (1, ’CLOSE’, 273); + (1, ’CLOSE’, 278); + (1, ’CLOSE’, 279); + (1, ’CLOSE’, 280); + (1, ’CLOSE’, 281); + (1, ’CLOSE’, 319); + (1, ’INSIDE’, 205) |
| 4 | \[WALK\] \<lightswitch\> (427) | 成功 | \- (1, ’CLOSE’, 173); - (1, ’CLOSE’, 178); - (1, ’CLOSE’, 229); - (1, ’CLOSE’, 231); - (1, ’CLOSE’, 233); - (1, ’CLOSE’, 252); - (1, ’CLOSE’, 253); - (1, ’CLOSE’, 254); - (1, ’CLOSE’, 255); - (1, ’CLOSE’, 256); - (1, ’CLOSE’, 261); - (1, ’CLOSE’, 262); - (1, ’CLOSE’, 263); - (1, ’CLOSE’, 265); - (1, ’CLOSE’, 268); - (1, ’CLOSE’, 270); - (1, ’CLOSE’, 271); - (1, ’CLOSE’, 272); - (1, ’CLOSE’, 273); - (1, ’CLOSE’, 278); - (1, ’CLOSE’, 279); - (1, ’CLOSE’, 280); - (1, ’CLOSE’, 281); - (1, ’CLOSE’, 319); - (1, ’INSIDE’, 205); - (173, ’CLOSE’, 1); - (261, ’CLOSE’, 1); + (1, ’CLOSE’, 251); + (1, ’CLOSE’, 332); + (1, ’CLOSE’, 333); + (1, ’CLOSE’, 334); + (1, ’CLOSE’, 415); + (1, ’CLOSE’, 418); + (1, ’CLOSE’, 420); + (1, ’CLOSE’, 427); + (1, ’CLOSE’, 428); + (1, ’CLOSE’, 453); + (1, ’INSIDE’, 335); + (427, ’CLOSE’, 1) |
| 5 | \[SWITCHON\] \<lightswitch\> (427) | 成功 | 427: OFF -\> ON; + (1, ’CLOSE’, 258) |

<a id="section-25"></a>

### 配置task65

人物の初期位置は\[9.582918, 1.25, -4.21981239\]である．

<a id="lst-inline12"></a>

**Listing A12：最初の判定へ送信した環境知識全文**

```text
The current states in the home are as follows: 
The plum (53) is ON the kitchencounter (92) and and is INSIDE the kitchen (11).
The plum (54) is ON the kitchencounter (92) and and is INSIDE the kitchen (11).
The fridge (103) is CLOSED and and is INSIDE the kitchen (11).
The kitchencounter (92) is CLOSED and is INSIDE the dishwasher (104) and and is INSIDE the kitchen (11).
plum (53) and plum (54) are ON the kitchencounter (92).
You are INSIDE the bedroom (211).

```

<a id="tab-real-edges-test-task65"></a>

**表A29：初期グラフの対象・人物からの関係抜粋**

| 始点ID | クラス         | 関係   | 終点ID | クラス         |
|:-------|:---------------|:-------|:-------|:---------------|
| 53     | plum           | INSIDE | 11     | kitchen        |
| 54     | plum           | INSIDE | 11     | kitchen        |
| 92     | kitchencounter | INSIDE | 11     | kitchen        |
| 103    | fridge         | INSIDE | 11     | kitchen        |
| 1      | character      | INSIDE | 211    | bedroom        |
| 53     | plum           | ON     | 92     | kitchencounter |
| 54     | plum           | ON     | 92     | kitchencounter |
| 92     | kitchencounter | ON     | 19     | floor          |
| 92     | kitchencounter | INSIDE | 104    | dishwasher     |
| 1      | character      | CLOSE  | 214    | desk           |
| 1      | character      | CLOSE  | 217    | cabinet        |
| 1      | character      | CLOSE  | 218    | lightswitch    |
| 1      | character      | CLOSE  | 231    | apple          |
| 1      | character      | CLOSE  | 232    | apple          |
| 1      | character      | CLOSE  | 233    | apple          |
| 1      | character      | CLOSE  | 234    | apple          |
| 1      | character      | CLOSE  | 235    | apple          |
| 1      | character      | CLOSE  | 236    | apple          |
| 1      | character      | CLOSE  | 237    | apple          |
| 1      | character      | CLOSE  | 238    | apple          |
| 1      | character      | CLOSE  | 239    | apple          |
| 1      | character      | CLOSE  | 240    | apple          |
| 1      | character      | CLOSE  | 241    | apple          |
| 1      | character      | CLOSE  | 242    | dishbowl       |
| 1      | character      | CLOSE  | 245    | cupcake        |
| 1      | character      | CLOSE  | 246    | plate          |
| 1      | character      | CLOSE  | 249    | cellphone      |
| 1      | character      | CLOSE  | 270    | bookshelf      |
| 1      | character      | CLOSE  | 299    | powersocket    |
| 1      | character      | CLOSE  | 300    | lightswitch    |
| 1      | character      | CLOSE  | 301    | rug            |
| 1      | character      | CLOSE  | 313    | clothespile    |
| 1      | character      | CLOSE  | 316    | facecream      |
| 1      | character      | CLOSE  | 317    | deodorant      |
| 1      | character      | CLOSE  | 318    | hairproduct    |
| 1      | character      | CLOSE  | 319    | hairproduct    |
| 1      | character      | CLOSE  | 321    | box            |
| 1      | character      | CLOSE  | 327    | folder         |
| 1      | character      | CLOSE  | 328    | folder         |
| 1      | character      | CLOSE  | 329    | folder         |
| 1      | character      | CLOSE  | 330    | folder         |

関係変化の$`+`$/$`-`$は追加／削除を表し，対象辞書内の物体と人物を始点とするON・INSIDE・保持・CLOSEに限定する．座標変化そのものや無関係な辺は省略する．

<a id="tab-real-changes-test-task65"></a>

**表A30：行動と状態・関係の変化**

| step | 実行行動 | VH | 変化 |
|---:|:---|:---|:---|
| 1 | \[WALK\] \<kitchen\> (11) | 成功 | \- (1, ’CLOSE’, 214); - (1, ’CLOSE’, 217); - (1, ’CLOSE’, 218); - (1, ’CLOSE’, 231); - (1, ’CLOSE’, 232); - (1, ’CLOSE’, 233); - (1, ’CLOSE’, 234); - (1, ’CLOSE’, 235); - (1, ’CLOSE’, 236); - (1, ’CLOSE’, 237); - (1, ’CLOSE’, 238); - (1, ’CLOSE’, 239); - (1, ’CLOSE’, 240); - (1, ’CLOSE’, 241); - (1, ’CLOSE’, 242); - (1, ’CLOSE’, 245); - (1, ’CLOSE’, 246); - (1, ’CLOSE’, 249); - (1, ’CLOSE’, 270); - (1, ’CLOSE’, 299); - (1, ’CLOSE’, 300); - (1, ’CLOSE’, 301); - (1, ’CLOSE’, 313); - (1, ’CLOSE’, 316); - (1, ’CLOSE’, 317); - (1, ’CLOSE’, 318); - (1, ’CLOSE’, 319); - (1, ’CLOSE’, 321); - (1, ’CLOSE’, 327); - (1, ’CLOSE’, 328); - (1, ’CLOSE’, 329); - (1, ’CLOSE’, 330); - (1, ’INSIDE’, 211); + (1, ’CLOSE’, 46); + (1, ’CLOSE’, 57); + (1, ’CLOSE’, 58); + (1, ’CLOSE’, 59); + (1, ’CLOSE’, 62); + (1, ’CLOSE’, 64); + (1, ’CLOSE’, 65); + (1, ’CLOSE’, 68); + (1, ’CLOSE’, 69); + (1, ’CLOSE’, 70); + (1, ’CLOSE’, 71); + (1, ’CLOSE’, 72); + (1, ’CLOSE’, 116); + (1, ’CLOSE’, 117); + (1, ’CLOSE’, 123); + (1, ’CLOSE’, 124); + (1, ’CLOSE’, 125); + (1, ’CLOSE’, 126); + (1, ’CLOSE’, 127); + (1, ’CLOSE’, 128); + (1, ’CLOSE’, 129); + (1, ’CLOSE’, 130); + (1, ’CLOSE’, 131); + (1, ’CLOSE’, 132); + (1, ’CLOSE’, 133); + (1, ’CLOSE’, 134); + (1, ’CLOSE’, 135); + (1, ’CLOSE’, 136); + (1, ’CLOSE’, 137); + (1, ’CLOSE’, 138); + (1, ’CLOSE’, 139); + (1, ’CLOSE’, 140); + (1, ’CLOSE’, 141); + (1, ’CLOSE’, 142); + (1, ’CLOSE’, 158); + (1, ’INSIDE’, 11) |
| 2 | \[WALK\] \<fridge\> (103) | 成功 | \- (1, ’CLOSE’, 46); - (1, ’CLOSE’, 57); - (1, ’CLOSE’, 58); - (1, ’CLOSE’, 59); - (1, ’CLOSE’, 62); - (1, ’CLOSE’, 64); - (1, ’CLOSE’, 65); - (1, ’CLOSE’, 68); - (1, ’CLOSE’, 69); - (1, ’CLOSE’, 70); - (1, ’CLOSE’, 71); - (1, ’CLOSE’, 72); - (1, ’CLOSE’, 116); - (1, ’CLOSE’, 117); - (1, ’CLOSE’, 123); - (1, ’CLOSE’, 124); - (1, ’CLOSE’, 125); - (1, ’CLOSE’, 126); - (1, ’CLOSE’, 127); - (1, ’CLOSE’, 128); - (1, ’CLOSE’, 129); - (1, ’CLOSE’, 130); - (1, ’CLOSE’, 131); - (1, ’CLOSE’, 132); - (1, ’CLOSE’, 133); - (1, ’CLOSE’, 134); - (1, ’CLOSE’, 135); - (1, ’CLOSE’, 136); - (1, ’CLOSE’, 137); - (1, ’CLOSE’, 138); - (1, ’CLOSE’, 139); - (1, ’CLOSE’, 140); - (1, ’CLOSE’, 141); - (1, ’CLOSE’, 142); + (1, ’CLOSE’, 96); + (1, ’CLOSE’, 103); + (1, ’CLOSE’, 155); + (1, ’CLOSE’, 156); + (1, ’CLOSE’, 169); + (1, ’CLOSE’, 170); + (103, ’CLOSE’, 1) |
| 3 | \[OPEN\] \<fridge\> (103) | 成功 | 103: CLOSED -\> OPEN; + (1, ’CLOSE’, 94) |
| 4 | \[WALK\] \<kitchencounter\> (92) | 成功 | \- (1, ’CLOSE’, 94); - (1, ’CLOSE’, 96); - (1, ’CLOSE’, 103); - (1, ’CLOSE’, 155); - (1, ’CLOSE’, 156); - (1, ’CLOSE’, 158); - (1, ’CLOSE’, 169); - (1, ’CLOSE’, 170); - (103, ’CLOSE’, 1); + (1, ’CLOSE’, 47); + (1, ’CLOSE’, 48); + (1, ’CLOSE’, 49); + (1, ’CLOSE’, 50); + (1, ’CLOSE’, 51); + (1, ’CLOSE’, 52); + (1, ’CLOSE’, 53); + (1, ’CLOSE’, 54); + (1, ’CLOSE’, 55); + (1, ’CLOSE’, 56); + (1, ’CLOSE’, 60); + (1, ’CLOSE’, 61); + (1, ’CLOSE’, 63); + (1, ’CLOSE’, 70); + (1, ’CLOSE’, 71); + (1, ’CLOSE’, 73); + (1, ’CLOSE’, 74); + (1, ’CLOSE’, 75); + (1, ’CLOSE’, 92); + (1, ’CLOSE’, 102); + (1, ’CLOSE’, 104); + (1, ’CLOSE’, 105); + (1, ’CLOSE’, 106); + (1, ’CLOSE’, 107); + (1, ’CLOSE’, 108); + (1, ’CLOSE’, 118); + (1, ’CLOSE’, 119); + (1, ’CLOSE’, 120); + (1, ’CLOSE’, 121); + (1, ’CLOSE’, 122); + (1, ’CLOSE’, 125); + (1, ’CLOSE’, 126); + (1, ’CLOSE’, 134); + (1, ’CLOSE’, 135); + (1, ’CLOSE’, 136); + (1, ’CLOSE’, 157); + (53, ’CLOSE’, 1); + (54, ’CLOSE’, 1); + (92, ’CLOSE’, 1) |
| 5 | \[GRAB\] \<plum\> (53) | 成功 | \- (53, ’ON’, 92); + (1, ’HOLDS_RH’, 53) |
| 6 | \[PUTIN\] \<plum\> (53) \<fridge\> (103) | 成功 | \- (1, ’CLOSE’, 47); - (1, ’CLOSE’, 48); - (1, ’CLOSE’, 49); - (1, ’CLOSE’, 50); - (1, ’CLOSE’, 51); - (1, ’CLOSE’, 52); - (1, ’CLOSE’, 54); - (1, ’CLOSE’, 55); - (1, ’CLOSE’, 56); - (1, ’CLOSE’, 60); - (1, ’CLOSE’, 61); - (1, ’CLOSE’, 63); - (1, ’CLOSE’, 70); - (1, ’CLOSE’, 71); - (1, ’CLOSE’, 73); - (1, ’CLOSE’, 74); - (1, ’CLOSE’, 75); - (1, ’CLOSE’, 92); - (1, ’CLOSE’, 102); - (1, ’CLOSE’, 104); - (1, ’CLOSE’, 105); - (1, ’CLOSE’, 106); - (1, ’CLOSE’, 107); - (1, ’CLOSE’, 108); - (1, ’CLOSE’, 118); - (1, ’CLOSE’, 119); - (1, ’CLOSE’, 120); - (1, ’CLOSE’, 121); - (1, ’CLOSE’, 122); - (1, ’CLOSE’, 125); - (1, ’CLOSE’, 126); - (1, ’CLOSE’, 134); - (1, ’CLOSE’, 135); - (1, ’CLOSE’, 136); - (1, ’CLOSE’, 157); - (1, ’HOLDS_RH’, 53); - (53, ’INSIDE’, 11); - (54, ’CLOSE’, 1); - (92, ’CLOSE’, 1); + (1, ’CLOSE’, 96); + (1, ’CLOSE’, 103); + (1, ’CLOSE’, 116); + (1, ’CLOSE’, 117); + (1, ’CLOSE’, 155); + (1, ’CLOSE’, 158); + (1, ’CLOSE’, 169); + (1, ’CLOSE’, 170); + (53, ’INSIDE’, 103); + (103, ’CLOSE’, 1) |
| 7 | \[WALK\] \<plum\> (54) | 成功 | \- (1, ’CLOSE’, 53); - (1, ’CLOSE’, 96); - (1, ’CLOSE’, 103); - (1, ’CLOSE’, 116); - (1, ’CLOSE’, 117); - (1, ’CLOSE’, 155); - (1, ’CLOSE’, 158); - (1, ’CLOSE’, 169); - (1, ’CLOSE’, 170); - (53, ’CLOSE’, 1); - (103, ’CLOSE’, 1); + (1, ’CLOSE’, 47); + (1, ’CLOSE’, 48); + (1, ’CLOSE’, 49); + (1, ’CLOSE’, 50); + (1, ’CLOSE’, 51); + (1, ’CLOSE’, 52); + (1, ’CLOSE’, 54); + (1, ’CLOSE’, 55); + (1, ’CLOSE’, 56); + (1, ’CLOSE’, 61); + (1, ’CLOSE’, 63); + (1, ’CLOSE’, 73); + (1, ’CLOSE’, 74); + (1, ’CLOSE’, 75); + (1, ’CLOSE’, 76); + (1, ’CLOSE’, 92); + (1, ’CLOSE’, 93); + (1, ’CLOSE’, 104); + (1, ’CLOSE’, 107); + (1, ’CLOSE’, 108); + (1, ’CLOSE’, 118); + (1, ’CLOSE’, 119); + (1, ’CLOSE’, 157); + (54, ’CLOSE’, 1); + (92, ’CLOSE’, 1) |
| 8 | \[GRAB\] \<plum\> (54) | 成功 | \- (54, ’ON’, 92); + (1, ’HOLDS_RH’, 54) |
| 9 | \[PUTIN\] \<plum\> (54) \<fridge\> (103) | 成功 | \- (1, ’CLOSE’, 47); - (1, ’CLOSE’, 48); - (1, ’CLOSE’, 49); - (1, ’CLOSE’, 50); - (1, ’CLOSE’, 51); - (1, ’CLOSE’, 52); - (1, ’CLOSE’, 55); - (1, ’CLOSE’, 56); - (1, ’CLOSE’, 61); - (1, ’CLOSE’, 63); - (1, ’CLOSE’, 73); - (1, ’CLOSE’, 74); - (1, ’CLOSE’, 75); - (1, ’CLOSE’, 76); - (1, ’CLOSE’, 92); - (1, ’CLOSE’, 93); - (1, ’CLOSE’, 104); - (1, ’CLOSE’, 107); - (1, ’CLOSE’, 108); - (1, ’CLOSE’, 118); - (1, ’CLOSE’, 119); - (1, ’CLOSE’, 157); - (1, ’HOLDS_RH’, 54); - (54, ’INSIDE’, 11); - (92, ’CLOSE’, 1); + (1, ’CLOSE’, 53); + (1, ’CLOSE’, 96); + (1, ’CLOSE’, 103); + (1, ’CLOSE’, 155); + (1, ’CLOSE’, 156); + (1, ’CLOSE’, 158); + (1, ’CLOSE’, 169); + (1, ’CLOSE’, 170); + (53, ’CLOSE’, 1); + (54, ’INSIDE’, 103); + (103, ’CLOSE’, 1) |

[^1]: <https://github.com/xavierpuigf/virtualhome/blob/58970fd80951c2eaa1af713e0917d1a105353ad8/virtualhome/simulation/evolving_graph/execution.py>


## 関連資料と編集元

- [前提条件の公式資料との照合](revision-completion/Precondition-Sources.md)：公式Actions文書、resources、公開実行コードの固定版と条件ごとの対応。
- [知識変換・プロンプトのコードと入力例](listings/)／[前提条件辞書](../precondition.json)。
- [集計資料](analysis/)／[構成要素比較の記録](vh_step4/)／[著者による未充足条件の確認票](human-unmet-review/semantic_review.csv)。
- 旧付録のTeXソース：[実装](appendix-implementation.tex)、[評価](appendix-evaluation.tex)、[著者確認](appendix-human-review.tex)、[統計](appendix-statistics.tex)、[実入力](appendix-real-inputs.tex)。
