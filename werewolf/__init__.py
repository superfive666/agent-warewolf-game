"""agent 狼人杀：12 人标准屠边局的引擎与 agent 后端。"""
from .state import GameConfig, new_game  # noqa: F401
from .engine import Engine, play_game  # noqa: F401

__all__ = ["GameConfig", "new_game", "Engine", "play_game"]
