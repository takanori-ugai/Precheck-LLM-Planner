"""Run up to twelve precondition-rejected representative candidates in VH, no API."""
import csv, json, gzip, hashlib, time
from pathlib import Path
import vh_step4 as s

ROOT=s.vh.ROOT; OUT=ROOT/'Paper/vh_counterfactual'; SOURCE=ROOT/'Paper/vh_step4'

def load_graph(folder,name):
    with gzip.open(folder/name,'rt') as f:return json.load(f)

def choose():
    rows=list(csv.DictReader((SOURCE/'precondition_labels.csv').open()))
    rows=[r for r in rows if r['stage']=='precondition' and r['checker_accepts']=='False']
    chosen=[]
    for task in ['state_change_task/test_task1','state_change_task/test_task6','placement_task/test_task1','placement_task/test_task65']:
        pool=[r for r in rows if f"{r['kind']}/{r['task_id']}"==task]
        seen=set()
        for r in pool:
            key=(r['model'],r['arm'])
            if key not in seen:
                chosen.append(r); seen.add(key)
                if len([x for x in chosen if f"{x['kind']}/{x['task_id']}"==task])>=3: break
    return chosen[:12]

def run(row):
    rid=row['run_id']; src=SOURCE/'runs'/rid; result=json.loads((src/'result.json').read_text())
    events=[]
    for line in (src/'events.jsonl').read_text().splitlines():
        e=json.loads(line)
        if e.get('phase')=='execution' and e['simulator_result'][0]: events.append(e['action'])
    before=[e for e in json.loads('\n'.join([]))] if False else None
    target_step=int(row['step']); prefix=events[:target_step-1]
    folder=OUT/'runs'/hashlib.sha256(rid.encode()).hexdigest()[:16]; folder.mkdir(parents=True,exist_ok=True)
    cfg=json.loads((SOURCE/'config.json').read_text()); ep=s.Episode(cfg,row['kind'],row['task_id'],'counterfactual',row['model'],int(result['repeat']),None)
    ep.folder=folder; ep.comm=s.vh.connect(cfg['host'],cfg['port'],folder); ep.knowledge.comm=ep.comm
    ep.initialize(ep.task['scene'],ep.task['initial_room'],ep.task['initial_states'])
    for action in prefix:
        if not ep.execute(['<char0> '+action]): raise RuntimeError('prefix execution failed')
    start=ep.comm.environment_graph()[1]; ok=ep.execute(['<char0> '+row['action']]); end=ep.comm.environment_graph()[1]
    s.vh.write(folder/'counterfactual.json',dict(source_run_id=rid,source_step=target_step,source_label=row['checker_accepts'],action=row['action'],vh_success=ok,initial_graph=ep.initial['graph_file'],before_graph=ep.comm.last_path,goal_after=s.vh.goal(end,ep.task),successful_prefix_length=len(prefix),utc=s.vh.utc(),api_requests=0))
    return ok

def main():
    OUT.mkdir(exist_ok=True); chosen=choose(); s.vh.write(OUT/'selection.csv',chosen)
    rows=[]
    for r in chosen:
        rows.append(dict(run_id=r['run_id'],kind=r['kind'],task_id=r['task_id'],model=r['model'],arm=r['arm'],step=r['step'],action=r['action'],selection_reason='precondition rejected',vh_success=run(r)))
    with (OUT/'results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    s.vh.write(OUT/'completion.json',dict(planned=12,selected=len(chosen),completed=len(rows),api_requests=0,vh_successes=sum(x['vh_success'] for x in rows),unselected_rejected_candidates='reported by count in source precondition_labels.csv'))
    print(f'counterfactual representative runs: {len(rows)}; VH success {sum(x["vh_success"] for x in rows)}; API 0')
if __name__=='__main__':main()
