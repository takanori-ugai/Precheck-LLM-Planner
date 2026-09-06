#!/usr/bin/env python3
"""Reconstruct notebook retrieval with local MiniLM weights; no API/network calls."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('Paper/analysis/retrieval_scores.json'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.output = args.output.resolve()
    if not args.output.is_relative_to(root / 'Paper' / 'analysis'):
        parser.error('output must be inside Paper/analysis (derived artifacts only)')
    model_dir = args.model_dir.resolve()
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    from sentence_transformers import SentenceTransformer, util
    import torch

    torch.set_num_threads(2)
    torch.manual_seed(0)
    model = SentenceTransformer(str(model_dir), device='cpu', local_files_only=True)
    source_paths = sorted((root / 'dataset').glob('*/*.json'))
    source_paths += [root / name for name in ('single-prompt.ipynb', 'multi-prompts.ipynb')]
    metadata = {
        'kind': 'new_offline_reconstruction_not_historical_retrieval_log',
        'model_id': 'sentence-transformers/all-MiniLM-L6-v2',
        'model_revision': model_dir.name,
        'model_files_sha256': {
            str(p.relative_to(model_dir)): sha256(p)
            for p in sorted(model_dir.rglob('*')) if p.is_file()
        },
        'source_sha256': {str(p.relative_to(root)): sha256(p) for p in source_paths},
        'versions': {k: importlib.metadata.version(k) for k in
                     ('sentence-transformers', 'transformers', 'torch', 'numpy')},
        'device': 'cpu', 'encode_batch_size': 1,
        'tie_rule': 'descending cosine; lexical task name on exact ties',
        'historical_limitation': 'Original model revision, dependency runtime and set order were not logged.',
    }
    pairs = []
    for kind in ('state_change_task', 'placement_task'):
        datasets = {split: json.loads((root / 'dataset' / kind / f'{split}.json').read_text())
                    for split in ('test', 'example')}
        names = {split: sorted({t['task'] for t in data.values()})
                 for split, data in datasets.items()}
        # Same sentence encoder and cosine operation as notebook cell 10.
        candidates = model.encode(names['example'], batch_size=1, show_progress_bar=False)
        for name in names['test']:
            scores = util.cos_sim(model.encode(name, show_progress_bar=False), candidates)[0]
            for candidate, score in zip(names['example'], scores.tolist()):
                pairs.append({'task_type': kind, 'test_task_name': name,
                              'example_task_name': candidate, 'cosine': score})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'metadata': metadata, 'pairs': pairs}, ensure_ascii=False, indent=2) + '\n')
    print(f'Wrote {len(pairs)} candidate similarities to {args.output}')


if __name__ == '__main__':
    main()
