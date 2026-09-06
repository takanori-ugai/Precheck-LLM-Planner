# 掲載候補：保存行動列から確認できる事例

目的に沿って選んだ事例であり、無作為標本ではない。原因を断定するには追加ログが必要。

## state_change_task / test_task6

Listing 6に対応する成功例。手法：multi-prompts/gpt-4o/precheck。結果：Success。

指示：Turn on all lightswitches。参照長 4、保存実行長 4。

```json
{
  "initial_states": [
    {
      "id": 71,
      "states": [
        "ON"
      ]
    },
    {
      "id": 173,
      "states": [
        "OFF"
      ]
    },
    {
      "id": 261,
      "states": [
        "ON"
      ]
    },
    {
      "id": 427,
      "states": [
        "OFF"
      ]
    }
  ],
  "goal_states": [
    {
      "id": 71,
      "states": [
        "ON"
      ]
    },
    {
      "id": 173,
      "states": [
        "ON"
      ]
    },
    {
      "id": 261,
      "states": [
        "ON"
      ]
    },
    {
      "id": 427,
      "states": [
        "ON"
      ]
    }
  ],
  "reference_actions": [
    "[WALK] <lightswitch> (173)",
    "[SWITCHON] <lightswitch> (173)",
    "[WALK] <lightswitch> (427)",
    "[SWITCHON] <lightswitch> (427)"
  ],
  "actions": [
    "[WALK] <lightswitch> (173)",
    "[SWITCHON] <lightswitch> (173)",
    "[WALK] <lightswitch> (427)",
    "[SWITCHON] <lightswitch> (427)"
  ]
}
```

## placement_task / test_task65

Listing 7との参照列差・閉鎖不要の例。手法：multi-prompts/gpt-4o/precheck。結果：Success。

指示：Put all plums in the fridge。参照長 9、保存実行長 10。

```json
{
  "initial_states": [
    {
      "id": 103,
      "states": [
        "CLOSED"
      ]
    }
  ],
  "goal_states": [
    {
      "from_id": 53,
      "to_id": 103,
      "relation_type": "INSIDE"
    },
    {
      "from_id": 54,
      "to_id": 103,
      "relation_type": "INSIDE"
    }
  ],
  "reference_actions": [
    "[WALK] <plum> (53)",
    "[GRAB] <plum> (53)",
    "[WALK] <fridge> (103)",
    "[OPEN] <fridge> (103)",
    "[PUTIN] <plum> (53) <fridge> (103)",
    "[WALK] <plum> (54)",
    "[GRAB] <plum> (54)",
    "[WALK] <fridge> (103)",
    "[PUTIN] <plum> (54) <fridge> (103)"
  ],
  "actions": [
    "[WALK] <kitchen> (11)",
    "[WALK] <fridge> (103)",
    "[OPEN] <fridge> (103)",
    "[WALK] <plum> (53)",
    "[GRAB] <plum> (53)",
    "[WALK] <fridge> (103)",
    "[PUTIN] <plum> (53) <fridge> (103)",
    "[WALK] <plum> (54)",
    "[GRAB] <plum> (54)",
    "[PUTIN] <plum> (54) <fridge> (103)"
  ]
}
```

## placement_task / test_task2

成功しても同じ行動を反復する例。手法：multi-prompts/gpt-4o/precheck。結果：Success。

指示：Put all bananas on the kitchencounter。参照長 12、保存実行長 17。

```json
{
  "initial_states": [],
  "goal_states": [
    {
      "from_id": 315,
      "to_id": 238,
      "relation_type": "ON"
    },
    {
      "from_id": 316,
      "to_id": 238,
      "relation_type": "ON"
    },
    {
      "from_id": 439,
      "to_id": 238,
      "relation_type": "ON"
    }
  ],
  "reference_actions": [
    "[WALK] <bananas> (315)",
    "[GRAB] <bananas> (315)",
    "[WALK] <kitchencounter> (238)",
    "[PUT] <bananas> (315) <kitchencounter> (238)",
    "[WALK] <bananas> (316)",
    "[GRAB] <bananas> (316)",
    "[WALK] <kitchencounter> (238)",
    "[PUT] <bananas> (316) <kitchencounter> (238)",
    "[WALK] <bananas> (439)",
    "[GRAB] <bananas> (439)",
    "[WALK] <kitchencounter> (238)",
    "[PUT] <bananas> (439) <kitchencounter> (238)"
  ],
  "actions": [
    "[WALK] <dishbowl> (445)",
    "[GRAB] <bananas> (439)",
    "[WALK] <kitchencounter> (238)",
    "[PUT] <bananas> (439) <kitchencounter> (238)",
    "[WALK] <bookshelf> (249)",
    "[GRAB] <bananas> (315)",
    "[WALK] <kitchencounter> (238)",
    "[PUT] <bananas> (315) <kitchencounter> (238)",
    "[GRAB] <bananas> (315)",
    "[PUT] <bananas> (315) <kitchencounter> (238)",
    "[GRAB] <bananas> (439)",
    "[PUT] <bananas> (439) <kitchencounter> (238)",
    "[GRAB] <bananas> (315)",
    "[PUT] <bananas> (315) <kitchencounter> (238)",
    "[WALK] <bookshelf> (249)",
    "[GRAB] <bananas> (316)",
    "[PUT] <bananas> (316) <kitchencounter> (238)"
  ]
}
```

## placement_task / test_task3

未操作ゴールIDを含むETFR例。手法：multi-prompts/gpt-4o/precheck。結果：Erroneous Terminate。

指示：Put all bellpeppers on the kitchentable。参照長 24、保存実行長 41。

```json
{
  "initial_states": [],
  "goal_states": [
    {
      "from_id": 320,
      "to_id": 231,
      "relation_type": "ON"
    },
    {
      "from_id": 321,
      "to_id": 231,
      "relation_type": "ON"
    },
    {
      "from_id": 322,
      "to_id": 231,
      "relation_type": "ON"
    },
    {
      "from_id": 323,
      "to_id": 231,
      "relation_type": "ON"
    },
    {
      "from_id": 324,
      "to_id": 231,
      "relation_type": "ON"
    },
    {
      "from_id": 325,
      "to_id": 231,
      "relation_type": "ON"
    }
  ],
  "reference_actions": [
    "[WALK] <bellpepper> (320)",
    "[GRAB] <bellpepper> (320)",
    "[WALK] <kitchentable> (231)",
    "[PUT] <bellpepper> (320) <kitchentable> (231)",
    "[WALK] <bellpepper> (321)",
    "[GRAB] <bellpepper> (321)",
    "[WALK] <kitchentable> (231)",
    "[PUT] <bellpepper> (321) <kitchentable> (231)",
    "[WALK] <bellpepper> (322)",
    "[GRAB] <bellpepper> (322)",
    "[WALK] <kitchentable> (231)",
    "[PUT] <bellpepper> (322) <kitchentable> (231)",
    "[WALK] <bellpepper> (323)",
    "[GRAB] <bellpepper> (323)",
    "[WALK] <kitchentable> (231)",
    "[PUT] <bellpepper> (323) <kitchentable> (231)",
    "[WALK] <bellpepper> (324)",
    "[GRAB] <bellpepper> (324)",
    "[WALK] <kitchentable> (231)",
    "[PUT] <bellpepper> (324) <kitchentable> (231)",
    "[WALK] <bellpepper> (325)",
    "[GRAB] <bellpepper> (325)",
    "[WALK] <kitchentable> (231)",
    "[PUT] <bellpepper> (325) <kitchentable> (231)"
  ],
  "actions": [
    "[WALK] <kitchencounterdrawer> (244)",
    "[GRAB] <bellpepper> (320)",
    "[WALK] <kitchentable> (231)",
    "[PUT] <bellpepper> (320) <kitchentable> (231)",
    "[WALK] <kitchencounterdrawer> (244)",
    "[GRAB] <bellpepper> (321)",
    "[WALK] <kitchentable> (231)",
    "[PUT] <bellpepper> (321) <kitchentable> (231)",
    "[WALK] <kitchencounter> (238)",
    "[OPEN] <kitchencounter> (238)",
    "[GRAB] <bellpepper> (322)",
    "[WALK] <kitchentable> (231)",
    "[PUT] <bellpepper> (322) <kitchentable> (231)",
    "[GRAB] <bellpepper> (322)",
    "[PUT] <bellpepper> (322) <kitchentable> (231)",
    "[GRAB] <bellpepper> (322)",
    "[PUT] <bellpepper> (322) <kitchentable> (231)",
    "[GRAB] <bellpepper> (322)",
    "[PUT] <bellpepper> (322) <kitchentable> (231)",
    "[GRAB] <bellpepper> (322)",
    "[PUT] <bellpepper> (322) <kitchentable> (231)",
    "[GRAB] <bellpepper> (320)",
    "[PUT] <bellpepper> (320) <kitchentable> (231)",
    "[GRAB] <bellpepper> (320)",
    "[PUT] <bellpepper> (320) <kitchentable> (231)",
    "[GRAB] <bellpepper> (320)",
    "[PUT] <bellpepper> (320) <kitchentable> (231)",
    "[GRAB] <bellpepper> (320)",
    "[PUT] <bellpepper> (320) <kitchentable> (231)",
    "[GRAB] <bellpepper> (320)",
    "[PUT] <bellpepper> (320) <kitchentable> (231)",
    "[GRAB] <bellpepper> (320)",
    "[PUT] <bellpepper> (320) <kitchentable> (231)",
    "[GRAB] <bellpepper> (320)",
    "[PUT] <bellpepper> (320) <kitchentable> (231)",
    "[WALK] <kitchencounterdrawer> (244)",
    "[GRAB] <bellpepper> (323)",
    "[WALK] <kitchentable> (231)",
    "[PUT] <bellpepper> (323) <kitchentable> (231)",
    "[GRAB] <bellpepper> (323)",
    "[PUT] <bellpepper> (323) <kitchentable> (231)"
  ]
}
```

## placement_task / test_task1

実行失敗だが失敗アクションが保存されていない例。手法：multi-prompts/gpt-4o/precheck。結果：Execution Failure。

指示：Put all cupcakes on the kitchencounter。参照長 8、保存実行長 4。

```json
{
  "initial_states": [],
  "goal_states": [
    {
      "from_id": 195,
      "to_id": 238,
      "relation_type": "ON"
    },
    {
      "from_id": 196,
      "to_id": 238,
      "relation_type": "ON"
    }
  ],
  "reference_actions": [
    "[WALK] <cupcake> (195)",
    "[GRAB] <cupcake> (195)",
    "[WALK] <kitchencounter> (238)",
    "[PUT] <cupcake> (195) <kitchencounter> (238)",
    "[WALK] <cupcake> (196)",
    "[GRAB] <cupcake> (196)",
    "[WALK] <kitchencounter> (238)",
    "[PUT] <cupcake> (196) <kitchencounter> (238)"
  ],
  "actions": [
    "[WALK] <bedroom> (73)",
    "[GRAB] <cupcake> (195)",
    "[WALK] <kitchencounter> (238)",
    "[OPEN] <kitchencounter> (238)"
  ]
}
```

## placement_task / test_task4

ゼロ参照列で終了判定に失敗した例。手法：multi-prompts/gpt-4o/precheck。結果：Reaching Maximum Attempts。

指示：Put all bellpeppers on the kitchencounter。参照長 0、保存実行長 0。

```json
{
  "initial_states": [],
  "goal_states": [
    {
      "from_id": 320,
      "to_id": 238,
      "relation_type": "ON"
    },
    {
      "from_id": 321,
      "to_id": 238,
      "relation_type": "ON"
    },
    {
      "from_id": 322,
      "to_id": 238,
      "relation_type": "ON"
    },
    {
      "from_id": 323,
      "to_id": 238,
      "relation_type": "ON"
    },
    {
      "from_id": 324,
      "to_id": 238,
      "relation_type": "ON"
    },
    {
      "from_id": 325,
      "to_id": 238,
      "relation_type": "ON"
    }
  ],
  "reference_actions": [],
  "actions": []
}
```
