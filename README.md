# agent 狼人杀 · Agent Werewolf

让 12 个 AI agent 坐在同一张牌桌上，各拿各的身份、各看各的信息，把一局
**标准 12 人狼人杀（屠边局）**从发牌打到分出胜负。

核心不是"写一个狼人杀"，而是**信息隔离**：怎么保证 12 个 agent 各自只看到该看的东西，
狼人有共享频道而好人没有，预言家的验人结果不会漏进别人的上下文。

```
$ python3 run_game.py --seed 7
```

---

## 快速开始

```bash
# 零依赖，开箱即跑：12 个内置规则 bot 打一局
python3 run_game.py

# 固定牌局 + 开上帝视角（能看到狼人频道和私聊）
python3 run_game.py --seed 7 --show-wolves

# 跑 200 局看胜率平衡
python3 run_game.py --games 200 --seed 0

# 用真的 Claude agent 来打（需要 pip install anthropic 和 ANTHROPIC_API_KEY）
python3 run_game.py --backend llm --show-thoughts

# 混合：1/2/3 号用 LLM，其余 9 个用规则 bot（低成本实验）
python3 run_game.py --backend llm --llm-seats 1,2,3

# 跑测试
python3 -m unittest discover -s tests -t .
```

---

## 文档

规则和设计都写在 `docs/`，代码以文档为准：

| 文档 | 内容 |
|---|---|
| [`docs/01-游戏规则.md`](docs/01-游戏规则.md) | 板子配置、胜利条件、6 种角色技能、警长、投票、术语表、全部配置项 |
| [`docs/02-游戏流程.md`](docs/02-游戏流程.md) | 完整状态机、每个阶段的 Action schema、非法动作的处理 |
| [`docs/03-技术设计.md`](docs/03-技术设计.md) | 带可见性标签的事件日志、视角生成、agent 接口、产物格式 |
| [`docs/04-视角与上下文.md`](docs/04-视角与上下文.md) | **12 份个人视角 + 1 份狼队视角的完整 JSON 规范** |

---

## 板子

| 阵营 | 角色 | 人数 |
|---|---|---|
| 狼人 | 狼人 | 4 |
| 好人（神） | 预言家 / 女巫 / 猎人 / 白痴 | 4 |
| 好人（民） | 平民 | 4 |

**屠边胜负**：狼人杀光 4 神（屠神）**或**杀光 4 民（屠民）即获胜；好人票出 4 狼即获胜。
含完整的**警长竞选**（上警 → 警上发言 → 退水 → 投票 → 警徽移交/撕毁）。

---

## 信息隔离是怎么做到的

整局游戏就是**一条只追加的事件流**，每条事件带一个可见性标签：

| 标签 | 谁能看到 |
|---|---|
| `PUBLIC` | 全部 12 人（含已出局者） |
| `WOLVES` | 全部狼人（含已出局的狼人） |
| `PRIVATE` | `visible_to` 里列出的座位 |
| `GOD` | 谁都看不到，只进复盘 |

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
它**根本没有 `role` 属性** —— 想读别人的身份会直接 `AttributeError`，而不是静默泄密。

### 13 份上下文

| 视角 | 份数 | 说明 |
|---|---|---|
| `PlayerView` 个人视角 | **12** | 每座位一份：身份区 + 公开状态 + 我可见的时间线 + 本轮可做的动作 |
| `WolfTeamView` 狼队视角 | **1** | 4 名狼人**共享同一份**，作为区块挂在他们的个人视角上 |

好人的 `wolf_team` 字段恒为 `null`——不是被隐藏，是根本没有被构造。

狼队视角里**也没有**任何好人的真实身份。狼人只知道"我们 4 个是狼"，剩下 8 人对他们同样是黑的。
里面的 `intel` 情报每一条都只来自狼人真实可观测的事实，比如：

- `witch_antidote_used: true` ← "我们刀了 3 号，但天亮 3 号没死" —— 这本账只有狼人对得上
- `suspected_god_seats` ← 纯粹按"谁公开起跳了神职"排序，**不是**上帝告诉他们谁是神

### 测试保证

`tests/test_visibility.py` 在**每一局的每一个决策点**都快照全部视角，跑 8 条断言：

1. 非狼玩家的时间线里不含任何狼人频道事件
2. 不含 `visible_to` 不包含自己的私有事件
3. 不含别人的真实身份（公开宣称和白痴翻牌等规则性公开除外）
4. 好人的 `wolf_team` 恒为 `None`，狼人的恒非空
5. 狼队视角不含任何好人身份，也不含"还剩几个神"这种上帝信息
6. 投票必须收齐后才公布——同一轮里先投和后投的人看到的票型完全相同
7. 预言家的验人结果只出现在预言家自己的视角里
8. 女巫的刀口告知只出现在女巫自己的视角里

```
$ python3 -m unittest discover -s tests -t .
Ran 41 tests in 7.1s
OK
```

---

## 两套 agent 后端

| 后端 | 说明 |
|---|---|
| `heuristic`（默认） | 纯 Python 规则 bot，零依赖。会悍跳、会跟查杀、会做站边分析。毫秒级跑完一局，用于回归测试和给 LLM 当陪练。 |
| `llm` | 调 Claude Messages API（默认 `claude-opus-5`）。**每个座位一个独立会话**，座位之间没有任何共享对象。 |

两者走**完全相同的信息通道**——都只拿到 `PlayerView`，没有后门。可以任意混搭。

LLM 后端的上下文组装：

- **system 整局逐字不变**（规则 + 身份卡 + 打法提示 + 输出约束）→ 命中 prompt cache
- **user 只发增量**（自上次决策以来的新事件）+ 当前局势摘要 + 本轮能做什么
- **输出用 JSON Schema 硬约束**（`output_config.format`），不靠"请输出 JSON"这种软约束
- 每次决策都有一个 `private_thought` 字段，只进复盘，**不进任何玩家的视角**

规则 bot 之间的对局，好人胜率约 **60%**（200 局统计），双方都能赢，不存在单边碾压。

---

## 产物

每局会写出：

```
runs/<时间戳>/
├── config.json       板子 / seed / 后端配置
├── events.jsonl      全部事件（含 GOD 级），完整上帝视角
├── result.json       胜负、真实身份表、票型、验人记录、用药记录
├── replay.md         人类可读的文字战报
├── thoughts.json     每个 LLM agent 每次决策的内心想法（仅 llm 后端）
└── views/
    ├── seat_01.json … seat_12.json   12 份个人视角
    └── wolf_team.json                1 份狼队视角
```

加 `--dump-views` 还会在**每个决策点**都快照一次视角，产出
`view_snapshots/turn_0007_seat_03_speech.json`，用来逐帧检查信息隔离。

---

## 目录结构

```
werewolf/
├── roles.py          角色 / 阵营 / 板子
├── events.py         ★ 事件 + 可见性模型（信息隔离的全部实现）
├── state.py          GameState / Player / GameConfig
├── views.py          ★ 视角生成：12 份个人视角 + 1 份狼队视角
├── actions.py        动作 schema + 合法性校验 + 安全回退
├── prompts.py        把视角渲染成 LLM prompt
├── engine.py         状态机 / 上帝
├── replay.py         复盘渲染
├── cli.py            命令行
└── agents/
    ├── base.py       Agent 接口（只有 act(view) 一个方法）
    ├── heuristic.py  规则 bot
    └── llm.py        Claude API 后端
```

## 依赖

- **规则 bot 后端**：只需要 Python 3.11+，零第三方依赖
- **LLM 后端**：`pip install -r requirements-llm.txt`，并设置 `ANTHROPIC_API_KEY`
