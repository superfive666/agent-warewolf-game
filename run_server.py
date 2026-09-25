#!/usr/bin/env python3
"""启动狼人杀沙箱 Web 服务。"""
import argparse

from werewolf.server import serve

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="狼人杀 agent 沙箱")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    serve(a.host, a.port)
