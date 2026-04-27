"""Configuration management for Revit MCP Server"""

import os
import json
from typing import Dict, Any

# Use AppData path - same as C# Settings window
DEFAULT_CONFIG_PATH = os.path.join(
    os.getenv('APPDATA'),
    'RevitMCP',
    'llm_config.json'
)

def _get_lmstudio_model():
    """Get LM Studio model from multi_model_config if available"""
    model_config_path = os.path.join(os.getenv('APPDATA', ''), 'RevitMCP', 'models', 'multi_model_config.json')
    if os.path.exists(model_config_path):
        try:
            with open(model_config_path, 'r') as f:
                config = json.load(f)
            return config.get("text_aligner", {}).get("model_id", "qwen2.5-0.5b-instruct")
        except:
            pass
    return "qwen2.5-0.5b-instruct"

DEFAULT_CONFIG = {
    "llm_provider": "lmstudio",
    "claude": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "model_sonnet": "claude-sonnet-4-20250514",
        "model_haiku": "claude-haiku-4-5-20251001"
    },
    "lmstudio": {
        "base_url": "http://localhost:1234/v1",
        "model": _get_lmstudio_model()
    },
    "gemini": {
        "api_key_env": "GOOGLE_API_KEY",
        "model": "gemini-2.0-flash-exp",
        "base_url": "https://generativelanguage.googleapis.com/v1beta"
    },
    "server": {
        "host": "0.0.0.0",
        "port": 8000,
        "revit_port": 48884
    }
}

def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Load configuration from JSON file"""
    print(f"🔍 Loading config from: {config_path}")
    
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                print(f"✅ Config loaded. Provider: {user_config.get('llm_provider', 'NOT SET')}")
                # Merge with defaults
                for key in DEFAULT_CONFIG:
                    if key not in user_config:
                        user_config[key] = DEFAULT_CONFIG[key]
                return user_config
        else:
            # Create default config
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
            print(f"✅ Created default config: {config_path}")
            return DEFAULT_CONFIG
    except Exception as e:
        print(f"⚠️ Error loading config: {e}")
        print(f"⚠️ Using default config instead")
        return DEFAULT_CONFIG