#!/usr/bin/env python3
"""Pilot battery runner: one model, all 15 scenarios, rep 1. Implements the
cli-reference.md protocol: success criteria, 2 retries with backoff, calls.jsonl."""
import argparse, glob, json, os, subprocess, time

ROOT = '/private/tmp/mbti-pilot'
SUBJECTS = f'{ROOT}/subjects'
SETTINGS = f'{ROOT}/subject-settings.json'

def run_claude(model, scen_file, out_base):
    env = os.environ.copy()
    env.pop('CLAUDECODE', None); env.pop('CLAUDE_CODE_ENTRYPOINT', None)
    cmd = ['claude', '-p', '--model', model, '--output-format', 'stream-json',
           '--verbose', '--strict-mcp-config', '--settings', SETTINGS, '--max-turns', '8']
    with open(scen_file) as fin, open(out_base+'.jsonl','w') as fout, open(out_base+'.stderr','w') as ferr:
        t0 = time.time()
        try:
            p = subprocess.run(cmd, stdin=fin, stdout=fout, stderr=ferr, cwd=SUBJECTS, env=env, timeout=300)
            exit_code = p.returncode
        except subprocess.TimeoutExpired:
            exit_code = 124
        dur = time.time() - t0
    answer, thinking, is_err = '', 0, True
    try:
        for line in open(out_base+'.jsonl'):
            line = line.strip()
            if not line: continue
            e = json.loads(line)
            if e['type'] == 'assistant':
                for b in e['message'].get('content', []):
                    if b.get('type') == 'thinking': thinking += 1
            if e['type'] == 'result':
                is_err = e.get('is_error', True); answer = e.get('result') or ''
    except Exception:
        pass
    ok = exit_code == 0 and not is_err and answer.strip() != ''
    return ok, exit_code, dur, answer, thinking

def run_codex(model, scen_file, out_base):
    env = os.environ.copy()
    env['CODEX_HOME'] = f'{ROOT}/codex-home'
    last = out_base + '.last.txt'
    cmd = ['codex', 'exec', '-m', model, '--skip-git-repo-check', '--sandbox', 'read-only',
           '-C', SUBJECTS, '--json', '--output-last-message', last, '-']
    with open(scen_file) as fin, open(out_base+'.jsonl','w') as fout, open(out_base+'.stderr','w') as ferr:
        t0 = time.time()
        try:
            p = subprocess.run(cmd, stdin=fin, stdout=fout, stderr=ferr, cwd=SUBJECTS, env=env, timeout=360)
            exit_code = p.returncode
        except subprocess.TimeoutExpired:
            exit_code = 124
        dur = time.time() - t0
    answer = ''
    if os.path.exists(last):
        answer = open(last).read()
    reasoning = 0
    try:
        for line in open(out_base+'.jsonl'):
            line = line.strip()
            if not line: continue
            e = json.loads(line)
            if 'reasoning' in json.dumps(e.get('type', '')) or 'reasoning' in str(e.get('msg', {}).get('type', '')):
                reasoning += 1
    except Exception:
        pass
    ok = exit_code == 0 and answer.strip() != ''
    return ok, exit_code, dur, answer, reasoning

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--side', choices=['claude', 'codex'], required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--tag', required=True, help='short model tag for filenames')
    args = ap.parse_args()
    os.makedirs(f'{ROOT}/answers', exist_ok=True)
    scenarios = sorted(glob.glob(f'{ROOT}/scenarios/*.txt'))
    assert len(scenarios) == 15, f'expected 15 scenarios, got {len(scenarios)}'
    for scen_file in scenarios:
        sid = os.path.basename(scen_file).replace('.txt', '')
        out_base = f'{ROOT}/raw/{args.tag}__{sid}__r1'
        status, exit_code, dur, answer, trace = 'failed', -1, 0.0, '', 0
        for attempt in range(1, 4):
            fn = run_claude if args.side == 'claude' else run_codex
            ok, exit_code, dur, answer, trace = fn(args.model, scen_file, out_base)
            if ok:
                status = 'ok'
                break
            print(f'{args.tag} {sid} attempt {attempt} FAILED exit={exit_code}', flush=True)
            if attempt < 3: time.sleep(15)
        ans_file = f'{ROOT}/answers/{args.tag}__{sid}.txt'
        if status == 'ok':
            open(ans_file, 'w').write(answer)
        rec = {'model': args.model, 'tag': args.tag, 'scenario': sid, 'rep': 1,
               'status': status, 'exit': exit_code, 'dur_s': round(dur, 1),
               'trace_blocks': trace, 'answer_file': ans_file if status == 'ok' else None,
               'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        with open(f'{ROOT}/calls.jsonl', 'a') as f:
            f.write(json.dumps(rec) + '\n')
        print(f'{args.tag} {sid}: {status} ({dur:.0f}s, trace={trace})', flush=True)
    print(f'{args.tag}: battery complete', flush=True)

if __name__ == '__main__':
    main()
