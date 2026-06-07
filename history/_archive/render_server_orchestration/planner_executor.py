# planner_executor.py
# Opus 4.5 creates the plan, Haiku 4.5 executes it

import json
from anthropic import Anthropic

CLAUDE_MODEL_OPUS = "claude-opus-4-5-20251101"
CLAUDE_MODEL_HAIKU = "claude-haiku-4-5-20251001"

PLANNING_SYSTEM_PROMPT = """You are an expert Revit BIM planning assistant. Your job is to create detailed execution plans.

Given a user request, create a step-by-step plan with EXACT tool calls needed.

CRITICAL PARAMETER NAMES (use these exactly):
- create_floor: points, level_name, floor_type
- create_roof_footprint: points, level_name, slope_degrees, roof_type
- place_door: host_id, point, family_name, type_name (ALL FOUR REQUIRED)
- place_window: host_id, point, family_name, type_name (ALL FOUR REQUIRED)
- create_walls_batch: walls (array of {start_point, end_point, level_name, height})
- create_grids_batch: grids (array of {name, start_point, end_point})
- create_rooms_batch: rooms (array of {point, level_name, room_name, room_number})
- create_room_separation_lines: lines (array of {start_point, end_point}), level_name
- create_schedule: category_name, name
- add_schedule_fields: schedule_id, parameter_names
- set_element_parameter: element_id, param_name, value
- create_text_note: text, point, view_id
- create_sheet: name, number, titleblock
- place_view_on_sheet: sheet_id, view_id, point
- create_dimension: element_ids, start_point, end_point, view_id

PLACEHOLDER NAMING CONVENTION (use these exact formats):
- Wall IDs from batch: {{west_wall_id_from_step_N}} or {{south_wall_id_from_step_N}}
- Any ID by index: {{id_index_0_from_step_N}}, {{id_index_1_from_step_N}}
- Schedule ID: {{schedule_id_from_step_N}}
- Sheet ID: {{sheet_id_from_step_N}}
- View ID: {{level_0_view_id_from_step_N}}
Where N is the step number that created the element.

IMPORTANT RULES:
1. Use "list_" tools FIRST to get IDs and available types before creating anything
2. Each step should be ONE tool call
3. Include exact parameter values where known - copy type names EXACTLY from list results
4. For place_door/place_window: Extract family_name from type (e.g., "Doors_IntSgl : 910x2110mm" → family_name="Doors_IntSgl", type_name="910x2110mm")
5. Group related operations (e.g., create all walls, then all doors)
6. For batch tools, pass arrays of OBJECTS not flat arrays
7. Use Level 0 (not Level 1) as the base level unless user specifies otherwise

Return ONLY a JSON object in this format:
{
  "summary": "Brief description of what will be created",
  "steps": [
    {"step": 1, "description": "Get current levels", "tool": "list_levels", "params": {}},
    {"step": 2, "description": "Create walls", "tool": "create_walls_batch", "params": {"walls": [...]}},
    {"step": 3, "description": "Place door on west wall", "tool": "place_door", "params": {
      "host_id": "{{west_wall_id_from_step_2}}",
      "point": [100, 12.5, 0],
      "family_name": "Doors_IntSgl",
      "type_name": "910x2110mm"
    }}
  ]
}

Be precise with coordinates and parameters. The executor will run these EXACTLY as specified."""

EXECUTOR_SYSTEM_PROMPT = """You are a Revit tool executor. You have a plan to follow.

Your job is to execute ONE step at a time from the plan.
- Call the exact tool specified
- Use the exact parameters given
- If a parameter references a previous step (like {{wall_id_from_step_3}}), use the actual value from the results

After executing, report what was done and any IDs created."""


async def create_plan_with_opus(client: Anthropic, user_request: str, available_tools: list) -> dict:
    """Use Opus to create a detailed execution plan with visible reasoning."""
    
    # Give Opus the tool schemas so it knows what's available
    tool_summary = []
    for tool in available_tools:
        name = tool.get("name", "")
        desc = tool.get("description", "")[:100]
        tool_summary.append(f"- {name}: {desc}")
    
    tools_text = "\n".join(tool_summary)
    
    planning_prompt = f"""Available tools:
{tools_text}

User request:
{user_request}

Think through this step-by-step:
1. What elements need to be created?
2. What order should they be created in?
3. What information do I need to gather first (list_ tools)?
4. What are the exact coordinates and parameters?

Then create a detailed execution plan with exact tool calls and parameters.
Return ONLY valid JSON at the end, no other text after the JSON."""

    print("🧠 OPUS: Creating execution plan...")
    print("=" * 60)
    
    # Retry logic for network errors
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print("💭 OPUS THINKING:")
            print("-" * 60)
            
            # Use streaming to show reasoning in real-time
            thinking_text = ""
            plan_text = ""
            
            with client.messages.stream(
                model=CLAUDE_MODEL_OPUS,
                max_tokens=8000,
                thinking={
                    "type": "enabled",
                    "budget_tokens": 5000  # Allow up to 5000 tokens for thinking
                },
                system=PLANNING_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": planning_prompt}]
            ) as stream:
                for event in stream:
                    # Handle thinking blocks
                    if hasattr(event, 'type'):
                        if event.type == 'content_block_start':
                            if hasattr(event, 'content_block'):
                                if event.content_block.type == 'thinking':
                                    print("\n💭 [Thinking...]")
                                elif event.content_block.type == 'text':
                                    print("\n📝 [Planning...]")
                        
                        elif event.type == 'content_block_delta':
                            if hasattr(event, 'delta'):
                                if hasattr(event.delta, 'thinking'):
                                    # Print thinking in real-time
                                    chunk = event.delta.thinking
                                    print(chunk, end='', flush=True)
                                    thinking_text += chunk
                                elif hasattr(event.delta, 'text'):
                                    # Collect plan text
                                    chunk = event.delta.text
                                    print(chunk, end='', flush=True)
                                    plan_text += chunk
            
            print("\n" + "-" * 60)
            print(f"💭 Total thinking: {len(thinking_text)} chars")
            print("=" * 60)
            
            # Successfully got response, break retry loop
            break
            
        except Exception as e:
            print(f"\n❌ Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"🔄 Retrying in 2 seconds...")
                import time
                time.sleep(2)
            else:
                print("❌ All retries failed")
                return None
    
    # Clean up markdown if present
    if "```json" in plan_text:
        plan_text = plan_text.split("```json")[1].split("```")[0]
    elif "```" in plan_text:
        plan_text = plan_text.split("```")[1].split("```")[0]
    
    try:
        plan = json.loads(plan_text.strip())
        print(f"📋 OPUS: Plan created with {len(plan.get('steps', []))} steps")
        print(f"📋 Summary: {plan.get('summary', 'No summary')}")
        
        # Print the steps
        print("\n📋 EXECUTION PLAN:")
        print("-" * 40)
        for step in plan.get('steps', []):
            print(f"  Step {step.get('step', '?')}: {step.get('description', 'No description')}")
            print(f"         Tool: {step.get('tool', 'Unknown')}")
        print("-" * 40)
        
        return plan
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse plan: {e}")
        print(f"Raw response: {plan_text[:500]}")
        return None


async def execute_plan_with_haiku(
    client: Anthropic, 
    plan: dict, 
    execute_tool_func,
    available_tools: list
) -> dict:
    """Use Haiku to execute each step of the plan."""
    
    # Parameter aliases - map common variations to actual param names
    PARAM_ALIASES = {
        # Points/locations
        "boundary_points": "points",
        "location": "point",
        "position": "point",
        # IDs
        "wall_id": "host_id",
        # Type names for doors/windows
        "door_type": "type_name",
        "window_type": "type_name",
        # Parameters
        "parameter_name": "param_name",
        "param": "param_name",
        # Schedule - create_schedule uses category_name and name
        "category": "category_name",
        "schedule_name": "name",
        # Schedule fields - add_schedule_fields uses parameter_names
        "field_names": "parameter_names",
        "fields": "parameter_names",
        # Sheet - create_sheet uses name and number
        "sheet_number": "number",
        "sheet_name": "name",
        "title_block": "titleblock",
        # Roof
        "slope": "slope_degrees",
        # Dimension - uses element_ids, start_point, end_point
        "references": "element_ids",
        # Room separation lines
        "start": "start_point",
        "end": "end_point",
    }
    
    def fix_params(params: dict) -> dict:
        """Fix parameter names using aliases, including nested objects."""
        fixed = {}
        for key, value in params.items():
            # Check if this key has an alias
            new_key = PARAM_ALIASES.get(key, key)
            
            # If value is a list, check for nested objects that need fixing
            if isinstance(value, list):
                fixed_list = []
                for item in value:
                    if isinstance(item, dict):
                        # Fix nested object keys
                        fixed_item = {}
                        for k, v in item.items():
                            new_k = PARAM_ALIASES.get(k, k)
                            fixed_item[new_k] = v
                        fixed_list.append(fixed_item)
                    else:
                        fixed_list.append(item)
                fixed[new_key] = fixed_list
            else:
                fixed[new_key] = value
        return fixed
    
    results = {
        "success": True,
        "steps_completed": 0,
        "steps_total": len(plan.get("steps", [])),
        "step_results": [],
        "errors": []
    }
    
    # Track results for variable substitution
    step_outputs = {}  # step_num -> raw result
    extracted_ids = {}  # "wall_ids_from_step_5" -> [id1, id2, ...]
    
    def extract_ids_from_result(result, step_num, tool_name):
        """Extract IDs from tool results and store them for later use."""
        try:
            # Handle both string JSON and already-parsed objects
            if isinstance(result, str):
                # Check if it's an error message
                if result.startswith("Error") or result.startswith("=== ERROR"):
                    # Try to extract from error message if it contains results
                    if "results:" in result:
                        # Parse the results part
                        import re
                        match = re.search(r"results: (\[.*\])", result)
                        if match:
                            try:
                                data = {"results": eval(match.group(1))}
                            except:
                                return
                        else:
                            return
                    else:
                        return
                else:
                    try:
                        data = json.loads(result)
                    except json.JSONDecodeError:
                        return
            else:
                data = result
            
            # Handle different result formats
            if isinstance(data, dict):
                # Single item with ID
                if "id" in data:
                    extracted_ids[f"id_from_step_{step_num}"] = data["id"]
                    extracted_ids[f"{tool_name}_id"] = data["id"]
                
                # Batch results - e.g. {"status": "batch_complete", "results": [...]}
                if "results" in data and isinstance(data["results"], list):
                    ids = []
                    for i, r in enumerate(data["results"]):
                        if isinstance(r, dict):
                            # Handle nested format: {'index': 0, 'result': {'id': '123'}}
                            if "result" in r and isinstance(r["result"], dict):
                                rid = r["result"].get("id")
                                if rid:
                                    ids.append(rid)
                                    # Store by index
                                    extracted_ids[f"wall_id_index_{i}_from_step_{step_num}"] = rid
                                    extracted_ids[f"id_index_{i}_from_step_{step_num}"] = rid
                            # Handle flat format: {'id': '123'}
                            elif r.get("id"):
                                ids.append(r["id"])
                                extracted_ids[f"wall_id_index_{i}_from_step_{step_num}"] = r["id"]
                                extracted_ids[f"id_index_{i}_from_step_{step_num}"] = r["id"]
                    
                    if ids:
                        extracted_ids[f"ids_from_step_{step_num}"] = ids
                        # Store by position for walls (clockwise from south)
                        if "wall" in tool_name.lower():
                            if len(ids) >= 1: extracted_ids[f"south_wall_id_from_step_{step_num}"] = ids[0]
                            if len(ids) >= 2: extracted_ids[f"east_wall_id_from_step_{step_num}"] = ids[1]
                            if len(ids) >= 3: extracted_ids[f"north_wall_id_from_step_{step_num}"] = ids[2]
                            if len(ids) >= 4: extracted_ids[f"west_wall_id_from_step_{step_num}"] = ids[3]
                        if "grid" in tool_name.lower():
                            for i, gid in enumerate(ids):
                                extracted_ids[f"grid_{i+1}_id_from_step_{step_num}"] = gid
                
                # Schedule ID
                if "schedule_id" in data:
                    extracted_ids[f"schedule_id_from_step_{step_num}"] = data["schedule_id"]
                
                # Sheet ID  
                if "sheet_id" in data:
                    extracted_ids[f"sheet_id_from_step_{step_num}"] = data["sheet_id"]
                
                # Floor/Roof ID
                if "floor_id" in data:
                    extracted_ids[f"floor_id_from_step_{step_num}"] = data["floor_id"]
                if "roof_id" in data:
                    extracted_ids[f"roof_id_from_step_{step_num}"] = data["roof_id"]
                    
                # View ID from list_views - check for "views" key
                if "views" in data:
                    for v in data.get("views", []):
                        if isinstance(v, dict):
                            vname = str(v.get("name", "")).lower()
                            vid = v.get("id")
                            if vid:
                                if "level 0" in vname:
                                    extracted_ids[f"level_0_view_id_from_step_{step_num}"] = vid
                                if "level 1" in vname:
                                    extracted_ids[f"level_1_view_id_from_step_{step_num}"] = vid
                
            elif isinstance(data, list):
                # List of items - extract IDs and store by index and name
                ids = []
                for i, item in enumerate(data):
                    if isinstance(item, dict):
                        item_id = item.get("id")
                        item_name = item.get("name", "")
                        
                        if item_id:
                            ids.append(item_id)
                            # Store by index
                            extracted_ids[f"id_index_{i}_from_step_{step_num}"] = item_id
                            
                            # Store first item specially
                            if i == 0:
                                extracted_ids[f"first_id_from_step_{step_num}"] = item_id
                                extracted_ids[f"first_{tool_name}_id"] = item_id
                                # For door/window types
                                if "door" in tool_name.lower():
                                    extracted_ids[f"first_door_type_from_step_{step_num}"] = item_name
                                    extracted_ids[f"first_door_type_id"] = item_id
                                if "window" in tool_name.lower():
                                    extracted_ids[f"first_window_type_from_step_{step_num}"] = item_name
                                    extracted_ids[f"first_window_type_id"] = item_id
                            
                            # Store level IDs by name
                            if "level" in tool_name.lower():
                                level_key = item_name.replace(' ', '_').lower() + "_id"
                                extracted_ids[level_key] = item_id
                            
                            # Store view IDs by name  
                            if "view" in tool_name.lower():
                                name_lower = item_name.lower()
                                if "level 0" in name_lower:
                                    extracted_ids[f"level_0_view_id_from_step_{step_num}"] = item_id
                                if "level 1" in name_lower:
                                    extracted_ids[f"level_1_view_id_from_step_{step_num}"] = item_id
                
                if ids:
                    extracted_ids[f"ids_from_step_{step_num}"] = ids
                    # If this is walls, store by position
                    if "wall" in tool_name.lower():
                        if len(ids) >= 1: extracted_ids[f"south_wall_id_from_step_{step_num}"] = ids[0]
                        if len(ids) >= 2: extracted_ids[f"east_wall_id_from_step_{step_num}"] = ids[1]
                        if len(ids) >= 3: extracted_ids[f"north_wall_id_from_step_{step_num}"] = ids[2]
                        if len(ids) >= 4: extracted_ids[f"west_wall_id_from_step_{step_num}"] = ids[3]
            
            # Debug: Print what we extracted
            if extracted_ids:
                print(f"   🔑 Extracted IDs: {list(extracted_ids.keys())[-10:]}")  # Show last 10 keys
                        
        except Exception as e:
            print(f"   ⚠️ Could not extract IDs: {e}")
    
    def resolve_placeholders(params_str):
        """Replace all {{placeholder}} patterns with actual values."""
        import re
        
        # Find all placeholders like {{something_from_step_N}}
        pattern = r'\{\{([^}]+)\}\}'
        
        def replace_match(match):
            placeholder_name = match.group(1)
            
            # Check if we have this ID
            if placeholder_name in extracted_ids:
                value = extracted_ids[placeholder_name]
                # Return raw value - the JSON already has quotes around the placeholder
                # So "{{placeholder}}" becomes "value" (value replaces {{placeholder}})
                return str(value)
            
            # Try partial matches
            for key, value in extracted_ids.items():
                if placeholder_name.replace("_", "") in key.replace("_", ""):
                    return str(value)
            
            # Not found - return as-is (will likely cause an error)
            print(f"   ⚠️ Unresolved placeholder: {placeholder_name}")
            print(f"   📋 Available IDs: {list(extracted_ids.keys())}")
            return match.group(0)
        
        return re.sub(pattern, replace_match, params_str)
    
    for step in plan.get("steps", []):
        step_num = step.get("step", 0)
        tool_name = step.get("tool", "")
        params = step.get("params", {})
        description = step.get("description", "")
        
        print(f"\n🔧 Step {step_num}: {description}")
        print(f"   Tool: {tool_name}")
        
        # Resolve placeholders with actual IDs
        params_str = json.dumps(params)
        params_str = resolve_placeholders(params_str)
        try:
            params = json.loads(params_str)
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON parse error after placeholder resolution: {e}")
            print(f"   Params string: {params_str[:200]}")
            results["errors"].append({
                "step": step_num,
                "tool": tool_name,
                "error": f"Placeholder resolution failed: {e}"
            })
            continue
        
        # Fix parameter names using aliases
        params = fix_params(params)
        
        print(f"   Params: {json.dumps(params)[:200]}...")
        
        # Execute the tool directly
        try:
            result = await execute_tool_func(tool_name, params)
            step_outputs[step_num] = result
            
            # DEBUG: Print the raw result to see what we're getting
            print(f"   📤 Raw result: {str(result)[:500]}")
            
            # Extract IDs for future steps
            extract_ids_from_result(result, step_num, tool_name)
            
            # DEBUG: Print extracted IDs so far
            if extracted_ids:
                print(f"   🔑 Extracted IDs: {list(extracted_ids.keys())}")
            
            print(f"   ✅ Success")
            results["steps_completed"] += 1
            results["step_results"].append({
                "step": step_num,
                "tool": tool_name,
                "status": "success",
                "result_preview": str(result)[:200]
            })
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results["errors"].append({
                "step": step_num,
                "tool": tool_name,
                "error": str(e)
            })
            # Continue with next step (don't stop on errors)
    
    results["success"] = len(results["errors"]) == 0
    return results


async def plan_and_execute(
    client: Anthropic,
    user_request: str,
    execute_tool_func,
    available_tools: list
) -> dict:
    """Main function: Opus plans, Haiku executes."""
    
    print("\n" + "="*60)
    print("🎯 PLANNER-EXECUTOR MODE")
    print("="*60)
    
    # Step 1: Opus creates the plan
    plan = await create_plan_with_opus(client, user_request, available_tools)
    
    if not plan:
        return {
            "success": False,
            "error": "Failed to create plan",
            "reply": "I couldn't create an execution plan for this request."
        }
    
    # Step 2: Execute each step
    print("\n" + "-"*60)
    print("⚡ EXECUTING PLAN")
    print("-"*60)
    
    results = await execute_plan_with_haiku(
        client, 
        plan, 
        execute_tool_func,
        available_tools
    )
    
    # Step 3: Summary
    print("\n" + "="*60)
    print("📊 EXECUTION COMPLETE")
    print(f"   Steps: {results['steps_completed']}/{results['steps_total']}")
    print(f"   Errors: {len(results['errors'])}")
    print("="*60)
    
    # Build reply
    if results["success"]:
        reply = f"✅ Successfully completed all {results['steps_total']} steps!\n\n"
        reply += f"**Plan:** {plan.get('summary', 'N/A')}\n\n"
        reply += "**Steps completed:**\n"
        for step in plan.get("steps", []):
            reply += f"- Step {step['step']}: {step['description']}\n"
    else:
        reply = f"⚠️ Completed {results['steps_completed']}/{results['steps_total']} steps with {len(results['errors'])} errors.\n\n"
        for err in results["errors"]:
            reply += f"- Step {err['step']} ({err['tool']}): {err['error']}\n"
    
    return {
        "success": results["success"],
        "plan": plan,
        "results": results,
        "reply": reply
    }