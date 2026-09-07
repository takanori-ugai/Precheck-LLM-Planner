"""Validate user-entered unmet reviews without guessing or filling human labels."""
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'Paper/human-unmet-review'
LABELS={'正しい','一部正しい','誤り','判断不能'}


def validate(folder=FOLDER, review_name='review.csv'):
    def read(path):
        with path.open(encoding='utf-8-sig',newline='') as f:
            result=list(csv.DictReader(f))
        for row in result:
            extra=row.pop(None,[])
            if any(x.strip() for x in extra):raise ValueError('Nonempty extra CSV fields')
        return result
    expected=read(folder/'review_blank.csv');actual=read(folder/review_name)
    key=lambda r:(r['run_id'],r['step'])
    if len(actual)!=8 or len({key(r) for r in actual})!=8:
        raise ValueError('Review must contain eight distinct source candidates')
    source={key(r):r for r in expected}
    completed=[];pending=[]
    for row in actual:
        original=source[key(row)]
        for field in ('case','phase','action','unmet_response'):
            if row[field]!=original[field]:raise ValueError(f'Source field changed: case {row["case"]}, {field}')
        if not all(row[f].strip() for f in ('review_label','evidence','evaluator','date')):
            pending.append(row['case']);continue
        if row['review_label'] not in LABELS:raise ValueError('Unknown review label')
        value=row['date'].strip().replace('/','-')
        datetime.strptime(value,'%Y%m%d' if len(value)==8 and value.isdigit() else '%Y-%m-%d')
        completed.append(row)
    return {'target_phase':'unmet','review_file':review_name,
            'validation_scope':'form completeness only; not semantic correctness',
            'completed':len(completed),'pending_cases':pending,
            'labels':dict(Counter(r['review_label'] for r in completed)),
            'complete':len(completed)==8,'human_ratings_generated_by_script':False}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--semantic',action='store_true',help='Validate the separate unmet-condition re-review')
    args=parser.parse_args()
    result=validate(review_name='semantic_review.csv' if args.semantic else 'review.csv')
    (FOLDER/('semantic_status.json' if args.semantic else 'status.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
