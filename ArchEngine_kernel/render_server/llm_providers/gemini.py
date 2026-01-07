"""Gemini chat logic provider"""

import os
from typing import Dict, Any, List
import google.generativeai as genai
import json
import time 

def detect_loop(tool_history: List[List[str]], threshold: int = 3) -> bool:
    """
    Detect if LLM is stuck in a loop calling the same tools repeatedly.
    
    Args:
        tool_history: List of tool calls per iteration
        threshold: How many times same tools must repeat to be considered a loop
    
    Returns:
        True if loop detected, False otherwise
    """
    if len(tool_history) < threshold:
        return False
    
    # Check if last N iterations called identical tools
    last_n = tool_history[-threshold:]
    
    # All must be identical
    if all(tools == last_n[0] for tools in last_n):
        return True
    
    # Check if single tool being spammed
    if len(tool_history) >= threshold:
        for tool_name in set(sum(tool_history, [])):  # Flatten and get unique tools
            count = sum(1 for iteration_tools in tool_history if tool_name in iteration_tools)
            if count >= threshold * 2:  # Same tool called in 6+ iterations
                return True
    
    return False


def initialize(config: Dict) -> Dict:
    """Initialize Gemini client"""
    api_key = os.getenv(config["gemini"]["api_key_env"])
    if not api_key:
        raise ValueError(f"Missing {config['gemini']['api_key_env']} environment variable")
    
    genai.configure(api_key=api_key)
    
    print(f"✅ Gemini configured with model: {config['gemini']['model']}")
    
    return {
        "model": config["gemini"]["model"],
        "configured": True
    }

async def handle_gemini_chat(

    message: str,
    history: List[Dict],
    clients: Dict,
    tools: List[Dict],
    progress_callback=None

) -> Dict[str, Any]:
    """Process chat request using Gemini"""
    
    model_name = clients["model"]
    
    # Convert tools to Gemini format
    gemini_tools = convert_to_gemini_tools(tools)
    
    # Initialize model
    model = genai.GenerativeModel(
        model_name=model_name,
        tools=gemini_tools
    )
    
    # Build conversation history
    gemini_history = []
    for msg in history:
        if msg["role"] == "user":
            gemini_history.append({"role": "user", "parts": [msg["content"]]})
        elif msg["role"] == "assistant":
            gemini_history.append({"role": "model", "parts": [msg["content"]]})
    
    # Start chat
    chat = model.start_chat(history=gemini_history)
    
    # Track metrics
    tool_calls_count = 0
    total_input_tokens = 0
    total_output_tokens = 0
    max_iterations = 50  # Much higher
    timeout_seconds = 120  # 2 minute timeout
    start_time = time.time()
    tool_history = []  # ← Must be here, before the loop
    consecutive_errors = 0
    
    # Smart detection:
    if detect_loop(tool_history):
        return "Detected loop, stopping"
    if time.time() - start_time > timeout_seconds:
        return "Timeout, task too complex"
    if consecutive_errors >= 3:
        return "Too many errors, stopping"
    
    # Otherwise, keep going!
    # ADD THESE LINES:
    tool_history = []  # Track tool calls per iteration for loop detection
    consecutive_errors = 0  # Track consecutive errors
    # Send initial message
    response = chat.send_message(message)
    
    # Main loop for tool execution
    for iteration in range(max_iterations):
        print(f"📡 Gemini iteration {iteration + 1}/{max_iterations}")
        
        # Update tokens
        total_input_tokens += response.usage_metadata.prompt_token_count
        total_output_tokens += response.usage_metadata.candidates_token_count
        
        # Debug response
        print("="*60)
        print(f"🔍 GEMINI RESPONSE DEBUG:")
        print(f"   Finish reason: {response.candidates[0].finish_reason}")
        print(f"   Content parts: {len(response.candidates[0].content.parts)}")
        
        for i, part in enumerate(response.candidates[0].content.parts):
            print(f"   Part {i}: {type(part)}")
            if hasattr(part, 'function_call') and part.function_call.name:
                print(f"      - Function call: {part.function_call.name}")
            if hasattr(part, 'text') and part.text:
                print(f"      - Text: {part.text[:100]}...")
        
        print("="*60)
        
        # Check for function calls
        function_calls = []
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'function_call') and part.function_call.name:
                function_calls.append(part.function_call)
        # Check for function calls
        function_calls = []
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'function_call') and part.function_call.name:
                function_calls.append(part.function_call)

        # ADD THIS: Track tools called this iteration
        current_tool_names = [fc.name for fc in function_calls]
        tool_history.append(current_tool_names)

        # Loop detection
        if len(tool_history) >= 3 and tool_history[-1] == tool_history[-2] == tool_history[-3]:
            print(f"🔄 Loop detected: {tool_history[-1]}")
            return {
                "reply": f"Detected loop after {tool_calls_count} tool calls. Stopping.",
                "usage": {...}
            }
        MAX_TOOLS_PER_ITER = 3
        if len(function_calls) > MAX_TOOLS_PER_ITER:
            print(f"⚠️ Limiting {len(function_calls)} function calls to {MAX_TOOLS_PER_ITER}")
            function_calls = function_calls[:MAX_TOOLS_PER_ITER]


        # No function calls - return text response
        if not function_calls:
            try:
                final_text = response.text
            except ValueError:
                print(f"⚠️ No text in response")
                final_text = "Task completed."
            
            return {
                "reply": final_text,
                "usage": {
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                    "total_tokens": total_input_tokens + total_output_tokens,
                    "tool_calls": tool_calls_count
                }
            }
        
        # Execute function calls
        # Helper function to convert protobuf to Python types
        def convert_protobuf_to_dict(obj):
            
            # Import at function level to avoid issues
            try:
                from proto.marshal.collections.maps import MapComposite
                from proto.marshal.collections.repeated import RepeatedComposite
            except ImportError:
                # Fallback if imports fail
                MapComposite = None
                RepeatedComposite = None
    
            """Recursively convert protobuf objects to native Python types"""
            if isinstance(obj, str):
                return obj
            elif isinstance(obj, (int, float, bool)):
                return obj
            elif obj is None:
                return None
            elif MapComposite and isinstance(obj, MapComposite):
                return {key: convert_protobuf_to_dict(value) for key, value in dict(obj).items()}
            elif isinstance(obj, dict):
                return {key: convert_protobuf_to_dict(value) for key, value in obj.items()}
            elif RepeatedComposite and isinstance(obj, RepeatedComposite):
                return [convert_protobuf_to_dict(item) for item in obj]
            elif isinstance(obj, (list, tuple)):
                return [convert_protobuf_to_dict(item) for item in obj]
            elif hasattr(obj, 'items'):
                return {key: convert_protobuf_to_dict(value) for key, value in obj.items()}
            elif hasattr(obj, '__iter__') and not isinstance(obj, str):
                return [convert_protobuf_to_dict(item) for item in obj]
            else:
                return obj

        # Execute function calls
        function_responses = []
        for fc in function_calls:
            tool_calls_count += 1
            tool_name = fc.name
    
            # Convert protobuf args to Python dict/list
            tool_args = convert_protobuf_to_dict(dict(fc.args))
    
            print(f"🔧 Gemini calling tool: {tool_name}")
            print(f"🔍 Converted args: {json.dumps(tool_args, indent=2)}")
    
            # Execute tool
            from utils.tools import execute_tool_call
            result = await execute_tool_call(tool_name, tool_args)
    
            print(f"📋 Tool result: {str(result)[:200]}...")
    
            # Format response for Gemini
            function_responses.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=tool_name,
                        response={"result": str(result)}
                    )
                )
            )

        # Send function results back and get next response
        response = chat.send_message(function_responses)
    
    # Max iterations reached
    return {
        "reply": "Task completed (max iterations reached)",
        "usage": {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "tool_calls": tool_calls_count
        }
    }

def convert_to_gemini_tools(tools_list: List[Dict]) -> List:
    """Convert OpenAI-style tools to Gemini function declarations"""
    gemini_functions = []
    
    for tool in tools_list:
        if tool["type"] != "function":
            continue
        
        func = tool["function"]
        
        # Build parameters schema
        required = func.get("parameters", {}).get("required", [])
        properties = func.get("parameters", {}).get("properties", {})
        
        # Convert properties to Gemini schema
        gemini_properties = {}
        for param_name, param_info in properties.items():
            param_type_str = param_info.get("type", "string").upper()
            
            try:
                # Handle array types with items
                if param_type_str == "ARRAY":
                    items_info = param_info.get("items", {})
                    items_type_str = items_info.get("type", "string").upper()
                    
                    # Check if array contains arrays (nested)
                    if items_type_str == "ARRAY":
                        # Nested array - items contains arrays of numbers
                        nested_items = items_info.get("items", {})
                        nested_type_str = nested_items.get("type", "number").upper()
                        
                        gemini_properties[param_name] = genai.protos.Schema(
                            type=genai.protos.Type.ARRAY,
                            description=param_info.get("description", ""),
                            items=genai.protos.Schema(
                                type=genai.protos.Type.ARRAY,
                                items=genai.protos.Schema(
                                    type=getattr(genai.protos.Type, nested_type_str, genai.protos.Type.NUMBER)
                                )
                            )
                        )
                    else:
                        # Regular array
                        gemini_properties[param_name] = genai.protos.Schema(
                            type=genai.protos.Type.ARRAY,
                            description=param_info.get("description", ""),
                            items=genai.protos.Schema(
                                type=getattr(genai.protos.Type, items_type_str, genai.protos.Type.STRING)
                            )
                        )
                else:
                    # Regular types (string, number, boolean, etc)
                    gemini_properties[param_name] = genai.protos.Schema(
                        type=getattr(genai.protos.Type, param_type_str, genai.protos.Type.STRING),
                        description=param_info.get("description", "")
                    )
            except Exception as e:
                print(f"⚠️ Skipping parameter {param_name} in {func['name']}: {e}")
                continue
        
        # Create Gemini function declaration
        try:
            gemini_func = genai.protos.FunctionDeclaration(
                name=func["name"],
                description=func.get("description", ""),
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties=gemini_properties,
                    required=required
                )
            )
            
            gemini_functions.append(gemini_func)
            
        except Exception as e:
            print(f"⚠️ Failed to convert tool {func['name']}: {e}")
            continue
    
    print(f"✅ Converted {len(gemini_functions)} tools for Gemini")
    
    if not gemini_functions:
        print("⚠️ No tools successfully converted for Gemini")
        return []
    
    return [genai.protos.Tool(function_declarations=gemini_functions)]
