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
6. CRITICAL: Never repeat what you said before - each message must be unique and fresh
7. Don't make up non-existent information (fake book titles, movies, names, etc.)
8. Stay on topic: always respond to what they said, don't suddenly change subjects
9. Don't be a "repeater" - never echo back their words or say what they already said
10. If knowledge base content is provided, use it as reference but keep conversational tone

【Anti-Repetition Rules】
- NEVER repeat any previous message you sent, even paraphrased
- NEVER repeat what the other party just said back to them
- If you already said something similar, say something completely different
- Check the conversation history and avoid any overlap with your previous messages

【Recovery & Flexibility】
- If you're unsure how to respond, ask a clarifying question naturally
- If the conversation stalls, gently shift to a related topic
- If you made an error, acknowledge it briefly and move on
- When they seem confused, offer to explain in more detail or rephrase
- Be adaptable - real conversations aren't always perfect

【Explanation Control】
- Only explain when asked or when the topic clearly requires it
- Ask first: "Want me to explain more?" instead of launching into long explanations
- Keep explanations brief unless they request details
- Use "I can explain more if you'd like" instead of assuming they want it
- Match their engagement level - if they ask short questions, give short answers

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
- Not repeating anything I said before (check ALL my previous messages)
- Not echoing back what Other just said
- Not making up non-existent information
- No "Me:" or other prefix added
- Length and tone match their message
- If explaining: did they ask for it? If not, consider asking first

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

Review the recent conversation context, then choose ONE option:

【Option 1: WAIT】 - Output just "WAIT" if:
- You just asked a question that needs thought
- The topic seems to need consideration
- Recent exchange was substantial

【Option 2: Gentle nudge (max 10 chars)】 if:
- Conversation was light and could continue
- A simple follow-up makes sense
- They might have gotten distracted

Examples of good nudges:
- "还在吗？" (Still there?)
- "你觉得呢？" (What do you think?)
- "嗯？" (Hmm?)

【Option 3: Fresh topic starter (max 12 chars)】 if:
- Current topic seems exhausted
- Long pause suggests they want to switch
- A light subject change would help

Requirements:
- Don't sound impatient or demanding
- Match the tone of your last message
- Keep it natural and friendly
- Never apologize excessively

Output your choice directly (WAIT or the message content, no prefix):
"""

# Refusal message for strict KB mode when no results found
KB_STRICT_REFUSAL = "I'm sorry, I don't have relevant information in my knowledge base to answer this question."


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
        previous_self_messages: list[str] | None = None,
        kb_context: str | None= None,
    ) -> str:
        """Build the user message content for LLM.
        
        Args:
            conversation_context: Formatted conversation history
            last_other_message: Most recent message from other party
            is_first_message: Whether this is the first message
           previous_self_messages: Recent messages sent by self (for anti-repetition)
            kb_context: Optional knowledge base context to include as reference
            
        Returns:
            Formatted prompt for LLM
        """
        if is_first_message:
            return self.get_first_message_prompt()
        
        if last_other_message:
            parts = []

            # Inject KB context if available
            if kb_context:
                parts.append("【Reference Knowledge Base Content】")
                parts.append(kb_context)
                parts.append("")
                parts.append("Please use the above reference material to inform your response where relevant.")
                parts.append("---")
                parts.append("")

            parts.append(conversation_context)
            parts.append("")
            
            # Add anti-repetition reminder with previous messages
            if previous_self_messages:
                parts.append("【DO NOT REPEAT - My previous messages were:】")
                for i, msg in enumerate(previous_self_messages[-5:], 1):
                    parts.append(f"{i}. \"{msg}\"")
                parts.append("")
            
            parts.append(f"Please respond naturally to what they said: \"{last_other_message}\"")
            parts.append("Requirements:")
            parts.append("- Directly respond to their message")
            parts.append("- Stay on topic")
            parts.append("- Say something NEW - do NOT repeat or paraphrase any of my previous messages above")
            parts.append("- Do NOT echo back what they said")
            
            return "\n".join(parts)
        
        return self.get_first_message_prompt()
