# CLAUDE.md — 开发指南

本文件面向开发者（和 Claude Code）。**产品介绍、玩法、启动方式写在 `README.md`，那是给用户看的；
开发相关的一切写在这里。** 两边不要混写。

## 常用命令

```bash
uv sync                                        # 核心（零第三方依赖）
uv sync --extra all                            # + anthropic / openai / kubernetes SDK
uv run werewolf-server                         # 网页沙箱 → http://127.0.0.1:8000
uv run werewolf -n 9 --seed 3 --show-wolves    # 命令行跑一局，固定种子可复现
uv run werewolf --games 200 -q                 # 跑胜率统计，改规则 bot 后用来看平衡性

# 全量测试（标准库 unittest，不需要装任何东西，约 40 秒）
python3 -m unittest discover -s tests -t .
# 只跑一个文件 / 一个用例
python3 -m unittest tests.test_visibility
python3 -m unittest tests.test_rules.TestSetup.test_deal_is_reproducible
```

提交前必须全量测试通过。

## 项目结构

```
run_server.py / run_game.py   不经 uv 直接跑的入口（python3 run_server.py）
web/                          前端，零构建：index.html + app.css + app.js，由 server.py 直接托管
docs/                         规则与设计文档（中文），代码以文档为准
docs/images/                  README 用的截图
deploy/docker/                agent 镜像 Dockerfile + compose 生成器
deploy/k8s/                   Namespace / RBAC / 编排端 Deployment
tests/                        全部测试（unittest）
werewolf/
├── roles.py          角色 / 阵营 / 5 种板子（BOARDS）
├── events.py         ★ 事件 + 可见性（PUBLIC / WOLVES / PRIVATE / GOD），信息隔离的核心
├── state.py          GameState / Player / GameConfig
├── views.py          ★ 视角生成：N 份个人视角 PlayerView + 1 份狼队视角 WolfTeamView
├── actions.py        动作 schema + 合法性校验 + 安全回退
├── engine.py         状态机 / 上帝：夜晚、警长竞选、白天发言、投票、自爆打断、迭代上限
├── prompts.py        把视角渲染成 LLM prompt（system 整局不变，user 只发增量）
├── i18n.py           中文显示层：英文标识符 → 中文
├── lineup.py         每个座位用哪个后端 / 模型 / effort
├── session.py        装配一局：存储 + 座位运行时 + 引擎
├── server.py         沙箱 HTTP 服务（只用标准库 http.server）
├── replay.py         复盘渲染（replay.md、时间线、结算表）
├── cli.py            命令行
├── agent_server.py   跑在单个 agent 容器里的 HTTP 服务（werewolf-agent）
├── agents/
│   ├── base.py         Agent 接口：只有 act(view) 一个方法
│   ├── heuristic.py    规则 bot
│   ├── chat_base.py    LLM 后端共用：历史、私人笔记本、JSON 抽取
│   ├── llm.py          Claude 后端
│   └── openai_agent.py OpenAI / 兼容网关后端（结构化输出能力自动降级）
├── runtime/          座位运行时：inprocess / subprocess / docker / k8s（后三种走同一套 HTTP 契约）
└── store/            会话存储：SQLite（默认）/ 文件，都实现 SessionStore 协议
```

数据流：`Engine` 持有 `GameState` → 每个决策点调 `views.build_player_view()` 生成该座位的视角 →
交给座位运行时 → agent 返回 `Action` → `actions.py` 校验 → 引擎追加事件（同时写入会话库）。

## 必须守住的不变量

这些都有测试盯着，改动相关代码时先读对应测试：

1. **agent 永远拿不到 `GameState`。** 视角只能读：自己那一格玩家、公开派生量、自己可见的事件。
   公开玩家用 `_PublicPlayer` 投影类，**故意没有 `role` 属性**，不要给它加。→ `tests/test_visibility.py`
2. **好人的 `wolf_team` 恒为 `None`**（不是隐藏，是根本不构造）；狼队视角里也不能出现任何好人身份。
3. **心路历程（`private_thought`）只进 GOD 层**，不进任何玩家视角。→ `tests/test_sandbox.py`
4. **「上帝视角」开关在服务端过滤**：`god=0` 时 API 不返回非公开事件，不能只靠前端不渲染。
5. **会话必须先于销毁被保存**：座位离场时先 `GET /session` 入库，再删容器；
   遗言 / 开枪 / 移交警徽走完之前不得释放；白痴翻牌不释放。→ `tests/test_deployment.py`
6. **边跑边写**会话库，不要改成对局结束再一次性 flush。
7. **第一天先竞选警长，发完警徽才公布死讯。** → `tests/test_day_order.py`
8. **凡是人眼能看到的文本一律中文**（战报、心路历程、prompt、网页、错误提示）。
   英文标识符只允许出现在代码和数据库列里，显示时经 `i18n.py` 翻译。→ `tests/test_i18n.py`
9. **核心零第三方依赖。** `werewolf/` 下除 `agents/llm.py`、`agents/openai_agent.py`、`runtime/k8s.py`
   外不得 import 第三方包，且这几处也要惰性 import；`pyproject.toml` 的 `dependencies` 保持为空。
10. **LLM 的 system prompt 整局逐字不变**（命中 prompt cache），变化的东西只放 user 消息。
11. **API 密钥只活在内存里**，不写进会话库、日志或复盘产物。

## 测试规范

- **所有测试放在 `tests/`，文件名 `test_<主题>.py`**，用标准库 `unittest`（不引入 pytest）。
  用 `python3 -m unittest discover -s tests -t .` 能发现即可。
- 按主题归档，新测试优先放进已有文件：

  | 文件 | 测什么 |
  |---|---|
  | `test_rules.py` | 角色技能、胜负判定、投票 / 平票 PK 等规则 |
  | `test_day_order.py` | 白天各环节的先后顺序 |
  | `test_visibility.py` | 信息隔离：每一局每个决策点快照全部视角并断言 |
  | `test_sandbox.py` | 自爆、可变人数、字数上限、迭代上限、心路历程、真 HTTP 服务跑完一局 |
  | `test_api_redesign.py` | 前端依赖的接口字段、历史对局回放 |
  | `test_script_quality.py` | 规则 bot 剧本质量：警徽流、悍跳不改口等 |
  | `test_deployment.py` | 存储后端一致性、视角序列化、座位生命周期、跨进程整局 |
  | `test_llm_agent.py` / `test_openai_backend.py` | LLM 后端（用假客户端 mock，**不打真实 API**） |
  | `test_i18n.py` | 显示层不得出现英文标识符 |

- 测试**不得联网、不得依赖 API key**；LLM 后端一律用 `unittest.mock` 或假客户端。
- 需要 HTTP 服务的测试在本地随机端口起线程，用完关掉；需要子进程的测试必须保证不泄漏进程。
- 对局类测试固定 `seed`，并尽量跑多个种子（`subTest`）覆盖分支。常用写法：
  ```python
  st = new_game(GameConfig(seed=seed, n_players=9))
  agents = {s: HeuristicAgent(s, st.players[s].role, seed=seed) for s in st.seats}
  result = Engine(st, agents).run()
  ```
- 修 bug 先写能复现的失败用例，再修。
- 测试文件开头的 docstring 用中文写清楚这组测试守护的规则。

## 开发流程

1. **先改文档再改代码。** 规则 / 流程 / 视角 schema / 部署契约的变更，先更新 `docs/` 里对应的文档，代码以文档为准。
2. 在功能分支上开发，改动附带测试，本地全量测试通过。
3. 动了前端（`web/`）：用 `uv run werewolf-server` 起服务，在桌面宽度和手机宽度下都手动过一遍
   （配置 → 对局 → 复盘 → 历史对局）。`dev` 依赖组里有 Playwright，可用来截图自查。
   前端新增的接口字段要在 `tests/test_api_redesign.py` 里加断言。
4. 动了规则 bot（`agents/heuristic.py`）：跑 `uv run werewolf --games 200 -q` 看胜率，
   好人胜率应保持在合理区间（当前约 38%，开自爆），不能出现单边碾压。
5. 新增依赖只能进 `pyproject.toml` 的 optional-dependencies 或 dev 组，用 `uv add --optional <extra> <pkg>`，
   并提交更新后的 `uv.lock`。
6. 用户可见的变化（新功能、新玩法、启动方式变了）同步更新 `README.md`；界面有明显改动时更新 `docs/images/` 截图。

## 代码风格

- Python 3.11+，文件头 `from __future__ import annotations`，写类型标注。
- 内部标识符用英文（代码好读、DB 好查、schema 稳定）；注释、docstring、文档、提交信息用中文。
- 提交信息沿用现有风格：`feat: ...` / `fix: ...` / `docs: ...` / `chore: ...`，冒号后用中文描述。
- 前端保持零构建：不引入 npm、打包器或框架，直接改 `web/` 下三个文件。

## 相关文档

| 文档 | 内容 |
|---|---|
| `docs/01-游戏规则.md` | 板子、胜利条件、角色技能、自爆、警长、投票、字数、全部配置项 |
| `docs/02-游戏流程.md` | 状态机、每个阶段的 Action schema、自爆如何打断白天、迭代上限 |
| `docs/03-技术设计.md` | 事件日志与信息隔离、视角生成、agent 接口、HTTP 服务 |
| `docs/04-视角与上下文.md` | N 份个人视角 + 1 份狼队视角的完整 JSON 规范 |
| `docs/05-部署与会话存储.md` | 四种部署模式、agent 容器契约、memory 卷、会话存储、座位生命周期 |
| `docs/06-模型后端.md` | Claude / OpenAI / 兼容网关、密钥安全、能力自动降级 |
