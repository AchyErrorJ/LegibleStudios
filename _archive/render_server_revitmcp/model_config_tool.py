"""
Model Configuration Tool
========================
Easy setup and testing of multi-model endpoints for sketch-to-plan processing.

Usage:
    # Interactive CLI setup
    python model_config_tool.py setup

    # Quick configure single model
    python model_config_tool.py set vision1 http://localhost:1234/v1 qwen-3-vl

    # Test all configured models
    python model_config_tool.py test

    # Show current configuration
    python model_config_tool.py show

    # Reset to defaults
    python model_config_tool.py reset
"""

import json
import os
import sys
import requests
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

# Config directory
CONFIG_DIR = Path(os.getenv('APPDATA', os.path.expanduser('~'))) / 'RevitMCP' / 'models'
CONFIG_FILE = CONFIG_DIR / 'multi_model_config.json'


# =============================================================================
# MODEL SLOTS - Simplified naming for user
# =============================================================================

MODEL_SLOTS = {
    # Vision models (for image analysis)
    "vision1": {
        "key": "vision_primary",
        "name": "Primary Vision Model",
        "description": "Main vision model for corner extraction (e.g., Qwen 3 VL 4B)",
        "role": "vision",
        "task": "corner_extraction",
        "default_port": 1234,
    },
    "vision2": {
        "key": "vision_secondary",
        "name": "Secondary Vision Model",
        "description": "Backup vision model for room detection (e.g., Ministral 3B)",
        "role": "vision",
        "task": "room_detection",
        "default_port": 1235,
    },

    # Text models (for specialized tasks)
    "text1": {
        "key": "text_aligner",
        "name": "Wall Alignment Model",
        "description": "Aligns walls to grid (0.5B model)",
        "role": "text",
        "task": "wall_alignment",
        "default_port": 1236,
    },
    "text2": {
        "key": "text_scaler",
        "name": "Scale Calculator Model",
        "description": "Calculates scale factors (0.5B model)",
        "role": "text",
        "task": "scale_calculation",
        "default_port": 1237,
    },
    "text3": {
        "key": "text_labeler",
        "name": "Room Labeler Model",
        "description": "Labels rooms by type (0.5B model)",
        "role": "text",
        "task": "room_labeling",
        "default_port": 1238,
    },
    "text4": {
        "key": "text_door_placer",
        "name": "Door Placement Model",
        "description": "Suggests door locations (0.5B model)",
        "role": "text",
        "task": "door_placement",
        "default_port": 1239,
    },
    "text5": {
        "key": "text_window_placer",
        "name": "Window Placement Model",
        "description": "Suggests window locations (0.5B model)",
        "role": "text",
        "task": "window_placement",
        "default_port": 1240,
    },
    "text6": {
        "key": "text_validator",
        "name": "Validation Model",
        "description": "Validates final geometry (0.5B model)",
        "role": "text",
        "task": "validation",
        "default_port": 1241,
    },
}


# =============================================================================
# CONFIGURATION MANAGEMENT
# =============================================================================

def get_default_config() -> Dict[str, Dict]:
    """Generate default configuration"""
    config = {}
    for slot_name, slot_info in MODEL_SLOTS.items():
        config[slot_info["key"]] = {
            "name": slot_info["name"],
            "api_url": f"http://localhost:{slot_info['default_port']}/v1",
            "model_id": "local-model",
            "role": slot_info["role"],
            "task": slot_info["task"],
            "weight": 1.0 if slot_info["role"] == "vision" else 0.8,
            "timeout": 120 if slot_info["role"] == "vision" else 30,
            "enabled": True
        }
    return config


def load_config() -> Dict[str, Dict]:
    """Load configuration from disk"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception as e:
            print(f"[!]  Error loading config: {e}")
    return get_default_config()


def save_config(config: Dict[str, Dict]) -> bool:
    """Save configuration to disk"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"[X] Error saving config: {e}")
        return False


def set_model(slot: str, api_url: str, model_id: str, enabled: bool = True) -> bool:
    """
    Set configuration for a model slot.

    Args:
        slot: Slot name (vision1, vision2, text1-text6)
        api_url: API URL (e.g., http://localhost:1234/v1)
        model_id: Model identifier for the API
        enabled: Whether this model is active
    """
    if slot not in MODEL_SLOTS:
        print(f"[X] Unknown slot: {slot}")
        print(f"   Available: {', '.join(MODEL_SLOTS.keys())}")
        return False

    slot_info = MODEL_SLOTS[slot]
    config = load_config()

    # Ensure URL has /v1 suffix for OpenAI-compatible APIs
    if not api_url.endswith('/v1'):
        if api_url.endswith('/'):
            api_url = api_url + 'v1'
        else:
            api_url = api_url + '/v1'

    config[slot_info["key"]] = {
        "name": slot_info["name"],
        "api_url": api_url,
        "model_id": model_id,
        "role": slot_info["role"],
        "task": slot_info["task"],
        "weight": 1.0 if slot_info["role"] == "vision" else 0.8,
        "timeout": 120 if slot_info["role"] == "vision" else 30,
        "enabled": enabled
    }

    if save_config(config):
        print(f"[OK] Set {slot} ({slot_info['name']})")
        print(f"   URL: {api_url}")
        print(f"   Model: {model_id}")
        return True
    return False


def set_all_same_server(api_url: str, vision_model: str, text_model: str) -> bool:
    """
    Configure all models to use the same server with different model IDs.
    Useful when running multiple models in LM Studio.

    Args:
        api_url: Base API URL (e.g., http://localhost:1234/v1)
        vision_model: Model ID for vision tasks
        text_model: Model ID for text tasks
    """
    config = load_config()

    for slot_name, slot_info in MODEL_SLOTS.items():
        model_id = vision_model if slot_info["role"] == "vision" else text_model
        config[slot_info["key"]] = {
            "name": slot_info["name"],
            "api_url": api_url,
            "model_id": model_id,
            "role": slot_info["role"],
            "task": slot_info["task"],
            "weight": 1.0 if slot_info["role"] == "vision" else 0.8,
            "timeout": 120 if slot_info["role"] == "vision" else 30,
            "enabled": True
        }

    if save_config(config):
        print(f"[OK] All models configured to use {api_url}")
        print(f"   Vision model: {vision_model}")
        print(f"   Text model: {text_model}")
        return True
    return False


# =============================================================================
# LM STUDIO INTEGRATION
# =============================================================================

def discover_lm_studio(port: int = 1234) -> Dict[str, Any]:
    """
    Discover LM Studio and list loaded models.

    Args:
        port: LM Studio port (default 1234)

    Returns:
        Dict with status and available models
    """
    url = f"http://localhost:{port}/v1"

    try:
        response = requests.get(f"{url}/models", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = data.get("data", [])

            # Extract model info
            model_list = []
            for m in models:
                model_id = m.get("id", "unknown")
                model_list.append({
                    "id": model_id,
                    "owned_by": m.get("owned_by", ""),
                    # Try to detect if it's a vision model
                    "is_vision": any(v in model_id.lower() for v in ["vl", "vision", "llava", "qwen-vl"])
                })

            return {
                "success": True,
                "status": "online",
                "url": url,
                "port": port,
                "models": model_list,
                "model_count": len(model_list)
            }
        else:
            return {
                "success": False,
                "status": "error",
                "error": f"HTTP {response.status_code}"
            }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "status": "offline",
            "port": port,
            "error": "LM Studio not running or not on this port"
        }
    except Exception as e:
        return {
            "success": False,
            "status": "error",
            "error": str(e)
        }


def auto_configure_from_lm_studio(port: int = 1234) -> Dict[str, Any]:
    """
    Auto-configure models based on what's loaded in LM Studio.

    Args:
        port: LM Studio port

    Returns:
        Configuration result
    """
    print(f"\n[*] Discovering LM Studio on port {port}...")

    discovery = discover_lm_studio(port)

    if not discovery.get("success"):
        print(f"[X] {discovery.get('error', 'Could not connect to LM Studio')}")
        return discovery

    models = discovery.get("models", [])

    if not models:
        print("[!] LM Studio is running but no models are loaded.")
        print("    Load a model in LM Studio first, then run this again.")
        return {
            "success": False,
            "error": "No models loaded in LM Studio"
        }

    print(f"\n[+] Found {len(models)} model(s) in LM Studio:")
    for i, m in enumerate(models):
        vision_tag = " [VISION]" if m.get("is_vision") else ""
        print(f"    {i+1}. {m['id']}{vision_tag}")

    # Try to find vision and text models
    vision_models = [m for m in models if m.get("is_vision")]
    text_models = [m for m in models if not m.get("is_vision")]

    # Auto-select
    if vision_models:
        vision_model_id = vision_models[0]["id"]
        print(f"\n[OK] Auto-selected vision model: {vision_model_id}")
    else:
        # Use first available for vision (user may have a vision model not detected)
        vision_model_id = models[0]["id"]
        print(f"\n[!] No vision model detected, using: {vision_model_id}")

    if text_models:
        text_model_id = text_models[0]["id"]
        print(f"[OK] Auto-selected text model: {text_model_id}")
    elif len(models) > 1:
        # Use second model for text
        text_model_id = models[1]["id"]
        print(f"[OK] Using second model for text: {text_model_id}")
    else:
        # Same model for both
        text_model_id = vision_model_id
        print(f"[!] Only one model loaded, using for both vision and text")

    # Configure
    url = f"http://localhost:{port}/v1"
    success = set_all_same_server(url, vision_model_id, text_model_id)

    if success:
        return {
            "success": True,
            "url": url,
            "vision_model": vision_model_id,
            "text_model": text_model_id,
            "models_found": len(models)
        }
    else:
        return {
            "success": False,
            "error": "Failed to save configuration"
        }


def scan_lm_studio_ports() -> Dict[str, Any]:
    """Scan common ports for LM Studio instances"""
    common_ports = [1234, 1235, 8080, 8000, 5000]
    found = []

    print("\n[*] Scanning for LM Studio instances...")

    for port in common_ports:
        result = discover_lm_studio(port)
        if result.get("success"):
            found.append({
                "port": port,
                "models": result.get("models", []),
                "model_count": result.get("model_count", 0)
            })
            print(f"   [OK] Port {port}: {result.get('model_count', 0)} model(s)")
        else:
            print(f"   [ ]  Port {port}: not active")

    return {
        "success": True,
        "instances_found": len(found),
        "instances": found
    }


# =============================================================================
# TESTING
# =============================================================================

def test_model(slot: str) -> Dict[str, Any]:
    """Test a single model endpoint"""
    if slot not in MODEL_SLOTS:
        return {"success": False, "error": f"Unknown slot: {slot}"}

    slot_info = MODEL_SLOTS[slot]
    config = load_config()
    model_config = config.get(slot_info["key"], {})

    if not model_config.get("enabled", True):
        return {"success": True, "status": "disabled", "slot": slot}

    api_url = model_config.get("api_url", "")
    model_id = model_config.get("model_id", "")

    try:
        # Try to list models (works with most OpenAI-compatible APIs)
        response = requests.get(f"{api_url}/models", timeout=5)
        if response.status_code == 200:
            return {
                "success": True,
                "status": "online",
                "slot": slot,
                "name": slot_info["name"],
                "api_url": api_url,
                "model_id": model_id
            }
        else:
            return {
                "success": False,
                "status": "error",
                "slot": slot,
                "error": f"HTTP {response.status_code}"
            }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "status": "offline",
            "slot": slot,
            "api_url": api_url,
            "error": "Connection refused"
        }
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "status": "timeout",
            "slot": slot,
            "api_url": api_url,
            "error": "Request timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "status": "error",
            "slot": slot,
            "error": str(e)
        }


def test_all_models() -> Dict[str, Any]:
    """Test all configured model endpoints"""
    results = {
        "vision": [],
        "text": [],
        "summary": {"online": 0, "offline": 0, "disabled": 0}
    }

    print("\n[*] Testing model endpoints...\n")

    for slot_name, slot_info in MODEL_SLOTS.items():
        result = test_model(slot_name)

        category = "vision" if slot_info["role"] == "vision" else "text"
        results[category].append(result)

        if result.get("status") == "online":
            results["summary"]["online"] += 1
            print(f"  [OK] {slot_name}: {slot_info['name']} - ONLINE")
        elif result.get("status") == "disabled":
            results["summary"]["disabled"] += 1
            print(f"  [-]  {slot_name}: {slot_info['name']} - DISABLED")
        else:
            results["summary"]["offline"] += 1
            print(f"  [X] {slot_name}: {slot_info['name']} - {result.get('error', 'OFFLINE')}")

    print(f"\n📊 Summary: {results['summary']['online']} online, "
          f"{results['summary']['offline']} offline, "
          f"{results['summary']['disabled']} disabled")

    return results


# =============================================================================
# DISPLAY
# =============================================================================

def show_config():
    """Display current configuration"""
    config = load_config()

    print("\n" + "=" * 60)
    print("MULTI-MODEL CONFIGURATION")
    print("=" * 60)
    print(f"Config file: {CONFIG_FILE}")
    print()

    # Vision models
    print("[>] VISION MODELS (for image analysis)")
    print("-" * 40)
    for slot_name, slot_info in MODEL_SLOTS.items():
        if slot_info["role"] != "vision":
            continue
        model = config.get(slot_info["key"], {})
        enabled = "[OK]" if model.get("enabled", True) else "[-]"
        print(f"  {enabled} {slot_name}: {slot_info['name']}")
        print(f"      URL: {model.get('api_url', 'not set')}")
        print(f"      Model: {model.get('model_id', 'not set')}")
        print()

    # Text models
    print("📝 TEXT MODELS (for specialized tasks)")
    print("-" * 40)
    for slot_name, slot_info in MODEL_SLOTS.items():
        if slot_info["role"] != "text":
            continue
        model = config.get(slot_info["key"], {})
        enabled = "[OK]" if model.get("enabled", True) else "[-]"
        print(f"  {enabled} {slot_name}: {slot_info['name']}")
        print(f"      URL: {model.get('api_url', 'not set')}")
        print(f"      Model: {model.get('model_id', 'not set')}")
        print()


def show_quick_setup():
    """Show quick setup instructions"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║              QUICK SETUP GUIDE                               ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  EASIEST: Auto-detect from LM Studio                         ║
║  ─────────────────────────────────────────────────────────── ║
║  1. Load your models in LM Studio                            ║
║  2. Run:  python model_config_tool.py lmstudio               ║
║     (Auto-detects and configures everything!)                ║
║                                                              ║
║  OPTION 2: Manual same-server setup                          ║
║  ─────────────────────────────────────────────────────────── ║
║  python model_config_tool.py same-server \\                   ║
║      http://localhost:1234 \\                                 ║
║      qwen-3-vl-4b \\                                          ║
║      qwen-0.5b                                               ║
║                                                              ║
║  OPTION 3: Configure individual models                       ║
║  ─────────────────────────────────────────────────────────── ║
║  python model_config_tool.py set vision1 \\                   ║
║      http://localhost:1234/v1 qwen-3-vl-4b                   ║
║                                                              ║
║  OTHER COMMANDS                                              ║
║  ─────────────────────────────────────────────────────────── ║
║  lmstudio  - Auto-detect models from LM Studio (easiest!)    ║
║  scan      - Scan for LM Studio on multiple ports            ║
║  show      - Display current configuration                   ║
║  test      - Test all model endpoints                        ║
║  setup     - Interactive setup wizard                        ║
║  reset     - Reset to default configuration                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


# =============================================================================
# INTERACTIVE SETUP
# =============================================================================

def interactive_setup():
    """Interactive configuration wizard"""
    print("\n" + "=" * 60)
    print("MULTI-MODEL SETUP WIZARD")
    print("=" * 60)

    print("""
How would you like to configure your models?

  1. Same server for all (easiest - LM Studio with multiple models)
  2. Separate servers for vision vs text
  3. Individual configuration for each model
  4. Cancel

""")

    choice = input("Enter choice (1-4): ").strip()

    if choice == "1":
        # Same server for all
        print("\n[>] Single Server Configuration")
        print("-" * 40)

        url = input("Server URL (e.g., http://localhost:1234): ").strip()
        if not url:
            url = "http://localhost:1234"

        print("\nAvailable model IDs depend on what you have loaded in LM Studio.")
        print("Common examples: qwen-3-vl-4b, ministral-3b, qwen-0.5b, smollm-0.5b")

        vision_model = input("\nVision model ID (for image analysis): ").strip()
        if not vision_model:
            vision_model = "qwen-3-vl-4b"

        text_model = input("Text model ID (for small tasks): ").strip()
        if not text_model:
            text_model = "local-model"

        set_all_same_server(url, vision_model, text_model)

    elif choice == "2":
        # Separate vision/text servers
        print("\n[>] Separate Vision/Text Configuration")
        print("-" * 40)

        vision_url = input("Vision server URL (e.g., http://localhost:1234): ").strip()
        vision_model = input("Vision model ID: ").strip()

        text_url = input("Text server URL (e.g., http://localhost:1235): ").strip()
        text_model = input("Text model ID: ").strip()

        config = load_config()
        for slot_name, slot_info in MODEL_SLOTS.items():
            if slot_info["role"] == "vision":
                url, model_id = vision_url, vision_model
            else:
                url, model_id = text_url, text_model

            config[slot_info["key"]] = {
                "name": slot_info["name"],
                "api_url": url + "/v1" if not url.endswith("/v1") else url,
                "model_id": model_id,
                "role": slot_info["role"],
                "task": slot_info["task"],
                "weight": 1.0 if slot_info["role"] == "vision" else 0.8,
                "timeout": 120 if slot_info["role"] == "vision" else 30,
                "enabled": True
            }
        save_config(config)
        print("\n[OK] Configuration saved!")

    elif choice == "3":
        # Individual configuration
        print("\n[>] Individual Model Configuration")
        print("-" * 40)

        for slot_name, slot_info in MODEL_SLOTS.items():
            print(f"\n{slot_name}: {slot_info['name']}")
            print(f"   ({slot_info['description']})")

            url = input(f"   URL [http://localhost:{slot_info['default_port']}]: ").strip()
            if not url:
                url = f"http://localhost:{slot_info['default_port']}"

            model_id = input(f"   Model ID [local-model]: ").strip()
            if not model_id:
                model_id = "local-model"

            set_model(slot_name, url, model_id)

    else:
        print("Cancelled.")
        return

    print("\n[*] Testing configuration...")
    test_all_models()


# =============================================================================
# MCP TOOL INTERFACE
# =============================================================================

def configure_models_tool(
    mode: str = "show",
    slot: str = None,
    api_url: str = None,
    model_id: str = None,
    vision_model: str = None,
    text_model: str = None
) -> Dict[str, Any]:
    """
    MCP tool for configuring multi-model endpoints.

    Args:
        mode: "show", "set", "same-server", "test", "reset"
        slot: Model slot (vision1, vision2, text1-6) for "set" mode
        api_url: API URL for the model server
        model_id: Model identifier
        vision_model: Vision model ID for "same-server" mode
        text_model: Text model ID for "same-server" mode

    Returns:
        Configuration status and results
    """
    if mode == "show":
        config = load_config()
        return {
            "success": True,
            "config": config,
            "slots": list(MODEL_SLOTS.keys())
        }

    elif mode == "set":
        if not all([slot, api_url, model_id]):
            return {
                "success": False,
                "error": "Missing required parameters: slot, api_url, model_id"
            }
        success = set_model(slot, api_url, model_id)
        return {"success": success}

    elif mode == "same-server":
        if not all([api_url, vision_model, text_model]):
            return {
                "success": False,
                "error": "Missing required parameters: api_url, vision_model, text_model"
            }
        success = set_all_same_server(api_url, vision_model, text_model)
        return {"success": success}

    elif mode == "test":
        return test_all_models()

    elif mode == "reset":
        config = get_default_config()
        save_config(config)
        return {"success": True, "message": "Reset to defaults"}

    elif mode == "lmstudio":
        port = kwargs.get("port", 1234)
        return auto_configure_from_lm_studio(port)

    elif mode == "discover":
        port = kwargs.get("port", 1234)
        return discover_lm_studio(port)

    elif mode == "scan":
        return scan_lm_studio_ports()

    else:
        return {
            "success": False,
            "error": f"Unknown mode: {mode}",
            "available_modes": ["show", "set", "same-server", "test", "reset", "lmstudio", "discover", "scan"]
        }


# =============================================================================
# CLI
# =============================================================================

def main():
    if len(sys.argv) < 2:
        show_quick_setup()
        return

    command = sys.argv[1].lower()

    if command == "setup":
        interactive_setup()

    elif command == "show":
        show_config()

    elif command == "test":
        test_all_models()

    elif command == "reset":
        config = get_default_config()
        save_config(config)
        print("[OK] Reset to default configuration")
        show_config()

    elif command == "set":
        if len(sys.argv) < 5:
            print("Usage: python model_config_tool.py set <slot> <url> <model_id>")
            print(f"Slots: {', '.join(MODEL_SLOTS.keys())}")
            return
        slot = sys.argv[2]
        url = sys.argv[3]
        model_id = sys.argv[4]
        set_model(slot, url, model_id)

    elif command == "same-server":
        if len(sys.argv) < 5:
            print("Usage: python model_config_tool.py same-server <url> <vision_model> <text_model>")
            return
        url = sys.argv[2]
        vision_model = sys.argv[3]
        text_model = sys.argv[4]
        set_all_same_server(url, vision_model, text_model)

    elif command in ["disable", "enable"]:
        if len(sys.argv) < 3:
            print(f"Usage: python model_config_tool.py {command} <slot>")
            return
        slot = sys.argv[2]
        if slot not in MODEL_SLOTS:
            print(f"Unknown slot: {slot}")
            return
        config = load_config()
        key = MODEL_SLOTS[slot]["key"]
        config[key]["enabled"] = (command == "enable")
        save_config(config)
        print(f"{'[OK] Enabled' if command == 'enable' else '[-] Disabled'}: {slot}")

    elif command == "lmstudio":
        # Auto-detect and configure from LM Studio
        port = 1234
        if len(sys.argv) > 2:
            try:
                port = int(sys.argv[2])
            except ValueError:
                pass
        auto_configure_from_lm_studio(port)

    elif command == "scan":
        # Scan for LM Studio instances
        scan_lm_studio_ports()

    elif command == "help":
        show_quick_setup()

    else:
        print(f"Unknown command: {command}")
        show_quick_setup()


if __name__ == "__main__":
    main()
