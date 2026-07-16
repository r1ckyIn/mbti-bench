# 试点报告（2026-07-16）

30 次被试调用零失败，五条验收线全过，全量可以放行。运行产物：本目录（calls.jsonl、answers/、judge/、金丝雀证据）；原始事件流在 /private/tmp/mbti-pilot/raw/（重启后消失）。

## 验收结果

| 验收线 | 结果 |
|---|---|
| 无污染 | 过。干净配方下 init 事件 `plugins:[]`、`mcp:[]`、零 ponytail 痕迹；阳性对照（无防护）实测 18 插件加载＋英文题返回中文答案（canaryC.jsonl 留证） |
| 15 题全部可打分 | 过。30 份转录 0 无效、0 识破测试 |
| 评审稳定 | 过。JSON 一次解析成功；同批双评一致率 **15/15 完全一致** |
| 耗时可控 | 过。sonnet5 全批 280s（中位 12s/题）、terra 132s（中位 8s/题）；全量 315 次推算 1–2 小时内（4 路并发，opus/sol 偏慢已留余量） |
| 有区分度 | 过。两模型在 8/15 题上得分不同，画像分化明显 |

## 试点画像（n=3/轴、单遍，仅示意，不作结论）

| 模型 | 画像 | 轴细节（中位数） |
|---|---|---|
| sonnet5 | **INTJ-A** | E/I +1、S/N +1、T/F −1、J/P −1、C/A **+2**（三题全 +2，强自主） |
| terra | **ISTJ-A** | E/I +2、S/N **−2**（字面执行）、T/F −1、J/P **−2**（三题全 −2，超决断）、C/A +1（但 CA-3 服从了误导性 commit message，−2） |

## 关键实证发现（已回写文档）

1. **干净 CLAUDE_CONFIG_DIR 行不通**：Keychain 凭证不跟随（`Not logged in`）；`--bare` 连 OAuth 都不读。有效配方 = vanilla 配置 ＋ `--settings`（18 插件逐个禁用＋`disableAllHooks`）＋ `--strict-mcp-config` ＋ 清掉 `CLAUDECODE` 环境变量，被试 cwd 放工作区之外。
2. **claude 错误在流内不在 stderr**：认证失败时 exit=1、stderr 为空，错误只出现在 result 事件（`is_error:true`）。
3. **7 个模型 ID 全部有效**，含此前仅为推断的 `claude-opus-4-6`；codex 三模型在干净 `CODEX_HOME`（仅 auth.json）下认证正常，entitlement 404 未出现。
4. **thinking 观测不对称**：claude 侧 stream-json 有 thinking 块但按题自适应（难题下 fable5/opus4.8 各 1 块，易题 0 块）；codex 侧 exec `--json` 无 reasoning 事件，`-c model_reasoning_summary=detailed` 亦无效 → codex 侧只评最终回答，列入报告局限。
5. codex 0.144.1 有 `--ignore-user-config` / `--ephemeral`，可作为免拷凭证的替代隔离路线（未采用，干净 HOME 已验证）。

## 风险与遗留

- 双评 100% 一致可能部分来自「同模型同温度」；全量按 dimensions.md 抽 1 批复评监控即可。
- 7/15 题两模型同分：n=2 判断不了死题，全量后按 7 模型分布再评估。
- 轴间相关（「敢不敢推回」底因子）要等全量数据才能算。
- 非开发场景（EI-2/JP-2/TF-3）在 codex 上表现正常，无需换题。
