"""Build self-contained revision appendices and blank human review, without APIs/VH."""
import argparse
import csv
import hashlib
import io
import json
from collections import defaultdict
from pathlib import Path

from audit_reply_evidence import one, rows
from summarize_vh import graph, read_lines

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / 'Paper'
ANALYSIS = PAPER / 'analysis'
SOURCES = set()


def read(path):
    SOURCES.add(path)
    return path.read_text(encoding='utf-8')


def records(name):
    path = ANALYSIS / (name + '.csv')
    return list(csv.DictReader(io.StringIO(read(path))))


def tex(value):
    return ''.join({'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '_': r'\_',
                    '#': r'\#', '{': r'\{', '}': r'\}', '<': r'\textless{}',
                    '>': r'\textgreater{}', '$': r'\$', '^': r'\textasciicircum{}',
                    '~': r'\textasciitilde{}'}.get(c, c) for c in str(value))


def num(value, percent=False):
    return '--' if value in ('', None) else f'{float(value) * (100 if percent else 1):.3f}'


def table(caption, label, headers, data, spec=None):
    spec = spec or ('l' * len(headers))
    lines = [r'{\scriptsize\setlength{\tabcolsep}{3pt}',
             r'\begin{longtable}{' + spec + '}',
             r'\caption{' + caption + r'}\label{' + label + r'}\\', r'\hline',
             ' & '.join(headers) + r'\\\hline\endfirsthead',
             ' & '.join(headers) + r'\\\hline\endhead', r'\hline\endfoot']
    for row in data:
        assert len(row) == len(headers), (label, row)
        lines.append(' & '.join(map(str, row)) + r' \\')
    return '\n'.join(lines + [r'\end{longtable}}', ''])


def statistics_appendix():
    metrics, lengths = records('metrics'), records('lengths_by_outcome')
    ids = {(r['task_type'], r['method']): f'M{i}' for i, r in enumerate(metrics, 1)}
    mid = lambda r: ids[r['task_type'], r['method']]
    out = [r'''\onecolumn
\section{分布・対応比較・データ網羅の詳細}\label{app:statistics}
本付録の数値は基本性能評価の同じ結果ラベルと記録列から求めた．M1--M18は表\ref{tab:method_dictionary}の条件，S/Fは成功／失敗，E/R/TはExecution Failure／Reaching Maximum Attempts／Erroneous Terminateを表す．SDは標本標準偏差，IQRは第3四分位点と第1四分位点の差で，四分位点はソート後の位置$(n-1)p$を線形補間した．空集合の統計と1件以下のSDは未定義（--）であり，0ではない．
''']
    out.append(table('詳細集計に用いる条件番号', 'tab:method_dictionary',
                     ['番号', 'タスク', '提示', 'モデル', '検証'],
                     [[mid(r), '状態' if r['task_type']=='state_change_task' else '配置',
                       {'baseline':'Baseline','single-prompt':'Single','multi-prompts':'Multi'}[r['prompt']],
                       'mini' if 'mini' in r['model_claimed'] else '4o',
                       {'True':'あり','False':'なし','':'--'}[r['precheck']]] for r in metrics]))
    sf = [r for r in lengths if r['group'] in ('success','failure')]
    out.append(table('成功・失敗別の列長分布', 'tab:length_distribution',
        ['条件','結果','$n$','記録中央値','SD','IQR','参照中央値','SD','IQR'],
        [[mid(r),'S' if r['group']=='success' else 'F',r['n']] +
         [num(r[f'{p}_{s}']) for p in ('executed','reference') for s in ('median','sd_sample','iqr')] for r in sf]))
    out.append(table('失敗類型別の列長', 'tab:failure_lengths',
        ['条件','類型','$n$','記録平均','中央値','SD','IQR','参照平均'],
        [[mid(r),{'Execution Failure':'E','Reaching Maximum Attempts':'R','Erroneous Terminate':'T'}[r['group']],r['n']] +
         [num(r['executed_'+s]) for s in ('mean','median','sd_sample','iqr')] + [num(r['reference_mean'])]
         for r in lengths if r['group'] in ('Execution Failure','Reaching Maximum Attempts','Erroneous Terminate')]))
    out.append(r'''\subsection{参照列との差と比}
差$D=L_{exec}-L_{ref}$は同一IDごとに計算する．比$Q=L_{exec}/L_{ref}$は参照長が正のIDだけを用い，表の$n_Q$を分母とする．状態変化27件・配置2件の参照長0は比から除く．成功・失敗ごとに平均の比ではなく各IDの比を平均する．手法間で成功集合が異なるため，表\ref{tab:common_success_internal}の共通成功集合による比較も併用する．
''')
    out.append(table('同一IDでの列長差と比', 'tab:length_ratios',
        ['条件','結果','$n_D$','D平均','中央値','SD','IQR','$n_Q$','Q平均','中央値','SD','IQR'],
        [[mid(r),'S' if r['group']=='success' else 'F',r['difference_n']] +
         [num(r['difference_'+s]) for s in ('mean','median','sd_sample','iqr')] + [r['ratio_n']] +
         [num(r['ratio_'+s]) for s in ('mean','median','sd_sample','iqr')] for r in sf]))
    out.append(r'''\subsection{タスク名の依存を考慮した成功率}
マクロSRはタスク名ごとのSRを等重み平均する．95\%区間はタスク名をクラスターとして復元抽出し，選んだ名前の全インスタンスを保持した4000回の再標本化の2.5・97.5百分位点である（seed 20260906）．区間内のSRはインスタンス重みであり，マクロSRの区間ではない．検証有無の差では同じIDの成功差を保持して再標本化する．家屋の共有による名前間の依存は除去できず，状態変化の6名では区間推定自体が不安定になり得る．因果効果や独立タスクによる有意差の検定とは解釈しない．
''')
    out.append(table(r'マクロ成功率とタスク名クラスター区間（\%）', 'tab:macro_intervals',
        ['条件','名前数','SR','マクロSR','SR下限','SR上限'],
        [[mid(r),r['task_name_clusters']] + [num(r[s],True) for s in ('SR','task_name_macro_SR','SR_cluster_ci_low','SR_cluster_ci_high')] for r in metrics]))
    pairs = records('precheck_paired_comparison')
    out.append(table('検証なしからありへの対応変化とSR差（percentage points）','tab:paired_intervals',
        ['あり条件','$n$','改善数','悪化数','両成功','両失敗','SR差','下限','上限'],
        [[ids[r['task_type'],f"{r['prompt']}/{r['model']}/precheck"],r['n'],r['gain_n'],r['loss_n'],r['both_success_n'],r['both_failure_n']] +
         [num(r[s]) for s in ('SR_difference_pp','difference_ci_low_pp','difference_ci_high_pp')] for r in pairs]))
    out.append(r'''\subsection{検索類似度と成績の関係}
検索の構成と候補名順序は\ref{app:retrieval_conditions}に従う．表\ref{tab:retrieval_distribution}では名前等重みとインスタンス等重みを区別する．表\ref{tab:retrieval_strata}のO/A/Dは対象クラス／操作／配置先の一致，1/0は一致／不一致を表す．同じ試行を複数軸で分けた記述的集計であり，各行を合算しない．列長差はその行の成功IDのみを分母とする．状態変化には配置先がないためDは解釈対象から外す．空の層は成績表に行を設けていない．
''')
    rr=records('retrieval_summary')
    out.append(table('検索類似度の分布','tab:retrieval_distribution',
        ['タスク','重み','$n$','平均','中央値','Q1','Q3','最小','最大'],
        [['状態' if r['task_type']=='state_change_task' else '配置','名前' if r['weighting']=='task_name' else '事例',r['cosine_n']] +
         [num(r['cosine_'+s]) for s in ('mean','median','q1','q3','min','max')] for r in rr]))
    pr=records('performance_by_retrieval')
    out.append(table('検索類似度・共有構造別の成功率と成功時列長差','tab:retrieval_strata',
        ['条件','層','$n$','成功数',r'SR (\%)','成功時D平均'],
        [[mid(r),tex(r['value']) if r['dimension']=='cosine_bin' else
          {'same_object':'O','same_operation':'A','same_destination':'D'}[r['dimension']] + ('1' if r['value']=='True' else '0'),
          r['n'],r['success_n'],num(r['SR'],True),num(r['success_difference_mean'])] for r in pr
         if not (r['task_type']=='state_change_task' and r['dimension']=='same_destination')]))
    out.append(r'''\subsection{全インスタンスの組合せ網羅表}\label{app:coverage_joint}
指示Nと初期状態Iは後続の辞書に完全に展開する．状態変化の指示はTurn on/off all，配置の指示はPut all ... in/on the ...で，対象・目標状態／配置先を指示辞書から一意に読める．S/Pは状態変化／配置，T/Eはテスト／事例用，部屋B/D/K/Lはbathroom／bedroom／kitchen／livingroomである．ID欄の整数はtest\_taskまたはexample\_taskに続く番号で，各IDの後の文字がinitial\_roomとなる．同一指示・シーン・初期状態の行をまとめただけであり，全618件を重複なく列挙する．物体位置はシーンに依存し，Iはノード状態配列の上書きである．列挙は観測組合せであり，全組合せの設計網羅を主張しない．
''')
    coverage=records('dataset_coverage')
    # Exact task names and IDs come from the inventory, avoiding reverse inflection.
    inv=records('task_inventory')
    names={r['task_name'] for r in inv}
    names={n:f'N{i}' for i,n in enumerate(sorted(names),1)}
    states=sorted({r['initial_states_json'] for r in coverage})
    states={v:f'I{i}' for i,v in enumerate(states,1)}
    index={(r['task_type'],r['split'],r['task_id']):r for r in inv}
    groups=defaultdict(list)
    for r in coverage:
        for task_id in json.loads(r['task_ids']):
            task=index[r['task_type'],r['split'],task_id]
            key=(r['task_type'],r['split'],task['task_name'],int(r['scene']),r['initial_states_json'])
            groups[key].append((task_id, r['initial_room']))
    assert sum(map(len,groups.values()))==618
    out.append(table('タスク指示の辞書','tab:instruction_dictionary',['番号','指示全文'],
        [[i,tex(n)] for n,i in names.items()],r'lp{.85\linewidth}'))
    out.append(table('初期状態の辞書（ID:状態配列）','tab:initial_state_dictionary',['番号','状態上書き'],
        [[i,tex('; '.join(str(x['id'])+':'+','.join(x['states']) for x in json.loads(s)) or '(empty)')] for s,i in states.items()],r'lp{.85\linewidth}'))
    out.append(table('全インスタンスの組合せ（ID:初期部屋）','tab:joint_coverage',
        ['種別','分割','指示','シーン','初期状態','件数','ID:部屋'],
        [['S' if kind=='state_change_task' else 'P','T' if split=='test' else 'E',names[name],scene,states[st],len(items),
          ', '.join(t.split('task')[-1]+':'+{'bathroom':'B','bedroom':'D','kitchen':'K','livingroom':'L'}[room] for t,room in sorted(items))]
         for (kind,split,name,scene,st),items in sorted(groups.items())],r'lllrlrp{.35\linewidth}'))
    return '\n'.join(out)


def source_events(run):
    path=PAPER/'vh_step4/runs'/run/'events.jsonl'
    read(path)
    return path.parent,read_lines(path)


def source_graph(folder,name):
    SOURCES.add(folder/name)
    return graph(folder,name)


def review_material():
    selected=json.loads(read(PAPER/'vh_counterfactual/selection.csv'))
    out=['# 違反説明全文の著者レビュー（再確認用）',
         '対象は `unmet` 応答であり、Yes/Noの判定応答ではありません。review.csv は現在状態との一致で採点した票として保持します。未充足条件としての再確認は Semantic-Review-Guide.md を読み、semantic_review.csv に記入してください。記入状況は検証器の semantic_status.json で確認できます。',
         '## 採点方法',
         '要求への応答として、列挙した条件が本当に未充足か、必要な違反の取りこぼしがないかを確認してください。「Object is OFF」は現在状態の断定ではなく、未充足条件の列挙の場合があります。',
         'ラベル：正しい（列挙と網羅が妥当）／一部正しい（妥当な部分と誤り・欠落がある）／誤り（説明の主要内容が状態・条件と矛盾）／判断不能（提示情報でも判断できない）。根拠に具体的な条件・ID・情報不足を記入してください。',
         'VH実行可能性と条件辞書の充足は別です。下の抽出辞書・グラフ抜粋は参考事実であり、人手の正解ラベルではありません。評価者・日付を全件に記入してください。']
    form=[]
    for i,r in enumerate(selected,1):
        folder,events=source_events(r['run_id']); step=int(r['step'])
        unmet=one(events,'unmet',step); ext=one(events,'extracted_knowledge',step)
        g=source_graph(folder,ext['graph_file']); nodes={n['id']:n for n in g['nodes']}
        import re
        ids={int(x) for x in re.findall(r'\((\d+)\)',r['action'])}|{1}
        edges=[e for e in g['edges'] if
               (e['from_id']==1 and e['to_id'] in ids and e['relation_type'] in ('CLOSE','HOLDS_RH','HOLDS_LH')) or
               (e['from_id'] in ids and e['relation_type'] in ('INSIDE','ON'))]
        relevant=ids|{e['from_id'] for e in edges}|{e['to_id'] for e in edges}
        excerpt={'nodes':[{k:nodes[j].get(k) for k in ('id','class_name','states','properties')} for j in sorted(relevant)],'edges':edges}
        out += [f"## {i}. {r['kind']} / {r['task_id']} / {r['model']} / {r['arm']} / step {step}",
                f"run ID: `{r['run_id']}`",f"候補行動: `{r['action']}`",'### 採点対象：未充足条件の説明全文',
                '```text\n'+unmet['response']+'\n```','### 実際の要求メッセージ全文（role・順序を保持）']
        for role,msg in unmet['messages']:
            out += [f'role: {role}','```text\n'+msg+'\n```']
        out += ['### 判定時点の抽出辞書（補助資料）','```json\n'+json.dumps({'objects':ext['objects'],'agent':ext['agent']},ensure_ascii=False,indent=2)+'\n```',
                '### 候補関連の完全グラフ抜粋（補助資料）','```json\n'+json.dumps(excerpt,ensure_ascii=False,indent=2)+'\n```',
                f"元ログ: `{folder.relative_to(ROOT)}/events.jsonl`、グラフ: `{ext['graph_file']}`。"]
        form.append({'case':i,'run_id':r['run_id'],'step':step,'phase':'unmet','action':r['action'],
                     'unmet_response':unmet['response'],'review_label':'','evidence':'','evaluator':'','date':''})
    stream=io.StringIO(newline=''); writer=csv.DictWriter(stream,fieldnames=list(form[0]));writer.writeheader();writer.writerows(form)
    return '\n\n'.join(out)+'\n',stream.getvalue()


def real_cases():
    out=[r'''\section{実シーンでの入力と行動前後の変化}\label{app:real_inputs}
構成要素比較のC1・GPT-4o・反復0から，状態変化task6と配置task65を固定して示す．結果の良否による選び直しは行わない．これは基本性能評価の未保存入力を復元したものではなく，付録の合成例とも異なる実際の観測である．以下の環境文は最初の終了判定へ送信した全文から末尾の判定指示のみを除いたもので，重複したand等も保持した．
''']
    for kind,task in [('state_change_task','test_task6'),('placement_task','test_task65')]:
        run=f'{kind}_{task}_C1_llm_precheck_gpt-4o-2024-08-06_r0'
        folder,events=source_events(run)
        ext=one(events,'extracted_knowledge',1)
        g=source_graph(folder,ext['graph_file']); nodes={n['id']:n for n in g['nodes']}
        end=next(e for e in events if e['phase']=='termination')
        # The last newline-prefixed completion question is not environment knowledge.
        prompt=end['messages'][-1][1]
        env=prompt.split('\nIf the following task')[0]
        assert env.startswith('The current states')
        out += [r'\subsection{'+('状態変化task6' if kind=='state_change_task' else '配置task65')+'}',
                '人物の初期位置は'+tex(nodes[1]['obj_transform']['position'])+'である．',
                r'\begin{lstlisting}[basicstyle=\ttfamily\scriptsize,breaklines=true,caption={最初の判定へ送信した環境知識全文}]',env,r'\end{lstlisting}']
        objids={int(x) for x in ext['objects']}|{1}
        es=[e for e in g['edges'] if e['from_id'] in objids and e['relation_type'] in ('INSIDE','ON','HOLDS_RH','HOLDS_LH','CLOSE')]
        out.append(table('初期グラフの対象・人物からの関係抜粋','tab:real_edges_'+task,
            ['始点ID','クラス','関係','終点ID','クラス'],
            [[e['from_id'],tex(nodes[e['from_id']]['class_name']),e['relation_type'],e['to_id'],tex(nodes[e['to_id']]['class_name'])] for e in es]))
        trajectory=[]
        for e in events:
            if e['phase']!='execution':continue
            before=source_graph(folder,e['before_graph']); after=source_graph(folder,e['after_graph'])
            a={n['id']:n for n in before['nodes']}; b={n['id']:n for n in after['nodes']}
            changes=[f"{j}: {','.join(a[j]['states'])} -> {','.join(b[j]['states'])}" for j in a.keys()&b.keys() if a[j]['states']!=b[j]['states']]
            def relevant_edges(gr):
                return {(x['from_id'],x['relation_type'],x['to_id']) for x in gr['edges'] if x['relation_type'] in ('ON','INSIDE','HOLDS_RH','HOLDS_LH','CLOSE') and x['from_id'] in objids}
            ae,be=relevant_edges(before),relevant_edges(after)
            changes += ['- '+str(x) for x in sorted(ae-be)]+['+ '+str(x) for x in sorted(be-ae)]
            trajectory.append([e['step'],tex(e['action']),'成功' if e['simulator_result'][0] else '失敗',tex('; '.join(changes) or 'なし')])
        out.append('関係変化の$+$/$-$は追加／削除を表し，対象辞書内の物体と人物を始点とするON・INSIDE・保持・CLOSEに限定する．座標変化そのものや無関係な辺は省略する．')
        out.append(table('行動と状態・関係の変化','tab:real_changes_'+task,
                         ['step','実行行動','VH','変化'],trajectory,r'rp{.28\linewidth}lp{.48\linewidth}'))
    return '\n'.join(out)


def build():
    SOURCES.clear()
    SOURCES.add(Path(__file__))
    review,blank=review_material()
    outputs={PAPER/'appendix-statistics.tex':statistics_appendix(),
             PAPER/'appendix-real-inputs.tex':real_cases(),
             PAPER/'human-unmet-review/Review.md':review,
             PAPER/'human-unmet-review/review_blank.csv':blank}
    manifest={'scope':'offline exports; no new human ratings or VH/API executions',
              'sources':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(SOURCES)}}
    outputs[PAPER/'human-unmet-review/export_manifest.json']=json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'
    return outputs


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    for path,content in build().items():
        if args.check:
            assert path.read_text(encoding='utf-8')==content.replace('\r\n','\n'), str(path)
        else:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding='utf-8')
            if path.name=='review_blank.csv':
                for name in ('review.csv','semantic_review.csv'):
                    editable=path.with_name(name)
                    if not editable.exists():
                        editable.write_text(content,encoding='utf-8')
        print(('checked' if args.check else 'exported'),path.relative_to(ROOT))


if __name__=='__main__':main()
