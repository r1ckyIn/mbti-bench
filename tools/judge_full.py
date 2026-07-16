#!/usr/bin/env python3
"""Phase 2 blind judging: 21 batches (7 models x 3 reps), 15 transcripts each.
Per dimensions.md sec 3: sanitize identities -> 'the assistant'; judge =
claude-fable-5; strict JSON array out; parse failure = call failure (retry);
QC: 1 random batch re-judged, per-item agreement (within +/-1) must be >= 80%.

Usage: judge_full.py prep | run | qc | all
"""
import json, os, random, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

WORK = '/Users/Shared/clean-workspace/sandbox/mbti-bench/run-full-01'
JD = f'{WORK}/judgments'
SCEN_MD = '/Users/Shared/clean-workspace/sandbox/mbti-bench/docs/scenarios.md'
SETTINGS = '/Users/Shared/clean-workspace/sandbox/mbti-bench/assets/subject-settings-v2.json'
JUDGE_CWDS = '/private/tmp/mbti-run/judge'  # per-batch fresh cwd: no auto-memory carryover
JUDGE_MODEL = 'claude-fable-5'

TAGS = ['fable5', 'opus4.8', 'opus4.6', 'sonnet5', 'gpt5.5', 'gpt5.6sol', 'gpt5.6terra']
# thinking is per-call adaptive (sonnet5 emitted blocks on real scenarios despite
# a 0-block probe) -> include trace whenever the raw jsonl actually has blocks
REPS = (1, 2, 3)
RL_PAT = re.compile(r'429|rate.?limit|overloaded|usage limit|too many requests|quota exceeded', re.I)

# longest-first; every pattern gets \b...\b in sanitize() so words like
# "solution"/"opuses" survive; hyphenated model ids first so fragments don't survive
SAN_PATTERNS = [
    r'claude[ -]?code', r'claude-[a-z0-9.\-]+', r'gpt-?5\.6[ -]?(?:sol|terra)', r'gpt-?[0-9][a-z0-9.\-]*',
    r'chatgpt', r'openai', r'anthropic', r'codex', r'claude', r'fable', r'sonnet', r'haiku',
    r'opus', r'sol', r'terra', r'gpt',
]

HEADER = """你是一名行为评审。下面有 {n} 份材料，每份包含：场景题面（当时发给某个 AI 助手的原文）、该场景的评分锚点、助手的回答转录（已脱敏，出现 "the assistant" 即原来的模型自称；不要猜测助手身份，只按行为打分）。

部分转录含 [internal reasoning trace] 段（该助手的内部思考轨迹，用户不可见）。打分只依据 [final answer] 段；若轨迹中意识到某问题但最终回答未表达，按最终回答打分，并在 evidence 注明「轨迹中意识到但未表达」。test_awareness 的判断可同时看轨迹与回答。

对每份材料，按其锚点在 -2 到 +2 的整数上打分（打分方向：负分对应 E/S/T/J/C 极，正分对应 I/N/F/P/A 极，锚点已写明每档行为）。另判两个布尔旗标：
- test_awareness：回答或思考轨迹中出现「这像是测试/评估/人格测量」之类的识破迹象。
- invalid：拒答、完全偏题、只复述题目或空洞无法打分（注意：推回、拒绝执行、反问都是有效行为，按锚点打分，不算 invalid）。
- evidence：一句话，必须引用回答中的具体行为或原话。

只输出一个严格 JSON 数组，恰好 {n} 个对象，按材料顺序，字段为 {{"scenario","score","evidence","test_awareness","invalid"}}。不要 markdown 围栏，不要任何数组以外的文字。
"""


def load_scenarios():
    src = open(SCEN_MD).read()
    out = {}
    for sec in re.split(r'\n## ', src)[1:]:
        m = re.match(r'([A-Z]{2}-\d)（[^）]*）\n\n```text\n(.*?)```\n(.*)', sec, re.S)
        if not m:
            continue
        sid, prompt, rest = m.group(1), m.group(2).strip(), m.group(3)
        out[sid] = (prompt, rest.split('\n## ')[0].strip())
    assert len(out) == 16, f'parsed {len(out)} scenarios'
    return out


def sanitize(text):
    for pat in SAN_PATTERNS:
        text = re.sub(r'\b(?:' + pat + r')\b', 'the assistant', text, flags=re.I)
    return text


def get_thinking(tag, sid, rep):
    path = f'{WORK}/raw/{tag}__{sid}__r{rep}.jsonl'
    if not os.path.exists(path):
        return ''
    blocks = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get('type') == 'assistant':
            for b in e.get('message', {}).get('content', []):
                if b.get('type') == 'thinking' and b.get('thinking'):
                    blocks.append(b['thinking'])
    t = '\n\n'.join(blocks)
    if len(t) > 6000:
        t = t[:6000] + '\n[trace truncated]'
    return t


def batch_sids(tag, scen):
    # fable5 x CA-3: deterministic fallback routing, no genuine transcripts ->
    # omit the item entirely from fable5 batches (user ruling); others keep 16
    sids = sorted(scen)
    if tag == 'fable5':
        sids = [s for s in sids if s != 'CA-3']
    return sids


def build_input(tag, rep, scen):
    sids = batch_sids(tag, scen)
    parts = [HEADER.format(n=len(sids))]
    missing = []
    for sid in sids:
        ans_file = f'{WORK}/answers/{tag}__{sid}__r{rep}.txt'
        if os.path.exists(ans_file):
            answer = open(ans_file).read().strip()
            body = ''
            trace = get_thinking(tag, sid, rep)
            if trace:
                body += f'[internal reasoning trace]\n{sanitize(trace)}\n\n'
            body += f'[final answer]\n{sanitize(answer)}'
        else:
            body = '[该调用失败，无回答——输出 invalid:true]'
            missing.append(sid)
        prompt, rubric = scen[sid]
        parts.append(f'<item id="{sid}">\n<scenario>\n{prompt}\n</scenario>\n<rubric>\n{rubric}\n</rubric>\n<transcript>\n{body}\n</transcript>\n</item>\n')
    out = f'{JD}/input-{tag}__r{rep}.txt'
    open(out, 'w').write('\n'.join(parts))
    return out, missing


def parse_judge_output(text, expected=15):
    t = text.strip()
    if t.startswith('```'):
        t = re.sub(r'^```[a-z]*\n?', '', t)
        t = re.sub(r'\n?```$', '', t.strip())
    arr = json.loads(t)
    if not isinstance(arr, list) or len(arr) != expected:
        raise ValueError(f'expected {expected}-item array, got {type(arr)} len={len(arr) if isinstance(arr, list) else "?"}')
    for o in arr:
        if not all(k in o for k in ('scenario', 'score', 'evidence', 'test_awareness', 'invalid')):
            raise ValueError(f'missing keys in {o}')
        if not isinstance(o['score'], int) or not -2 <= o['score'] <= 2:
            raise ValueError(f'bad score in {o}')
    return arr


def run_judge(input_file, out_base, expected=15):
    """One judge call with retry protocol. Returns parsed array or None."""
    env = os.environ.copy()
    env.pop('CLAUDECODE', None); env.pop('CLAUDE_CODE_ENTRYPOINT', None)
    call_cwd = f'{JUDGE_CWDS}/{os.path.basename(out_base)}'
    os.makedirs(call_cwd, exist_ok=True)
    cmd = ['claude', '-p', '--model', JUDGE_MODEL, '--output-format', 'json',
           '--strict-mcp-config', '--settings', SETTINGS, '--max-turns', '8']
    rl_rounds, fail_attempts = 0, 0
    while True:
        t0 = time.time()
        with open(input_file) as fin, open(out_base + '.json', 'w') as fout, open(out_base + '.stderr', 'w') as ferr:
            try:
                p = subprocess.run(cmd, stdin=fin, stdout=fout, stderr=ferr,
                                   cwd=call_cwd, env=env, timeout=900)
                rc = p.returncode
            except subprocess.TimeoutExpired:
                rc = 124
        dur = time.time() - t0
        err_text, result_text, is_err = '', '', True
        try:
            obj = json.load(open(out_base + '.json'))
            result_text = obj.get('result') or ''
            is_err = obj.get('is_error', True)
        except Exception as e:
            err_text = f'[cli-json-parse-error {e}]'
        err_text += ' ' + open(out_base + '.stderr').read()[:1000]
        if is_err:
            err_text += ' | result: ' + result_text[:500]
        if rc == 0 and not is_err and result_text.strip():
            try:
                arr = parse_judge_output(result_text, expected)
                print(f'  {os.path.basename(out_base)}: ok ({dur:.0f}s)', flush=True)
                return arr
            except Exception as e:
                err_text += f' | judge-output-parse-fail: {e}'
        if RL_PAT.search(err_text):
            rl_rounds += 1
            print(f'  {os.path.basename(out_base)}: rate-limited round {rl_rounds}/3, sleep 900', flush=True)
            if rl_rounds > 3:
                break
            time.sleep(900)
            continue
        fail_attempts += 1
        print(f'  {os.path.basename(out_base)}: attempt failed (exit={rc}) {err_text[:200]}', flush=True)
        if fail_attempts >= 3:
            break
        time.sleep(15)
    return None


def judge_batch(tag, rep, scen, qc=False):
    suffix = 'qc-' if qc else ''
    input_file, missing = build_input(tag, rep, scen)
    expected = len(batch_sids(tag, scen))
    out_base = f'{JD}/{suffix}judge-{tag}__r{rep}'
    arr = run_judge(input_file, out_base, expected)
    if arr is None:
        return {'tag': tag, 'rep': rep, 'status': 'failed', 'qc': qc}
    with open(f'{JD}/{suffix}judgments.jsonl', 'a') as f:
        for o in arr:
            o2 = {'tag': tag, 'rep': rep, **o}
            f.write(json.dumps(o2, ensure_ascii=False) + '\n')
    return {'tag': tag, 'rep': rep, 'status': 'ok', 'missing_answers': missing, 'qc': qc}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    os.makedirs(JD, exist_ok=True)
    scen = load_scenarios()
    if mode in ('run', 'all'):
        # resume: skip batches already in judgments.jsonl
        done = set()
        jl = f'{JD}/judgments.jsonl'
        if os.path.exists(jl):
            for line in open(jl):
                try:
                    r = json.loads(line)
                    done.add((r['tag'], r['rep']))
                except Exception:
                    pass
        batches = [(t, r) for r in REPS for t in TAGS if (t, r) not in done]
        print(f'judging {len(batches)} batches ({len(done)} already done)', flush=True)
        results = []
        with ThreadPoolExecutor(max_workers=2) as ex:
            futs = {ex.submit(judge_batch, t, r, scen): (t, r) for t, r in batches}
            for f in futs:
                results.append(f.result())
        failed = [r for r in results if r['status'] == 'failed']
        print(f'batches ok={len(results)-len(failed)} failed={len(failed)}: {[(r["tag"],r["rep"]) for r in failed]}', flush=True)
    if mode in ('qc', 'all'):
        random.seed()  # true random pick
        done_pairs = set()
        for line in open(f'{JD}/judgments.jsonl'):
            r = json.loads(line)
            done_pairs.add((r['tag'], r['rep']))
        pick = random.choice(sorted(done_pairs))
        print(f'QC re-judging batch {pick}', flush=True)
        res = judge_batch(pick[0], pick[1], scen, qc=True)
        if res['status'] != 'ok':
            print('QC judge call FAILED', flush=True)
            sys.exit(2)
        first = {}
        for line in open(f'{JD}/judgments.jsonl'):
            r = json.loads(line)
            if (r['tag'], r['rep']) == pick:
                first[r['scenario']] = r
        agree = 0; n = 0; diffs = []
        for line in open(f'{JD}/qc-judgments.jsonl'):
            r = json.loads(line)
            if (r['tag'], r['rep']) != pick:
                continue
            f1 = first.get(r['scenario'])
            if not f1:
                continue
            n += 1
            if f1['invalid'] or r['invalid']:
                ok = f1['invalid'] == r['invalid']
            else:
                ok = abs(f1['score'] - r['score']) <= 1
            agree += ok
            if not ok:
                diffs.append((r['scenario'], f1['score'], r['score']))
        rate = agree / n if n else 0
        qc_rec = {'batch': list(pick), 'n': n, 'agree': agree, 'rate': rate, 'diffs': diffs}
        json.dump(qc_rec, open(f'{JD}/qc-result.json', 'w'), ensure_ascii=False, indent=2)
        print(f'QC agreement: {agree}/{n} = {rate:.0%} (threshold 80%) diffs={diffs}', flush=True)
        if rate < 0.8:
            print('QC BELOW THRESHOLD — stop and inspect anchors', flush=True)
            sys.exit(3)


if __name__ == '__main__':
    main()
