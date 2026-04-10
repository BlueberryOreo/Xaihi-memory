# Prompts

This directory contains prompt templates for the memory system.

## Usage

Create your own prompt files here. The system will look for templates when summarizing conversations.

## Creating a Summarization Prompt

Create `summarize.md` with your custom prompt template:

```markdown
You are a memory consolidation assistant. Summarize the following conversation...
```

The `summarize.md` template should include `{conversation}` as a placeholder for the actual conversation content.

## Default Prompt

```
You are a memory consolidation assistant. Review the following conversation and generate a structured memory summary.

Important rules:
1. Use actual names/titles from the conversation (e.g., "user", not "the user")
2. summary should be in first person if appropriate, natural tone
3. importance score guidelines:
   - 0.9-1.0: Critical requests, important decisions, strong emotions
   - 0.7-0.8: Clear plans, specific requirements
   - 0.5-0.6: Daily conversations, basic Q&A
   - 0.3-0.4: Casual chat
   - 0.0-0.2: Meaningless
4. Output must be valid JSON format, no other text

# Output Format (JSON)
{
  "summary": "Conversation summary in natural language",
  "topics": ["topic1", "topic2"],
  "key_facts": ["key fact 1", "key fact 2"],
  "sentiment": "positive|neutral|negative",
  "importance": 0.0-1.0
}
```