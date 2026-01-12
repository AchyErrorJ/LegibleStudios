"""Loop detection utilities for preventing infinite tool calls"""

from typing import List, Set

class LoopDetector:
    """Detects when LLM is stuck in a tool-calling loop"""
    
    def __init__(self):
        self.tool_call_history: List[List[str]] = []
        self.unique_tools: Set[str] = set()
        self.total_calls = 0
    
    def add_call(self, tool_names: List[str]):
        """Record a set of tool calls"""
        self.tool_call_history.append(tool_names)
        for tool in tool_names:
            self.unique_tools.add(tool)
        self.total_calls += len(tool_names)
    
    def detect_repetition(self, threshold: int = 3) -> bool:
        """Detect if same tools called N times in a row"""
        if len(self.tool_call_history) < threshold:
            return False
        
        last_n = self.tool_call_history[-threshold:]
        return all(calls == last_n[0] for calls in last_n)
    
    def detect_stuck(self, min_calls: int = 6, max_unique: int = 2) -> bool:
        """Detect if not making progress (few unique tools after many calls)"""
        return self.total_calls >= min_calls and len(self.unique_tools) <= max_unique
    
    def detect_single_tool_spam(self, tool_name: str, threshold: int = 3) -> bool:
        """Detect if single tool called too many times"""
        count = sum(1 for calls in self.tool_call_history if tool_name in calls)
        return count >= threshold
    
    def is_looping(self) -> tuple[bool, str]:
        """Check all loop conditions, return (is_looping, reason)"""
        if self.detect_repetition():
            return (True, f"Same tools repeated 3 times: {self.tool_call_history[-1]}")
        
        if self.detect_stuck():
            return (True, f"Stuck with only {len(self.unique_tools)} unique tools after {self.total_calls} calls")
        
        if len(self.tool_call_history) > 0:
            last_tools = self.tool_call_history[-1]
            for tool in last_tools:
                if self.detect_single_tool_spam(tool):
                    return (True, f"Tool '{tool}' called too many times")
        
        return (False, "")