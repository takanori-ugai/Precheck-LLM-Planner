#!/usr/bin/env python3
"""Export only knowledge functions and explicit synthetic examples from notebook sources."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def notebook_functions(name, names):
    found = {}
    for cell in json.loads((ROOT / name).read_text())['cells']:
        if cell['cell_type'] != 'code':
            continue
        source = ''.join(cell['source'])
        for node in ast.parse(source).body:
            if isinstance(node, ast.FunctionDef) and node.name in names:
                found[node.name] = ast.get_source_segment(source, node)
    if set(found) != set(names):
        raise ValueError('Missing requested notebook function')
    return found


def main():
    names = ['extract_nouns', 'extract_environment_knowledge', 'return_nlp']
    single = notebook_functions('single-prompt.ipynb', names)
    multi = notebook_functions('multi-prompts.ipynb', names)
    for name in names:
        if ast.dump(ast.parse(single[name])) != ast.dump(ast.parse(multi[name])):
            raise ValueError(f'Knowledge function differs between notebooks: {name}')
    folder = ROOT / 'Paper/listings'
    (folder / 'knowledge_extraction.py').write_text(
        '# Extracted from published notebooks; external globals are supplied by the notebooks.\n'
        'room_list = ["bathroom", "bedroom", "kitchen", "livingroom"]\n\n' +
        '\n\n'.join(single.values()) + '\n')
    (folder / 'knowledge_serialization.py').write_text(single['return_nlp'] + '\n')
    # Synthetic nodes use deliberately separate IDs, NOT reconstructed VH scenes.
    state_objects = {9002: {'states': ['OFF'], 'on': None, 'inside': None,
                           'location': 9001, 'hold': []}}
    placement_objects = {
        9012: {'states': [], 'on': 9013, 'inside': None, 'location': 9001, 'hold': []},
        9013: {'states': [], 'on': None, 'inside': None, 'location': 9001, 'hold': [9012]},
        9014: {'states': ['CLOSED'], 'on': None, 'inside': None, 'location': 9001, 'hold': []}}
    agent = {'close_to': [9002], 'hold_rh': None, 'hold_lh': None, 'location': 9001}
    fixture = {'kind': 'synthetic_serialization_example_not_VH_graph_or_experiment_log',
               'object_names': {9001: 'kitchen', 9002: 'lightswitch', 9012: 'plum',
                                9013: 'kitchentable', 9014: 'fridge'},
               'properties': {9002: [], 9012: [], 9013: [], 9014: ['CONTAINERS']},
               'state_objects': state_objects, 'placement_objects': placement_objects,
               'state_agent': agent, 'placement_agent': dict(agent, close_to=[9012, 9013])}
    namespace = {'objId_dic': fixture['object_names'], 'objProp_dic': fixture['properties']}
    # Only the inspected pure serializer is executed; no imports, API or simulator calls.
    exec(compile(single['return_nlp'], 'notebook:return_nlp', 'exec'), namespace)
    for kind in ('state', 'placement'):
        text = namespace['return_nlp'](fixture[kind + '_objects'], fixture[kind + '_agent'])
        (folder / f'knowledge_example_{kind}.txt').write_text(text)
    (folder / 'knowledge_example_inputs.json').write_text(json.dumps(fixture, indent=2) + '\n')
    sources = ['single-prompt.ipynb', 'multi-prompts.ipynb', 'precondition.json']
    sources += [str(p.relative_to(ROOT)) for p in sorted(folder.glob('knowledge_*'))]
    receipt = {'kind': 'static_code_export_and_synthetic_serialization_examples',
               'sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources}}
    target = ROOT / 'Paper/implementation'
    target.mkdir(parents=True, exist_ok=True)
    (target / 'export_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('Exported identical knowledge functions and two explicitly synthetic examples.')


if __name__ == '__main__':
    main()
