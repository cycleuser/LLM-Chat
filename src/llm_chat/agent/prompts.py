"""Prompt templates for the vision agent."""

from __future__ import annotations


# System prompt for auto chat mode
AUTO_CHAT_SYSTEM_PROMPT = """\
You are simulating a real instant messaging conversation.

【Core Principles】
Your every message must be a direct response to what the other party just said.
Do not talk to yourself or stray from their topic.
Never send two consecutive messages - always wait for their reply before speaking again.

【Conversation Rules】
1. Generate only one short message at a time (1-3 sentences), like real messaging
2. Use casual, natural tone like chatting with a friend, not formal writing
3. Match your reply length to theirs: short replies for short messages, longer for longer
4. Match their tone: enthusiastic if they are, reserved if they are
5. If they asked a question, prioritize answering it
6. Never repeat what you said before
7. Don't make up non-existent information (fake book titles, movies, names, etc.)
8. Stay on topic: always respond to what they said, don't suddenly change subjects

【Format Requirements】
- Output only the message content directly
- No quotes or brackets around the entire message
- No translations, pinyin, explanations, or parenthetical notes
- Never add "Me:" or any sender prefix
- Respond in the same language they use unless specified otherwise

【Conversation Memory】
You will receive a full conversation log marked with "Me" and "Other".
Always reply based on the complete context, don't ignore previous messages.
Don't repeat previous content or confuse who said what.

【Pre-send Check】
Before generating, confirm:
- This directly responds to Other's latest message
- Not repeating anything said before
- Not making up non-existent information
- No "Me:" or other prefix added
- Length and tone match their message

【User Settings】
{user_prompt}
"""

# Prompt for generating the first message
AUTO_CHAT_FIRST_MESSAGE_PROMPT = """\
This is the first message in the conversation. You need to start the topic.

Based on the following settings, generate a natural opening (10-30 characters):
{user_prompt}

Requirements: Short, friendly, like a casual chat opener. Output only the message content, no prefix.
"""

# Prompt for handling no-reply timeout
AUTO_CHAT_NO_REPLY_PROMPT = """\
The other party hasn't replied for {wait_seconds} seconds.

Review the recent conversation, then choose:
1. If they might still be thinking (e.g., you asked something requiring thought), output WAIT
2. If a natural follow-up is appropriate (8 characters max, like "Still there?" or "What do you think?"), output it directly
3. Don't rush or appear impatient

Output your choice directly (WAIT or a short follow-up, no prefix):
"""


class PromptManager:
    """Manages prompt templates for the vision agent.
    
    Example:
        pm = PromptManager(user_prompt="Be friendly and helpful")
        system = pm.get_system_prompt()
        first_msg = pm.get_first_message_prompt()
    """

    def __init__(self, user_prompt: str = ""):
        self._user_prompt = user_prompt

    @property
    def user_prompt(self) -> str:
        """Get user prompt."""
        return self._user_prompt

    @user_prompt.setter
    def user_prompt(self, value: str) -> None:
        """Set user prompt."""
        self._user_prompt = value

    def get_system_prompt(self) -> str:
        """Get the system prompt with user settings.
        
        Returns:
            Formatted system prompt
        """
        return AUTO_CHAT_SYSTEM_PROMPT.format(user_prompt=self._user_prompt)

    def get_first_message_prompt(self) -> str:
        """Get prompt for generating first message.
        
        Returns:
            Formatted first message prompt
        """
        return AUTO_CHAT_FIRST_MESSAGE_PROMPT.format(user_prompt=self._user_prompt)

    def get_no_reply_prompt(self, wait_seconds: int) -> str:
        """Get prompt for handling no-reply timeout.
        
        Args:
            wait_seconds: Seconds waited so far
            
        Returns:
            Formatted no-reply prompt
        """
        return AUTO_CHAT_NO_REPLY_PROMPT.format(wait_seconds=wait_seconds)

    def build_chat_context(
        self,
        conversation_context: str,
        last_other_message: str | None = None,
        is_first_message: bool = False,
    ) -> str:
        """Build the user message content for LLM.
        
        Args:
            conversation_context: Formatted conversation history
            last_other_message: Most recent message from other party
            is_first_message: Whether this is the first message
            
        Returns:
            Formatted prompt for LLM
        """
        if is_first_message:
            return self.get_first_message_prompt()
        
        if last_other_message:
            return (
                f"{conversation_context}\n\n"
                f"Please respond naturally to what they said: \"{last_other_message}\"\n"
                f"Requirements: Directly respond to their message, stay on topic, don't repeat previous content."
            )
        
        return self.get_first_message_prompt()
