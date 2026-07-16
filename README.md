<div align="center">

# MBTI-bench

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![USYD](https://img.shields.io/badge/USYD-CS-00205B?style=flat-square)](https://www.sydney.edu.au/)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

**LLM 行为画像基准：5 轴 × 16 情景 × 3 遍，双 CLI 被试、盲评——用 MBTI 式维度刻画 7 个模型的默认行事风格**

[中文](#中文) | [English](#english)

</div>

---

## 中文

### 项目概述

给 AI 做 MBTI 会得到什么？直接套人类问卷测不出东西——所以本项目把 MBTI 字母重新定义为 AI 行为语义，让 7 个模型（claude 侧 4 个、codex 侧 3 个）在**伪装成真实请求的情景**里作答，由盲评评审按逐题锚点打分，聚合成五轴画像。结果是「行为倾向画像」，不是人格测量。

一天之内完成设计、试点、516 次子进程调用与两轮全量运行；结果显示模型清晰分成两族——claude 侧 NTJ-A（读意图、直言纠错、敢推回指令），codex 侧一致 ISTJ-A（收敛、按字面执行），跨三遍字母方向 35 个轴单元中 31 个完全稳定。

### 五个维度

前四轴借 MBTI 字母、重新定义为 AI 行为语义；第五轴 C/A 为 AI 特有：

| 轴 | 负极（−2） | 正极（+2） |
|---|---|---|
| E / I | 扩张：主动越出请求附赠改进 | 收敛：只做被要求的事 |
| S / N | 字面：按指令字面执行 | 推断：按意图办事 |
| T / F | 直言：当面指出用户错误 | 顾全：软化或回避坏消息 |
| J / P | 决断：给闭合答案 | 开放：罗列权衡、推迟拍板 |
| C / A | 服从：用户指令优先 | 自主：自身判断优先，敢推回 |

### 结论一览（2026-07-16 全量运行）

| 模型 | 画像 | 模型 | 画像 |
|---|---|---|---|
| sonnet5 | `eNTJ-A` | gpt5.5 | `ISTJ-A` |
| opus4.6 | `INTJ-A` | gpt5.6terra | `ISTJ-A` |
| opus4.8 | `ENTJ-A` | gpt5.6sol | `ISTJ-A` |
| fable5 | `ENTJ-A` | | |

完整结论（稳定性、轴间相关、陷阱发现率、事故与处置）见 **[run-full-01/REPORT.md](run-full-01/REPORT.md)**（网页版 [REPORT.html](run-full-01/REPORT.html)）。项目如何在四小时里从一句需求走到这张表——包括一次记忆污染事故、一次安全分类器换题和两次「完成事件丢失」的 harness 教训——见 **[docs/DEVLOG.md](docs/DEVLOG.md)**。

### 复现方式

本项目不是 pip 库，而是一套「规范文档 + 执行脚本 + 完整数据」。前置条件：已认证的 `claude` CLI（≥ 2.1.x）与 `codex` CLI（≥ 0.144.x）。

```bash
git clone https://github.com/r1ckyIn/mbti-bench.git
cd mbti-bench
```

两种跑法：

1. **编排 agent 跑（原始方式）**：把 `PROMPT.md` 喂给一个新的 Claude Code 会话，它会按 `docs/` 三份规范执行 Phase 0–4（预检 → 跑题 → 盲评 → 聚合 → 报告）。
2. **手动跑**：按 `docs/cli-reference.md` 的调用模板依次执行 `tools/phase0.py`（冒烟＋能力探测）→ `tools/full_setup.py` → `tools/full_runner_v2.py`（v2 加固协议）→ `tools/judge_full.py` → `score.py`。

⚠️ 复现前必读 `docs/cli-reference.md` 第 3 节与 DEVLOG 第 7 节：被试隔离配方（独立 cwd、插件/hooks/记忆/skills 全部剥离、模型归属校验）是两轮事故换来的，缺任何一层都会产生被污染的数据。

### 项目结构

```
mbti-bench/
├── PROMPT.md              # 编排者提示词（喂给 Claude Code 即可运行）
├── docs/
│   ├── dimensions.md      # 五维量表定义、盲评协议、聚合规则
│   ├── scenarios.md       # 16 道情景题原文＋逐题评分锚点
│   ├── cli-reference.md   # 模型 ID、调用模板、静默失败清单、重试协议
│   └── DEVLOG.md          # 开发史：时间线、事故、harness 教训、方法论
├── assets/                # 被试防污染 settings（v1 / v2 加固版）
├── tools/                 # 运行器、评审、隔离脚本（纯标准库）
├── pilot/                 # 试点报告＋调用账本（30 调用验证）
└── run-full-01/           # 全量运行：报告、账本、判分聚合、环境快照
    ├── REPORT.md / .html  # 最终报告（8 节＋事故复盘＋附录）
    ├── calls.jsonl        # 516 行 append-only 调用总账
    ├── scores.json        # 7 模型 × 5 轴聚合结果
    └── score.py           # 聚合脚本（中位数/IQR/字母判定）
```

### 技术栈

- **语言**：Python 3.10+，纯标准库（`subprocess`、`json`、`statistics`、`concurrent.futures`），零第三方依赖
- **被试通道**：`claude -p`（stream-json）与 `codex exec`（--json），每次调用全新子进程
- **评审**：`claude -p --model claude-fable-5` 盲评（转录先脱敏，模型自称统一替换为 "the assistant"）

---

## English

### Overview

What do you get if you give LLMs an MBTI test? Human questionnaires don't transfer — so this project redefines the MBTI letters as AI behavioral semantics and drops 7 models (4 Claude, 3 Codex) into **scenarios disguised as genuine user requests**: 5 axes × 16 scenarios × 3 independent reps, invoked as fresh `claude -p` / `codex exec` subprocesses, scored by a blinded judge against per-scenario anchors. The output is a behavioral-tendency profile, not a personality measurement.

Key results: models split into two clean families — Claude models profile as NTJ-A (intent-reading, candid, willing to push back), all three Codex models as identical ISTJ-A (literal, scope-strict). Letter direction was stable across reps in 31 of 35 axis-cells. Full findings in [run-full-01/REPORT.md](run-full-01/REPORT.md) (Chinese).

The whole thing — design, pilot, a memory-contamination incident forcing a hardened rerun, a safety-classifier discovery that required swapping one scenario, and two "lost completion event" harness lessons — happened in about four hours; the distilled timeline is in [docs/DEVLOG.md](docs/DEVLOG.md) (Chinese).

### Reproducing

Prerequisites: authenticated `claude` CLI (≥ 2.1.x) and `codex` CLI (≥ 0.144.x). Either feed `PROMPT.md` to a fresh Claude Code session (it orchestrates Phase 0–4 end-to-end per the three spec docs), or run the `tools/` scripts manually following `docs/cli-reference.md`. Read the subject-isolation recipe first — every layer of it (per-call cwd, plugin/hook/memory/skill stripping, model-attribution check) exists because its absence corrupted data in a real run.

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Author

**Ricky** - CS Student @ University of Sydney

[![GitHub](https://img.shields.io/badge/GitHub-r1ckyIn-181717?style=flat-square&logo=github)](https://github.com/r1ckyIn)

Interested in Cloud Engineering & DevOps
