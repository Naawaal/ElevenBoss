"""Backward-compatible shim for setuptools py-modules entry."""
from player_engine.procedural_generator import generate_player, generate_squad

__all__ = ["generate_player", "generate_squad"]
