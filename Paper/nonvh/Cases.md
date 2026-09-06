# 静的評価の誤判定事例

以下は新規の合成入力に対するAPI応答。元のVH実行失敗の原因分析ではない。
goldは既知の有限close/held集合を前提とする。元の自然言語変換は空集合を文にしないため、入力表現と評価仮定の隔たりに注意する。

## pc_GRAB_violate_1

モデル `gpt-4o-mini-2024-07-18`、反復 0、正解 `false`、元分岐 `true`。

入力環境：

```text
The current states in the home are as follows: 
The apple (101) and is INSIDE the kitchen (900).
The fridge (102) is CLOSED and and is INSIDE the kitchen (900).
The lightswitch (103) is OFF and and is INSIDE the kitchen (900).
The kitchentable (104) and is INSIDE the kitchen (900).
You are INSIDE the kitchen (900).
```

候補：`[GRAB] <apple> (101)`

構造化事実：

```json
{
  "states": {
    "101": [],
    "102": [
      "CLOSED"
    ],
    "103": [
      "OFF"
    ],
    "104": []
  },
  "held": [],
  "close": []
}
```

違反条件：You are close to <apple> (101).

生応答：

```text
To determine if the preconditions are satisfied, we need to analyze the current states:

1. You are INSIDE the kitchen (900).
2. The apple (101) is also INSIDE the kitchen (900).
3. There is no information indicating that you are holding the apple (101) in either hand.

Based on this information, we can conclude:

- You are close to the apple (101) since both you and the apple are in the same location (the kitchen).
- The apple (101) is not held in your right hand or left hand.

Since both preconditions are satisfied, the output is:

**Yes**
```

## pc_SWITCHON_violate_1

モデル `gpt-4o-mini-2024-07-18`、反復 0、正解 `false`、元分岐 `true`。

入力環境：

```text
The current states in the home are as follows: 
The apple (101) and is INSIDE the kitchen (900).
The fridge (102) is CLOSED and and is INSIDE the kitchen (900).
The lightswitch (103) is OFF and and is INSIDE the kitchen (900).
The kitchentable (104) and is INSIDE the kitchen (900).
You are INSIDE the kitchen (900).
```

候補：`[SWITCHON] <lightswitch> (103)`

構造化事実：

```json
{
  "states": {
    "101": [],
    "102": [
      "CLOSED"
    ],
    "103": [
      "OFF"
    ],
    "104": []
  },
  "held": [],
  "close": []
}
```

違反条件：You are close to <lightswitch> (103).

生応答：

```text
Yes
```

## pc_SWITCHOFF_violate_1

モデル `gpt-4o-mini-2024-07-18`、反復 0、正解 `false`、元分岐 `true`。

入力環境：

```text
The current states in the home are as follows: 
The apple (101) and is INSIDE the kitchen (900).
The fridge (102) is CLOSED and and is INSIDE the kitchen (900).
The lightswitch (103) is ON and and is INSIDE the kitchen (900).
The kitchentable (104) and is INSIDE the kitchen (900).
You are INSIDE the kitchen (900).
```

候補：`[SWITCHOFF] <lightswitch> (103)`

構造化事実：

```json
{
  "states": {
    "101": [],
    "102": [
      "CLOSED"
    ],
    "103": [
      "ON"
    ],
    "104": []
  },
  "held": [],
  "close": []
}
```

違反条件：You are close to <lightswitch> (103).

生応答：

```text
Yes
```

## pc_OPEN_violate_1

モデル `gpt-4o-mini-2024-07-18`、反復 0、正解 `false`、元分岐 `true`。

入力環境：

```text
The current states in the home are as follows: 
The apple (101) and is INSIDE the kitchen (900).
The fridge (102) is CLOSED and and is INSIDE the kitchen (900).
The lightswitch (103) is OFF and and is INSIDE the kitchen (900).
The kitchentable (104) and is INSIDE the kitchen (900).
You are INSIDE the kitchen (900).
```

候補：`[OPEN] <fridge> (102)`

構造化事実：

```json
{
  "states": {
    "101": [],
    "102": [
      "CLOSED"
    ],
    "103": [
      "OFF"
    ],
    "104": []
  },
  "held": [],
  "close": []
}
```

違反条件：You are close to <fridge> (102).

生応答：

```text
Yes
```

## pc_CLOSE_violate_1

モデル `gpt-4o-mini-2024-07-18`、反復 0、正解 `false`、元分岐 `true`。

入力環境：

```text
The current states in the home are as follows: 
The apple (101) and is INSIDE the kitchen (900).
The fridge (102) is OPEN and and is INSIDE the kitchen (900).
The lightswitch (103) is OFF and and is INSIDE the kitchen (900).
The kitchentable (104) and is INSIDE the kitchen (900).
You are INSIDE the kitchen (900).
```

候補：`[CLOSE] <fridge> (102)`

構造化事実：

```json
{
  "states": {
    "101": [],
    "102": [
      "OPEN"
    ],
    "103": [
      "OFF"
    ],
    "104": []
  },
  "held": [],
  "close": []
}
```

違反条件：You are close to <fridge> (102).

生応答：

```text
Yes
```

## pc_PUT_violate_2

モデル `gpt-4o-mini-2024-07-18`、反復 0、正解 `false`、元分岐 `true`。

入力環境：

```text
The current states in the home are as follows: 
The apple (101) and is INSIDE the kitchen (900).
The fridge (102) is CLOSED and and is INSIDE the kitchen (900).
The lightswitch (103) is OFF and and is INSIDE the kitchen (900).
The kitchentable (104) and is INSIDE the kitchen (900).
You are INSIDE the kitchen (900).
You are holding the apple (101) in your right hand.
```

候補：`[PUT] <apple> (101) <kitchentable> (104)`

構造化事実：

```json
{
  "states": {
    "101": [],
    "102": [
      "CLOSED"
    ],
    "103": [
      "OFF"
    ],
    "104": []
  },
  "held": [
    101
  ],
  "close": []
}
```

違反条件：You are close to <kitchentable> (104).

生応答：

```text
To determine if the preconditions are satisfied, we need to check the following:

1. You are holding the apple (101) in your right hand (which is true).
2. You are close to the kitchentable (104) (which is also true since you are inside the kitchen where the kitchentable is located).

Since both conditions are satisfied, the output is:

**Yes**
```

## end_placement_1

モデル `gpt-4o-mini-2024-07-18`、反復 0、由来 `synthetic`。

タスク：Put all apples in the fridge。正解 `Continue`、元分岐 `End`。

```text
The current states in the home are as follows: 
The apple (101) is INSIDE the fridge (102).
The apple (105) is ON the fridge (102).
The fridge (102) is OPEN.
```

生応答：

```text
End
```

## end_placement_2

モデル `gpt-4o-mini-2024-07-18`、反復 0、由来 `synthetic`。

タスク：Put all apples in the fridge。正解 `Continue`、元分岐 `End`。

```text
The current states in the home are as follows: 
The apple (101) is ON the fridge (102).
The apple (105) is ON the fridge (102).
The fridge (102) is OPEN.
```

生応答：

```text
End
```

