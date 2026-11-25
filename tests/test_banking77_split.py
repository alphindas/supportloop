"""Pools must never share a message, and the split must be repeatable."""

from app.banking77 import Message, split_into_pools

MESSAGES = [Message(f"m{i}", f"text {i}", f"intent{i % 3}") for i in range(30)]
SIZES = {"eval": 3, "mining": 4, "ab": 3}


def test_pools_are_disjoint_and_balanced() -> None:
    pools = split_into_pools(MESSAGES, SIZES, seed=1)
    ids = [m.message_id for pool in pools.values() for m in pool]
    assert len(ids) == len(set(ids)) == 30
    for name, size in SIZES.items():
        assert len(pools[name]) == size * 3


def test_split_is_repeatable_and_depends_on_seed() -> None:
    assert split_into_pools(MESSAGES, SIZES, 1) == split_into_pools(MESSAGES, SIZES, 1)
    assert split_into_pools(MESSAGES, SIZES, 1) != split_into_pools(MESSAGES, SIZES, 2)
