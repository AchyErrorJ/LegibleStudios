# planner.py
import json
import logging
import re

logger = logging.getLogger(__name__)

class PlanningAgent:
    def __init__(self, executor, available_tools):
        """
        Initializes the Planning Agent.
        
        Args:
            executor: The LLM Executor class (handles the API call to LM Studio).
            available_tools: Dictionary of {tool_name: function_object}.
        """
        self.executor = executor
        self.available_tools = available_tools
        self.history = []
        self.system_prompt = self._construct_system_prompt()

    def _construct_system_prompt(self):
        """Generates the System Prompt, including the dynamic tool list."""
        tool_descriptions = []
        
        # Loop through the registered tools to generate documentation
        for name, func in self.available_tools.items():
            # Try to get metadata from the decorator if available, else docstring
            desc = getattr(func, "tool_description", func.__doc__ or "No description provided.")
            
            # Simple signature generation
            tool_descriptions.append(f"- {name}: {desc}")

        tools_str = "\n".join(tool_descriptions)

        return f"""You are an expert Revit Automation Architect. You have access to a specific set of Python tools to control Autodesk Revit.

### YOUR GOAL
You must answer the user's request by orchestrating the necessary tool calls. You can call multiple tools in sequence if needed.

### AVAILABLE TOOLS
{tools_str}

### RESPONSE FORMAT
You must output your thought process and tool calls in a specific JSON format.
If you need to call a tool, output a JSON block like this:

{{
    "thought": "I need to check the wall types first.",
    "tool": "list_wall_types",
    "args": {{}}
}}

If the tool requires arguments (like creating a wall), provide them in "args":

{{
    "thought": "I will create a wall from (0,0,0) to (10,0,0).",
    "tool": "create_wall",
    "args": {{
        "start_point": [0, 0, 0],
        "end_point": [10, 0, 0],
        "level_name": "Level 1",
        "height": 12.0
    }}
}}

### FINAL ANSWER
When you have completed the task or if you just need to answer a question without tools, output a JSON block with "final_answer":

{{
    "thought": "I have finished creating the walls.",
    "final_answer": "I have successfully created the walls on Level 1."
}}

Do not output any text outside of the JSON block.
"""

    def get_next_action(self, user_input: str):
        """Sends the context to the LLM and gets the next response."""
        # 1. Add user input to history
        self.history.append({"role": "user", "content": user_input})
        
        # 2. Call the LLM Executor
        # We assume the executor handles the actual API call logic
        response_text = self.executor.generate_response(
            system_prompt=self.system_prompt,
            history=self.history
        )
        
        # 3. Add response to history (temporarily, we might refine this)
        self.history.append({"role": "assistant", "content": response_text})
        
        return response_text

    def check_for_final_answer(self, llm_response: str) -> bool:
        """Checks if the LLM provided a final answer."""
        try:
            data = self._parse_json(llm_response)
            return "final_answer" in data
        except:
            return False

    def extract_final_answer(self, llm_response: str) -> str:
        """Extracts the final answer text."""
        try:
            data = self._parse_json(llm_response)
            return data.get("final_answer", str(data))
        except:
            return llm_response

    def parse_tool_call(self, llm_response: str) -> dict:
        """Parses the tool name and arguments from the LLM response."""
        data = self._parse_json(llm_response)
        
        if "tool" not in data:
            raise ValueError("No 'tool' key found in LLM response.")
            
        return {
            "name": data["tool"],
            "args": data.get("args", {})
        }

    def add_tool_result(self, tool_name: str, result: str):
        """Adds the result of a tool execution back to the conversation history."""
        message = f"Tool '{tool_name}' Output: {result}"
        self.history.append({"role": "system", "content": message})

    def add_error_message(self, error_msg: str):
        """Adds an error message to the history so the LLM can correct itself."""
        self.history.append({"role": "system", "content": f"Error: {error_msg}"})

    def _parse_json(self, text: str) -> dict:
        """Helper to extract JSON from markdown code blocks or raw text."""
        text = text.strip()
        
        # Try to find JSON inside ```json ... ``` blocks
        json_match = re.search(r'```json\s*({.*?})\s*```', text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        elif "{" in text and "}" in text:
            # Fallback: try to find the first { and last }
            start = text.find("{")
            end = text.rfind("}") + 1
            text = text[start:end]
            
        return json.loads(text)
