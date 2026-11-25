"""Short conversation memory, held in the process. Phase 2 adds database storage."""

from collections import OrderedDict
from dataclasses import dataclass


@dataclass(frozen=True)
class Turn:
    """One earlier exchange. The question is already redacted."""

    question: str
    answer: str


class ConversationStore:
    """Keeps the last few turns of the most recently used conversations.

    The key includes the user ID, so one user can never see another user's history by
    sending the same conversation ID. (The API has no authentication, so this relies on
    the caller sending an honest user ID.) Everything is lost on restart.
    """

    def __init__(self, max_turns: int, max_conversations: int) -> None:
        self._max_turns = max_turns
        self._max_conversations = max_conversations
        self._data: OrderedDict[tuple[str, str], list[Turn]] = OrderedDict()

    def get(self, user_id: str, conversation_id: str) -> list[Turn]:
        """Earlier turns, oldest first."""
        return list(self._data.get((user_id, conversation_id), []))

    def add(self, user_id: str, conversation_id: str, turn: Turn) -> None:
        """Remember a turn and forget the oldest conversations if there are too many."""
        if self._max_turns == 0:
            return
        key = (user_id, conversation_id)
        self._data[key] = [*self._data.get(key, []), turn][-self._max_turns :]
        self._data.move_to_end(key)
        while len(self._data) > self._max_conversations:
            self._data.popitem(last=False)
