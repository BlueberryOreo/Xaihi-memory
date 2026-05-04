"""Remember engine for xaihi memory system."""
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    from .config import config
    from .embedding import get_embedding_client
    from .llm_summarizer import get_llm_summarizer
    from .chroma_client import chroma_client
except ImportError:
    from config import config
    from embedding import get_embedding_client
    from llm_summarizer import get_llm_summarizer
    from chroma_client import chroma_client


def expand_path(path: str) -> Path:
    """Expand ~ and environment variables in path."""
    return Path(os.path.expandvars(os.path.expanduser(path)))


def get_buffer_file() -> Path:
    return expand_path(config.get_memory().get("buffer_file", "~/.claude/memory/conversation_buffer.jsonl"))


def get_counter_file() -> Path:
    return expand_path(config.get_memory().get("counter_file", "~/.claude/memory/counter.json"))


def ensure_temp_dir() -> None:
    """Ensure temp directory exists."""
    get_buffer_file().parent.mkdir(parents=True, exist_ok=True)


def read_counter() -> int:
    """Read current round counter."""
    counter_file = get_counter_file()
    if counter_file.exists():
        try:
            with open(counter_file, "r") as f:
                data = json.load(f)
                return data.get("count", 0)
        except Exception:
            return 0
    return 0


def write_counter(count: int) -> None:
    """Write counter value."""
    ensure_temp_dir()
    counter_file = get_counter_file()
    with open(counter_file, "w") as f:
        json.dump({"count": count, "updated_at": datetime.now(timezone.utc).isoformat()}, f)


def append_to_buffer(user_message: str, assistant_message: str) -> None:
    """Append a conversation round to the buffer."""
    ensure_temp_dir()
    buffer_file = get_buffer_file()
    entry = {
        "id": str(uuid.uuid4()),
        "round": read_counter() + 1,
        "user": user_message,
        "assistant": assistant_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(buffer_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_buffer() -> list[dict]:
    """Read all entries from buffer."""
    buffer_file = get_buffer_file()
    if not buffer_file.exists():
        return []

    entries = []
    with open(buffer_file, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
    return entries


def format_conversation_for_summary(entries: list[dict]) -> str:
    """Format conversation entries for LLM summarization."""
    lines = []
    for entry in entries:
        ts = entry.get("timestamp", "")[:19]
        user = entry.get("user", "").replace("\n", " ").strip()
        assistant = entry.get("assistant", "").replace("\n", " ").strip()
        if user:
            lines.append(f"[管理员 | {ts}] - {user}")
        if assistant:
            lines.append(f"[赛希 | {ts}] - {assistant}")
    return "\n".join(lines)


def clear_buffer() -> None:
    """Clear the conversation buffer."""
    buffer_file = get_buffer_file()
    if buffer_file.exists():
        buffer_file.unlink()


def reset_counter() -> None:
    """Reset counter to zero."""
    write_counter(0)


def summarize_and_store() -> bool:
    """Summarize buffer content and store to MongoDB."""
    entries = read_buffer()
    if not entries:
        return False

    if len(entries) < 2:
        # Too few entries, don't summarize yet
        return False

    # Format conversation
    conversation = format_conversation_for_summary(entries)

    # Check length limit
    summary_cfg = config.get_summary()
    max_len = summary_cfg.get("max_input_length", 8000)
    if len(conversation) > max_len:
        conversation = conversation[:max_len] + "\n...(对话过长已截断)"

    try:
        # Call LLM to summarize
        result = get_llm_summarizer().summarize(conversation)

        # Generate embedding for the summary
        summary_text = result.get("summary", "")
        embedding = get_embedding_client().embed(summary_text)

        # Generate session ID
        first_entry = entries[0]
        session_id = f"session-{first_entry.get('timestamp', datetime.now(timezone.utc).isoformat())[:10]}-{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        # Store in ChromaDB
        chroma_client.add_memory(
            memory_id=f"mem-{uuid.uuid4().hex[:12]}",
            content=summary_text,
            embedding=embedding,
            metadata={
                "topics": result.get("topics", []),
                "key_facts": result.get("key_facts", []),
                "importance": result.get("importance", 0.5),
                "sentiment": result.get("sentiment", "neutral"),
                "source": "auto_summary",
                "session_id": session_id,
                "created_at": created_at,
            },
        )

        # Clear buffer and reset counter
        clear_buffer()
        reset_counter()

        return True

    except Exception as e:
        with open("remember_engine_errors.log", "a") as log_file:
            log_file.write(f"{datetime.now().isoformat()} - Error during summarization: {e}\n")
        print(f"Error during summarization: {e}", file=sys.stderr)
        return False


import re


def strip_tool_calls(text: str) -> str:
    """Remove Claude Code tool call blocks from assistant message."""
    if not text:
        return text
    # Remove <tool_use>...</tool_use> blocks
    text = re.sub(r'<tool_use>.*?</tool_use>', '', text, flags=re.DOTALL)
    # Remove <tool-response>...</tool-response> blocks
    text = re.sub(r'<tool-response>.*?</tool-response>', '', text, flags=re.DOTALL)
    # Remove <command-...> blocks
    text = re.sub(r'<command-[^>]*>.*?</command-[^>]*>', '', text, flags=re.DOTALL)
    # Collapse multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def handle_stop_hook(user_message: str, assistant_message: str) -> None:
    """
    Handle Stop hook: append conversation and check for summarization trigger.
    """
    # Strip tool calls from assistant message
    clean_assistant = strip_tool_calls(assistant_message)
    append_to_buffer(user_message, clean_assistant)

    # Increment counter
    count = read_counter() + 1
    write_counter(count)

    # Check if we should summarize
    trigger_rounds = config.get_memory().get("summary_trigger_rounds", 10)
    if count >= trigger_rounds:
        summarize_and_store()


def handle_session_end() -> None:
    """
    Handle SessionEnd hook: summarize remaining buffer content.
    """
    entries = read_buffer()
    if entries:
        summarize_and_store()
    # Always ensure cleanup
    clear_buffer()
    reset_counter()


def manual_remember(conversation: str) -> bool:
    """
    Manually trigger a remember operation with given conversation text.
    Used for importing existing memory files.
    """
    if not conversation or len(conversation.strip()) < 10:
        return False

    try:
        result = get_llm_summarizer().summarize(conversation)
        summary_text = result.get("summary", "")
        embedding = get_embedding_client().embed(summary_text)

        session_id = f"manual-{datetime.now(timezone.utc).isoformat()[:10]}-{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        chroma_client.add_memory(
            memory_id=f"mem-{uuid.uuid4().hex[:12]}",
            content=summary_text,
            embedding=embedding,
            metadata={
                "topics": result.get("topics", []),
                "key_facts": result.get("key_facts", []),
                "importance": result.get("importance", 0.5),
                "sentiment": result.get("sentiment", "neutral"),
                "source": "manual",
                "session_id": session_id,
                "created_at": created_at,
            },
        )
        return True

    except Exception as e:
        print(f"Error during manual remember: {e}", file=sys.stderr)
        return False


def main():
    """Entry point for CLI / hook calls."""
    if len(sys.argv) > 1 and sys.argv[1] == "--session-end":
        handle_session_end()
    elif len(sys.argv) > 2 and sys.argv[1] == "--stop-hook":
        # Called by stop_hook.sh with file path
        tmpfile = sys.argv[2]
        try:
            with open(tmpfile) as f:
                raw = f.read()
            data = json.loads(raw) if raw.strip() else {}

            last_assistant = data.get("last_assistant_message", "")
            transcript_path = data.get("transcript_path", "")

            # Get the last user message from transcript
            last_user = ""
            if transcript_path:
                try:
                    lines = open(transcript_path).readlines()
                    for line in reversed(lines):
                        try:
                            msg = json.loads(line)
                            if msg.get("type") == "user" and not msg.get("isMeta"):
                                content = msg.get("message", {}).get("content", "")
                                if isinstance(content, str) and content.strip():
                                    last_user = content.strip()
                                    break
                                elif isinstance(content, list):
                                    for c in content:
                                        if isinstance(c, dict) and c.get("type") == "text":
                                            last_user = c.get("text", "").strip()
                                            break
                                    if last_user:
                                        break
                        except Exception:
                            continue
                except Exception:
                    pass

            handle_stop_hook(last_user, last_assistant)
        except Exception as ex:
            pass

    elif len(sys.argv) > 1:
        # Fallback: prompt from args
        pass


if __name__ == "__main__":
    main()
