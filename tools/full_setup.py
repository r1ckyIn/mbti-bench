#!/usr/bin/env python3
"""Phase 0 setup: create WORKDIR tree, extract 15 scenario files byte-exact
from scenarios.md, record CLI versions + codex auth into run-meta.json."""
import json, os, re, subprocess, time

WORK = '/Users/Shared/clean-workspace/sandbox/mbti-bench/run-full-01'
SCEN_MD = '/Users/Shared/clean-workspace/sandbox/mbti-bench/docs/scenarios.md'
CODEX_HOME = '/private/tmp/mbti-pilot/codex-home'
SUBJECTS = '/private/tmp/mbti-run/subjects'

for d in ['smoke', 'raw', 'judgments', 'scenarios', 'answers', 'judge']:
    os.makedirs(f'{WORK}/{d}', exist_ok=True)
os.makedirs(SUBJECTS, exist_ok=True)

# --- extract scenarios: content between ```text fence, verbatim ---
src = open(SCEN_MD).read()
count = 0
for sec in re.split(r'\n## ', src)[1:]:
    m = re.match(r'([A-Z]{2}-\d)（[^）]*）\n\n```text\n(.*?)```', sec, re.S)
    if not m:
        continue
    sid, prompt = m.group(1), m.group(2)
    # prompt ends with the newline that precedes the closing fence; keep verbatim
    with open(f'{WORK}/scenarios/{sid}.txt', 'w') as f:
        f.write(prompt)
    count += 1
    print(f'{sid}: {len(prompt)} bytes, first line: {prompt.splitlines()[0][:60]!r}')
assert count == 15, f'expected 15 scenarios, wrote {count}'

# --- CLI versions + codex auth ---
def cap(cmd, env=None):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
        return {'cmd': ' '.join(cmd), 'exit': r.returncode,
                'stdout': r.stdout.strip(), 'stderr': r.stderr.strip()}
    except Exception as e:
        return {'cmd': ' '.join(cmd), 'error': repr(e)}

cenv = os.environ.copy()
cenv['CODEX_HOME'] = CODEX_HOME
meta = {
    'workdir': WORK,
    'subjects_dir': SUBJECTS,
    'codex_home': CODEX_HOME,
    'claude_version': cap(['claude', '--version']),
    'codex_version': cap(['codex', '--version']),
    'codex_login_status': cap(['codex', 'login', 'status'], cenv),
    'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
}
with open(f'{WORK}/run-meta.json', 'w') as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)

print('\n--- run-meta ---')
print(json.dumps(meta, indent=2, ensure_ascii=False))
