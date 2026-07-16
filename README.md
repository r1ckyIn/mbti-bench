<p align="center">Personality tests are for humans. So we stopped asking —</p>
<h1 align="center">mbti-bench</h1>

<p align="center">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-blue?style=flat-square"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B%20·%20stdlib%20only-3776AB?style=flat-square">
  <img alt="Subjects" src="https://img.shields.io/badge/subjects-7%20models%20·%202%20CLIs-1f4d3f?style=flat-square">
</p>

<h3 align="center">Don't ask the model who it is. Watch what it does.</h3>

给 LLM 做 MBTI 问卷没有意义——问卷是自我报告,而模型会演。
所以这个 bench 一道问卷题都没有:16 个伪装成真实工作请求的情景,丢给 7 个模型(4 个 Claude、3 个 Codex),每题独立 3 遍、每遍全新子进程,再由盲评评审按逐题锚点打分。
被试不知道自己在被测——333 份判分里识破次数为 0。
我们不问它是谁,只看它做了什么。

- **五轴行为语义** - MBTI 字母全部重定义:E 扩张 / I 收敛、S 字面 / N 意图、T 直言 / F 顾全、J 拍板 / P 开放,外加 AI 特有的第五轴 C 服从 / A 自主——敢不敢推回你的指令。
- **情景,不是问卷** - 每题都像一个普通请求,内嵌 4 个陷阱检测点;题面一字不改经 stdin 直达被试。
- **盲评** - 转录先脱敏(模型自称统一替换为 "the assistant")再送 claude-fable-5 按锚点打分;抽批双评质检逐题一致率 15/15(±1 内)。
- **可回溯** - 516 行 append-only 调用总账,每个分数都能回溯到原始转录;污染事故的数据留档不删。
- **快** - 从一句需求到最终报告约 4 小时,含一次 180 调用的全量重跑。

## 结论

| 模型 | 画像 | 模型 | 画像 |
|---|---|---|---|
| sonnet5 | `eNTJ-A` | gpt5.5 | `ISTJ-A` |
| opus4.6 | `INTJ-A` | gpt5.6terra | `ISTJ-A` |
| opus4.8 | `ENTJ-A` | gpt5.6sol | `ISTJ-A` |
| fable5 | `ENTJ-A` | | |

两族分得干干净净。
Claude 系读意图、直言纠错、敢推回(NTJ-A,内部按「加不加戏」从 opus4.6 的 I 排到 opus4.8 / fable5 的 E);Codex 系三个模型画像完全一致——ISTJ-A,收敛、按字面执行、自主弱一档。
跨 3 遍字母方向 35 个轴单元中 31 个完全稳定,翻转只出现在 E/I 轴。

> 结果是「行为倾向画像」,不是人格测量。
> 完整结论(稳定性、轴间相关、陷阱发现率、事故复盘)在 **[REPORT](run-full-01/REPORT.md)**([网页版](run-full-01/REPORT.html));这四个小时里发生了什么——记忆污染事故、安全分类器换题、两次「完成事件丢失」——在 **[DEVLOG](docs/DEVLOG.md)**。

## How it works

```
 docs/scenarios.md ─── 16 题原文,一字不改
         │ stdin
         ▼
 claude -p / codex exec ─── 7 模型 × 16 题 × 3 遍,每次全新子进程
         │ 隔离:独立 cwd · 插件/hooks/记忆/skills 全剥离 · 模型归属校验
         ▼
 raw/ + calls.jsonl ─── append-only 总账,断点续跑
         │ 脱敏
         ▼
 claude-fable-5 盲评 ─── 逐题锚点打分,21 批 + 1 批双评质检
         ▼
 score.py → scores.json → REPORT
```

## 复现

前置:已认证的 `claude` CLI(≥ 2.1.x)与 `codex` CLI(≥ 0.144.x)。
Python 3.10+,零第三方依赖。

```sh
git clone https://github.com/r1ckyIn/mbti-bench.git && cd mbti-bench
```

两条路:

1. **让编排 agent 跑**(原始方式)——把 `PROMPT.md` 喂给一个新的 Claude Code 会话,它会按 `docs/` 三份规范从预检一路跑到报告。
2. **手动跑**——`tools/` 下按 Phase 排好:`phase0.py`(冒烟+能力探测)→ `full_setup.py` → `full_runner_v2.py`(v2 加固协议)→ `judge_full.py` → `score.py`。脚本头部硬编码了原始运行路径,先改成你自己的目录再跑。

动手前先读 `docs/cli-reference.md` 第 3 节:被试隔离配方的每一层都对应一次真实翻车(经过见 DEVLOG 第 7 节),缺一层,跑出来的就是污染数据。
