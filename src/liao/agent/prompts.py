"""Prompt templates for the vision agent."""

from __future__ import annotations


# System prompt for auto chat mode
AUTO_CHAT_SYSTEM_PROMPT = """\
You are having a natural instant messaging conversation with a friend.

【Basic Rules】
1. One short message at a time (1-2 sentences max, like real texting)
2. Reply directly to what they just said - don't ignore their message
3. Be casual and conversational, not formal
4. Match their message length and tone
5. If they asked something, answer it first

【Anti-Repetition】
- NEVER repeat anything you said before in this conversation
- NEVER echo back their words to them
- Check conversation history and say something NEW each time
- If you already responded to something similar, take a different angle

【Natural Flow】
- Don't force explanations unless asked
- Ask follow-up questions naturally when appropriate
- Use short responses for simple messages (just "好的", "嗯嗯", "哈哈" when fitting)
- Stay on their topic - don't randomly change subjects
- Be genuinely engaged in the conversation

【Output Format】
- Just the message content, nothing else
- No "Me:", no quotes, no explanations
- Same language they use

【User Settings】
{user_prompt}
"""

# Prompt for generating the first message
AUTO_CHAT_FIRST_MESSAGE_PROMPT = """\
This is the first message. Generate a natural opening (10-30 characters).

Settings: {user_prompt}

Output only the message content, no prefix.
"""

# Prompt for handling no-reply timeout
AUTO_CHAT_NO_REPLY_PROMPT = """\
No reply for {wait_seconds} seconds. Choose ONE:

1. "WAIT" - if you asked a question that needs thought
2. A short nudge (max 10 chars) - e.g., "还在吗？", "你觉得呢？"
3. A fresh topic (max 12 chars)

Output your choice directly:
"""

# Refusal message for strict KB mode
KB_STRICT_REFUSAL = "Sorry, I don't have relevant information to answer this."


class PromptManager:
    """Manages prompt templates."""

    def __init__(self, user_prompt: str = ""):
        self._user_prompt = user_prompt

    @property
    def user_prompt(self) -> str:
        return self._user_prompt

    @user_prompt.setter
    def user_prompt(self, value: str) -> None:
        self._user_prompt = value

    def get_system_prompt(self) -> str:
        return AUTO_CHAT_SYSTEM_PROMPT.format(user_prompt=self._user_prompt)

    def get_first_message_prompt(self) -> str:
        return AUTO_CHAT_FIRST_MESSAGE_PROMPT.format(user_prompt=self._user_prompt)

    def get_no_reply_prompt(self, wait_seconds: int) -> str:
        return AUTO_CHAT_NO_REPLY_PROMPT.format(wait_seconds=wait_seconds)

    def build_chat_context(
        self,
        conversation_context: str,
        last_other_message: str | None = None,
        is_first_message: bool = False,
        previous_self_messages: list[str] | None = None,
        kb_context: str | None = None,
    ) -> str:
        """Build the user message content for LLM."""
        if is_first_message:
            return self.get_first_message_prompt()

        if last_other_message:
            parts = []

            if kb_context:
                parts.append("【Reference】")
                parts.append(kb_context[:500])
                parts.append("")

            parts.append(conversation_context)
            parts.append("")

            if previous_self_messages:
                parts.append("My previous messages (DO NOT repeat):")
                for msg in previous_self_messages[-3:]:
                    parts.append(f'  "{msg}"')
                parts.append("")

            parts.append(f'They said: "{last_other_message}"')
            parts.append("Your reply (new, not repeating above):")

            return "\n".join(parts)

        return self.get_first_message_prompt()
