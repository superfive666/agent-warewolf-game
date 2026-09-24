# 狼人杀 Agent 沙箱 · Agent Werewolf

一个能跑起来的沙箱：**在网页上选人数、选每个座位用什么 agent 和什么模型 → 点开始 →
整局自动跑完 → 输出一份含每个 agent 心路历程的详细复盘。**

```bash
python3 run_server.py      # 打开 http://127.0.0.1:8000
```

零依赖即可运行（内置规则 bot）；想让真正的 Claude 来打，再装 `anthropic` 并配 API key。

支持四种部署：同进程 / 每座位一个进程 / 每座位一个 Docker 容器 / 每座位一个 k8s Pod。
**玩家离场（被刀、被票、自爆）立刻销毁容器，但会话在销毁之前就已入库，永远留得住。**

---

## 它能做什么

- **可变板子**：6 / 8 / 9 / 10 / 12 人，全部屠边局
- **每个座位单独配 agent**：规则 bot / Claude Opus 5 / Sonnet 5 / Haiku 4.5，还能分别设思考强度
- **完整规则**：警长竞选（上警→警上发言→退水→投票→警徽移交/撕毁）、狼人夜间协商刀人、
  女巫解药毒药、预言家验人、猎人开枪、白痴翻牌、平票 PK、**狼人自爆**
- **像真人一样发言**：每次发言有字数上限（默认 450 字 ≈ 真人讲 2 分钟），超长会被打回重说
- **思考不设限、迭代有上限**：agent 想多久想多长都行，但每个决策点最多问它 3 次
- **开局后全自动**：点一次开始，整局跑到分出胜负
- **详细复盘**：战报 + 每个 agent 在每个决策点的内心想法 + 完整会话存档 + N+1 份上下文可下载
- **四种部署**：同进程 / 进程 / Docker 容器 / k8s Pod，换一个参数就切
- **会话永久保留**：边跑边写进 SQLite，容器销毁前先抓会话；agent 的私有笔记挂在比容器活得久的卷上

---

## 快速开始

### 网页沙箱（推荐）

```bash
python3 run_server.py                 # → http://127.0.0.1:8000
python3 run_server.py --port 9000     # 换端口
```

1. 选人数（6/8/9/10/12）
2. 逐座位选后端和模型，或者用「快速套用」一键刷全桌
3. 高级选项里可以设种子、发言字数上限、最大迭代次数、关掉警长或自爆
4. 点「开始游戏」——之后全自动，不需要再点任何东西
5. 跑完自动弹出复盘：战报 / 心路历程 / 原始数据三个页签

对局进行中可以勾「上帝视角」，实时看到狼人频道和各神的私聊。

### 命令行

```bash
python3 run_game.py                        # 12 个规则 bot 打一局
python3 run_game.py -n 9 --seed 3          # 9 人局，固定牌型
python3 run_game.py --show-wolves          # 开上帝视角看狼人频道
python3 run_game.py --games 200            # 跑 200 局统计胜率
python3 run_game.py --no-explode           # 禁止自爆
python3 run_game.py --max-speech-chars 300 # 发言限制更短

# 真 LLM
pip install -r requirements-llm.txt && export ANTHROPIC_API_KEY=...
python3 run_game.py --backend llm --show-thoughts
python3 run_game.py --backend llm --llm-seats 1,2,3   # 3 个 LLM + 9 个 bot，先小成本试

# 测试
python3 -m unittest discover -s tests -t .
```

> ⚠️ 一局 12 人对局大约需要 **150+ 次模型调用**。先用 `--llm-seats` 或网页里只给
> 几个座位配 Claude 来试水。

---

## 文档

规则和设计都写在 `docs/`，**代码以文档为准**：

| 文档 | 内容 |
|---|---|
| [`docs/01-游戏规则.md`](docs/01-游戏规则.md) | 5 种板子、胜利条件、6 种角色技能、**自爆**、警长、投票、发言字数、全部配置项 |
| [`docs/02-游戏流程.md`](docs/02-游戏流程.md) | 完整状态机、每个阶段的 Action schema、自爆如何打断白天、迭代上限与心路历程 |
| [`docs/03-技术设计.md`](docs/03-技术设计.md) | 事件日志与信息隔离、视角生成、agent 接口、沙箱 HTTP 服务 |
| [`docs/04-视角与上下文.md`](docs/04-视角与上下文.md) | **N 份个人视角 + 1 份狼队视角的完整 JSON 规范** |
| [`docs/05-部署与会话存储.md`](docs/05-部署与会话存储.md) | 四种部署模式、agent 容器契约、私有 memory 卷、会话存储（DB vs 文件）、座位生命周期 |

---

## 信息隔离是怎么做到的

整局游戏就是**一条只追加的事件流**，每条事件带一个可见性标签：

| 标签 | 谁能看到 |
|---|---|
| `PUBLIC` | 全部玩家（含已出局者） |
| `WOLVES` | 全部狼人（含已出局的狼人） |
| `PRIVATE` | `visible_to` 里列出的座位 |
| `GOD` | 谁都看不到，只进复盘（心路历程就在这一层） |

某个座位的"视角"就是这条流过滤后的子序列。过滤逻辑一共 4 行：

```python
def visible_to_seat(event, seat, is_wolf):
    if event.audience is Audience.PUBLIC:  return True
    if event.audience is Audience.WOLVES:  return is_wolf
    if event.audience is Audience.PRIVATE: return seat in event.visible_to
    return False   # GOD
```

**agent 永远拿不到 `GameState`。** 视角构造函数只被允许读三样东西：自己那一格玩家、
公开派生量、以及自己可见的事件。为了防止手滑，公开玩家是一个叫 `_PublicPlayer` 的投影类，
它**根本没有 `role` 属性**——想读别人的身份会直接 `AttributeError`，而不是静默泄密。

网页端的「上帝视角」开关也是**服务端**过滤的：`god=0` 时 API 根本不返回非公开事件，
不是靠前端不渲染。

### N+1 份上下文

| 视角 | 份数 | 说明 |
|---|---|---|
| `PlayerView` 个人视角 | **N** | 每座位一份：身份区 + 公开状态 + 我可见的时间线 + 本轮可做的动作 |
| `WolfTeamView` 狼队视角 | **1** | 全体狼人**共享同一份**，作为区块挂在他们的个人视角上 |

好人的 `wolf_team` 字段恒为 `null`——不是被隐藏，是根本没有被构造。

狼队视角里**也没有**任何好人的真实身份。狼人只知道"我们几个是狼"，其余人对他们同样是黑的。
里面的 `intel` 情报每一条都只来自狼人真实可观测的事实，比如：

- `witch_antidote_used: true` ← "我们刀了 3 号，但天亮 3 号没死" —— 这本账只有狼人对得上
- `suspected_god_seats` ← 纯粹按"谁公开起跳了神职"排序，**不是**上帝告诉他们谁是神

### 测试保证

`tests/test_visibility.py` 在**每一局的每一个决策点**都快照全部视角，跑 8 条断言：

1. 非狼玩家的时间线里不含任何狼人频道事件
2. 不含 `visible_to` 不包含自己的私有事件
3. 不含别人的真实身份（白痴翻牌、狼人自爆等规则性公开除外）
4. 好人的 `wolf_team` 恒为 `None`，狼人的恒非空
5. 狼队视角不含任何好人身份，也不含"还剩几个神"这种上帝信息
6. 投票必须收齐后才公布——同一轮里先投和后投的人看到的票型完全相同
7. 预言家的验人结果只出现在预言家自己的视角里
8. 女巫的刀口告知只出现在女巫自己的视角里

外加：
- `tests/test_sandbox.py` —— 心路历程只活在 GOD 层、自爆规则、字数上限、迭代上限，
  以及起一个真的 HTTP 服务跑完一局、检查每个前端要用的接口
- `tests/test_script_quality.py` —— 警徽流必报/不改口/兑现、悍跳狼不得改口、
  一队至多一个悍跳、第一天发言必须出现在后期 prompt 里
- `tests/test_deployment.py` —— 两种存储后端行为一致、视角序列化无损、
  **会话必须先于销毁被保存**、每个座位恰好释放一次且原因正确、
  遗言/开枪/移交警徽之前不得释放、跨进程跑完整局且不泄漏进程

```
$ python3 -m unittest discover -s tests -t .
Ran 97 tests in 40s
OK
```

---

## 两套 agent 后端

| 后端 | 说明 |
|---|---|
| `heuristic`（默认） | 纯 Python 规则 bot，零依赖。会悍跳、跟查杀、做站边分析、在压力下自爆，并且会输出自己的心路历程。毫秒级跑完一局。 |
| `llm` | 调 Claude Messages API。**每个座位可以单独指定模型和 effort**，每个座位一个独立会话，座位之间没有任何共享对象。 |

两者走**完全相同的信息通道**——都只拿到 `PlayerView`，没有后门。可以任意混搭。

LLM 后端的上下文组装：

- **system 整局逐字不变**（规则 + 身份卡 + 打法提示 + 输出约束）→ 命中 prompt cache
- **user 只发增量**（自上次决策以来的新事件）+ 当前局势摘要 + 本轮能做什么
- **输出用 JSON Schema 硬约束**（`output_config.format`），不靠"请输出 JSON"这种软约束
- **`thinking: adaptive`**，思考长度不设限；约束的是**迭代次数**而不是思考深度
- 每次决策都有一个 `private_thought`，只进复盘，**不进任何玩家的视角**

规则 bot 之间的对局，100 局统计好人胜率约 **38%**（开自爆），双方都能赢，不存在单边碾压。

---

## 部署与会话存储

`agent 跑在哪` 和 `会话存在哪` 耦合在一条约束上：
**玩家离场就销毁容器，但会话必须保留下来复盘。**

| 部署模式 | 一个座位 = | 隔离 |
|---|---|---|
| `inprocess` | 一个 Python 对象 | 无，最快 |
| `subprocess` | 一个 OS 进程 | 进程 + 独立 memory 目录 |
| `docker` | 一个容器 | 容器 + cgroup 限额 + 独立卷 |
| `k8s` | 一个 Pod | Pod + 资源限额 + 独立 PVC |

后三种走**完全相同的 HTTP 契约**，所以 CI 用 `subprocess` 就能验证容器路径的
全部逻辑（起 → 就绪 → act → 抓会话 → 销毁），不需要真的有集群。

容器里跑的是一个只认识自己座位的 agent：它拿不到 `GameState`，编排端把
`PlayerView` 序列化发过去，它在自己那边重建视角、读自己的私人笔记本、调自己的模型。

**会话存哪**：两个都要，按数据形状分 ——

- **SQLite（默认）** 存事件流、每一轮的动作和心路历程、agent 的对话历史。
  要跨局查询、要事务性追加；k8s 下 N 个 Pod 连一个 DB endpoint 比挂 RWX 共享卷简单。
  换 Postgres 只要照着 `SessionStore` 协议再写一个实现。
- **持久卷** 存 agent 自己写的 memory 文件。**卷活得比容器长**，
  k8s 的 RBAC 里故意没给编排端删 PVC 的权限。

两条硬规则：**边跑边写**（不是跑完一次性 flush，否则崩了就什么都不剩）、
**销毁前先抓会话**（顺序反了就永远拿不回来，有专门的测试盯着这个调用顺序）。

死了不等于能立刻拆 —— 被票出的还要留遗言、猎人还要开枪、警长还要移交警徽，
全部走完才释放。白痴翻牌不释放，因为他还活着还能发言。

详见 [`docs/05-部署与会话存储.md`](docs/05-部署与会话存储.md)。

## 复盘里有什么

网页上跑完自动展示，命令行则写到 `runs/<时间戳>/`：

```
runs/<时间戳>/
├── config.json       板子 / seed / 阵容配置
├── events.jsonl      全部事件（含 GOD 级），完整上帝视角
├── result.json       胜负、真实身份表、票型、验人、用药、自爆记录
├── replay.md         详细战报
├── thoughts.json     每个 agent 每个决策点的心路历程
└── views/
    ├── seat_01.json … seat_NN.json   N 份个人视角
    └── wolf_team.json                1 份狼队视角
```

`replay.md` 的结构：

1. **结果** — 谁赢了、为什么赢
2. **身份表** — 每个座位的身份、阵营、用的哪个 agent、怎么死的
3. **关键节点** — 按天列出每次出局和自爆
4. **神职与狼队的每一手** — 预言家每晚验了谁验出什么（并标注实际身份）、女巫用药、狼队每晚刀谁及结果
5. **投票记录** — 每一轮的完整票型和计票
6. **全过程** — 带可见性标记的完整事件流
7. **心路历程** — 按座位分组，每个决策点的内心想法 + 实际动作，含被判非法的尝试和自我修正
8. **统计** — 事件数、决策数、重试次数、自爆次数

---

## 目录结构

```
run_server.py         Web 沙箱入口
run_game.py           命令行入口
web/                  前端（零构建：index.html + app.css + app.js）
deploy/
├── docker/           Dockerfile + compose 生成器
└── k8s/              Namespace / RBAC / 编排端 Deployment
werewolf/
├── roles.py          角色 / 阵营 / 5 种板子
├── events.py         ★ 事件 + 可见性模型（信息隔离的全部实现）
├── state.py          GameState / Player / GameConfig
├── views.py          ★ 视角生成：N 份个人视角 + 1 份狼队视角
├── actions.py        动作 schema + 合法性校验 + 安全回退
├── prompts.py        把视角渲染成 LLM prompt
├── engine.py         状态机 / 上帝
├── lineup.py         每个座位用哪个后端、哪个模型
├── server.py         沙箱 HTTP 服务（只用标准库）
├── replay.py         复盘渲染
├── cli.py            命令行
├── session.py        一局对局的装配：存储 + 座位运行时 + 引擎
├── agent_server.py   跑在【单个 agent 容器】里的服务
├── store/            会话存储（SQLite / 文件 / 自己实现）
├── runtime/          座位运行时（同进程 / 进程 / Docker / k8s）
└── agents/
    ├── base.py       Agent 接口（只有 act(view) 一个方法）
    ├── heuristic.py  规则 bot
    └── llm.py        Claude API 后端（支持私有 memory 目录）
```

## 依赖

- **规则 bot + 网页沙箱**：只需要 Python 3.11+，**零第三方依赖**（前端也没有构建步骤）
- **LLM 后端**：`pip install -r requirements-llm.txt`，并设置 `ANTHROPIC_API_KEY`
- **k8s 部署**：`pip install -r requirements-k8s.txt`（官方 kubernetes SDK）
- **会话存储**：SQLite 走标准库 `sqlite3`，不需要装任何东西
