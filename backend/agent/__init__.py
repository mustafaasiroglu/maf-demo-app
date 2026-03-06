import logging
from typing import Sequence
from agent_framework import ChatMessage, ChatMessageStore

logger = logging.getLogger(__name__)

# Maximum number of user *turns* to keep in history.
# Each turn may include multiple ChatMessage objects (user msg, assistant tool
# calls, tool results, assistant text), so we count by user-role boundaries
# rather than raw message count to avoid splitting tool-call / tool-result pairs.
MAX_HISTORY_TURNS = 6


def _msg_role(m: ChatMessage) -> str:
    """Extract the role string from a ChatMessage, handling both enum and str."""
    if hasattr(m, 'role'):
        return m.role.value if hasattr(m.role, 'value') else str(m.role)
    return 'unknown'


class ReducingChatMessageStore(ChatMessageStore):
    """A ChatMessageStore that trims older *turns* when history exceeds a limit.

    A "turn" starts at each user-role message.  Trimming always removes
    complete turns so that tool-call / tool-result pairs are never orphaned.
    Keeps the most recent MAX_HISTORY_TURNS turns.
    """

    def __init__(self, messages: Sequence[ChatMessage] | None = None, max_turns: int = MAX_HISTORY_TURNS):
        super().__init__(messages)
        self.max_turns = max_turns
        self._trim()

    def _trim(self) -> None:
        """Trim messages to keep only the most recent `max_turns` user turns.

        A turn boundary is defined by a message with role == "user".
        We find the indices of all user-role messages, then keep everything
        from the Nth-from-last user message onward (where N = max_turns).
        """
        if not self.messages:
            return

        # Find indices of every user-role message (turn boundaries)
        user_indices = [
            i for i, m in enumerate(self.messages)
            if hasattr(m, 'role') and (
                (hasattr(m.role, 'value') and m.role.value == 'user')
                or str(m.role) == 'user'
            )
        ]

        if len(user_indices) <= self.max_turns:
            return  # nothing to trim

        # Keep from the (max_turns)-th-from-last user message onward
        cut_index = user_indices[-self.max_turns]
        trimmed = cut_index
        self.messages = self.messages[cut_index:]
        logger.info(
            f"🗑️ History trimmed: removed {trimmed} messages "
            f"({len(user_indices) - self.max_turns} old turns), "
            f"keeping {len(self.messages)} messages ({self.max_turns} turns)"
        )

    async def add_messages(self, messages: Sequence[ChatMessage]) -> None:
        roles = [_msg_role(m) for m in messages]
        logger.info(f"📝 Store.add_messages: adding {len(messages)} msgs (roles: {roles}), store had {len(self.messages)} msgs")
        await super().add_messages(messages)
        self._trim()
        logger.info(f"📝 Store.add_messages: store now has {len(self.messages)} msgs")

    async def list_messages(self) -> list[ChatMessage]:
        msgs = await super().list_messages()
        user_count = sum(1 for m in msgs if _msg_role(m) == 'user')
        logger.info(f"📖 Store.list_messages: returning {len(msgs)} msgs ({user_count} user turns)")
        return msgs