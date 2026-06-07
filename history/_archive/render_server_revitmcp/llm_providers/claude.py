"""Claude chat logic provider"""

import asyncio
from typing import Dict, Any, List
from anthropic import Anthropic

from utils.history import sanitize_history, compress_history
from utils.tools import execute_tool_call, summarize_tool_result

def initialize(config: Dict) -> Dict:
    """Initialize Claude client"""
    import os
    api_key = os.environ.get(config["claude"]["api_key_env"])
    if not api_key:
        raise ValueError(f"Missing {config['claude']['api_key_env']} environment variable")
    
    client = Anthropic(api_key=api_key)
    
    return {
        "client": client,
        "model_sonnet": config["claude"]["model_sonnet"],
        "model_haiku": config["claude"]["model_haiku"]
    }

def select_model(message: str, iteration: int) -> str:
    """Select appropriate Claude model based on complexity"""
    message_lower = message.lower()
    
    if iteration == 1:
        simple_keywords = ["list", "get", "show", "what are", "how many", "find"]
        complex_keywords = ["create", "build", "design", "plan", "why", "explain", "multiple"]
        
        is_simple = any(kw in message_lower for kw in simple_keywords)
        is_complex = any(kw in message_lower for kw in complex_keywords)
        
        if is_simple and not is_complex:
            return "haiku"
        else:
            return "sonnet"
    
    return "haiku"

async def handle_claude_chat(
    message: str,
    history: List[Dict],
    clients: Dict,
    tools: List[Dict]
) -> Dict[str, Any]:
    """Process chat request using Claude"""
    
    client = clients["client"]
    model_sonnet = clients["model_sonnet"]
    model_haiku = clients["model_haiku"]
    
    # Initialize tracking
    total_input_tokens = 0
    total_output_tokens = 0
    total_tool_calls = 0
    progress_updates = []
    
    def add_progress(msg: str):
        print(f"📢 {msg}")
        progress_updates.append(msg)
    
    system_prompt = """You are an expert Revit Automation Assistant. 
    You have access to tools to modify the model directly.
    Your priority is to complete the user's request using the available tools.
    You MUST execute tool calls one after the other until the request is complete.
    ALWAYS 'List then Act'. Do not guess IDs or names."""
    
    # Sanitize and build messages
    llm_messages = sanitize_history(history, provider="claude")
    
    # Limit history
    MAX_HISTORY = 10
    if len(llm_messages) > MAX_HISTORY:
        llm_messages = llm_messages[-MAX_HISTORY:]
    
    # Add current message
    llm_messages.append({
        "role": "user",
        "content": [{"type": "text", "text": message}]
    })
    
    # Convert tools to Claude format
    claude_tools = convert_to_claude_tools(tools)
    
    # Build base options
    base_options = {
        "max_tokens": 4096,
        "system": system_prompt,
        "tools": claude_tools
    }
    
    max_iterations = 15
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        # Select model
        model_choice = select_model(message, iteration)
        selected_model = model_sonnet if model_choice == "sonnet" else model_haiku
        base_options["model"] = selected_model
        
        # Compress if needed
        if len(llm_messages) > 12:
            llm_messages = [llm_messages[0]] + llm_messages[-8:]
        
        # Safety: Force stop at high iterations
        if iteration >= 12:
            add_progress(f"⚠️ Max iterations approaching")
            return {
                "reply": "Task too complex. Please break into smaller steps.",
                "usage": {
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                    "total_tokens": total_input_tokens + total_output_tokens,
                    "tool_calls": total_tool_calls
                }
            }
        
        add_progress(f"Step {iteration}: Calling Claude ({model_choice})...")
        
        # API call
        api_options = {**base_options, "messages": llm_messages}
        
        try:
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: client.messages.create(**api_options)),
                timeout=180.0
            )
            
            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens
            
        except asyncio.TimeoutError:
            return {
                "reply": f"API timeout on iteration {iteration}",
                "usage": {
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                    "total_tokens": total_input_tokens + total_output_tokens,
                    "tool_calls": total_tool_calls
                }
            }
        except Exception as e:
            return {
                "reply": f"Claude API Error: {str(e)}",
                "usage": {
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                    "total_tokens": total_input_tokens + total_output_tokens,
                    "tool_calls": total_tool_calls
                }
            }
        
        # Get tool use blocks
        tool_use_blocks = [block for block in response.content if block.type == "tool_use"]
        
        # No tools = done
        if not tool_use_blocks:
            final_text = next(
                (block.text for block in response.content if block.type == "text"),
                None
            )
            add_progress(f"✅ Complete! ({total_tool_calls} tool calls)")
            return {
                "reply": final_text or "Task completed.",
                "usage": {
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                    "total_tokens": total_input_tokens + total_output_tokens,
                    "tool_calls": total_tool_calls
                }
            }
        
        # Serialize assistant response
        assistant_content = []
        for block in response.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": dict(block.input)
                })
        
        llm_messages.append({"role": "assistant", "content": assistant_content})
        
        # Execute tools
        tool_results = []
        for tool_use_block in tool_use_blocks:
            tool_name = tool_use_block.name
            tool_input = dict(tool_use_block.input)
            tool_id = tool_use_block.id
            
            add_progress(f"Executing: {tool_name}")
            
            result = await execute_tool_call(tool_name, tool_input)
            summarized_result = summarize_tool_result(str(result))
            
            total_tool_calls += 1
            
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": summarized_result
            })
        
        # Add tool results
        llm_messages.append({
            "role": "user",
            "content": tool_results
        })
        
        # Check if we should return
        if response.stop_reason == "end_turn":
            final_text = next(
                (block.text for block in response.content if block.type == "text"),
                None
            )
            if final_text:
                add_progress(f"✅ Complete! ({total_tool_calls} tool calls)")
                return {
                    "reply": final_text,
                    "usage": {
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                        "total_tokens": total_input_tokens + total_output_tokens,
                        "tool_calls": total_tool_calls
                    }
                }
    
    # Max iterations
    return {
        "reply": f"Maximum iterations ({max_iterations}) reached.",
        "usage": {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "tool_calls": total_tool_calls
        }
    }

def convert_to_claude_tools(openai_tools: List[Dict]) -> List[Dict]:
    """Convert OpenAI-style tools to Claude format"""
    claude_tools = []
    for tool in openai_tools:
        func = tool["function"]
        claude_tools.append({
            "name": func["name"],
            "description": func["description"],
            "input_schema": func["parameters"]
        })
    return claude_tools
