"""
QBD (Question Based Design) Session Management
================================================
Interview-style workflow for guided building design.
Sessions persist across browser refreshes.

Uses relationship-based layout generation for floor plans.
"""

import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# Import relationship-based layout generator
try:
    from qbd_layout_generator import generate_qbd_plan
    USE_RELATIONSHIP_LAYOUT = True
except ImportError:
    USE_RELATIONSHIP_LAYOUT = False
    print("[QBD] Warning: qbd_layout_generator not available, using legacy mode")


# Session storage location
SESSION_DIR = Path(os.getenv('APPDATA', os.path.expanduser('~'))) / 'RevitMCP' / 'qbd_sessions'
SESSION_EXPIRY_HOURS = 24


# =============================================================================
# QUESTION FLOW DEFINITIONS
# =============================================================================

QBD_QUESTION_FLOW = {
    # Starting point
    "start": {
        "question": "What type of space are you designing?",
        "options": [
            {"value": "residential", "label": "Residential", "description": "House, apartment, or ADU"},
            {"value": "commercial", "label": "Commercial", "description": "Office, retail, or warehouse"},
            {"value": "mixed", "label": "Mixed Use", "description": "Combined residential and commercial"}
        ],
        "next": {
            "residential": "res_type",
            "commercial": "com_type",
            "mixed": "mixed_type"
        }
    },

    # Residential branch
    "res_type": {
        "question": "What style of residence?",
        "options": [
            {"value": "single_family", "label": "Single Family Home", "description": "Standalone house"},
            {"value": "apartment", "label": "Apartment Unit", "description": "Unit in a building"},
            {"value": "adu", "label": "ADU / Granny Flat", "description": "Accessory dwelling unit"},
            {"value": "townhouse", "label": "Townhouse", "description": "Multi-story attached unit"}
        ],
        "next": "bedrooms"
    },

    "bedrooms": {
        "question": "How many bedrooms?",
        "options": [
            {"value": "0", "label": "Studio", "description": "Open plan, no separate bedroom"},
            {"value": "1", "label": "1 Bedroom", "description": "One bedroom plus living area"},
            {"value": "2", "label": "2 Bedrooms", "description": "Two bedrooms"},
            {"value": "3", "label": "3 Bedrooms", "description": "Three bedrooms"},
            {"value": "4+", "label": "4+ Bedrooms", "description": "Four or more bedrooms"}
        ],
        "next": "bathrooms"
    },

    "bathrooms": {
        "question": "How many bathrooms?",
        "options": [
            {"value": "1", "label": "1 Bathroom", "description": "Single bathroom"},
            {"value": "1.5", "label": "1.5 Bathrooms", "description": "One full + one half bath"},
            {"value": "2", "label": "2 Bathrooms", "description": "Two full bathrooms"},
            {"value": "2.5", "label": "2.5 Bathrooms", "description": "Two full + one half bath"},
            {"value": "3+", "label": "3+ Bathrooms", "description": "Three or more bathrooms"}
        ],
        "next": "sqft"
    },

    "sqft": {
        "question": "What's your target square footage?",
        "input_type": "number",
        "placeholder": "Enter square feet (e.g., 1500)",
        "options": [
            {"value": "500", "label": "~500 sqft", "description": "Studio or small 1BR"},
            {"value": "800", "label": "~800 sqft", "description": "1BR or small 2BR"},
            {"value": "1200", "label": "~1200 sqft", "description": "2BR or small 3BR"},
            {"value": "1800", "label": "~1800 sqft", "description": "3BR family home"},
            {"value": "2500", "label": "~2500 sqft", "description": "Large family home"},
            {"value": "custom", "label": "Custom", "description": "Enter specific value"}
        ],
        "next": "garage"
    },

    "garage": {
        "question": "Do you need a garage?",
        "options": [
            {"value": "none", "label": "No Garage", "description": "No garage space"},
            {"value": "1car", "label": "1-Car Garage", "description": "Single car garage (~200 sqft)"},
            {"value": "2car", "label": "2-Car Garage", "description": "Two car garage (~400 sqft)"},
            {"value": "3car", "label": "3-Car Garage", "description": "Three car garage (~600 sqft)"}
        ],
        "next": "special_rooms"
    },

    "special_rooms": {
        "question": "Any special rooms? (Select all that apply)",
        "multi_select": True,
        "options": [
            {"value": "office", "label": "Home Office", "description": "Dedicated work space"},
            {"value": "media", "label": "Media Room", "description": "Entertainment/theater room"},
            {"value": "gym", "label": "Home Gym", "description": "Exercise space"},
            {"value": "mudroom", "label": "Mudroom", "description": "Entry/utility room"},
            {"value": "pantry", "label": "Walk-in Pantry", "description": "Large food storage"},
            {"value": "none", "label": "None", "description": "No special rooms needed"}
        ],
        "next": "style"
    },

    "style": {
        "question": "What architectural style do you prefer?",
        "options": [
            {"value": "modern", "label": "Modern", "description": "Clean lines, open spaces"},
            {"value": "traditional", "label": "Traditional", "description": "Classic proportions"},
            {"value": "contemporary", "label": "Contemporary", "description": "Current trends, mixed materials"},
            {"value": "minimal", "label": "Minimalist", "description": "Simple, efficient design"}
        ],
        "next": "confirm"
    },

    # Commercial branch
    "com_type": {
        "question": "What type of commercial space?",
        "options": [
            {"value": "office", "label": "Office", "description": "Workspace for business"},
            {"value": "retail", "label": "Retail", "description": "Store or shop"},
            {"value": "restaurant", "label": "Restaurant/Cafe", "description": "Food service"},
            {"value": "warehouse", "label": "Warehouse", "description": "Storage and logistics"}
        ],
        "next": "com_sqft"
    },

    "com_sqft": {
        "question": "What's your target square footage?",
        "options": [
            {"value": "1000", "label": "~1,000 sqft", "description": "Small retail or office"},
            {"value": "2500", "label": "~2,500 sqft", "description": "Medium office or retail"},
            {"value": "5000", "label": "~5,000 sqft", "description": "Large retail or restaurant"},
            {"value": "10000", "label": "~10,000 sqft", "description": "Warehouse or large office"},
            {"value": "custom", "label": "Custom", "description": "Enter specific value"}
        ],
        "next": "confirm"
    },

    # Mixed use branch
    "mixed_type": {
        "question": "What's the mix?",
        "options": [
            {"value": "retail_above", "label": "Retail Below, Residential Above", "description": "Ground floor shop with apartment above"},
            {"value": "office_above", "label": "Office Below, Residential Above", "description": "Ground floor office with apartment above"},
            {"value": "live_work", "label": "Live/Work Space", "description": "Combined living and working area"}
        ],
        "next": "mixed_sqft"
    },

    "mixed_sqft": {
        "question": "What's the total square footage?",
        "options": [
            {"value": "1500", "label": "~1,500 sqft", "description": "Small mixed use"},
            {"value": "2500", "label": "~2,500 sqft", "description": "Medium mixed use"},
            {"value": "4000", "label": "~4,000 sqft", "description": "Large mixed use"}
        ],
        "next": "confirm"
    },

    # Confirmation
    "confirm": {
        "question": "Ready to generate your design?",
        "is_final": True,
        "options": [
            {"value": "generate", "label": "Generate Design", "description": "Create the floor plan now"},
            {"value": "modify", "label": "Modify Choices", "description": "Go back and change answers"},
            {"value": "save", "label": "Save for Later", "description": "Save session and exit"}
        ]
    }
}


# =============================================================================
# QBD SESSION CLASS
# =============================================================================

class QBDSession:
    """Manages a Question Based Design session"""

    def __init__(self, session_id: str = None):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.state = "start"
        self.answers = {}
        self.history = []  # Track question/answer history
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        """Serialize session to dict"""
        return {
            "session_id": self.session_id,
            "state": self.state,
            "answers": self.answers,
            "history": self.history,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'QBDSession':
        """Deserialize session from dict"""
        session = cls(data.get("session_id"))
        session.state = data.get("state", "start")
        session.answers = data.get("answers", {})
        session.history = data.get("history", [])
        session.created_at = data.get("created_at", datetime.now().isoformat())
        session.updated_at = data.get("updated_at", datetime.now().isoformat())
        return session

    def save(self):
        """Persist session to disk"""
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        path = SESSION_DIR / f"{self.session_id}.json"
        self.updated_at = datetime.now().isoformat()
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        print(f"   💾 Session saved: {self.session_id}")

    @classmethod
    def load(cls, session_id: str) -> Optional['QBDSession']:
        """Load session from disk"""
        path = SESSION_DIR / f"{session_id}.json"
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)

                # Check expiry
                updated = datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat()))
                if datetime.now() - updated > timedelta(hours=SESSION_EXPIRY_HOURS):
                    print(f"   ⏰ Session expired: {session_id}")
                    path.unlink()  # Delete expired session
                    return None

                return cls.from_dict(data)
            except Exception as e:
                print(f"   ⚠️ Failed to load session {session_id}: {e}")
                return None
        return None

    @classmethod
    def get_latest(cls) -> Optional['QBDSession']:
        """Get the most recently updated session"""
        if not SESSION_DIR.exists():
            return None

        sessions = []
        for path in SESSION_DIR.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                    updated = datetime.fromisoformat(data.get("updated_at", "2000-01-01"))
                    sessions.append((path, updated, data))
            except:
                continue

        if not sessions:
            return None

        # Sort by update time, get most recent
        sessions.sort(key=lambda x: x[1], reverse=True)
        _, updated, data = sessions[0]

        # Check expiry
        if datetime.now() - updated > timedelta(hours=SESSION_EXPIRY_HOURS):
            return None

        return cls.from_dict(data)

    def get_current_question(self) -> Dict:
        """Get the current question based on state"""
        if self.state not in QBD_QUESTION_FLOW:
            return {"error": f"Invalid state: {self.state}"}

        q = QBD_QUESTION_FLOW[self.state]
        return {
            "state": self.state,
            "question": q["question"],
            "options": q.get("options", []),
            "multi_select": q.get("multi_select", False),
            "input_type": q.get("input_type"),
            "placeholder": q.get("placeholder"),
            "is_final": q.get("is_final", False),
            "session_id": self.session_id,
            "progress": self._calculate_progress()
        }

    def process_answer(self, answer: Any) -> Dict:
        """Process user's answer and advance to next question"""
        if self.state not in QBD_QUESTION_FLOW:
            return {"error": f"Invalid state: {self.state}"}

        current = QBD_QUESTION_FLOW[self.state]

        # Store answer
        self.answers[self.state] = answer
        self.history.append({
            "state": self.state,
            "question": current["question"],
            "answer": answer,
            "timestamp": datetime.now().isoformat()
        })

        # Handle final state
        if current.get("is_final"):
            if answer == "generate":
                plan = self.generate_plan()
                self.save()
                return {
                    "complete": True,
                    "action": "generate",
                    "plan": plan,
                    "summary": self._get_summary()
                }
            elif answer == "modify":
                # Go back to start
                self.state = "start"
                self.save()
                return self.get_current_question()
            elif answer == "save":
                self.save()
                return {
                    "complete": False,
                    "action": "saved",
                    "message": f"Session saved. Say 'continue design' to resume (ID: {self.session_id})"
                }

        # Determine next state
        next_state = current.get("next")
        if isinstance(next_state, dict):
            # Branching based on answer
            next_state = next_state.get(answer, list(next_state.values())[0])

        if next_state:
            self.state = next_state
            self.save()
            return self.get_current_question()
        else:
            return {"error": "No next state defined"}

    def _calculate_progress(self) -> float:
        """Calculate rough progress percentage"""
        # Count answered questions
        answered = len(self.answers)
        # Estimate total questions (varies by path, use average)
        estimated_total = 7
        return min(1.0, answered / estimated_total)

    def _get_summary(self) -> str:
        """Generate human-readable summary of answers"""
        lines = ["**Design Summary:**"]

        mapping = {
            "start": "Building Type",
            "res_type": "Residence Style",
            "bedrooms": "Bedrooms",
            "bathrooms": "Bathrooms",
            "sqft": "Square Footage",
            "garage": "Garage",
            "special_rooms": "Special Rooms",
            "style": "Style",
            "com_type": "Commercial Type",
            "com_sqft": "Commercial Size",
            "mixed_type": "Mixed Use Type",
            "mixed_sqft": "Total Size"
        }

        for key, label in mapping.items():
            if key in self.answers:
                value = self.answers[key]
                if isinstance(value, list):
                    value = ", ".join(value)
                lines.append(f"- {label}: {value}")

        return "\n".join(lines)

    def generate_plan(self) -> List[Dict]:
        """Generate execution plan from collected answers"""
        answers = self.answers

        # Use relationship-based layout if available
        if USE_RELATIONSHIP_LAYOUT:
            print("[QBD] Using relationship-based layout generator")
            return generate_qbd_plan(answers)

        # Fallback to legacy mode
        return self._generate_legacy_plan(answers)

    def _generate_legacy_plan(self, answers: Dict) -> List[Dict]:
        """Legacy plan generation (room list based)"""

        # Determine dimensions
        sqft = int(answers.get("sqft", answers.get("com_sqft", answers.get("mixed_sqft", "1200"))))

        # Calculate reasonable dimensions (golden ratio-ish)
        import math
        ratio = 1.4
        depth = math.sqrt(sqft / ratio)
        width = sqft / depth

        # Parse bedrooms/bathrooms
        bedrooms = int(answers.get("bedrooms", "2").replace("+", ""))
        bathrooms_str = answers.get("bathrooms", "1")
        bathrooms = int(float(bathrooms_str.replace("+", "")))

        # Build room list
        rooms = self._generate_room_list(bedrooms, bathrooms, sqft, answers)

        # Generate the plan
        plan = [
            {
                "step": 1,
                "tool": "create_levels_batch",
                "description": "Create floor levels",
                "args": {
                    "levels": [
                        {"name": "Level 1", "elevation": 0.0},
                        {"name": "Roof Level", "elevation": 10.0}
                    ]
                }
            },
            {
                "step": 2,
                "tool": "generate_floor_plan_walls",
                "description": f"Generate {bedrooms}BR/{bathrooms}BA floor plan",
                "args": {
                    "width": round(width, 1),
                    "depth": round(depth, 1),
                    "rooms": rooms,
                    "level_name": "Level 1",
                    "wall_height": 10.0,
                    "exterior_wall_type": "${default_exterior_wall_type}",
                    "interior_wall_type": "${default_interior_wall_type}",
                    "wet_wall_type": "${default_wet_wall_type}"
                }
            },
            {
                "step": 3,
                "tool": "create_floor",
                "description": "Create floor slab",
                "args": {
                    "points": [[0, 0, 0], [round(width, 1), 0, 0],
                              [round(width, 1), round(depth, 1), 0], [0, round(depth, 1), 0]],
                    "level_name": "Level 1"
                }
            },
            {
                "step": 4,
                "tool": "create_roof_footprint",
                "description": "Create roof",
                "args": {
                    "points": [[0, 0, 0], [round(width, 1), 0, 0],
                              [round(width, 1), round(depth, 1), 0], [0, round(depth, 1), 0]],
                    "level_name": "Roof Level",
                    "slope_degrees": 0.0
                }
            }
        ]

        return plan

    def _generate_room_list(self, bedrooms: int, bathrooms: int, sqft: int, answers: Dict) -> List[Dict]:
        """Generate room specifications based on answers"""
        rooms = []

        # Core rooms
        rooms.append({"type": "entry", "min_area": max(30, int(sqft * 0.03))})
        rooms.append({"type": "living", "min_area": max(150, int(sqft * 0.18))})
        rooms.append({"type": "kitchen", "min_area": max(80, int(sqft * 0.10))})

        if sqft > 800:
            rooms.append({"type": "dining", "min_area": max(80, int(sqft * 0.08))})

        # Bedrooms
        if bedrooms > 0:
            rooms.append({"type": "primary_bedroom", "min_area": max(120, int(sqft * 0.14))})
            for i in range(bedrooms - 1):
                rooms.append({"type": "bedroom", "min_area": max(100, int(sqft * 0.10)),
                             "name": f"Bedroom {i + 2}"})
            rooms.append({"type": "hallway", "min_area": max(40, int(sqft * 0.04))})

        # Bathrooms
        if bathrooms > 0:
            rooms.append({"type": "primary_bath", "min_area": max(50, int(sqft * 0.05))})
            for i in range(bathrooms - 1):
                rooms.append({"type": "bathroom", "min_area": max(35, int(sqft * 0.03)),
                             "name": f"Bathroom {i + 2}"})

        # Garage
        garage = answers.get("garage", "none")
        if garage == "1car":
            rooms.append({"type": "garage", "min_area": 200})
        elif garage == "2car":
            rooms.append({"type": "garage", "min_area": 400})
        elif garage == "3car":
            rooms.append({"type": "garage", "min_area": 600})

        # Special rooms
        special = answers.get("special_rooms", [])
        if isinstance(special, str):
            special = [special]

        if "office" in special:
            rooms.append({"type": "office", "min_area": max(80, int(sqft * 0.06))})
        if "media" in special:
            rooms.append({"type": "media_room", "min_area": max(150, int(sqft * 0.10))})
        if "gym" in special:
            rooms.append({"type": "gym", "min_area": max(100, int(sqft * 0.07))})
        if "mudroom" in special:
            rooms.append({"type": "mudroom", "min_area": max(40, int(sqft * 0.03))})
        if "pantry" in special:
            rooms.append({"type": "pantry", "min_area": max(30, int(sqft * 0.02))})

        # Utility rooms
        rooms.append({"type": "laundry", "min_area": max(30, int(sqft * 0.02))})

        # Closets
        for i in range(bedrooms):
            rooms.append({"type": "closet", "min_area": max(15, int(sqft * 0.015))})

        return rooms


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def detect_qbd_trigger(query_lower: str) -> bool:
    """Check if query should start/continue QBD session"""
    triggers = [
        "qbd", "question based design", "design interview",
        "help me design", "guided design", "design wizard",
        "start design", "new design", "design a",
        "continue design", "resume design"
    ]
    return any(t in query_lower for t in triggers)


def is_continue_trigger(query_lower: str) -> bool:
    """Check if query is asking to continue existing session"""
    return any(t in query_lower for t in ["continue design", "resume design", "continue qbd"])


def format_question_for_chat(question_data: Dict) -> str:
    """Format QBD question for chat display"""
    lines = [f"**{question_data['question']}**\n"]

    options = question_data.get("options", [])
    for i, opt in enumerate(options, 1):
        label = opt.get("label", opt.get("value", "?"))
        desc = opt.get("description", "")
        lines.append(f"{i}. **{label}** - {desc}")

    if question_data.get("multi_select"):
        lines.append("\n_You can select multiple options_")

    progress = question_data.get("progress", 0)
    if progress > 0:
        lines.append(f"\n_Progress: {int(progress * 100)}%_")

    return "\n".join(lines)
