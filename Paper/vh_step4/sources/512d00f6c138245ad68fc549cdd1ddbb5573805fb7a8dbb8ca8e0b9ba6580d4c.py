"""Explicit opt-in, resumable bounded API pilot. Never invokes VH or loads notebooks."""
import argparse
import json
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from nonvh_analysis import ROOT, OUT, PROMPT, PC, MODELS, digest, evaluate


def load_key():
    # Read ONLY the user-authorized .env.local. Never source shell code or log it.
    for line in (ROOT / '.env.local').read_text().splitlines():
        key, sep, value = line.strip().removeprefix('export ').partition('=')
        if sep and key.strip() == 'OPENAI_API_KEY':
            value = value.strip().strip('\"\'')
            if value:
                return value
    raise RuntimeError('OPENAI_API_KEY missing in authorized file')


def read_logs():
    path = OUT / 'api_log.jsonl'
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


class Runner:
    def __init__(self, limit):
        self.config = json.loads((OUT / 'config.json').read_text())
        assert digest(OUT / 'cases.json') == self.config['cases_sha256']
        for path, sha in self.config['source_sha256'].items():
            assert digest(ROOT / path) == sha, f'Source changed: {path}'
        self.logs = read_logs()
        self.done = {r['call_id']: r for r in self.logs if r['status'] == 'ok'}
        self.spent = sum(r.get('estimated_usd', r.get('reserved_usd', 0)) for r in self.logs)
        self.limit, self.calls = limit, 0
        self.key = load_key()

    def call(self, model, case_id, phase, repeat, messages):
        call_id = f'{model}/{case_id}/{phase}/{repeat}'
        payload = {'model': model, 'messages': [{'role': role, 'content': content} for role, content in messages],
                   'temperature': 0, 'max_completion_tokens': 160, 'n': 1, 'store': False}
        if call_id in self.done:
            assert self.done[call_id]['request'] == payload, f'Resume input mismatch: {call_id}'
            return self.done[call_id]['text']
        if self.calls >= self.limit:
            raise StopIteration('Per-invocation request cap reached')
        inp, output = self.config['prices_usd_per_million'][model]
        # UTF-8 byte count plus generous chat overhead upper-bounds typical token use.
        reserve = ((len(json.dumps(payload).encode()) + 512) * inp + 160 * output) / 1e6
        if self.spent + reserve > self.config['max_estimated_usd']:
            raise StopIteration('Cumulative estimated cost cap reached')
        log = {'call_id': call_id, 'case_id': case_id, 'phase': phase, 'repeat': repeat,
               'requested_model': model, 'request': payload, 'reserved_usd': reserve,
               'utc': datetime.now(timezone.utc).isoformat(), 'runner_sha256': digest(ROOT / 'scripts/run_nonvh_api.py'),
               'cases_sha256': self.config['cases_sha256']}
        request = urllib.request.Request('https://api.openai.com/v1/chat/completions',
                 data=json.dumps(payload).encode(), headers={'Authorization': 'Bearer ' + self.key,
                                                            'Content-Type': 'application/json'})
        start = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=45, context=ssl.create_default_context()) as response:
                raw = json.loads(response.read())
                request_id = response.headers.get('x-request-id')
            text = raw['choices'][0]['message'].get('content') or ''
            usage = raw['usage']
            cost = (usage['prompt_tokens'] * inp + usage['completion_tokens'] * output) / 1e6
            log.update(status='ok', response=raw, request_id=request_id, text=text, estimated_usd=cost)
            self.spent += cost
        except Exception as exc:
            # Exception messages/bodies can contain secrets. Only safe class/status metadata.
            log.update(status='error', error_type=type(exc).__name__, http_status=getattr(exc, 'code', None))
            self.spent += reserve  # conservatively reserve unknown failed-call billing
        log['elapsed_seconds'] = time.monotonic() - start
        with (OUT / 'api_log.jsonl').open('a') as file:
            file.write(json.dumps(log, ensure_ascii=False) + '\n')
            file.flush()
        self.calls += 1
        print(f'{call_id}: {log["status"]}; cumulative estimate ${self.spent:.5f}', flush=True)
        if log['status'] != 'ok':
            raise RuntimeError(f'API stopped: {log["error_type"]}, HTTP {log["http_status"]}; details redacted')
        self.done[call_id] = log
        return text


def run(limit):
    runner = Runner(limit)
    cases = json.loads((OUT / 'cases.json').read_text())
    for rep in range(3):
        for case in cases:
            for model in MODELS:
                runner.call(model, case['id'], case['kind'], rep, case['messages'])
    tasks = {'WALK': 'Pick up the apple', 'GRAB': 'Pick up the apple',
             'SWITCHON': 'Turn on all lightswitches', 'SWITCHOFF': 'Turn off all lightswitches',
             'OPEN': 'Open the fridge', 'CLOSE': 'Close the fridge',
             'PUT': 'Put the apple on the kitchentable', 'PUTIN': 'Put the apple in the fridge'}
    for case in cases:
        if case.get('variant') != 'violate_1':
            continue
        for model in MODELS:
            conditions = PROMPT.bind_conditions(case['action'], PC)
            check = runner.call(model, case['id'], 'precondition', 0, case['messages'])
            for arm in ['C1_llm_feedback', 'C2_symbolic_feedback', 'C4_neutral_revision']:
                if arm == 'C1_llm_feedback':
                    if 'Yes' in check:
                        continue  # original branch accepts unchanged; scorer accounts for it
                    unmet = runner.call(model, case['id'], 'unmet', 0,
                                        PROMPT.unmet_messages(case['env'], conditions, check))
                    reason = PROMPT.feedback(case['action'], unmet)
                elif arm == 'C2_symbolic_feedback':
                    reason = PROMPT.feedback(case['action'], '\n'.join(case['oracle']['violations']))
                else:
                    reason = 'Review the proposed next action once more using the current status and the task.'
                messages = PROMPT.regeneration_messages('multi', tasks[case['operation']], case['env'], '', [],
                                                       case['action'], reason)
                runner.call(model, case['id'], arm, 0, messages)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true', help='Required explicit live API opt-in')
    parser.add_argument('--limit', type=int, default=2, help='Maximum NEW requests; default two-call smoke test')
    args = parser.parse_args()
    if not args.execute:
        parser.error('Use --execute only after permission to reuse .env.local')
    try:
        run(args.limit)
    except (StopIteration, RuntimeError) as exc:
        print(str(exc))
        raise SystemExit(2)
