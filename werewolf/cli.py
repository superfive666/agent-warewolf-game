"""命令行入口。"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from .lineup import Lineup
from .runtime import DEPLOYMENTS
from .session import GameSession
from .events import Audience
from .replay import render_replay, result_summary
from .roles import BOARDS, Faction, Role
from .state import GameConfig, new_game
from .views import build_all_views


def _parse_seats(text: str | None) -> set[int] | None:
    if not text:
        return None
    if text.strip().lower() == "all":
        return None
    return {int(x) for x in text.replace("，", ",").split(",") if x.strip()}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_game.py",
        description="agent 狼人杀：12 人标准屠边局",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例：
  python3 run_server.py                        # ★ 启动 Web 沙箱（推荐）
  python3 run_game.py                          # 12 个规则 bot 打一局
  python3 run_game.py -n 9                     # 9 人局
  python3 run_game.py --seed 7 --show-wolves   # 固定牌局并显示狼人频道
  python3 run_game.py --games 100 --quiet      # 跑 100 局统计胜率
  python3 run_game.py --backend claude         # 12 个 Claude agent 打一局
  python3 run_game.py --backend openai --model gpt-5           # 用 OpenAI
  python3 run_game.py --backend openai --model qwen-max \\
      --base-url https://my-gateway/v1                         # 自建/兼容网关
  python3 run_game.py --backend claude --llm-seats 1,2,3       # 3 个 LLM + 9 个 bot
""",
    )
    p.add_argument("-n", "--n-players", type=int, default=12, choices=sorted(BOARDS),
                   help="人数（板子）")
    p.add_argument("--seed", type=int, default=None, help="随机种子，固定后牌局完全可复现")
    p.add_argument("--games", type=int, default=1, help="连打多少局（>1 时只输出统计）")
    p.add_argument("--backend", choices=["heuristic", "llm", "claude", "openai"],
                   default="heuristic", help="llm 是 claude 的旧名字")
    p.add_argument("--llm-seats", default=None, help="哪些座位用 LLM，如 1,2,3；默认全部")
    p.add_argument("--model", default=None,
                   help="模型 id。openai 后端可以随便填（自建网关的模型名）")
    p.add_argument("--base-url", default=None,
                   help="OpenAI 兼容网关地址，如 https://my-gateway/v1"
                        "（也可用环境变量 OPENAI_BASE_URL）")
    p.add_argument("--api-key-env", default=None,
                   help="去哪个环境变量取密钥。注意这里填【变量名】，不是密钥本身")
    p.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    p.add_argument("--win-rule", choices=["edge", "city"], default="edge", help="edge=屠边 city=屠城")
    p.add_argument("--no-sheriff", action="store_true", help="关闭警长竞选")
    p.add_argument("--no-explode", action="store_true", help="禁止狼人自爆")
    p.add_argument("--max-speech-chars", type=int, default=450,
                   help="发言字数上限，450 字 ≈ 真人讲 2 分钟")
    p.add_argument("--max-iterations", type=int, default=3,
                   help="每个决策点最多向 agent 索要几次动作（思考长度不限）")
    p.add_argument("--show-wolves", action="store_true", help="实时输出里显示狼人频道（观战上帝视角）")
    p.add_argument("--show-thoughts", action="store_true", help="显示 LLM agent 的内心想法")
    p.add_argument("--quiet", "-q", action="store_true", help="不输出过程")
    p.add_argument("--out", default=None, help="产物输出目录，默认 runs/<时间戳>")
    p.add_argument("--no-save", action="store_true", help="不写任何文件")
    p.add_argument("--dump-views", action="store_true",
                   help="在每个决策点都快照一份视角（用于逐帧检查信息隔离）")
    p.add_argument("--deployment", default="inprocess", choices=sorted(DEPLOYMENTS),
                   help="agent 跑在哪：" + "；".join(f"{k}={v}" for k, v in DEPLOYMENTS.items()))
    p.add_argument("--store", default=None,
                   help="会话存储 URI，如 sqlite:runs/werewolf.db / files:runs / none:"
                        "（默认 sqlite，环境变量 WEREWOLF_STORE 可覆盖）")
    p.add_argument("--image", default=None,
                   help="agent 容器镜像（docker / k8s 部署时用）")
    return p


def run_one(args, seed: int | None, quiet: bool) -> tuple:
    config = GameConfig(
        n_players=args.n_players,
        seed=seed,
        win_rule=args.win_rule,
        sheriff=not args.no_sheriff,
        wolf_explode=not args.no_explode,
        max_speech_chars=args.max_speech_chars,
        max_iterations=args.max_iterations,
    )
    llm_seats = _parse_seats(args.llm_seats)
    seats_payload = [
        {
            "seat": s,
            "backend": (args.backend
                        if args.backend != "heuristic" and (llm_seats is None or s in llm_seats)
                        else "heuristic"),
            "model": args.model or ("gpt-5" if args.backend == "openai" else "claude-opus-5"),
            "effort": args.effort,
            "base_url": args.base_url or "",
            "api_key_env": args.api_key_env or "",
        }
        for s in range(1, args.n_players + 1)
    ]
    lineup = Lineup.from_payload(args.n_players, seats_payload)

    session = GameSession(
        config, lineup,
        deployment=args.deployment,
        store_uri=args.store or os.environ.get("WEREWOLF_STORE", "sqlite:runs/werewolf.db"),
        image=args.image or os.environ.get("WEREWOLF_AGENT_IMAGE", "werewolf-agent:latest"),
        verbose=args.show_thoughts,
    )
    state = session.state

    def on_event(e):
        if quiet:
            return
        if e.audience is Audience.PUBLIC:
            print(e.text)
        elif args.show_wolves and e.audience is Audience.WOLVES:
            print(f"🐺 {e.text}")
        elif args.show_wolves and e.audience is Audience.PRIVATE:
            print(f"🔒 {e.text}")

    view_snapshots: list[dict] = []
    recorder = None
    if args.dump_views:
        def recorder(turn, seat, action_type, view):
            view_snapshots.append(
                {"turn": turn, "seat": seat, "action_type": action_type, "view": view.as_dict()}
            )

    state = session.run(on_event=on_event, view_recorder=recorder)
    return state, session, view_snapshots, lineup


def save_run(outdir: Path, state, session, args, view_snapshots, lineup=None) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "config.json").write_text(
        json.dumps({**state.config.as_dict(),
                    "lineup": lineup.as_list() if lineup else None},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "events.jsonl").write_text(state.event_log.to_jsonl(), encoding="utf-8")
    (outdir / "result.json").write_text(
        json.dumps(result_summary(state, lineup), ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "replay.md").write_text(render_replay(state, lineup=lineup), encoding="utf-8")
    (outdir / "thoughts.json").write_text(
        json.dumps([t for t in state.thought_log if t["thought"]],
                   ensure_ascii=False, indent=2), encoding="utf-8")
    # 每个座位的 agent 会话（容器销毁前抓下来的那份）
    sessions = session.store.load_agent_sessions(session.id)
    if sessions:
        (outdir / "agent_sessions.json").write_text(
            json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")

    views = build_all_views(state)
    vdir = outdir / "views"
    vdir.mkdir(exist_ok=True)
    for seat, v in views["players"].items():
        (vdir / f"seat_{int(seat):02d}.json").write_text(
            json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")
    (vdir / "wolf_team.json").write_text(
        json.dumps(views["wolf_team"], ensure_ascii=False, indent=2), encoding="utf-8")

    if view_snapshots:
        sdir = outdir / "view_snapshots"
        sdir.mkdir(exist_ok=True)
        for snap in view_snapshots:
            name = f"turn_{snap['turn']:04d}_seat_{snap['seat']:02d}_{snap['action_type']}.json"
            (sdir / name).write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.games > 1:
        from collections import Counter
        tally, days = Counter(), []
        for i in range(args.games):
            seed = None if args.seed is None else args.seed + i
            state, _, _, _ = run_one(args, seed, quiet=True)
            tally[state.winner.cn if state.winner else "平局"] += 1
            days.append(state.day)
        print(f"\n共 {args.games} 局：")
        for k, v in tally.most_common():
            print(f"  {k}: {v} 局 ({v / args.games:.1%})")
        print(f"  平均天数：{sum(days) / len(days):.2f}")
        return 0

    state, session, snaps, lineup = run_one(args, args.seed, quiet=args.quiet)

    if not args.quiet:
        print("\n" + "=" * 60)
        print("身份表：" + "　".join(f"{s}号={state.players[s].role.cn}" for s in state.seats))
        print(f"结果：{state.winner.cn if state.winner else '平局'} —— {state.end_reason}")

    if not args.no_save:
        outdir = Path(args.out) if args.out else Path("runs") / datetime.now().strftime("%Y%m%d-%H%M%S")
        save_run(outdir, state, session, args, snaps, lineup)
        print(f"\n会话已入库：{args.store or os.environ.get('WEREWOLF_STORE', 'sqlite:runs/werewolf.db')}"
              f"　game_id={session.id}")
        print(f"产物已写入：{outdir}/")
        print(f"  replay.md          文字战报（含上帝视角）")
        print(f"  events.jsonl       全部事件")
        print(f"  thoughts.json      每个 agent 的心路历程")
        print(f"  agent_sessions.json 每个座位的完整会话（容器销毁前抓下来的）")
        print(f"  views/seat_*.json + wolf_team.json   {args.n_players + 1} 份上下文")
    return 0


if __name__ == "__main__":
    sys.exit(main())
