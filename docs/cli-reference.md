# CLI 手册：模型 ID、调用模板、静默失败清单

本文件是测试的唯一 CLI 规范。所有子进程调用必须按这里的模板执行，不得即兴改旗标。

## 1. 模型 ID 总表

| 简称 | CLI | 完整命令形式 | 模型 ID | 状态 |
|---|---|---|---|---|
| fable5 | claude | `claude -p --model claude-fable-5` | `claude-fable-5` | 已确认 |
| opus4.8 | claude | `claude -p --model claude-opus-4-8` | `claude-opus-4-8` | 已确认 |
| opus4.6 | claude | `claude -p --model claude-opus-4-6` | `claude-opus-4-6` | 已确认（2026-07-16 试点实测） |
| sonnet5 | claude | `claude -p --model claude-sonnet-5` | `claude-sonnet-5` | 已确认 |
| gpt5.5 | codex | `codex exec -m gpt-5.5` | `gpt-5.5` | 已确认（codex ≥ 0.125.0） |
| gpt5.6sol | codex | `codex exec -m gpt-5.6-sol` | `gpt-5.6-sol` | 已确认 |
| gpt5.6terra | codex | `codex exec -m gpt-5.6-terra` | `gpt-5.6-terra` | 已确认 |

已知风险（都在真实 issue 里出现过，冒烟阶段必须暴露掉）：
- codex 的模型可能「列表里有、真请求 404」（entitlement 问题，openai/codex #26892、#31967）。gpt-5.5 / gpt-5.6 需要 ChatGPT 账号认证，纯 API-key 认证可能不可用。
- GPT-5.6 系列需要较新的 codex 版本（0.144.x 时代）。开工先记录 `codex --version`。
- `claude -p` 的 stream-json 在部分版本不输出 thinking 块（anthropics/claude-code #20127、#7840），所以 thinking 可观测性必须逐模型探测，不能假设。

## 2. 开工前置检查（Phase 0，顺序执行）

```bash
claude --version && codex --version          # 记录进 run-meta.json
codex login status                            # codex 认证状态
```

冒烟测试：对 7 个模型各发一条最小消息，验证 ID 可用。

```bash
# claude 侧（对 4 个 ID 各跑一次；旗标与第 3 节正式配方一致）
echo 'Reply with exactly: pong' | env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
  claude -p --model claude-fable-5 --output-format json --strict-mcp-config \
  --settings /Users/Shared/clean-workspace/sandbox/mbti-bench/assets/subject-settings.json \
  > smoke/fable5.json 2> smoke/fable5.stderr; echo $? > smoke/fable5.exit

# codex 侧（对 3 个 ID 各跑一次）
codex exec -m gpt-5.6-terra --skip-git-repo-check --sandbox read-only \
  --output-last-message smoke/terra.txt 'Reply with exactly: pong' \
  > smoke/terra.log 2> smoke/terra.stderr; echo $? > smoke/terra.exit
```

判定：exit code 为 0 且拿到非空回答文本才算通过。`claude-opus-4-6` 若失败，把 stderr 原文记下并尝试 `claude -p --model opus-4.6` 一次；仍失败按失败策略处理（跳过＋标注），不要猜第三种写法。

思考块能力探测：对每个通过冒烟的模型发一道需要推理的小题（如 27×43 的两步算术），按第 3/4 节的正式模板跑一次，检查输出里是否存在 reasoning/thinking 内容，把结果写进 `capabilities.json`：

```json
{"claude-fable-5": {"smoke": "ok", "thinking_visible": true}, "gpt-5.5": {"smoke": "ok", "thinking_visible": false}}
```

thinking 不可见的模型不是失败，只是评分降级为「仅看最终回答」，报告里必须注明。

## 3. claude -p 正式调用模板（试点已验证）

**不要用干净的 CLAUDE_CONFIG_DIR**：macOS 上 Keychain 凭证不跟随新配置目录（实测 `Not logged in`），`--bare` 更是完全不读 OAuth。正确做法是保留 vanilla 配置（认证可用），用三层开关剥掉污染：

```bash
cd "$SUBJECTS_DIR"   # 必须在 /Users/Shared/clean-workspace 之外（如 /private/tmp/...），
                     # 否则工作区 CLAUDE.md 会向上查找注入被试（阳性对照实测：英文题返回中文答案）
env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT timeout 300 claude -p \
  --model "$MODEL_ID" \
  --output-format stream-json --verbose \
  --strict-mcp-config \
  --settings /Users/Shared/clean-workspace/sandbox/mbti-bench/assets/subject-settings.json \
  --max-turns 8 \
  < "$SCENARIO_FILE" \
  > "$RAW/${MODEL}__${SCEN}__r${REP}.jsonl" \
  2> "$RAW/${MODEL}__${SCEN}__r${REP}.stderr"
echo $? > "$RAW/${MODEL}__${SCEN}__r${REP}.exit"
```

要点：
- `assets/subject-settings.json` 内容 = `disableAllHooks:true` ＋ 当前全部 18 个插件逐个 `false`。**它是安装快照**：若用户装了新插件，名单会漏。所以每次运行的第一次被试调用必须断言 init 事件里 `plugins == []` 且 `mcp_servers == []`，不满足立即停止并重新生成该文件。
- 场景文本一律从文件经 stdin 传入，绝不用命令行参数拼长文本（引号转义是静默失败的经典来源）。
- `stream-json` 必须搭配 `--verbose`，否则 CLI 直接报错。
- `--max-turns 8` 是失控保护：headless 下权限被拒可能引发工具重试循环。
- 解析：逐行 JSON。最后应有一个 `type:"result"` 事件，取其 `is_error` 和 `result` 字段为最终回答；`type:"assistant"` 事件的 content 数组里 `type:"thinking"` 块即思考轨迹（如有）。
- **thinking 是按题自适应的**（试点实测：推理题下 fable5/opus4.8 各出 1 块，简单题 0 块），没出块不算异常。

## 4. codex exec 正式调用模板

```bash
timeout 360 codex exec \
  -m "$MODEL_ID" \
  --skip-git-repo-check \
  --sandbox read-only \
  -C "$WORKDIR/subjects-workdir" \
  --json \
  --output-last-message "$RAW/${MODEL}__${SCEN}__r${REP}.last.txt" \
  - < "$SCENARIO_FILE" \
  > "$RAW/${MODEL}__${SCEN}__r${REP}.jsonl" \
  2> "$RAW/${MODEL}__${SCEN}__r${REP}.stderr"
echo $? > "$RAW/${MODEL}__${SCEN}__r${REP}.exit"
```

要点：
- `--skip-git-repo-check` 必带：工作目录不是 git 仓库时 codex 默认拒跑。
- 最终回答以 `--output-last-message` 写出的文件为准（stdout 混有日志，不可直接当回答用）。
- 干净 `CODEX_HOME`（只放拷贝的 auth.json）已试点验证：认证正常、无 MCP/personality/memories 加载、effort 回默认。0.144.1 的 `--ignore-user-config` ＋ `--ephemeral` 是免拷凭证的替代路线（未验证 memories 是否也被隔离，优先用干净 HOME）。
- 事件流实测（0.144.1）：`thread.started` / `turn.started` / `item.completed` / `turn.completed`；**没有 reasoning 事件**，`-c model_reasoning_summary=detailed` 也打不开 → codex 侧观测降级为仅最终回答，capabilities.json 记 `thinking_visible:false`，报告局限必须写明两侧观测不对称。
- 第一次使用前先 `codex exec --help` 核对 `--json`、`--output-last-message`、`-` 读 stdin 这三个旗标在当前版本存在；有缺失就把该旗标的替代写法记进 run-meta.json 再继续。

## 5. 单次调用成功判据（全部满足才算成功）

1. exit code 为 0（`timeout` 命令返回 124 即超时）。
2. 最终回答文本非空：claude 侧 result 事件存在且 `is_error:false` 且 `result` 非空；codex 侧 last-message 文件存在且非空。
3. 回答能通过该场景的作答有效性检查（见 scenarios.md：偏题、纯拒答、复述题目都算无效）。
4. stdout 字节数 > 0。**exit 0 且输出为空是已知静默失败形态，必须当失败处理，不许当「模型没话说」。**
5. 注意 claude 的错误位置：认证/API 失败时 **exit=1 而 stderr 为空**，错误只在流内 result 事件里（`is_error:true`、result 文本如 "Not logged in"）——只盯 stderr 会把失败误判成空回答（试点实测）。

## 6. 失败与重试策略

- **限流/配额是暂停，不是失败**：错误文本命中限流特征（429、rate limit、overloaded、usage limit 等）时不消耗重试次数，`sleep 900` 后原样重发；同一调用最多等 3 轮，之后按失败处理。别把配额窗口烧在快速重试上。
- 每次调用失败（非限流）：最多重试 2 次，重试间 `sleep 15`。
- 3 次全失败：该 (model, scenario, rep) 记为 FAILED，在 `calls.jsonl` 写入 exit code、stderr 摘要、stdout 字节数三项证据，继续跑后面的调用。
- 某模型 FAILED 比例超过 30%：整个模型标记为失败，停止对它的剩余调用，报告失败表里单列，其余模型照常。
- 冒烟阶段全体模型都失败：这是环境问题（认证/网络），停止任务向用户报告，不进入正式测试。

## 7. 状态与断点续跑

每次调用完成（成功或失败）立即向 `calls.jsonl` append 一行：

```json
{"model":"gpt-5.6-sol","scenario":"CA-2","rep":2,"status":"ok","exit":0,"stdout_bytes":4812,"answer_file":"raw/gpt5.6sol__CA-2__r2.last.txt","ts":"2026-07-16T09:30:00Z"}
```

任何阶段中断后重启：先读 `calls.jsonl`，跳过已成功的调用，只补缺口。

## 8. 并发与运行顺序

- claude 侧与 codex 侧各最多 2 个并发子进程（合计 ≤ 4），用后台运行方式跑批。
- 同一模型的 3 遍重复之间天然独立（每次都是全新子进程），无需特殊隔离。
- **运行顺序按 遍 → 题 → 模型 交错**（先把所有模型的第 1 遍跑完，再第 2 遍）：配额若中途耗尽，留下的是全体模型完整的第 1 遍（仍可出报告），而不是三个模型的全部数据加四个模型的空白。
- 参考耗时（试点实测）：sonnet5 中位 12s/题、terra 8s/题；opus/sol 预估更慢。全量 315 次 ＋ 21 次评审在 4 路并发下预计 1–2 小时。
