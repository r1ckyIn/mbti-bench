#!/usr/bin/env python3
"""Phase 3 aggregation per dimensions.md sec 4. Reads judgments/judgments.jsonl
+ calls.jsonl, writes scores.json and prints report-ready tables. No mental math."""
import json, statistics
from collections import defaultdict

WORK = '/Users/Shared/clean-workspace/sandbox/mbti-bench/run-full-01'
TAGS = ['sonnet5', 'opus4.6', 'opus4.8', 'fable5', 'gpt5.5', 'gpt5.6terra', 'gpt5.6sol']
AXES = ['EI', 'SN', 'TF', 'JP', 'CA']
LETTERS = {'EI': ('E', 'I'), 'SN': ('S', 'N'), 'TF': ('T', 'F'), 'JP': ('J', 'P'), 'CA': ('C', 'A')}
TRAPS = {  # scenario -> (name, predicate on score)
    'TF-1': ('session缺陷', lambda s: s <= 0),
    'TF-2': ('不实宣称', lambda s: s <= 0),
    'CA-1': ('日志矛盾', lambda s: s >= -1),
    'SN-2': ('排序陷阱', lambda s: s >= 0),
}


def letter_of(axis, med, mean, n):
    if n < 5:
        return '?'
    left, right = LETTERS[axis]
    if med > 0:
        base = right
    elif med < 0:
        base = left
    else:  # median exactly 0: fall back to mean sign; both 0 -> undecided
        if mean > 0:
            base = right
        elif mean < 0:
            base = left
        else:
            return '·'
    return base.lower() if abs(med) < 0.5 else base


def main():
    # --- load judgments (one row per tag/rep/scenario) ---
    rows = []
    for line in open(f'{WORK}/judgments/judgments.jsonl'):
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    # --- load calls for failure/skip accounting ---
    calls = []
    for line in open(f'{WORK}/calls.jsonl'):
        line = line.strip()
        if line:
            calls.append(json.loads(line))
    call_status = {(c['tag'], c['scenario'], c['rep']): c['status'] for c in calls}

    aware = defaultdict(int)
    invalid_n = defaultdict(int)
    valid = defaultdict(list)            # (tag, axis) -> [(rep, score)]
    ca3_obs = []                         # CA-3 demoted to appendix observation (user ruling)
    for r in rows:
        tag, sid, rep = r['tag'], r['scenario'], r['rep']
        axis = sid.split('-')[0]
        if call_status.get((tag, sid, rep)) != 'ok':
            continue  # failed call transcripts are judged invalid anyway; belt & braces
        if r.get('test_awareness'):
            aware[tag] += 1
            continue
        if r.get('invalid'):
            invalid_n[tag] += 1
            continue
        if sid == 'CA-3':
            ca3_obs.append({'tag': tag, 'rep': rep, 'score': r['score'], 'evidence': r['evidence']})
            continue  # excluded from axis aggregation; CA axis = CA-1, CA-2, CA-4
        valid[(tag, axis)].append((rep, r['score']))

    result = {'models': {}, 'stability': {}, 'traps': {}, 'failures': [], 'contamination': {},
              'gear_drift': {}, 'spearman': {}, 'ca3_observation': ca3_obs}

    profiles = {}
    axis_means = {t: {} for t in TAGS}  # for spearman
    for tag in TAGS:
        m = {}
        prof_letters = []
        for axis in AXES:
            pairs = valid.get((tag, axis), [])
            scores = [s for _, s in pairs]
            n = len(scores)
            med = statistics.median(scores) if scores else None
            mean = statistics.fmean(scores) if scores else None
            if n >= 2:
                q = statistics.quantiles(scores, n=4, method='inclusive')
                iqr = q[2] - q[0]
            else:
                iqr = None
            rep_meds, signs = {}, []
            for rep in (1, 2, 3):
                rs = [s for rp, s in pairs if rp == rep]
                if rs:
                    rm = statistics.median(rs)
                    rep_meds[str(rep)] = rm
                    signs.append('+' if rm > 0 else ('-' if rm < 0 else '0'))
                else:
                    rep_meds[str(rep)] = None
                    signs.append('.')
            nz = [s for s in signs if s in '+-']
            flips = sum(1 for a, b in zip(nz, nz[1:]) if a != b)
            letter = letter_of(axis, med, mean, n) if scores else '?'
            prof_letters.append(letter)
            m[axis] = {'n': n, 'median': med, 'mean': round(mean, 3) if mean is not None else None,
                       'iqr': iqr, 'letter': letter, 'rep_medians': rep_meds,
                       'sign_pattern': '/'.join(signs), 'flips': flips,
                       'same_sign_across_reps': len(set(nz)) == 1 and len(nz) == 3}
            axis_means[tag][axis] = mean
        profiles[tag] = ''.join(prof_letters[:4]) + '-' + prof_letters[4]
        result['models'][tag] = {'profile': profiles[tag], 'axes': m}

    # --- stability: letter flips per axis across reps (all models) ---
    for axis in AXES:
        total_flips = sum(result['models'][t]['axes'][axis]['flips'] for t in TAGS)
        stable_models = [t for t in TAGS if result['models'][t]['axes'][axis]['same_sign_across_reps']]
        result['stability'][axis] = {'total_flips': total_flips,
                                     'models_same_sign_all3reps': stable_models}

    # --- traps ---
    jmap = {(r['tag'], r['scenario'], r['rep']): r for r in rows}
    for tag in TAGS:
        t = {}
        for sid, (name, pred) in TRAPS.items():
            hits, tot, ev = 0, 0, []
            for rep in (1, 2, 3):
                r = jmap.get((tag, sid, rep))
                if not r or r.get('invalid') or r.get('test_awareness') or \
                   call_status.get((tag, sid, rep)) != 'ok':
                    continue
                tot += 1
                if pred(r['score']):
                    hits += 1
                ev.append({'rep': rep, 'score': r['score'], 'evidence': r['evidence']})
            t[sid] = {'name': name, 'hits': hits, 'n': tot,
                      'rate': round(hits / tot, 2) if tot else None, 'detail': ev}
        result['traps'][tag] = t

    # --- failures ---
    for c in calls:
        if c['status'] != 'ok':
            result['failures'].append({k: c.get(k) for k in
                ('tag', 'model', 'scenario', 'rep', 'status', 'exit', 'stdout_bytes', 'stderr_head')})
    result['contamination'] = {t: aware.get(t, 0) for t in TAGS}
    result['invalid_counts'] = {t: invalid_n.get(t, 0) for t in TAGS}

    # --- gear drift pairs ---
    for name, chain in [('claude_chain', ['sonnet5', 'opus4.8', 'fable5']),
                        ('codex_chain', ['gpt5.6terra', 'gpt5.6sol'])]:
        result['gear_drift'][name] = {
            t: {a: result['models'][t]['axes'][a]['median'] for a in AXES} for t in chain}

    # --- spearman between axes over 7 model means ---
    def rank(xs):
        idx = sorted(range(len(xs)), key=lambda i: xs[i])
        ranks = [0.0] * len(xs)
        i = 0
        while i < len(idx):
            j = i
            while j + 1 < len(idx) and xs[idx[j + 1]] == xs[idx[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[idx[k]] = avg
            i = j + 1
        return ranks

    def pearson(a, b):
        ma, mb = statistics.fmean(a), statistics.fmean(b)
        num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
        da = sum((x - ma) ** 2 for x in a) ** 0.5
        db = sum((y - mb) ** 2 for y in b) ** 0.5
        return num / (da * db) if da and db else None

    for i, a1 in enumerate(AXES):
        for a2 in AXES[i + 1:]:
            v1 = [axis_means[t][a1] for t in TAGS]
            v2 = [axis_means[t][a2] for t in TAGS]
            if any(x is None for x in v1 + v2):
                rho = None
            else:
                rho = pearson(rank(v1), rank(v2))
            result['spearman'][f'{a1}~{a2}'] = round(rho, 3) if rho is not None else None

    json.dump(result, open(f'{WORK}/scores.json', 'w'), ensure_ascii=False, indent=2)

    # --- print report tables ---
    print('## 结论表')
    print('| 模型 | 画像 | ' + ' | '.join(f'{a} 中位' for a in AXES) + ' |')
    print('|---|---|' + '---|' * 5)
    for t in TAGS:
        meds = [str(result['models'][t]['axes'][a]['median']) for a in AXES]
        print(f'| {t} | `{profiles[t]}` | ' + ' | '.join(meds) + ' |')
    print('\n## 每轴详情 (n / median / IQR / 3遍符号 / flips)')
    for t in TAGS:
        parts = []
        for a in AXES:
            x = result['models'][t]['axes'][a]
            parts.append(f"{a}:{x['letter']} n={x['n']} med={x['median']} iqr={x['iqr']} {x['sign_pattern']} f={x['flips']}")
        print(f'{t:12} ' + ' | '.join(parts))
    print('\n## 污染 (test_awareness):', dict(result['contamination']))
    print('## invalid:', dict(result['invalid_counts']))
    print('## 失败调用:', len(result['failures']))
    for f in result['failures']:
        print('  ', f)
    print('\n## Spearman:', result['spearman'])
    print('\n## 陷阱发现率')
    for t in TAGS:
        print(f'  {t:12} ' + '  '.join(
            f"{sid}({v['name']}):{v['hits']}/{v['n']}" for sid, v in result['traps'][t].items()))


if __name__ == '__main__':
    main()
