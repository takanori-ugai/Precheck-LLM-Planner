"""Bounded VH-only state-restoration diagnostic; no model/API or source-log writes."""
import argparse
import copy
import csv
import hashlib
import json
import time
from pathlib import Path

import vh_step4 as s
from audit_reply_evidence import one
from summarize_vh import graph, read_lines

ROOT=s.vh.ROOT
SOURCE=ROOT/'Paper/vh_step4'
OUT=ROOT/'Paper/vh_aligned_replay'


def matched_execution(comm, expected, action, prefix, log):
    """The last RPC before render is the recorded, gated observation itself."""
    before=comm.environment_graph()[1]
    before_path=comm.last_path
    check=s.alignment(expected,before)
    log('candidate_gate',before_graph=before_path,**check)
    if not check['passed']:
        return {'status':'state_not_restored','candidate_executed':False,'alignment':check,
                'before_graph':before_path}
    reply=comm.render_script(['<char0> '+action],find_solution=False,recording=True,
                             camera_mode=['PERSON_FROM_BACK'],file_name_prefix=prefix)
    after=comm.environment_graph()[1]
    log('candidate_execution',action=action,before_graph=before_path,
        after_graph=comm.last_path,simulator_result=reply)
    return {'status':'executed','candidate_executed':True,'alignment':check,
            'before_graph':before_path,'after_graph':comm.last_path,'vh_success':reply[0]}


def run(row,config):
    run_id,step=row['run_id'],int(row['step'])
    key=hashlib.sha256(f'{run_id}/{step}'.encode()).hexdigest()[:16]
    folder=OUT/'runs'/key
    target=folder/'result.json'
    if target.exists():return json.loads(target.read_text())
    if folder.exists() and any(folder.iterdir()):
        raise RuntimeError('Incomplete run preserved; explicit review required before retry')
    folder.mkdir(parents=True,exist_ok=True)
    events=read_lines(SOURCE/'runs'/run_id/'events.jsonl')
    decision=one(events,'extracted_knowledge',step)
    expected=graph(SOURCE/'runs'/run_id,decision['graph_file'])
    # Event position, rather than step-1, defines the exact prior execution prefix.
    prior=events[:events.index(decision)]
    prefix=[e['action'] for e in prior if e.get('phase')=='execution' and e['simulator_result'][0]]
    assert not any(e.get('phase')=='execution' and not e['simulator_result'][0] for e in prior)
    result={'run_id':run_id,'step':step,'action':row['action'],'api_requests':0,
            'expected_graph':str((SOURCE/'runs'/run_id/decision['graph_file']).relative_to(ROOT)),
            'prefix':prefix,'candidate_executed':False,'restoration_attempted':False}
    ep=s.Episode(config,row['kind'],row['task_id'],'alignment_replay',row['model'],0,None)
    ep.folder=folder
    ep.comm=s.vh.connect(config['host'],config['port'],folder);ep.knowledge.comm=ep.comm
    try:
        ep.initialize(ep.task['scene'],ep.task['initial_room'],ep.task['initial_states'])
        for action in prefix:
            if not ep.execute(['<char0> '+action]):
                result['status']='prefix_execution_failed'
                s.vh.write(target,result);return result
        observed=ep.comm.environment_graph()[1]
        check=s.alignment(expected,observed)
        ep.log('prefix_alignment',expected_graph=result['expected_graph'],**check)
        if not check['passed']:
            result['restoration_attempted']=True
            # Bounded attempt to transfer the graph, including transforms. Unity
            # may not restore all hidden state; never infer success from its ACK.
            reply=ep.comm.expand_scene(copy.deepcopy(expected),randomize=False,
                                       animate_character=False,transfer_transform=True)
            ep.log('restore_graph',simulator_result=reply,
                   expected_graph=result['expected_graph'])
            result['restore_reply_success']=reply[0]
            if not reply[0]:
                result['status']='restore_request_failed'
                s.vh.write(target,result);return result
        outcome=matched_execution(ep.comm,expected,row['action'],
                                  'val_'+key+'_'+str(time.time_ns())[-7:],ep.log)
        result.update(outcome)
    except Exception as exc:
        result.update(status='infrastructure_or_initialization_error',error_type=type(exc).__name__,error=str(exc))
        s.vh.write(target,result)
        raise
    s.vh.write(target,result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true');args=parser.parse_args()
    selected=json.loads((ROOT/'Paper/vh_counterfactual/selection.csv').read_text())
    config=json.loads((SOURCE/'config.json').read_text())
    OUT.mkdir(parents=True,exist_ok=True)
    protocol={'selected':len(selected),'unselected':51,'source_candidates':59,
              'position_tolerance':0.001,'quaternion_tolerance':0.0001,'api_requests':0,
              'policy':'Replay successful prefix; at most one expand_scene transfer if unequal; gate immediately before candidate; no retries; original trajectories unchanged',
              'script_sha256':s.vh.digest(Path(__file__)),
              'selection_sha256':s.vh.digest(ROOT/'Paper/vh_counterfactual/selection.csv')}
    p=OUT/'protocol.json'
    if p.exists():assert json.loads(p.read_text())==protocol,'Frozen protocol changed'
    else:s.vh.write(p,protocol)
    if not args.run:return
    try:
        for row in selected:
            result=run(row,config)
            print(row['run_id'],row['step'],result['status'],flush=True)
    finally:
        results=[json.loads(p.read_text()) for p in sorted((OUT/'runs').glob('*/result.json'))]
        summary={'selected':len(selected),'recorded':len(results),
                 'executed_aligned':sum(r['candidate_executed'] for r in results),
                 'vh_successes':sum(r.get('vh_success') is True for r in results),
                 'unselected':51,'api_requests':0,
                 'status_counts':{status:sum(r['status']==status for r in results) for status in sorted({r['status'] for r in results})}}
        s.vh.write(OUT/'summary.json',summary)
        s.vh.write(OUT/'results.json',results)
        print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
