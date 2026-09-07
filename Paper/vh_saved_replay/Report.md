# 過去に保存された行動列の追加再生

予定8件中8件完了。API要求は0件。

| 種別 | ID | モデル | 過去の結果 | 保存長 | 全保存行動再生 | 最終ゴール |
| --- | --- | --- | --- | ---: | --- | --- |
| placement_task | test_task1 | gpt-4o-mini | Execution Failure | 1 | True | False |
| placement_task | test_task1 | gpt-4o | Execution Failure | 4 | True | False |
| placement_task | test_task65 | gpt-4o-mini | Erroneous Terminate | 5 | True | False |
| placement_task | test_task65 | gpt-4o | Success | 10 | True | True |
| state_change_task | test_task1 | gpt-4o-mini | Success | 0 | True | True |
| state_change_task | test_task1 | gpt-4o | Success | 0 | True | True |
| state_change_task | test_task6 | gpt-4o-mini | Success | 5 | True | True |
| state_change_task | test_task6 | gpt-4o | Success | 4 | True | True |

保存列の再生は、過去に失敗した最後の未保存行動を復元するものではない。過去の初期位置・実行環境が未回収のため、現在の固定位置による新しい再生として区別する。
保存列が全実行できても、過去のExecution Failureが再現・否定されたとは解釈しない。途中のVH失敗後には自動修復せず停止する。設定・手順は[README.md](README.md)。
