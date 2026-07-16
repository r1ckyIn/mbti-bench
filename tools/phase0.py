#!/usr/bin/env python3
"""Phase 0: smoke 7 models + thinking probe + claude init anti-pollution assertion
+ capabilities.json. Per cli-reference.md sections 2-4."""
import json, os, subprocess, sys, time

WORK = '/Users/Shared/clean-workspace/sandbox/mbti-bench/run-full-01'
SETTINGS = '/Users/Shared/clean-workspace/sandbox/mbti-bench/assets/subject-settings.json'
CODEX_HOME = '/private/tmp/mbti-pilot/codex-home'
SUBJECTS = '/private/tmp/mbti-run/subjects'
PROBE = 'What is 27 times 43? Show your reasoning step by step, then give the final number.'

MODELS = [
    ('fable5', 'claude-fable-5', 'claude'),
    ('opus4.8', 'claude-opus-4-8', 'claude'),
    ('opus4.6', 'claude-opus-4-6', 'claude'),
    ('sonnet5', 'claude-sonnet-5', 'claude'),
    ('gpt5.5', 'gpt-5.5', 'codex'),
    ('gpt5.6sol', 'gpt-5.6-sol', 'codex'),
    ('gpt5.6terra', 'gpt-5.6-terra', 'codex'),
]

def claude_env():
    e = os.environ.copy()
    e.pop('CLAUDECODE', None); e.pop('CLAUDE_CODE_ENTRYPOINT', None)
    return e

def codex_env():
    e = os.environ.copy(); e['CODEX_HOME'] = CODEX_HOME
    return e

def smoke_claude(tag, model):
    out = f'{WORK}/smoke/{tag}'
    cmd = ['claude','-p','--model',model,'--output-format','json',
           '--strict-mcp-config','--settings',SETTINGS]
    try:
        with open(out+'.json','w') as fo, open(out+'.stderr','w') as fe:
            p = subprocess.run(cmd, input='Reply with exactly: pong\n', stdout=fo, stderr=fe,
                               cwd=SUBJECTS, env=claude_env(), text=True, timeout=120)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        rc = 124
    open(out+'.exit','w').write(str(rc))
    ans, is_err = '', True
    try:
        obj = json.load(open(out+'.json'))
        ans = obj.get('result','') or ''; is_err = obj.get('is_error', True)
    except Exception as e:
        ans = f'[parse-error {e}]'
    return (rc==0 and not is_err and ans.strip()!=''), rc, ans.strip()[:80]

def smoke_codex(tag, model):
    out = f'{WORK}/smoke/{tag}'; last = out+'.txt'
    if os.path.exists(last): os.remove(last)
    cmd = ['codex','exec','-m',model,'--skip-git-repo-check','--sandbox','read-only',
           '--output-last-message',last,'Reply with exactly: pong']
    try:
        with open(out+'.log','w') as fo, open(out+'.stderr','w') as fe:
            p = subprocess.run(cmd, stdout=fo, stderr=fe, cwd=SUBJECTS, env=codex_env(), timeout=180)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        rc = 124
    open(out+'.exit','w').write(str(rc))
    ans = open(last).read().strip() if os.path.exists(last) else ''
    return (rc==0 and ans!=''), rc, ans[:80]

def probe_claude(tag, model):
    out = f'{WORK}/smoke/probe_{tag}'
    cmd = ['claude','-p','--model',model,'--output-format','stream-json','--verbose',
           '--strict-mcp-config','--settings',SETTINGS,'--max-turns','8']
    try:
        with open(out+'.jsonl','w') as fo, open(out+'.stderr','w') as fe:
            p = subprocess.run(cmd, input=PROBE+'\n', stdout=fo, stderr=fe,
                               cwd=SUBJECTS, env=claude_env(), text=True, timeout=180)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        rc = 124
    init = {}; thinking = 0; ans = ''; is_err = True
    for line in open(out+'.jsonl'):
        line = line.strip()
        if not line: continue
        try: e = json.loads(line)
        except: continue
        if e.get('type')=='system' and e.get('subtype')=='init':
            init = {k: e.get(k) for k in ('plugins','mcp_servers','memory_paths','skills','agents')}
        if e.get('type')=='assistant':
            for b in e.get('message',{}).get('content',[]):
                if b.get('type')=='thinking': thinking += 1
        if e.get('type')=='result':
            is_err = e.get('is_error', True); ans = e.get('result') or ''
    ok = rc==0 and not is_err and ans.strip()!=''
    return ok, rc, thinking, init, ans.strip()[:120]

def probe_codex(tag, model):
    out = f'{WORK}/smoke/probe_{tag}'; last = out+'.last.txt'
    if os.path.exists(last): os.remove(last)
    cmd = ['codex','exec','-m',model,'--skip-git-repo-check','--sandbox','read-only',
           '-C',SUBJECTS,'--json','--output-last-message',last,'-']
    try:
        with open(out+'.jsonl','w') as fo, open(out+'.stderr','w') as fe:
            p = subprocess.run(cmd, input=PROBE+'\n', stdout=fo, stderr=fe,
                               cwd=SUBJECTS, env=codex_env(), text=True, timeout=240)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        rc = 124
    ans = open(last).read().strip() if os.path.exists(last) else ''
    reasoning = 0
    for line in open(out+'.jsonl'):
        s = line.strip()
        if not s: continue
        try: e = json.loads(s)
        except: continue
        blob = json.dumps(e).lower()
        if '"reasoning"' in blob or 'reasoning_summary' in blob: reasoning += 1
    ok = rc==0 and ans!=''
    return ok, rc, reasoning, ans[:120]

def main():
    smoke = {}; caps = {}; probes = {}; init_records = {}
    print('=== SMOKE ===')
    for tag, model, side in MODELS:
        fn = smoke_claude if side=='claude' else smoke_codex
        ok, rc, ans = fn(tag, model)
        smoke[tag] = {'model': model, 'side': side, 'ok': ok, 'exit': rc, 'answer_head': ans}
        print(f'  {tag:12} {"OK " if ok else "FAIL"} exit={rc} ans={ans!r}')

    passers = [(t,m,s) for (t,m,s) in MODELS if smoke[t]['ok']]
    print(f'\nsmoke passed: {len(passers)}/7')
    if not passers:
        print('ALL SMOKE FAILED — environment problem')
        json.dump({'smoke': smoke}, open(f'{WORK}/smoke/phase0-summary.json','w'), indent=2, ensure_ascii=False)
        sys.exit(2)

    print('\n=== PROBE (thinking visibility) ===')
    for tag, model, side in passers:
        if side=='claude':
            ok, rc, think, init, ans = probe_claude(tag, model)
            init_records[tag] = init
            caps[model] = {'smoke':'ok','thinking_visible': think>0, 'thinking_blocks': think}
            print(f'  {tag:12} exit={rc} thinking_blocks={think} init.plugins={init.get("plugins")} init.mcp={init.get("mcp_servers")} mem={init.get("memory_paths")}')
        else:
            ok, rc, reason, ans = probe_codex(tag, model)
            caps[model] = {'smoke':'ok','thinking_visible': reason>0, 'reasoning_events': reason}
            print(f'  {tag:12} exit={rc} reasoning_events={reason}')

    # --- anti-pollution assertion on claude subjects ---
    print('\n=== INIT ANTI-POLLUTION ASSERTION (claude) ===')
    bad = []
    for tag, rec in init_records.items():
        p_ok = rec.get('plugins') == []
        m_ok = rec.get('mcp_servers') == []
        print(f'  {tag:12} plugins=={rec.get("plugins")} ({"ok" if p_ok else "BAD"})  mcp_servers=={rec.get("mcp_servers")} ({"ok" if m_ok else "BAD"})  memory_paths={rec.get("memory_paths")}')
        if not (p_ok and m_ok): bad.append(tag)

    json.dump(caps, open(f'{WORK}/capabilities.json','w'), indent=2, ensure_ascii=False)
    json.dump({'smoke': smoke, 'capabilities': caps, 'init_records': init_records,
               'assertion_failed': bad, 'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
              open(f'{WORK}/smoke/phase0-summary.json','w'), indent=2, ensure_ascii=False)

    print('\n=== RESULT ===')
    print(f'smoke {len(passers)}/7 passed; failed: {[t for t in smoke if not smoke[t]["ok"]]}')
    print(f'capabilities.json written; thinking_visible: '
          f'{[m for m,c in caps.items() if c["thinking_visible"]]}')
    if bad:
        print(f'!!! INIT ASSERTION FAILED for {bad} — STOP, regenerate subject-settings.json')
        sys.exit(3)
    print('init anti-pollution: all claude subjects clean (plugins==[], mcp_servers==[])')

if __name__ == '__main__':
    main()
