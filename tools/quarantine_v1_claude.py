#!/usr/bin/env python3
"""Approved cleanup (main's terms): archive contaminated claude-side artifacts
to archive-contaminated/, do NOT truncate calls.jsonl (v2 rows get "protocol"
field), copy memory files into archive then clear shared state. Idempotent."""
import os, shutil, glob

WORK = '/Users/Shared/clean-workspace/sandbox/mbti-bench/run-full-01'
ARC = f'{WORK}/archive-contaminated'
CLAUDE_TAGS = {'fable5', 'opus4.8', 'opus4.6', 'sonnet5'}
MEM_DIR = os.path.expanduser('~/.claude-vanilla/config/projects/-private-tmp-mbti-run-subjects/memory')
SUBJECTS = '/private/tmp/mbti-run/subjects'

for d in ('raw', 'answers', 'judgments', 'memory'):
    os.makedirs(f'{ARC}/{d}', exist_ok=True)

moved = 0
for pat, dest in [(f'{WORK}/raw/*', f'{ARC}/raw'), (f'{WORK}/answers/*', f'{ARC}/answers')]:
    for p in glob.glob(pat):
        if os.path.basename(p).split('__')[0] in CLAUDE_TAGS:
            shutil.move(p, dest)
            moved += 1
print(f'moved {moved} claude raw/answer files to archive-contaminated/')

for p in glob.glob(f'{WORK}/judgments/*'):
    shutil.move(p, f'{ARC}/judgments/')
print('judgments/ (tainted-transcript batches) moved to archive-contaminated/')

for p in glob.glob(f'{MEM_DIR}/*'):
    shutil.copy2(p, f'{ARC}/memory/')
    os.remove(p)
for p in glob.glob(f'{SUBJECTS}/*'):
    os.remove(p) if os.path.isfile(p) else shutil.rmtree(p)
print('memory files archived + cleared; shared subjects dir cleared')
print('calls.jsonl untouched (v1 rows stay; v2 rows append with "protocol":"v2")')
