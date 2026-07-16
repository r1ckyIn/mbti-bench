#!/usr/bin/env python3
"""Full battery runner: 7 models x 15 scenarios x 3 reps = 315 calls.
Order: rep -> scenario -> model (cli-reference.md sec 8). Concurrency: <=2 per
side. Retry/rate-limit per sec 6; calls.jsonl append per task; resume skips
recorded tasks."""
import json, os, re, subprocess, threading, time
from concurrent.futures import ThreadPoolExecutor

WORK = '/Users/Shared/clean-workspace/sandbox/mbti-bench/run-full-01'
RAW = f'{WORK}/raw'
ANS = f'{WORK}/answers'
CALLS = f'{WORK}/calls.jsonl'
SETTINGS = '/Users/Shared/clean-workspace/sandbox/mbti-bench/assets/subject-settings.json'
CODEX_HOME = '/private/tmp/mbti-pilot/codex-home'
SUBJECTS = '/private/tmp/mbti-run/subjects'

MODELS = [
    ('fable5', 'claude-fable-5', 'claude'),
    ('opus4.8', 'claude-opus-4-8', 'claude'),
    ('opus4.6', 'claude-opus-4-6', 'claude'),
    ('sonnet5', 'claude-sonnet-5', 'claude'),
    ('gpt5.5', 'gpt-5.5', 'codex'),
    ('gpt5.6sol', 'gpt-5.6-sol', 'codex'),
    ('gpt5.6terra', 'gpt-5.6-terra', 'codex'),
]
SIDS = ['EI-1', 'EI-2', 'EI-3', 'SN-1', 'SN-2', 'SN-3', 'TF-1', 'TF-2', 'TF-3',
        'JP-1', 'JP-2', 'JP-3', 'CA-1', 'CA-2', 'CA-3']
RL_PAT = re.compile(r'429|rate.?limit|overloaded|usage limit|too many requests|quota exceeded', re.I)

lock = threading.Lock()
state = {'dead': set(), 'final': {}, 'fail_n': {}, 'total_n': {}, 'done_n': 0}


def run_claude(model, scen_file, out_base):
    env = os.environ.copy()
    env.pop('CLAUDECODE', None); env.pop('CLAUDE_CODE_ENTRYPOINT', None)
    cmd = ['claude', '-p', '--model', model, '--output-format', 'stream-json',
           '--verbose', '--strict-mcp-config', '--settings', SETTINGS, '--max-turns', '8']
    t0 = time.time()
    with open(scen_file) as fin, open(out_base + '.jsonl', 'w') as fout, open(out_base + '.stderr', 'w') as ferr:
        try:
            p = subprocess.run(cmd, stdin=fin, stdout=fout, stderr=ferr,
                               cwd=SUBJECTS, env=env, timeout=300)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = 124
    dur = time.time() - t0
    answer, thinking, is_err = '', 0, True
    try:
        for line in open(out_base + '.jsonl'):
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            if e.get('type') == 'assistant':
                for b in e.get('message', {}).get('content', []):
                    if b.get('type') == 'thinking':
                        thinking += 1
            if e.get('type') == 'result':
                is_err = e.get('is_error', True)
                answer = e.get('result') or ''
    except Exception:
        pass
    sb = os.path.getsize(out_base + '.jsonl') if os.path.exists(out_base + '.jsonl') else 0
    err_text = open(out_base + '.stderr').read()[:2000]
    if is_err:
        err_text += ' | result: ' + answer[:500]
    ok = rc == 0 and not is_err and answer.strip() != '' and sb > 0
    return {'ok': ok, 'exit': rc, 'dur': dur, 'answer': answer, 'trace': thinking,
            'stdout_bytes': sb, 'err': err_text}


def run_codex(model, scen_file, out_base):
    env = os.environ.copy()
    env['CODEX_HOME'] = CODEX_HOME
    last = out_base + '.last.txt'
    if os.path.exists(last):
        os.remove(last)
    cmd = ['codex', 'exec', '-m', model, '--skip-git-repo-check', '--sandbox', 'read-only',
           '-C', SUBJECTS, '--json', '--output-last-message', last, '-']
    t0 = time.time()
    with open(scen_file) as fin, open(out_base + '.jsonl', 'w') as fout, open(out_base + '.stderr', 'w') as ferr:
        try:
            p = subprocess.run(cmd, stdin=fin, stdout=fout, stderr=ferr,
                               cwd=SUBJECTS, env=env, timeout=360)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = 124
    dur = time.time() - t0
    answer = open(last).read() if os.path.exists(last) else ''
    sb = os.path.getsize(out_base + '.jsonl') if os.path.exists(out_base + '.jsonl') else 0
    tail = ''
    try:
        tail = open(out_base + '.jsonl').read()[-2000:]
    except Exception:
        pass
    err_text = open(out_base + '.stderr').read()[:2000] + ' | tail: ' + tail
    ok = rc == 0 and answer.strip() != '' and sb > 0
    return {'ok': ok, 'exit': rc, 'dur': dur, 'answer': answer, 'trace': 0,
            'stdout_bytes': sb, 'err': err_text}


def append_call(rec):
    with lock:
        with open(CALLS, 'a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def mark_final(tag, sid, rep, status):
    with lock:
        state['final'][(tag, sid, rep)] = status
        state['total_n'][tag] = state['total_n'].get(tag, 0) + 1
        if status == 'failed':
            state['fail_n'][tag] = state['fail_n'].get(tag, 0) + 1
        state['done_n'] += 1
        n, fn = state['total_n'][tag], state['fail_n'].get(tag, 0)
        if n >= 5 and fn > 0.3 * n and tag not in state['dead']:
            state['dead'].add(tag)
            print(f'!!! MODEL {tag} marked DEAD: {fn}/{n} failed (>30%)', flush=True)
        return state['done_n']


def execute_task(tag, model, side, sid, rep, total):
    with lock:
        if tag in state['dead']:
            skip = True
        else:
            skip = False
    if skip:
        rec = {'model': model, 'tag': tag, 'scenario': sid, 'rep': rep,
               'status': 'skipped_dead_model', 'exit': None, 'stdout_bytes': 0,
               'answer_file': None, 'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        append_call(rec)
        n = mark_final(tag, sid, rep, 'skipped_dead_model')
        print(f'[{n}/{total}] {tag} {sid} r{rep}: SKIPPED (dead model)', flush=True)
        return
    scen_file = f'{WORK}/scenarios/{sid}.txt'
    out_base = f'{RAW}/{tag}__{sid}__r{rep}'
    fn = run_claude if side == 'claude' else run_codex
    attempts_log, rl_rounds, fail_attempts = [], 0, 0
    res = None
    while True:
        res = fn(model, scen_file, out_base)
        attempts_log.append({'exit': res['exit'], 'dur_s': round(res['dur'], 1),
                             'stdout_bytes': res['stdout_bytes'], 'rl': False})
        if res['ok']:
            status = 'ok'
            break
        if RL_PAT.search(res['err'] or ''):
            attempts_log[-1]['rl'] = True
            rl_rounds += 1
            print(f'  {tag} {sid} r{rep}: rate-limited (round {rl_rounds}/3), sleep 900s', flush=True)
            if rl_rounds > 3:
                status = 'failed'
                break
            time.sleep(900)
            continue
        fail_attempts += 1
        if fail_attempts >= 3:
            status = 'failed'
            break
        time.sleep(15)
    open(out_base + '.exit', 'w').write(str(res['exit']))
    ans_file = None
    if status == 'ok':
        ans_file = f'{ANS}/{tag}__{sid}__r{rep}.txt'
        open(ans_file, 'w').write(res['answer'])
    rec = {'model': model, 'tag': tag, 'scenario': sid, 'rep': rep, 'status': status,
           'exit': res['exit'], 'dur_s': round(res['dur'], 1),
           'stdout_bytes': res['stdout_bytes'], 'trace_blocks': res['trace'],
           'attempts': attempts_log, 'rl_rounds': rl_rounds,
           'stderr_head': (res['err'] or '')[:300] if status != 'ok' else '',
           'answer_file': ans_file,
           'raw_file': out_base + ('.jsonl'),
           'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    append_call(rec)
    n = mark_final(tag, sid, rep, status)
    print(f'[{n}/{total}] {tag} {sid} r{rep}: {status} ({res["dur"]:.0f}s, trace={res["trace"]})', flush=True)


def main():
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(ANS, exist_ok=True)
    # resume: skip tasks already recorded (ok / failed / skipped are final)
    done = {}
    if os.path.exists(CALLS):
        for line in open(CALLS):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            key = (r['tag'], r['scenario'], r['rep'])
            done[key] = r['status']
    with lock:
        state['final'].update(done)
        for (tag, sid, rep), st in done.items():
            state['total_n'][tag] = state['total_n'].get(tag, 0) + 1
            if st == 'failed':
                state['fail_n'][tag] = state['fail_n'].get(tag, 0) + 1
    todo_per_rep = {}
    for rep in (1, 2, 3):
        cl, cx = [], []
        for sid in SIDS:
            for tag, model, side in MODELS:
                if (tag, sid, rep) in done:
                    continue
                (cl if side == 'claude' else cx).append((tag, model, side, sid, rep))
        todo_per_rep[rep] = (cl, cx)
    total = len(done) + sum(len(c) + len(x) for c, x in todo_per_rep.values())
    with lock:
        state['done_n'] = len(done)
    print(f'resume: {len(done)} recorded, {total - len(done)} to run', flush=True)

    for rep in (1, 2, 3):
        cl, cx = todo_per_rep[rep]
        if not cl and not cx:
            print(f'=== rep {rep}: nothing to do ===', flush=True)
            continue
        print(f'=== rep {rep}: {len(cl)} claude + {len(cx)} codex calls ===', flush=True)
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=2) as ec, ThreadPoolExecutor(max_workers=2) as ex:
            futs = [ec.submit(execute_task, *t, total) for t in cl]
            futs += [ex.submit(execute_task, *t, total) for t in cx]
            for f in futs:
                f.result()
        print(f'=== rep {rep} complete in {(time.time()-t0)/60:.1f} min ===', flush=True)

    with lock:
        ok_n = sum(1 for s in state['final'].values() if s == 'ok')
        fail_n = sum(1 for s in state['final'].values() if s == 'failed')
        skip_n = sum(1 for s in state['final'].values() if s == 'skipped_dead_model')
    print(f'ALL DONE: ok={ok_n} failed={fail_n} skipped={skip_n} dead_models={sorted(state["dead"])}', flush=True)


if __name__ == '__main__':
    main()
