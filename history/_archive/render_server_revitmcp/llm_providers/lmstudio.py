"""LM Studio chat logic provider"""

import json
import os
import time
import re
from typing import Dict, Any, List
from openai import OpenAI

# These will be imported from utils
from utils.loop_detection import LoopDetector

# System prompt - defined at module level
SYSTEM_PROMPT = """You are an expert Revit Automation Assistant.

CRITICAL RULES:
1. Execute tools ONE AT A TIME until the request is complete
2. After executing tools successfully, ALWAYS respond with descriptive text
3. NEVER call the same tool twice in a row
4. Maximum 3-4 tool calls per request - then STOP and summarize
5. NEVER use <think> tags in your responses
6. Use list_ tools FIRST to get IDs (like list_levels, list_walls)
7. When types aren't specified, use the first available type from list results

If you don't know what tools are available, use list_levels or list_walls to start exploring."""


def initialize(config: Dict) -> Dict:
    """Initialize LM Studio client"""
    base_url = config["lmstudio"]["base_url"]
    model = config["lmstudio"]["model"]
    
    client = OpenAI(
        base_url=base_url,
        api_key="lm-studio"
    )
    
    print(f"✅ LM Studio initialized")
    print(f"   URL: {base_url}")
    print(f"   Model: {model}")
    
    return {
        "client": client,
        "model": model
    }


async def handle_lmstudio_chat(
    message: str,
    history: List[Dict],
    clients: Dict,
    tools: List[Dict]
) -> Dict[str, Any]:
    """Process chat request using LM Studio"""
    
    print(">>> LM Studio chat logic started")
    
    client = clients["client"]
    model_dict = clients.get("model", {})
    
    if isinstance(model_dict, dict):
        model_name = model_dict.get("id", "qwen2.5-0.5b-instruct")
    else:
        model_name = str(model_dict) if model_dict else "qwen2.5-0.5b-instruct"
    
    # Build messages with system prompt
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    
    # Add conversation history
    for msg in history:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    # Add current message
    messages.append({"role": "user", "content": message})
    
    print(f"📜 Total messages: {len(messages)}")
    print(f"🔧 Using {len(tools)} tools")
    
    # Track metrics
    tool_calls_count = 0
    total_input_tokens = 0
    total_output_tokens = 0
    max_iterations = 10
    iteration = 0
    
    # Tool call history for loop detection
    tool_history = []
    
    while iteration < max_iterations:
        iteration += 1
        print(f"📢 Step {iteration}: Calling LM Studio...")
        
        # Force text-only response after iteration 4
        if iteration >= 4:
            print(f"⚠️ Iteration {iteration}: Forcing text-only response")
            # Remove tools to force completion
            current_tools = []
        else:
            current_tools = tools
        
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=current_tools if current_tools else None,
                temperature=0.34,
            )
            
            choice = response.choices[0]
            message_content = choice.message
            
            # Update tokens
            if hasattr(response, 'usage'):
                total_input_tokens += response.usage.prompt_tokens
                total_output_tokens += response.usage.completion_tokens
            
            print(f"📡 API response received. Finish reason: {choice.finish_reason}")
            
            # Check for tool calls
            tool_calls = message_content.tool_calls
            
            if not tool_calls or iteration >= 4:
                # No more tool calls or forced completion
                final_text = message_content.content or ""
                
                # Strip <think> tags
                final_text = re.sub(r'<think>.*?</think>', '', final_text, flags=re.DOTALL).strip()
                
                if not final_text:
                    final_text = "Operation completed successfully."
                
                print(f"✅ Final response (no tools): {final_text[:100]}...")
                print(f"📢 ✅ Complete! ({tool_calls_count} tool calls)")
                
                return {
                    "reply": final_text,
                    "usage": {
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                        "total_tokens": total_input_tokens + total_output_tokens,
                        "tool_calls": tool_calls_count
                    }
                }
            
            # Execute tool calls
            print(f"🔧 Found {len(tool_calls)} tool call(s)")
            
            # Track tools for loop detection
            current_tool_names = [tc.function.name for tc in tool_calls]
            tool_history.append(current_tool_names)
            
            # Simple loop detection
            if len(tool_history) >= 3:
                if tool_history[-1] == tool_history[-2] == tool_history[-3]:
                    print(f"🔄 Loop detected: {tool_history[-1]}")
                    return {
                        "reply": f"Stopped after detecting loop. Executed {tool_calls_count} tool calls.",
                        "usage": {
                            "tool_calls": tool_calls_count
                        }
                    }
            
            # Execute each tool
            tool_results = []
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments
                
                print(f"📢 Executing: {tool_name}")
                
                # Import here to avoid circular dependency
                from utils.tools import execute_tool_call
                import json
                
                try:
                    args_dict = json.loads(tool_args) if tool_args else {}
                except:
                    args_dict = {}
                
                result = await execute_tool_call(tool_name, args_dict)
                
                tool_calls_count += 1
                
                # Add tool result to messages
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": str(result)
                })
            
            # Add assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": message_content.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in tool_calls
                ]
            })
            
            # Add tool results
            messages.extend(tool_results)
            
            print(f"✅ Executed {len(tool_calls)} tool(s) - Total: {tool_calls_count}")
            
        except Exception as e:
            print(f"❌ Error in LM Studio call: {e}")
            return {
                "reply": f"Error: {str(e)}",
                "usage": {
                    "tool_calls": tool_calls_count
                }
            }
    
    # Max iterations reached
    print(f"⚠️ Max iterations ({max_iterations}) reached")
    return {
        "reply": f"Task incomplete after {max_iterations} iterations. Executed {tool_calls_count} tool calls.",
        "usage": {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "tool_calls": tool_calls_count
        }
    }