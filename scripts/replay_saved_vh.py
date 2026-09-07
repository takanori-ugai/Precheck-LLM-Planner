"""Replay stored Multi action prefixes without LLM calls; never reconstruct missing failed actions."""
import argparse
import copy
import json
import shutil
import time
from pathlib import Path

import vh_step4 as s

OUT = s.vh.ROOT / 'Paper/vh_saved_replay'


def prepare():
    config = copy.deepcopy(json.loads((s.REFERENCE / 'config.json').read_text()))
    config['design'] = 'eight_saved_multi_prefix_replays_four_tasks_two_models_no_API'
    config['selected_tasks'] = s.vh.SELECTED
    config['repeats'] = 1
    config['max_estimated_usd'] = 0
    config['runner_sha256'] = s.vh.digest(Path(__file__))
    config['helper_sha256'] = s.vh.digest(Path(s.__file__))
    config['notes'] = ['Replay saved successful-action prefix only; missing final failed action cannot be recovered',
        'Fixed positions from previous pilot, not known historical positions',
        'No action rewriting, model call, planner, termination model, or success-rate reproduction claim',
        'All stored commands attempted in sequence until first returned VH failure; graph goals scored independently']
    for kind, _ in s.vh.SELECTED:
        for model in ['gpt-4o-mini', 'gpt-4o']:
            path = s.vh.ROOT / f'result/{kind}/result_multi-prompts_{model}.json'
            config['source_sha256'][str(path.relative_to(s.vh.ROOT))] = s.vh.digest(path)
    path = OUT / 'config.json'
    if path.exists():
        assert json.loads(path.read_text()) == json.loads(json.dumps(config))
    else:
        s.vh.write(path, config)
        for p in [Path(__file__), Path(s.__file__), Path(s.vh.__file__)]:
            target = OUT / 'sources' / f'{s.vh.digest(p)}.py'
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(p, target)
    return config


def replay(config, kind, task_id, model):
    source = s.vh.ROOT / f'result/{kind}/result_multi-prompts_{model}.json'
    stored = json.loads(source.read_text())[task_id]
    episode = s.Episode(config, kind, task_id, 'saved_replay', model, 0, None)
    result_path = episode.folder / 'result.json'
    if result_path.exists():
        return json.loads(result_path.read_text())
    if episode.folder.exists() and any(episode.folder.iterdir()):
        raise RuntimeError('Incomplete saved replay preserved; investigate before restarting')
    episode.comm = s.vh.connect(config['host'], config['port'], episode.folder)
    episode.knowledge.comm = episode.comm
    start = time.monotonic()
    try:
        episode.initialize(episode.task['scene'], episode.task['initial_room'], episode.task['initial_states'])
        episode.log('historical_source', path=str(source.relative_to(s.vh.ROOT)), sha256=s.vh.digest(source), stored=stored)
        for command in stored['action script']:
            if not episode.execute(['<char0> ' + command]):
                break
        final = episode.comm.environment_graph()[1]
        result = dict(run_id=episode.run_id, kind=kind, task_id=task_id, model=model,
            original_result=stored['result'], original_saved_length=len(stored['action script']),
            historical_prefix_replayed_in_full=len(episode.actions) == len(stored['action script']),
            execution_attempts=episode.execution_attempts, successful_actions=episode.actions,
            initial=episode.initial, final_goal=s.vh.goal(final, episode.task), final_graph=episode.comm.last_path,
            elapsed_seconds=time.monotonic() - start, utc=s.vh.utc(), runner_sha256=s.vh.digest(Path(__file__)),
            config_sha256=s.vh.digest(OUT / 'config.json'), api_requests=0)
        s.vh.write(result_path, result)
        print(f'{episode.run_id}: prefix={result["historical_prefix_replayed_in_full"]}, goal={result["final_goal"]["all_satisfied"]}', flush=True)
        return result
    except Exception as exc:
        s.vh.write(episode.folder / 'infrastructure_error.json', dict(utc=s.vh.utc(), error_type=type(exc).__name__))
        raise


def report():
    import csv
    from summarize_vh import graph, read_lines
    rows = []
    for path in sorted((OUT / 'runs').glob('*/result.json')):
        result = json.loads(path.read_text())
        task = json.loads((s.vh.ROOT / f'dataset/{result["kind"]}/test.json').read_text())[result['task_id']]
        assert s.vh.goal(graph(path.parent, result['final_graph']), task) == result['final_goal']
        executions = [e for e in read_lines(path.parent / 'events.jsonl') if e['phase'] == 'execution']
        assert [e['action'] for e in executions if e['simulator_result'][0]] == result['successful_actions']
        rows.append({k: result[k] for k in ['run_id', 'kind', 'task_id', 'model', 'original_result',
            'original_saved_length', 'historical_prefix_replayed_in_full', 'execution_attempts']} |
            {'successful_actions': len(result['successful_actions']), 'final_goal': result['final_goal']['all_satisfied']})
    if rows:
        with (OUT / 'replays.csv').open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    s.vh.write(OUT / 'completion.json', dict(planned=8, completed=len(rows), api_requests=0,
        fully_replayed_prefixes=sum(r['historical_prefix_replayed_in_full'] for r in rows),
        final_goal_satisfied=sum(r['final_goal'] for r in rows)))
    lines = ['# 過去に保存された行動列の追加再生', '', f'予定8件中{len(rows)}件完了。API要求は0件。', '',
        '| 種別 | ID | モデル | 過去の結果 | 保存長 | 全保存行動再生 | 最終ゴール |',
        '| --- | --- | --- | --- | ---: | --- | --- |']
    lines += [f'| {r["kind"]} | {r["task_id"]} | {r["model"]} | {r["original_result"]} | {r["original_saved_length"]} | {r["historical_prefix_replayed_in_full"]} | {r["final_goal"]} |' for r in rows]
    lines += ['', '保存列の再生は、過去に失敗した最後の未保存行動を復元するものではない。過去の初期位置・実行環境が未回収のため、現在の固定位置による新しい再生として区別する。',
        '保存列が全実行できても、過去のExecution Failureが再現・否定されたとは解釈しない。途中のVH失敗後には自動修復せず停止する。設定・手順は[README.md](README.md)。']
    (OUT / 'Report.md').write_text('\n'.join(lines) + '\n')
    print(f'Saved replay: {len(rows)}/8 complete; no API')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['prepare', 'run', 'summary'], required=True)
    args = parser.parse_args()
    s.OUT = s.vh.OUT = OUT
    if args.phase == 'summary':
        report()
        return
    config = prepare()
    if args.phase == 'run':
        for kind, task_id in s.vh.SELECTED:
            for model in ['gpt-4o-mini', 'gpt-4o']:
                replay(config, kind, task_id, model)
        report()


if __name__ == '__main__':
    main()
