"""
QBD Interview Layer
====================
Natural language conversational interface for Question Based Design.

Sits on top of QBD session to provide:
- Natural language answer parsing
- Conversational context
- Clarification handling
- Progressive information gathering

The interview collects design requirements through conversation,
then passes structured data to the QBD layout generator.
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from qbd_session import QBDSession, QBD_QUESTION_FLOW
from qbd_layout_generator import (
    generate_floor_plan_from_qbd,
    export_for_archengine,
    export_for_revit,
    OutputFormat
)


# =============================================================================
# INTERVIEW STATE
# =============================================================================

class InterviewPhase(Enum):
    """Phases of the design interview"""
    GREETING = "greeting"
    BUILDING_TYPE = "building_type"
    SIZE_SCOPE = "size_scope"
    ROOM_REQUIREMENTS = "room_requirements"
    SPECIAL_FEATURES = "special_features"
    STYLE_PREFERENCES = "style_preferences"
    REVIEW = "review"
    GENERATING = "generating"
    COMPLETE = "complete"


@dataclass
class DesignRequirements:
    """Collected design requirements from interview"""
    # Building type
    building_type: str = ""  # residential, commercial, mixed
    residence_type: str = ""  # single_family, apartment, adu, townhouse
    commercial_type: str = ""  # office, retail, restaurant, warehouse

    # Size
    target_sqft: int = 0
    num_floors: int = 1

    # Rooms
    bedrooms: int = 0
    bathrooms: float = 0
    garage: str = "none"  # none, 1car, 2car, 3car

    # Special rooms
    special_rooms: List[str] = field(default_factory=list)

    # Style
    style: str = "modern"
    open_concept: bool = True

    # Additional notes from conversation
    notes: List[str] = field(default_factory=list)

    def to_qbd_answers(self) -> Dict:
        """Convert to QBD answer format"""
        answers = {
            "start": self.building_type,
            "sqft": str(self.target_sqft),
            "garage": self.garage,
            "special_rooms": self.special_rooms,
            "style": self.style
        }

        if self.building_type == "residential":
            answers["res_type"] = self.residence_type
            answers["bedrooms"] = str(self.bedrooms)
            answers["bathrooms"] = str(self.bathrooms)
        elif self.building_type == "commercial":
            answers["com_type"] = self.commercial_type
            answers["com_sqft"] = str(self.target_sqft)
        elif self.building_type == "mixed":
            answers["mixed_type"] = "live_work"
            answers["mixed_sqft"] = str(self.target_sqft)

        return answers

    def summary(self) -> str:
        """Generate human-readable summary"""
        lines = []

        if self.building_type == "residential":
            lines.append(f"**{self.residence_type.replace('_', ' ').title()}**")
            lines.append(f"- {self.bedrooms} bedroom(s), {self.bathrooms} bathroom(s)")
            lines.append(f"- {self.target_sqft:,} sq ft")
            if self.garage != "none":
                lines.append(f"- {self.garage.replace('car', '-car')} garage")
        elif self.building_type == "commercial":
            lines.append(f"**{self.commercial_type.title()} Space**")
            lines.append(f"- {self.target_sqft:,} sq ft")
        else:
            lines.append(f"**Mixed Use**")
            lines.append(f"- {self.target_sqft:,} sq ft total")

        if self.special_rooms:
            lines.append(f"- Special: {', '.join(self.special_rooms)}")

        lines.append(f"- Style: {self.style}")

        return "\n".join(lines)


@dataclass
class InterviewContext:
    """Maintains conversation context"""
    phase: InterviewPhase = InterviewPhase.GREETING
    requirements: DesignRequirements = field(default_factory=DesignRequirements)
    conversation_history: List[Dict] = field(default_factory=list)
    clarification_needed: Optional[str] = None
    last_question: str = ""
    attempts: int = 0  # Track repeated clarification attempts

    def add_message(self, role: str, content: str):
        """Add message to conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })


# =============================================================================
# NATURAL LANGUAGE PARSING
# =============================================================================

class AnswerParser:
    """Parse natural language answers into structured data"""

    # Number words to digits
    NUMBER_WORDS = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
        "ten": 10, "eleven": 11, "twelve": 12
    }

    # Building type patterns
    BUILDING_TYPE_PATTERNS = {
        "residential": [
            r"\b(house|home|residence|residential|living|apartment|condo|adu|granny|dwelling)\b",
            r"\b(single.?family|townhouse|duplex)\b"
        ],
        "commercial": [
            r"\b(commercial|business|office|retail|store|shop|warehouse|restaurant|cafe)\b"
        ],
        "mixed": [
            r"\b(mixed.?use|live.?work|shop.?below|apartment.?above)\b"
        ]
    }

    # Residence type patterns
    RESIDENCE_PATTERNS = {
        "single_family": [r"\b(single.?family|house|home|detached)\b"],
        "apartment": [r"\b(apartment|flat|condo|unit)\b"],
        "adu": [r"\b(adu|accessory|granny|in.?law|guest.?house|backyard)\b"],
        "townhouse": [r"\b(townhouse|townhome|row.?house|attached)\b"]
    }

    # Style patterns
    STYLE_PATTERNS = {
        "modern": [r"\b(modern|clean|sleek|minimalist)\b"],
        "traditional": [r"\b(traditional|classic|colonial|craftsman|farmhouse)\b"],
        "contemporary": [r"\b(contemporary|current|trendy)\b"],
        "minimal": [r"\b(minimal|simple|efficient|compact)\b"]
    }

    # Special room patterns
    SPECIAL_ROOM_PATTERNS = {
        "office": [r"\b(office|study|work.?room|home.?office|wfh)\b"],
        "media": [r"\b(media|theater|movie|entertainment)\b"],
        "gym": [r"\b(gym|exercise|workout|fitness)\b"],
        "mudroom": [r"\b(mudroom|mud.?room|entry.?room|boot.?room)\b"],
        "pantry": [r"\b(pantry|food.?storage|butler)\b"]
    }

    @classmethod
    def parse_number(cls, text: str) -> Optional[int]:
        """Extract a number from text"""
        text_lower = text.lower()

        # Check number words first
        for word, num in cls.NUMBER_WORDS.items():
            if word in text_lower:
                return num

        # Look for digits
        match = re.search(r'\b(\d+)\b', text)
        if match:
            return int(match.group(1))

        return None

    @classmethod
    def parse_sqft(cls, text: str) -> Optional[int]:
        """Extract square footage from text"""
        text_lower = text.lower()

        # Patterns: "1500 sqft", "1,500 sq ft", "1500 square feet", "about 2000"
        patterns = [
            r'(\d{1,2}[,.]?\d{3})\s*(?:sq\.?\s*ft|square\s*feet?|sqft|sf)',
            r'(?:about|around|approximately|roughly|~)\s*(\d{1,2}[,.]?\d{3})',
            r'(\d{3,5})\s*(?:sq\.?\s*ft|square\s*feet?|sqft|sf)?'
        ]

        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                num_str = match.group(1).replace(',', '').replace('.', '')
                return int(num_str)

        return None

    @classmethod
    def parse_bathrooms(cls, text: str) -> Optional[float]:
        """Extract bathroom count (handles half baths)"""
        text_lower = text.lower()

        # "2.5 bathrooms", "2 and a half", "2 full 1 half"
        if "half" in text_lower or ".5" in text_lower:
            full_match = re.search(r'(\d+)\s*(?:full|and)', text_lower)
            full = int(full_match.group(1)) if full_match else 0

            half_match = re.search(r'(\d+)\s*half', text_lower)
            half = int(half_match.group(1)) if half_match else 1

            if ".5" in text_lower:
                match = re.search(r'(\d+\.5)', text_lower)
                if match:
                    return float(match.group(1))

            return full + (half * 0.5)

        return cls.parse_number(text)

    @classmethod
    def parse_building_type(cls, text: str) -> Optional[str]:
        """Identify building type from text"""
        text_lower = text.lower()

        for btype, patterns in cls.BUILDING_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return btype
        return None

    @classmethod
    def parse_residence_type(cls, text: str) -> Optional[str]:
        """Identify residence type from text"""
        text_lower = text.lower()

        for rtype, patterns in cls.RESIDENCE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return rtype
        return "single_family"  # Default

    @classmethod
    def parse_style(cls, text: str) -> Optional[str]:
        """Identify architectural style from text"""
        text_lower = text.lower()

        for style, patterns in cls.STYLE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return style
        return None

    @classmethod
    def parse_garage(cls, text: str) -> str:
        """Parse garage requirements"""
        text_lower = text.lower()

        if any(w in text_lower for w in ["no garage", "don't need", "no car", "none", "without"]):
            return "none"

        if "3" in text_lower or "three" in text_lower:
            return "3car"
        if "2" in text_lower or "two" in text_lower:
            return "2car"
        if "1" in text_lower or "one" in text_lower or "single" in text_lower:
            return "1car"

        if "garage" in text_lower:
            return "2car"  # Default if garage mentioned

        return "none"

    @classmethod
    def parse_special_rooms(cls, text: str) -> List[str]:
        """Extract special room requests"""
        text_lower = text.lower()
        rooms = []

        for room, patterns in cls.SPECIAL_ROOM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    rooms.append(room)
                    break

        return rooms

    @classmethod
    def parse_yes_no(cls, text: str) -> Optional[bool]:
        """Parse yes/no response"""
        text_lower = text.lower().strip()

        yes_patterns = ["yes", "yeah", "yep", "sure", "ok", "okay", "correct", "right", "absolutely", "definitely"]
        no_patterns = ["no", "nope", "nah", "not", "don't", "negative"]

        for pattern in yes_patterns:
            if pattern in text_lower:
                return True
        for pattern in no_patterns:
            if pattern in text_lower:
                return False

        return None

    @classmethod
    def parse_open_concept(cls, text: str) -> Optional[bool]:
        """Parse open concept preference"""
        text_lower = text.lower()

        if any(w in text_lower for w in ["open", "open concept", "open plan", "open floor"]):
            return True
        if any(w in text_lower for w in ["separate", "traditional", "closed", "distinct"]):
            return False

        return None


# =============================================================================
# INTERVIEW CONDUCTOR
# =============================================================================

class QBDInterview:
    """Conducts the design interview"""

    def __init__(self):
        self.context = InterviewContext()
        self.parser = AnswerParser()

    def start(self) -> str:
        """Start a new interview"""
        self.context = InterviewContext()
        self.context.phase = InterviewPhase.GREETING

        greeting = self._generate_greeting()
        self.context.add_message("assistant", greeting)
        return greeting

    def process_input(self, user_input: str) -> str:
        """Process user input and return next response"""
        self.context.add_message("user", user_input)

        # Route to appropriate handler based on phase
        handlers = {
            InterviewPhase.GREETING: self._handle_greeting,
            InterviewPhase.BUILDING_TYPE: self._handle_building_type,
            InterviewPhase.SIZE_SCOPE: self._handle_size_scope,
            InterviewPhase.ROOM_REQUIREMENTS: self._handle_room_requirements,
            InterviewPhase.SPECIAL_FEATURES: self._handle_special_features,
            InterviewPhase.STYLE_PREFERENCES: self._handle_style_preferences,
            InterviewPhase.REVIEW: self._handle_review,
        }

        handler = handlers.get(self.context.phase, self._handle_unknown)
        response = handler(user_input)

        self.context.add_message("assistant", response)
        return response

    def _generate_greeting(self) -> str:
        """Generate initial greeting"""
        return """Welcome to the Design Interview!

I'll help you design your space by asking a few questions. You can answer naturally - no need to pick from a list.

**What kind of space are you looking to design?**
(For example: "a 3-bedroom house", "a small retail shop", "an apartment")"""

    def _handle_greeting(self, text: str) -> str:
        """Handle initial response - extract as much as possible"""
        req = self.context.requirements

        # Try to extract building type
        btype = self.parser.parse_building_type(text)
        if btype:
            req.building_type = btype

            if btype == "residential":
                req.residence_type = self.parser.parse_residence_type(text)

                # Try to get bedrooms from initial statement
                bedrooms = self.parser.parse_number(text)
                if bedrooms and bedrooms <= 10:
                    req.bedrooms = bedrooms

                # Try to get sqft
                sqft = self.parser.parse_sqft(text)
                if sqft:
                    req.target_sqft = sqft

        # Advance phase
        if req.building_type:
            self.context.phase = InterviewPhase.SIZE_SCOPE
            return self._ask_size_question()
        else:
            # Need clarification
            return """I want to make sure I understand correctly.

Are you designing:
- A **home** (house, apartment, ADU)
- A **commercial** space (office, retail, restaurant)
- A **mixed-use** building (live/work, shop with apartment above)"""

    def _handle_building_type(self, text: str) -> str:
        """Handle building type clarification"""
        req = self.context.requirements

        btype = self.parser.parse_building_type(text)
        if btype:
            req.building_type = btype
            if btype == "residential":
                req.residence_type = self.parser.parse_residence_type(text)
            self.context.phase = InterviewPhase.SIZE_SCOPE
            return self._ask_size_question()

        # Still unclear
        self.context.attempts += 1
        if self.context.attempts >= 3:
            req.building_type = "residential"
            req.residence_type = "single_family"
            self.context.phase = InterviewPhase.SIZE_SCOPE
            return "I'll assume we're designing a single-family home.\n\n" + self._ask_size_question()

        return "I didn't quite catch that. Just tell me: **home**, **commercial**, or **mixed-use**?"

    def _ask_size_question(self) -> str:
        """Generate size/scope question based on building type"""
        req = self.context.requirements

        if req.building_type == "residential":
            if req.bedrooms > 0:
                return f"""Got it - a {req.bedrooms}-bedroom {req.residence_type.replace('_', ' ')}.

**How many bathrooms do you need?**
(For example: "2 bathrooms", "2 full and 1 half bath")"""
            else:
                return """**How many bedrooms and bathrooms do you need?**
(For example: "3 bedrooms and 2 bathrooms", "it's a 2BR/2BA")"""

        elif req.building_type == "commercial":
            return """**What type of commercial space and how large?**
(For example: "a 2000 sqft retail store", "small office about 1500 square feet")"""

        else:  # mixed
            return """**What's the total size you're looking for?**
(For example: "about 2500 sqft total", "small - maybe 1500 square feet")"""

    def _handle_size_scope(self, text: str) -> str:
        """Handle size and scope answers"""
        req = self.context.requirements

        # Extract bedrooms if not set
        if req.building_type == "residential" and req.bedrooms == 0:
            bedrooms = self.parser.parse_number(text)
            if bedrooms and bedrooms <= 10:
                req.bedrooms = bedrooms

        # Extract bathrooms
        bathrooms = self.parser.parse_bathrooms(text)
        if bathrooms:
            req.bathrooms = bathrooms

        # Extract sqft
        sqft = self.parser.parse_sqft(text)
        if sqft:
            req.target_sqft = sqft

        # For commercial, get type
        if req.building_type == "commercial":
            for ctype in ["office", "retail", "restaurant", "warehouse"]:
                if ctype in text.lower():
                    req.commercial_type = ctype
                    break

        # Check what we still need
        if req.building_type == "residential":
            if req.bedrooms == 0:
                return "How many **bedrooms** do you need?"
            if req.bathrooms == 0:
                return "And how many **bathrooms**?"
            if req.target_sqft == 0:
                # Estimate based on bedrooms
                req.target_sqft = 800 + (req.bedrooms * 400)

        if req.building_type == "commercial" and req.target_sqft == 0:
            return "What's the approximate **square footage** you need?"

        # Move to next phase
        self.context.phase = InterviewPhase.ROOM_REQUIREMENTS
        return self._ask_room_requirements()

    def _ask_room_requirements(self) -> str:
        """Ask about room requirements"""
        req = self.context.requirements

        if req.building_type == "residential":
            return f"""A {req.bedrooms}BR/{req.bathrooms}BA at ~{req.target_sqft:,} sqft - nice!

**Do you need a garage?** If so, how many cars?
(For example: "yes, 2-car garage", "no garage needed")"""
        else:
            return """**What are the main spaces you need?**
(For example: "reception area, 4 offices, and a conference room")"""

    def _handle_room_requirements(self, text: str) -> str:
        """Handle room requirements"""
        req = self.context.requirements

        if req.building_type == "residential":
            req.garage = self.parser.parse_garage(text)

        # Move to special features
        self.context.phase = InterviewPhase.SPECIAL_FEATURES
        return self._ask_special_features()

    def _ask_special_features(self) -> str:
        """Ask about special features"""
        return """**Any special rooms or features you'd like?**

Some options: home office, media room, gym, mudroom, walk-in pantry

(Just list what you want, or say "none" if the basics are fine)"""

    def _handle_special_features(self, text: str) -> str:
        """Handle special features response"""
        req = self.context.requirements

        if "none" not in text.lower():
            special = self.parser.parse_special_rooms(text)
            req.special_rooms = special

        # Check for open concept preference
        open_pref = self.parser.parse_open_concept(text)
        if open_pref is not None:
            req.open_concept = open_pref

        # Move to style
        self.context.phase = InterviewPhase.STYLE_PREFERENCES
        return self._ask_style()

    def _ask_style(self) -> str:
        """Ask about style preferences"""
        return """**What architectural style do you prefer?**

- **Modern** - clean lines, open spaces, minimal ornamentation
- **Traditional** - classic proportions, defined rooms
- **Contemporary** - current trends, mixed materials
- **Minimalist** - simple, efficient, compact

(Or just describe what you like!)"""

    def _handle_style_preferences(self, text: str) -> str:
        """Handle style preference"""
        req = self.context.requirements

        style = self.parser.parse_style(text)
        if style:
            req.style = style

        # Also check for open concept here
        open_pref = self.parser.parse_open_concept(text)
        if open_pref is not None:
            req.open_concept = open_pref

        # Move to review
        self.context.phase = InterviewPhase.REVIEW
        return self._generate_review()

    def _generate_review(self) -> str:
        """Generate design summary for review"""
        req = self.context.requirements
        summary = req.summary()

        return f"""Here's what I've gathered:

{summary}

**Does this look right?**
(Say "yes" to generate, or tell me what to change)"""

    def _handle_review(self, text: str) -> str:
        """Handle review confirmation"""
        confirmation = self.parser.parse_yes_no(text)

        if confirmation:
            return self._generate_design()

        # Look for modifications
        text_lower = text.lower()
        req = self.context.requirements

        # Check for specific changes
        if "bedroom" in text_lower:
            num = self.parser.parse_number(text)
            if num:
                req.bedrooms = num
                return self._generate_review()

        if "bathroom" in text_lower:
            num = self.parser.parse_bathrooms(text)
            if num:
                req.bathrooms = num
                return self._generate_review()

        if "sqft" in text_lower or "square" in text_lower:
            sqft = self.parser.parse_sqft(text)
            if sqft:
                req.target_sqft = sqft
                return self._generate_review()

        # General modification - go back to style for quick fixes
        return "What would you like to change? You can adjust bedrooms, bathrooms, sqft, garage, or style."

    def _generate_design(self) -> str:
        """Generate the design"""
        self.context.phase = InterviewPhase.GENERATING
        req = self.context.requirements

        # Convert to QBD answers
        answers = req.to_qbd_answers()

        # Generate the floor plan
        result = generate_floor_plan_from_qbd(answers, output_format=OutputFormat.REVIT)

        if result["success"]:
            self.context.phase = InterviewPhase.COMPLETE

            summary = result["summary"]
            placed = summary["rooms_placed"]
            requested = summary["rooms_requested"]

            response = f"""**Design Generated!**

Layout: {result['width']:.0f}' x {result['depth']:.0f}' ({result['sqft']} sqft)
- {summary['total_walls']} walls ({summary['exterior_walls']} exterior, {summary['interior_walls']} interior)
- {summary['doors']} doors
- {placed}/{requested} rooms placed

"""
            if result["unplaced_rooms"]:
                response += f"Note: Some rooms couldn't fit: {', '.join(result['unplaced_rooms'])}\n\n"

            response += "The floor plan is ready! Would you like me to export it for **Revit** or **ArchEngine**?"

            # Store result for export
            self.context.last_result = result
            return response
        else:
            return f"There was an issue generating the design: {result.get('error', 'Unknown error')}\n\nWould you like to adjust the requirements?"

    def _handle_unknown(self, text: str) -> str:
        """Handle unknown phase"""
        return "I'm not sure where we are in the conversation. Let's start fresh.\n\n" + self.start()

    def export(self, format_type: str = "revit") -> Dict:
        """Export the generated design"""
        if not hasattr(self.context, 'last_result'):
            return {"error": "No design has been generated yet"}

        answers = self.context.requirements.to_qbd_answers()

        if format_type.lower() == "archengine":
            return export_for_archengine(answers)
        else:
            return export_for_revit(answers)

    def get_state(self) -> Dict:
        """Get current interview state for persistence"""
        return {
            "phase": self.context.phase.value,
            "requirements": {
                "building_type": self.context.requirements.building_type,
                "residence_type": self.context.requirements.residence_type,
                "commercial_type": self.context.requirements.commercial_type,
                "target_sqft": self.context.requirements.target_sqft,
                "bedrooms": self.context.requirements.bedrooms,
                "bathrooms": self.context.requirements.bathrooms,
                "garage": self.context.requirements.garage,
                "special_rooms": self.context.requirements.special_rooms,
                "style": self.context.requirements.style,
                "open_concept": self.context.requirements.open_concept
            },
            "conversation_history": self.context.conversation_history
        }

    def restore_state(self, state: Dict):
        """Restore interview state"""
        self.context.phase = InterviewPhase(state.get("phase", "greeting"))

        req_data = state.get("requirements", {})
        req = self.context.requirements
        req.building_type = req_data.get("building_type", "")
        req.residence_type = req_data.get("residence_type", "")
        req.commercial_type = req_data.get("commercial_type", "")
        req.target_sqft = req_data.get("target_sqft", 0)
        req.bedrooms = req_data.get("bedrooms", 0)
        req.bathrooms = req_data.get("bathrooms", 0)
        req.garage = req_data.get("garage", "none")
        req.special_rooms = req_data.get("special_rooms", [])
        req.style = req_data.get("style", "modern")
        req.open_concept = req_data.get("open_concept", True)

        self.context.conversation_history = state.get("conversation_history", [])


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def start_interview() -> Tuple[QBDInterview, str]:
    """Start a new interview session"""
    interview = QBDInterview()
    greeting = interview.start()
    return interview, greeting


def quick_design(description: str) -> Dict:
    """Generate a design from a single description"""
    interview = QBDInterview()
    interview.start()

    # Process the description through all phases
    interview.process_input(description)

    # Fill in defaults and generate
    req = interview.context.requirements
    if req.building_type == "":
        req.building_type = "residential"
        req.residence_type = "single_family"
    if req.bedrooms == 0:
        req.bedrooms = 3
    if req.bathrooms == 0:
        req.bathrooms = 2
    if req.target_sqft == 0:
        req.target_sqft = 1500

    answers = req.to_qbd_answers()
    return generate_floor_plan_from_qbd(answers)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("QBD INTERVIEW TEST")
    print("=" * 60)

    # Test the interview flow
    interview = QBDInterview()

    # Simulate conversation
    test_inputs = [
        "I want to design a 3-bedroom house",
        "2 full bathrooms",
        "yes, 2-car garage please",
        "home office and a pantry",
        "modern style with open concept",
        "yes"
    ]

    print("\n" + interview.start())

    for user_input in test_inputs:
        print(f"\n>>> {user_input}")
        response = interview.process_input(user_input)
        print(f"\n{response}")

    # Test quick design
    print("\n" + "=" * 60)
    print("QUICK DESIGN TEST")
    print("=" * 60)

    result = quick_design("a modern 4-bedroom house with 2.5 bathrooms and a 2-car garage, about 2200 sqft")
    if result["success"]:
        print(f"\nQuick design generated: {result['width']}x{result['depth']} ({result['sqft']} sqft)")
        print(f"Rooms placed: {result['summary']['rooms_placed']}/{result['summary']['rooms_requested']}")
