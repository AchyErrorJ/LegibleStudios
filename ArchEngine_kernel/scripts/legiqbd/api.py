"""LegiQBD API for Legible Studio integration.

Provides a clean interface for the CAD frontend to consume.
When no file is open, the chat panel appears with initial questions.

Usage:
    from legiqbd.api import LegiQBDAPI

    api = LegiQBDAPI()

    # Get initial state (for empty/new file)
    state = api.get_initial_state()
    # Returns: {
    #     "greeting": "What kind of home are you dreaming of?",
    #     "questions": [...],  # First 3 questions
    #     "phase": "greeting",
    #     "has_design": False
    # }

    # Process user input
    result = api.chat("I need a 3 bedroom 2 bath house")
    # Returns: {
    #     "response": "Great! Let me set that up...",
    #     "rooms": [...],
    #     "questions": [...],  # Follow-up questions
    #     "phase": "discovery",
    #     "is_solvable": True,
    #     "layout": {...},  # If solved
    #     "reality": {...}  # Physics, economics, psychology analysis
    # }

    # Run reality layer analysis
    reality = api.analyze_reality()
    # Returns environment, materiality, perception results
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

# Setup path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from qbd import QBDState, generate_questions, solve_state
from qbd.layers import EnvironmentLayer, MaterialityLayer, PerceptionLayer
from qbd.layers.materiality import ConstructionSystem, QualityLevel
from llm import LLMConfig

from .session import Session, SessionPhase, SessionConfig
from .engine import ConversationEngine
from .formatter import ResponseFormatter


# =============================================================================
# INITIAL PROMPTS
# =============================================================================

GREETING_PROMPTS = [
    "What kind of home are you dreaming of?",
    "Tell me about your ideal home.",
    "Let's design your perfect space. What do you have in mind?",
]

STARTER_QUESTIONS = [
    {
        "id": "q_start_bedrooms",
        "text": "How many bedrooms do you need?",
        "options": ["1", "2", "3", "4", "5+"],
        "category": "program"
    },
    {
        "id": "q_start_style",
        "text": "What style appeals to you?",
        "options": ["Modern", "Traditional", "Farmhouse", "Ranch", "Not sure"],
        "category": "character"
    },
    {
        "id": "q_start_size",
        "text": "Roughly how big?",
        "options": ["Small (<1500 sqft)", "Medium (1500-2500)", "Large (2500+)", "Not sure"],
        "category": "constraints"
    },
]


# =============================================================================
# API RESPONSE TYPES
# =============================================================================

@dataclass
class InitialState:
    """State returned when no file is open."""
    greeting: str
    questions: List[Dict]
    phase: str
    has_design: bool
    session_id: str


@dataclass
class ChatResponse:
    """Response from processing user input."""
    response: str
    rooms: List[Dict]
    room_count: int
    questions: List[Dict]
    phase: str
    is_solvable: bool
    is_solved: bool
    layout: Optional[Dict]
    errors: List[str]
    session_id: str
    reality: Optional[Dict[str, Any]] = None  # Reality layer analysis


@dataclass
class DesignState:
    """Current state of the design."""
    rooms: List[Dict]
    room_count: int
    adjacencies: int
    constraints: Dict
    phase: str
    is_solvable: bool
    is_solved: bool
    layout: Optional[Dict]
    score: Optional[float]
    session_id: str


@dataclass
class RealityAnalysis:
    """Combined reality layer analysis results."""
    environment: Dict[str, Any]  # Solar, thermal, acoustics
    materiality: Dict[str, Any]  # Cost, construction, complexity
    perception: Dict[str, Any]  # Wayfinding, comfort, delight
    overall_score: float  # 0-1, overall design quality
    critical_issues: List[str]
    recommendations: List[str]


@dataclass
class EnvironmentAnalysis:
    """Environment layer (physics) results."""
    thermal_load_kw: float
    cooling_load_kw: float
    daylight_factors: Dict[str, float]  # room_id -> factor
    acoustic_privacy: Dict[str, str]  # room_id -> privacy level
    passive_strategies: List[str]
    physics_violations: List[str]


@dataclass
class MaterialityAnalysis:
    """Materiality layer (economics) results."""
    total_cost: float
    cost_per_sqft: float
    budget_status: str  # "under", "near", "over"
    construction_weeks: int
    crew_size: int
    carbon_footprint_kg: float
    lifecycle_cost_30yr: float


@dataclass
class PerceptionAnalysis:
    """Perception layer (psychology) results."""
    wayfinding_score: float  # 0-1
    comfort_scores: Dict[str, float]  # room_id -> comfort
    delight_scores: Dict[str, float]  # room_id -> delight
    overall_experience: float  # 0-1
    enhancement_opportunities: List[str]


# =============================================================================
# LEGIQBD API
# =============================================================================

class LegiQBDAPI:
    """
    API for LegiQBD integration with Legible Studio.

    Manages sessions and provides a clean interface for the CAD frontend.
    """

    def __init__(self):
        """Initialize API with session management."""
        self._sessions: Dict[str, ConversationEngine] = {}
        self._active_session: Optional[str] = None

        # Check LLM availability
        self._llm_available = self._check_llm()

    def _check_llm(self) -> bool:
        """Check if LLM is available."""
        try:
            status = LLMConfig.status()
            return status.get("active") is not None
        except:
            return False

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    def new_session(self) -> str:
        """Create a new session and return its ID."""
        engine = ConversationEngine()
        session_id = engine.session.id
        self._sessions[session_id] = engine
        self._active_session = session_id
        return session_id

    def get_session(self, session_id: str = None) -> Optional[ConversationEngine]:
        """Get a session by ID, or the active session."""
        if session_id:
            return self._sessions.get(session_id)
        if self._active_session:
            return self._sessions.get(self._active_session)
        return None

    def set_active_session(self, session_id: str):
        """Set the active session."""
        if session_id in self._sessions:
            self._active_session = session_id

    # =========================================================================
    # INITIAL STATE (No file open)
    # =========================================================================

    def get_initial_state(self) -> Dict[str, Any]:
        """
        Get initial state for when no file is open.

        This is what the chat panel shows on startup.
        Returns greeting and starter questions.
        """
        # Create new session
        session_id = self.new_session()
        engine = self._sessions[session_id]

        # Get greeting from LLM if available, otherwise use default
        if self._llm_available:
            try:
                response = engine.start_conversation()
                greeting = response.text
            except:
                greeting = GREETING_PROMPTS[0]
        else:
            greeting = GREETING_PROMPTS[0]

        return asdict(InitialState(
            greeting=greeting,
            questions=STARTER_QUESTIONS,
            phase="greeting",
            has_design=False,
            session_id=session_id
        ))

    def get_starter_questions(self) -> List[Dict]:
        """Get the starter questions for quick-start UI."""
        return STARTER_QUESTIONS

    # =========================================================================
    # CHAT INTERFACE
    # =========================================================================

    def chat(self, message: str, session_id: str = None,
            include_reality: bool = False) -> Dict[str, Any]:
        """
        Process a chat message and return response.

        Args:
            message: User's message
            session_id: Optional session ID (uses active if not provided)
            include_reality: Whether to include reality layer analysis

        Returns:
            ChatResponse as dict
        """
        engine = self.get_session(session_id)

        if not engine:
            # Create new session if none exists
            session_id = self.new_session()
            engine = self._sessions[session_id]
            engine.start_conversation()

        # Process input
        response = engine.process_input(message)

        # Get current rooms
        rooms = [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "type": r.get("type"),
                "area_min": r.get("area_min")
            }
            for r in engine.session.qbd_state.rooms
        ]

        # Get follow-up questions
        questions = []
        if not response.is_solved:
            try:
                questions = generate_questions(engine.session.qbd_state, max_questions=3)
            except:
                pass

        # Get layout if solved
        layout = None
        if response.is_solved:
            layout = engine.session.solved_layout

        # Optional reality analysis
        reality = None
        if include_reality and len(engine.session.qbd_state.rooms) > 0:
            try:
                reality = self.analyze_reality(session_id)
            except:
                reality = None

        return asdict(ChatResponse(
            response=response.text,
            rooms=rooms,
            room_count=len(rooms),
            questions=questions,
            phase=response.phase,
            is_solvable=response.is_solvable,
            is_solved=response.is_solved,
            layout=layout,
            errors=response.errors,
            session_id=engine.session.id,
            reality=reality
        ))

    def answer_question(self, question_id: str, answer: str,
                        session_id: str = None) -> Dict[str, Any]:
        """
        Answer a specific question.

        Args:
            question_id: ID of the question being answered
            answer: User's answer
            session_id: Optional session ID

        Returns:
            ChatResponse as dict
        """
        # Convert to natural language and process
        message = f"{answer}"
        return self.chat(message, session_id)

    # =========================================================================
    # DESIGN STATE
    # =========================================================================

    def get_design_state(self, session_id: str = None) -> Dict[str, Any]:
        """
        Get current state of the design.

        Args:
            session_id: Optional session ID

        Returns:
            DesignState as dict
        """
        engine = self.get_session(session_id)

        if not engine:
            return asdict(DesignState(
                rooms=[],
                room_count=0,
                adjacencies=0,
                constraints={},
                phase="greeting",
                is_solvable=False,
                is_solved=False,
                layout=None,
                score=None,
                session_id=""
            ))

        state = engine.session.qbd_state
        session = engine.session

        rooms = [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "type": r.get("type"),
                "area_min": r.get("area_min")
            }
            for r in state.rooms
        ]

        layout = session.solved_layout
        score = None
        if layout:
            score = layout.get("score")

        return asdict(DesignState(
            rooms=rooms,
            room_count=len(rooms),
            adjacencies=len(state.adjacencies),
            constraints={k: v for k, v in state.constraints.items() if v is not None},
            phase=session.phase.value,
            is_solvable=session.is_solvable,
            is_solved=session.is_solved,
            layout=layout,
            score=score,
            session_id=session.id
        ))

    # =========================================================================
    # SOLVER
    # =========================================================================

    def solve(self, session_id: str = None) -> Dict[str, Any]:
        """
        Manually trigger the solver.

        Returns:
            Dict with success status and layout or error
        """
        engine = self.get_session(session_id)

        if not engine:
            return {"success": False, "error": "No active session"}

        if not engine.session.is_solvable:
            return {"success": False, "error": "Not enough information to solve"}

        success, result = engine.solve()

        if success:
            return {
                "success": True,
                "layout": result.get("layout"),
                "score": result.get("score"),
                "metrics": result.get("metrics")
            }
        else:
            return {
                "success": False,
                "error": result.get("error"),
                "message": result.get("message")
            }

    # =========================================================================
    # REALITY LAYER ANALYSIS
    # =========================================================================

    def analyze_reality(self, session_id: str = None,
                       construction_system: str = "wood_light_frame",
                       quality_level: str = "standard",
                       region: str = "northeast") -> Dict[str, Any]:
        """
        Run all three reality layers on the current design.

        Args:
            session_id: Optional session ID
            construction_system: Construction system type
            quality_level: Quality level (basic, standard, premium, custom)
            region: Region for cost calculations

        Returns:
            RealityAnalysis as dict
        """
        engine = self.get_session(session_id)

        if not engine or len(engine.session.qbd_state.rooms) == 0:
            return asdict(RealityAnalysis(
                environment={},
                materiality={},
                perception={},
                overall_score=0.0,
                critical_issues=["No design to analyze"],
                recommendations=[]
            ))

        state = engine.session.qbd_state

        # Run all three layers
        env_result = self._analyze_environment(state)
        mat_result = self._analyze_materiality(state, construction_system, quality_level, region)
        perc_result = self._analyze_perception(state, env_result)

        # Combine into overall assessment
        all_issues = (
            env_result.get("physics_violations", []) +
            mat_result.get("risk_factors", []) +
            perc_result.get("critical_issues", [])
        )

        all_recommendations = (
            env_result.get("passive_strategies", []) +
            perc_result.get("enhancement_opportunities", [])
        )

        # Calculate overall score (average of layer scores)
        env_score = self._calculate_environment_score(env_result)
        mat_score = self._calculate_materiality_score(mat_result)
        perc_score = perc_result.get("overall_experience", 0.5)
        overall = (env_score + mat_score + perc_score) / 3

        return asdict(RealityAnalysis(
            environment=env_result,
            materiality=mat_result,
            perception=perc_result,
            overall_score=round(overall, 2),
            critical_issues=all_issues,
            recommendations=all_recommendations
        ))

    def analyze_environment(self, session_id: str = None) -> Dict[str, Any]:
        """
        Run environment layer (physics) analysis.

        Returns:
            EnvironmentAnalysis as dict
        """
        engine = self.get_session(session_id)

        if not engine or len(engine.session.qbd_state.rooms) == 0:
            return asdict(EnvironmentAnalysis(
                thermal_load_kw=0,
                cooling_load_kw=0,
                daylight_factors={},
                acoustic_privacy={},
                passive_strategies=[],
                physics_violations=["No design to analyze"]
            ))

        result = self._analyze_environment(engine.session.qbd_state)
        return asdict(EnvironmentAnalysis(
            thermal_load_kw=result.get("thermal_load_kw", 0),
            cooling_load_kw=result.get("cooling_load_kw", 0),
            daylight_factors=result.get("daylight_factors", {}),
            acoustic_privacy=result.get("acoustic_privacy", {}),
            passive_strategies=result.get("passive_strategies", []),
            physics_violations=result.get("physics_violations", [])
        ))

    def analyze_materiality(self, session_id: str = None,
                           construction_system: str = "wood_light_frame",
                           quality_level: str = "standard",
                           region: str = "northeast") -> Dict[str, Any]:
        """
        Run materiality layer (economics) analysis.

        Returns:
            MaterialityAnalysis as dict
        """
        engine = self.get_session(session_id)

        if not engine or len(engine.session.qbd_state.rooms) == 0:
            return asdict(MaterialityAnalysis(
                total_cost=0,
                cost_per_sqft=0,
                budget_status="unknown",
                construction_weeks=0,
                crew_size=0,
                carbon_footprint_kg=0,
                lifecycle_cost_30yr=0
            ))

        result = self._analyze_materiality(
            engine.session.qbd_state,
            construction_system,
            quality_level,
            region
        )
        return asdict(MaterialityAnalysis(
            total_cost=result.get("total_cost", 0),
            cost_per_sqft=result.get("cost_per_sqft", 0),
            budget_status=result.get("budget_status", "unknown"),
            construction_weeks=result.get("construction_weeks", 0),
            crew_size=result.get("crew_size", 0),
            carbon_footprint_kg=result.get("carbon_footprint_kg", 0),
            lifecycle_cost_30yr=result.get("lifecycle_cost_30yr", 0)
        ))

    def analyze_perception(self, session_id: str = None) -> Dict[str, Any]:
        """
        Run perception layer (psychology) analysis.

        Returns:
            PerceptionAnalysis as dict
        """
        engine = self.get_session(session_id)

        if not engine or len(engine.session.qbd_state.rooms) == 0:
            return asdict(PerceptionAnalysis(
                wayfinding_score=0,
                comfort_scores={},
                delight_scores={},
                overall_experience=0,
                enhancement_opportunities=[]
            ))

        state = engine.session.qbd_state
        env_result = self._analyze_environment(state)
        result = self._analyze_perception(state, env_result)

        return asdict(PerceptionAnalysis(
            wayfinding_score=result.get("wayfinding_score", 0),
            comfort_scores=result.get("comfort_scores", {}),
            delight_scores=result.get("delight_scores", {}),
            overall_experience=result.get("overall_experience", 0),
            enhancement_opportunities=result.get("enhancement_opportunities", [])
        ))

    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================

    def _analyze_environment(self, state: QBDState) -> Dict[str, Any]:
        """Run environment layer analysis."""
        try:
            env_layer = EnvironmentLayer(state.site)
            result = env_layer.analyze(
                rooms=state.rooms,
                adjacencies=state.adjacencies,
                separations=state.separations,
                building_layout={}
            )

            return {
                "thermal_load_kw": round(result.thermal.total_heating_load, 1),
                "cooling_load_kw": round(result.thermal.total_cooling_load, 1),
                "daylight_factors": {
                    rid: round(d.daylight_factor, 2)
                    for rid, d in result.solar.items()
                },
                "acoustic_privacy": {
                    rid: a.privacy_level
                    for rid, a in result.acoustic.items()
                },
                "passive_strategies": result.thermal.passive_strategy_potential,
                "physics_violations": result.critical_issues
            }
        except Exception as e:
            return {
                "thermal_load_kw": 0,
                "cooling_load_kw": 0,
                "daylight_factors": {},
                "acoustic_privacy": {},
                "passive_strategies": [],
                "physics_violations": [f"Analysis error: {e}"]
            }

    def _analyze_materiality(self, state: QBDState, system: str,
                            quality: str, region: str) -> Dict[str, Any]:
        """Run materiality layer analysis."""
        try:
            mat_layer = MaterialityLayer(region=region)
            result = mat_layer.analyze(
                rooms=state.rooms,
                site=state.site,
                construction_system=ConstructionSystem[system.upper()],
                quality_level=QualityLevel[quality.upper()]
            )

            return {
                "total_cost": result.cost.total_cost,
                "cost_per_sqft": result.cost.cost_per_sqft,
                "budget_status": result.cost.budget_status,
                "construction_weeks": result.complexity.duration_weeks,
                "crew_size": result.complexity.crew_size,
                "carbon_footprint_kg": result.carbon_footprint,
                "lifecycle_cost_30yr": result.lifecycle_cost_30yr,
                "risk_factors": result.complexity.risk_factors
            }
        except Exception as e:
            return {
                "total_cost": 0,
                "cost_per_sqft": 0,
                "budget_status": "error",
                "construction_weeks": 0,
                "crew_size": 0,
                "carbon_footprint_kg": 0,
                "lifecycle_cost_30yr": 0,
                "risk_factors": [f"Analysis error: {e}"]
            }

    def _analyze_perception(self, state: QBDState, env_result: Dict) -> Dict[str, Any]:
        """Run perception layer analysis."""
        try:
            perc_layer = PerceptionLayer()
            result = perc_layer.analyze(
                rooms=state.rooms,
                adjacencies=state.adjacencies,
                separations=state.separations,
                layout={},  # Empty for now
                environmental_result=None  # Simplified
            )

            return {
                "wayfinding_score": round(result.wayfinding.overall_legibility, 2),
                "comfort_scores": {
                    rid: round(c.overall_comfort, 2)
                    for rid, c in result.comfort.items()
                },
                "delight_scores": {
                    rid: round(d.delight_score, 2)
                    for rid, d in result.delight.items()
                },
                "overall_experience": round(result.overall_experience_score, 2),
                "critical_issues": result.critical_issues,
                "enhancement_opportunities": result.enhancement_opportunities
            }
        except Exception as e:
            return {
                "wayfinding_score": 0,
                "comfort_scores": {},
                "delight_scores": {},
                "overall_experience": 0,
                "critical_issues": [f"Analysis error: {e}"],
                "enhancement_opportunities": []
            }

    def _calculate_environment_score(self, env: Dict) -> float:
        """Calculate environment score (0-1)."""
        # Lower violations = higher score
        violations = len(env.get("physics_violations", []))
        score = max(0, 1.0 - (violations * 0.2))
        return round(score, 2)

    def _calculate_materiality_score(self, mat: Dict) -> float:
        """Calculate materiality score (0-1)."""
        # Budget under = good, risks = bad
        if mat.get("budget_status") == "under":
            score = 1.0
        elif mat.get("budget_status") == "near":
            score = 0.8
        else:
            score = 0.5

        # Subtract for risks
        risks = len(mat.get("risk_factors", []))
        score = max(0, score - (risks * 0.1))
        return round(score, 2)

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def save_session(self, session_id: str = None) -> str:
        """Save session to JSON string."""
        engine = self.get_session(session_id)
        if engine:
            return engine.session.to_json()
        return "{}"

    def load_session(self, json_str: str) -> str:
        """Load session from JSON string. Returns session ID."""
        data = json.loads(json_str)
        session = Session.from_dict(data)
        engine = ConversationEngine(session=session)

        self._sessions[session.id] = engine
        self._active_session = session.id

        return session.id

    # =========================================================================
    # STATUS
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get API status."""
        return {
            "llm_available": self._llm_available,
            "active_session": self._active_session,
            "session_count": len(self._sessions),
            "llm_provider": LLMConfig.status().get("active") if self._llm_available else None
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_api_instance: Optional[LegiQBDAPI] = None

def get_api() -> LegiQBDAPI:
    """Get the singleton API instance."""
    global _api_instance
    if _api_instance is None:
        _api_instance = LegiQBDAPI()
    return _api_instance


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def initial_state() -> Dict[str, Any]:
    """Get initial state for new/empty file."""
    return get_api().get_initial_state()

def chat(message: str) -> Dict[str, Any]:
    """Process a chat message."""
    return get_api().chat(message)

def design_state() -> Dict[str, Any]:
    """Get current design state."""
    return get_api().get_design_state()

def solve() -> Dict[str, Any]:
    """Solve the current design."""
    return get_api().solve()

def analyze_reality(**kwargs) -> Dict[str, Any]:
    """Analyze all reality layers (environment, materiality, perception)."""
    return get_api().analyze_reality(**kwargs)

def analyze_environment(**kwargs) -> Dict[str, Any]:
    """Analyze environment layer (solar, thermal, acoustics)."""
    return get_api().analyze_environment(**kwargs)

def analyze_materiality(**kwargs) -> Dict[str, Any]:
    """Analyze materiality layer (cost, construction, materials)."""
    return get_api().analyze_materiality(**kwargs)

def analyze_perception(**kwargs) -> Dict[str, Any]:
    """Analyze perception layer (wayfinding, comfort, delight)."""
    return get_api().analyze_perception(**kwargs)
