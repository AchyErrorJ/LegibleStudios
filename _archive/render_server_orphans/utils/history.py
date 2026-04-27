"""Conversation history utilities"""

from typing import List, Dict, Any

def sanitize_history(history: List[Dict], provider: str = "claude") -> List[Dict]:
    """Convert history to format expected by LLM provider"""
    sanitized = []
    
    for msg in history:
        content = msg.get("content", "")
        role = msg.get("role", "user")
        
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            text = " ".join(text_parts)
        else:
            continue
        
        if text.strip():
            if provider == "claude":
                sanitized.append({"role": role, "content": [{"type": "text", "text": text}]})
            else:
                sanitized.append({"role": role, "content": text})
    
    return sanitized

def compress_history(messages: List[Dict], max_messages: int = 10) -> List[Dict]:
    """Compress history to stay under token limits"""
    if len(messages) <= max_messages:
        return messages
    
    # Keep system message + first user message + last N messages
    system_msgs = [m for m in messages[:2] if m.get("role") == "system"]
    first_user = [messages[1]] if len(messages) > 1 and messages[1].get("role") == "user" else []
    recent = messages[-(max_messages - len(system_msgs) - len(first_user)):]
    
    return system_msgs + first_user + recent