# planner_executor_lmstudio.py

import os
import requests
import json
import logging
from pathlib import Path
from typing import Dict, Any, List # Ensure List is imported if needed
from vision_processor import VisionProcessor


def _get_model_from_config() -> str:
    """Load model name from config file"""
    config_path = Path(os.getenv('APPDATA', os.path.expanduser('~'))) / 'RevitMCP' / 'models' / 'multi_model_config.json'
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
            return config.get("text_aligner", {}).get("model_id", "qwen2.5-0.5b-instruct")
        except:
            pass
    return "qwen2.5-0.5b-instruct"


class LMStudioAPIClient:

    PLANNER_SYSTEM_PROMPT = (
        "You are an expert planning agent for a Revit design system. "
        "Your task is to convert the user's request into a strict, sequential JSON plan. "
        "Adhere strictly to the JSON format and rules provided in the user prompt."
    )

    def __init__(self, model_name=None, api_url="http://localhost:1234/v1"):
        self.api_url = api_url
        self.model_name = model_name or _get_model_from_config()
        self.logger = logging.getLogger("LMStudioExecutor")
        self.vision = VisionProcessor()

    # --- REQUIRED PUBLIC METHOD (Orchestration entry point) ---
    # This method signature is only correct if the entire orchestration flow
    # (Discovery, Planning, Execution) is housed here, which is standard for local executors.
    # NOTE: It relies on methods like _run_discovery existing in client_orchestrator.py
    
        
    # --- INTERNAL HELPER METHOD (API Communication) ---
    async def _call_llm_api(self, system_prompt: str, user_query_content: str) -> str: 
        """
        Constructs the payload and sends the chat completion request to LM Studio.
        """
        headers = {
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query_content}
            ],
            "temperature": 0.0,
            "max_tokens": 2000,
            "stream": False
        }

        try:
            response = requests.post(f"{self.api_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            return content

        except Exception as e:
            self.logger.error(f"Error generating plan: {e}")
            return "[]"