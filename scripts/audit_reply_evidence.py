"""Audit saved reviewer-response evidence offline; never call VH or an API."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from summarize_vh import graph, read_lines
from vh_fixed_initial import alignment

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'Paper/vh_step4'
REPLAY = ROOT / 'Paper/vh_counterfactual'
OUT = ROOT / 'Paper/reply-evidence'


def rows(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def save_csv(path, records):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def one(events, phase, step):
    matches = [e for e in events if e.get('phase') == phase and e.get('step') == step]
    if len(matches) != 1:
        raise ValueError(f'Expected one {phase} event at step {step}; got {len(matches)}')
    return matches[0]


def main():
    # The historical file has a .csv extension but contains a JSON array.
    selected = json.loads((REPLAY / 'selection.csv').read_text(encoding='utf-8'))
    human_rows = rows(REPLAY / 'human_review_completed.csv')
    human = {(r['run_id'], int(r['step'])): r for r in human_rows}
    keys = {(r['run_id'], int(r['step'])) for r in selected}
    if len(keys) != len(selected) or len(human) != len(human_rows) or keys != human.keys():
        raise ValueError('Selection and human review must have unique, matching run/step keys')
    pool = [r for r in rows(SOURCE / 'precondition_labels.csv')
            if r['stage'] == 'precondition' and r['checker_accepts'] == 'False']
    pool_keys = {(r['run_id'], int(r['step'])) for r in pool}
    if not keys <= pool_keys:
        raise ValueError('Selection contains candidates outside the rejected LLM pool')
    alignments, phases = [], []
    inputs = {Path(__file__), ROOT / 'scripts/vh_fixed_initial.py',
              ROOT / 'scripts/vh_experiment.py', ROOT / 'scripts/summarize_vh.py',
              ROOT / 'scripts/run_representative_counterfactual.py',
              SOURCE / 'precondition_labels.csv', REPLAY / 'selection.csv',
              REPLAY / 'human_review_completed.csv', REPLAY / 'human_review_form.md'}
    for row in selected:
        run_id, step = row['run_id'], int(row['step'])
        src = SOURCE / 'runs' / run_id
        replay = REPLAY / 'runs' / hashlib.sha256(run_id.encode()).hexdigest()[:16]
        events = read_lines(src / 'events.jsonl')
        executions = [e for e in read_lines(replay / 'events.jsonl')
                      if e.get('phase') == 'execution']
        candidate = executions[-1]
        result = json.loads((replay / 'counterfactual.json').read_text(encoding='utf-8'))
        if (candidate['action'] != row['action'] or result['action'] != row['action']
                or result['source_run_id'] != run_id or result['source_step'] != step
                or result['vh_success'] != candidate['simulator_result'][0]):
            raise ValueError(f'Candidate/result mismatch: {run_id}, step {step}')
        source_graph = one(events, 'extracted_knowledge', step)['graph_file']
        # counterfactual.json.before_graph points to the LAST environment_graph
        # request, after execution. Use the execution event's actual before_graph.
        replay_graph = candidate['before_graph']
        check = alignment(graph(src, source_graph), graph(replay, replay_graph))
        alignments.append(dict(
            run_id=run_id, step=step, action=row['action'],
            source_graph=str((src / source_graph).relative_to(ROOT)),
            replay_before_graph=str((replay / replay_graph).relative_to(ROOT)),
            position_tolerance=0.001, quaternion_tolerance=0.0001,
            **check, vh_success=result['vh_success'],
            successful_prefix_length=result['successful_prefix_length']))
        review = human[(run_id, step)]
        precondition = one(events, 'precondition', step)['response']
        unmet = one(events, 'unmet', step)['response']
        if precondition != row['response']:
            raise ValueError(f'Selected response differs from source log: {run_id}')
        phases.append(dict(
            run_id=run_id, step=step, action=row['action'],
            source_events=str((src / 'events.jsonl').relative_to(ROOT)),
            supplied_review_phase='precondition', precondition_response=precondition,
            unmet_response=unmet, unmet_present=bool(unmet.strip()),
            review_label=review['review_label'], evidence=review['evidence'],
            evaluator=review['evaluator'], date=review['date']))
        inputs.update([src / 'events.jsonl', src / source_graph,
                       replay / 'events.jsonl', replay / replay_graph,
                       replay / 'counterfactual.json'])
    if not alignments:
        raise ValueError('No selected candidates')
    OUT.mkdir(parents=True, exist_ok=True)
    save_csv(OUT / 'counterfactual_alignment.csv', alignments)
    save_csv(OUT / 'review_phase_audit.csv', phases)
    summary = dict(
        scope='Offline audit of saved logs; no new VH/API runs or human ratings',
        rejected_llm_candidates=len(pool), selected=len(selected),
        unselected=len(pool) - len(selected),
        selected_by_task=dict(sorted(Counter(f"{r['kind']}/{r['task_id']}"
                                             for r in selected).items())),
        replay_vh_successes=sum(r['vh_success'] for r in alignments),
        symbolic_matches=sum(r['symbolic_equal'] for r in alignments),
        aligned_within_tolerance=sum(r['passed'] for r in alignments),
        human_labels=dict(Counter(r['review_label'] for r in phases)),
        separate_unmet_responses=sum(r['unmet_present'] for r in phases),
        source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sorted(inputs)})
    (OUT / 'verification.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'source_sha256'},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
