"""
Entropy-Driven Question Generator for QBD Algebra

Replaces fixed-phase interview with dynamic, information-theoretic question selection.
Questions emerge from state based on what would reduce design uncertainty most.
"""

from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from enum import Enum, auto
import math
from collections import defaultdict

from room_relationships import SpatialGraph, Room, RoomTypeSpec, ROOM_TYPES, Zone


# =============================================================================
# ENTROPY AND INFORMATION THEORY
# =============================================================================

@dataclass
class UncertaintyProfile:
    """Measures uncertainty in a design state."""
    
    # Entity uncertainties
    undefined_entities: int = 0  # Count of entities with no type
    underspecified_rooms: int = 0  # Rooms missing area or dimensions
    
    # Relationship uncertainties  
    unplaced_entities: int = 0  # Entities not yet in layout
    unresolved_adjacencies: int = 0  # Adjacencies without positions
    
    # Constraint uncertainties
    open_constraints: int = 0  # Constraints with wide bounds
    conflicting_constraints: int = 0  # Detected conflicts
    
    # Priority uncertainties
    neutral_priorities: int = 0  # Priorities at default (5/10)
    
    def total_entropy(self) -> float:
        """Calculate total entropy score."""
        return (
            self.undefined_entities * 2.0 +
            self.underspecified_rooms * 1.5 +
            self.unplaced_entities * 1.0 +
            self.unresolved_adjacencies * 0.8 +
            self.open_constraints * 0.5 +
            self.conflicting_constraints * 3.0 +
            self.neutral_priorities * 0.3
        )


def calculate_state_entropy(graph: SpatialGraph, priorities: Dict[str, int]) -> UncertaintyProfile:
    """
    Calculate uncertainty profile for current state.
    
    This measures what we don't know yet — higher entropy = more uncertainty.
    """
    profile = UncertaintyProfile()
    
    # Count underspecified rooms
    for room_id, room in graph.rooms.items():
        if room.min_area is None or room.min_area == 0:
            profile.underspecified_rooms += 1
        if not room.furniture and room.min_area is None:
            # No way to derive area
            profile.underspecified_rooms += 1
    
    # Count unresolved relationships
    profile.unresolved_adjacencies = len(graph.adjacencies)
    
    # Count neutral priorities
    for factor, value in priorities.items():
        if value == 5:  # Default neutral
            profile.neutral_priorities += 1
    
    # Check for conflicts (high entropy)
    conflicts = detect_conflicts(graph)
    profile.conflicting_constraints = len(conflicts)
    
    return profile


def detect_conflicts(graph: SpatialGraph) -> List[Dict]:
    """Detect constraint conflicts that create uncertainty."""
    conflicts = []
    
    # Check for adjacency + separation between same pair
    adjacency_pairs = set()
    for adj in graph.adjacencies:
        pair = tuple(sorted([adj.room_a, adj.room_b]))
        adjacency_pairs.add((pair, adj.strength))
    
    for sep in graph.separations:
        pair = tuple(sorted([sep.room_a, sep.room_b]))
        for adj_pair, adj_strength in adjacency_pairs:
            if pair == adj_pair:
                if sep.strength == "required" and adj_strength == "required":
                    conflicts.append({
                        "type": "contradiction",
                        "entities": pair,
                        "description": f"{pair[0]} and {pair[1]} are both adjacent and separated"
                    })
    
    # Check for area sum exceeding footprint (if footprint known)
    total_min_area = sum(r.min_area or 0 for r in graph.rooms.values())
    # TODO: Compare to footprint constraint when available
    
    return conflicts


# =============================================================================
# QUESTION TYPES
# =============================================================================

class QuestionCategory(Enum):
    """Categories of questions ordered by typical entropy impact."""
    BLOCKING = auto()      # Must answer to proceed
    STRUCTURAL = auto()    # Defines topology (room count, types)
    SPATIAL = auto()       # Defines sizes and relationships
    PRIORITY = auto()      # Defines optimization weights
    DETAIL = auto()        # Fine-tuning (minor entropy reduction)


@dataclass
class Question:
    """A question that can be asked to reduce entropy."""
    
    id: str
    text: str
    category: QuestionCategory
    
    # What this question targets
    target_entity: Optional[str] = None
    target_property: Optional[str] = None
    
    # Expected answers and their effects
    answer_type: str = "choice"  # "choice", "number", "text", "boolean"
    options: List[Dict] = field(default_factory=list)
    
    # Entropy metrics
    expected_entropy_reduction: float = 0.0
    blocking: bool = False
    
    # Dependencies
    requires: List[str] = field(default_factory=list)  # Question IDs that must be answered first
    
    # Follow-up questions triggered by specific answers
    follow_ups: Dict[str, List[str]] = field(default_factory=dict)
    
    # Can this be skipped with a default?
    can_skip: bool = True
    default_value: Any = None
    
    # Why are we asking this?
    rationale: str = ""


# =============================================================================
# QUESTION POOL
# =============================================================================

class QuestionPool:
    """Repository of all possible questions."""
    
    def __init__(self):
        self.questions: Dict[str, Question] = {}
        self._initialize_questions()
    
    def _initialize_questions(self):
        """Define all possible questions."""
        
        # === BLOCKING QUESTIONS ===
        # These must be answered to generate any design
        
        self.questions["q_building_type"] = Question(
            id="q_building_type",
            text="What type of building are you designing?",
            category=QuestionCategory.BLOCKING,
            answer_type="choice",
            options=[
                {"value": "residential", "label": "Residential (house, apartment)", "entropy_reduction": 5.0},
                {"value": "commercial", "label": "Commercial (office, retail)", "entropy_reduction": 5.0},
                {"value": "mixed", "label": "Mixed-use (live/work)", "entropy_reduction": 5.0},
            ],
            expected_entropy_reduction=5.0,
            blocking=True,
            can_skip=False,
            rationale="Determines the fundamental room types and relationships"
        )
        
        self.questions["q_site_size"] = Question(
            id="q_site_size",
            text="What are your site dimensions or footprint limit?",
            category=QuestionCategory.BLOCKING,
            answer_type="text",
            expected_entropy_reduction=4.0,
            blocking=True,
            can_skip=False,
            rationale="Without size constraints, the design space is infinite"
        )
        
        # === STRUCTURAL QUESTIONS ===
        # Define the topology of the design
        
        self.questions["q_bedroom_count"] = Question(
            id="q_bedroom_count",
            text="How many bedrooms do you need?",
            category=QuestionCategory.STRUCTURAL,
            target_property="rooms.bedroom.count",
            answer_type="number",
            options=[
                {"value": 1, "label": "1 bedroom", "entropy_reduction": 2.0},
                {"value": 2, "label": "2 bedrooms", "entropy_reduction": 2.0},
                {"value": 3, "label": "3 bedrooms", "entropy_reduction": 2.0},
                {"value": 4, "label": "4 bedrooms", "entropy_reduction": 2.0},
                {"value": 5, "label": "5+ bedrooms", "entropy_reduction": 2.0},
            ],
            expected_entropy_reduction=2.0,
            requires=["q_building_type"],
            follow_ups={
                "3": ["q_primary_suite"],
                "4": ["q_primary_suite", "q_guest_room"],
                "5": ["q_primary_suite", "q_guest_room"],
            },
            rationale="Bedrooms are major space consumers and drive layout topology"
        )
        
        self.questions["q_primary_suite"] = Question(
            id="q_primary_suite",
            text="Should the primary bedroom have an ensuite bathroom?",
            category=QuestionCategory.STRUCTURAL,
            target_property="rooms.primary_bedroom.ensuite",
            answer_type="boolean",
            expected_entropy_reduction=1.0,
            requires=["q_bedroom_count"],
            rationale="Ensuite requirement affects adjacency and plumbing clustering"
        )
        
        self.questions["q_garage"] = Question(
            id="q_garage",
            text="Do you need a garage? If so, how many cars?",
            category=QuestionCategory.STRUCTURAL,
            target_property="rooms.garage.size",
            answer_type="choice",
            options=[
                {"value": "none", "label": "No garage", "entropy_reduction": 0.5},
                {"value": "1car", "label": "1-car garage", "entropy_reduction": 1.0},
                {"value": "2car", "label": "2-car garage", "entropy_reduction": 1.0},
                {"value": "3car", "label": "3-car garage", "entropy_reduction": 1.0},
            ],
            expected_entropy_reduction=1.0,
            requires=["q_building_type"],
            follow_ups={
                "1car": ["q_mudroom"],
                "2car": ["q_mudroom"],
                "3car": ["q_mudroom"],
            },
            rationale="Garage affects footprint, entry sequence, and vehicle access"
        )
        
        # === SPATIAL QUESTIONS ===
        # Define sizes and relationships
        
        self.questions["q_bed_size_primary"] = Question(
            id="q_bed_size_primary",
            text="What size bed in the primary bedroom?",
            category=QuestionCategory.SPATIAL,
            target_property="rooms.primary_bedroom.furniture.bed.size",
            answer_type="choice",
            options=[
                {"value": "queen", "label": "Queen", "entropy_reduction": 0.8},
                {"value": "king", "label": "King", "entropy_reduction": 0.8},
                {"value": "california_king", "label": "California King", "entropy_reduction": 0.8},
            ],
            expected_entropy_reduction=0.8,
            requires=["q_bedroom_count"],
            default_value="queen",
            rationale="Bed size determines minimum room dimensions via derivation rules"
        )
        
        self.questions["q_open_concept"] = Question(
            id="q_open_concept",
            text="Do you prefer open-concept living or defined rooms?",
            category=QuestionCategory.SPATIAL,
            target_property="relationships.living_kitchen.type",
            answer_type="choice",
            options=[
                {"value": "open", "label": "Open concept (kitchen opens to living)", "entropy_reduction": 0.6},
                {"value": "partial", "label": "Partial (island or peninsula divider)", "entropy_reduction": 0.6},
                {"value": "defined", "label": "Defined rooms (separate kitchen)", "entropy_reduction": 0.6},
            ],
            expected_entropy_reduction=0.6,
            requires=["q_building_type"],
            default_value="open",
            rationale="Affects adjacency graph and wall generation"
        )
        
        self.questions["q_work_from_home"] = Question(
            id="q_work_from_home",
            text="Do you work from home?",
            category=QuestionCategory.SPATIAL,
            answer_type="boolean",
            expected_entropy_reduction=0.5,
            requires=["q_building_type"],
            follow_ups={
                "true": ["q_office_location"],
            },
            rationale="May trigger office room addition"
        )
        
        self.questions["q_office_location"] = Question(
            id="q_office_location",
            text="Where should the home office be located?",
            category=QuestionCategory.SPATIAL,
            target_property="rooms.office.zone",
            answer_type="choice",
            options=[
                {"value": "quiet", "label": "Quiet area (away from living spaces)", "entropy_reduction": 0.4},
                {"value": "central", "label": "Central (near entry)", "entropy_reduction": 0.4},
                {"value": "view", "label": "Best view", "entropy_reduction": 0.4},
            ],
            expected_entropy_reduction=0.4,
            requires=["q_work_from_home"],
            rationale="Affects placement in layout and adjacency decisions"
        )
        
        # === PRIORITY QUESTIONS ===
        # Define optimization weights
        
        self.questions["q_priority_light"] = Question(
            id="q_priority_light",
            text="How important is natural light?",
            category=QuestionCategory.PRIORITY,
            target_property="priorities.natural_light",
            answer_type="scale",
            options=[
                {"value": 3, "label": "Not important", "entropy_reduction": 0.3},
                {"value": 5, "label": "Nice to have", "entropy_reduction": 0.2},
                {"value": 8, "label": "Very important", "entropy_reduction": 0.4},
                {"value": 10, "label": "Critical", "entropy_reduction": 0.5},
            ],
            expected_entropy_reduction=0.3,
            default_value=5,
            rationale="Affects window placement and room orientation in solver"
        )
        
        self.questions["q_priority_privacy"] = Question(
            id="q_priority_privacy",
            text="How important is privacy between rooms?",
            category=QuestionCategory.PRIORITY,
            target_property="priorities.privacy",
            answer_type="scale",
            options=[
                {"value": 3, "label": "Open plan preferred", "entropy_reduction": 0.3},
                {"value": 5, "label": "Balanced", "entropy_reduction": 0.2},
                {"value": 8, "label": "Private spaces important", "entropy_reduction": 0.4},
                {"value": 10, "label": "Maximum privacy", "entropy_reduction": 0.5},
            ],
            expected_entropy_reduction=0.3,
            default_value=5,
            rationale="Affects separation constraints and zone placement"
        )
        
        # === DETAIL QUESTIONS ===
        # Fine-tuning with minor entropy reduction
        
        self.questions["q_ceiling_height"] = Question(
            id="q_ceiling_height",
            text="Preferred ceiling height?",
            category=QuestionCategory.DETAIL,
            target_property="constraints.ceiling_height",
            answer_type="choice",
            options=[
                {"value": 2.4, "label": "Standard (8 ft)", "entropy_reduction": 0.1},
                {"value": 2.7, "label": "High (9 ft)", "entropy_reduction": 0.1},
                {"value": 3.0, "label": "Very high (10 ft)", "entropy_reduction": 0.1},
            ],
            expected_entropy_reduction=0.1,
            default_value=2.4,
            rationale="Minor impact on volume and material costs"
        )
        
        self.questions["q_style"] = Question(
            id="q_style",
            text="What architectural style do you prefer?",
            category=QuestionCategory.DETAIL,
            target_property="character.style",
            answer_type="choice",
            options=[
                {"value": "modern", "label": "Modern", "entropy_reduction": 0.1},
                {"value": "traditional", "label": "Traditional", "entropy_reduction": 0.1},
                {"value": "minimal", "label": "Minimalist", "entropy_reduction": 0.1},
            ],
            expected_entropy_reduction=0.1,
            default_value="modern",
            rationale="Primarily affects aesthetics, not topology"
        )
    
    def get_question(self, question_id: str) -> Optional[Question]:
        """Get a question by ID."""
        return self.questions.get(question_id)
    
    def get_all_questions(self) -> List[Question]:
        """Get all questions."""
        return list(self.questions.values())
    
    def get_questions_by_category(self, category: QuestionCategory) -> List[Question]:
        """Get questions in a category."""
        return [q for q in self.questions.values() if q.category == category]


# =============================================================================
# ENTROPY-DRIVEN QUESTION GENERATOR
# =============================================================================

class EntropyDrivenQuestionGenerator:
    """
    Generates questions based on information theory.
    
    Selects questions that maximally reduce uncertainty in the design state.
    """
    
    def __init__(self, pool: QuestionPool = None):
        self.pool = pool or QuestionPool()
        self.answered_questions: Set[str] = set()
        self.asked_questions: Set[str] = set()
        self.answer_history: Dict[str, Any] = {}
    
    def generate_questions(
        self,
        graph: SpatialGraph,
        priorities: Dict[str, int],
        max_questions: int = 5
    ) -> List[Question]:
        """
        Generate the next best questions to ask.
        
        Algorithm:
        1. Calculate current entropy
        2. Find all available questions (dependencies met)
        3. Estimate entropy reduction for each
        4. Select top questions, balancing categories
        """
        # Calculate current uncertainty
        uncertainty = calculate_state_entropy(graph, priorities)
        current_entropy = uncertainty.total_entropy()
        
        # Get available questions
        available = self._get_available_questions(graph, priorities)
        
        if not available:
            return []
        
        # Score each question
        scored = []
        for question in available:
            score = self._score_question(question, graph, priorities, current_entropy)
            scored.append((question, score))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Balance categories (don't ask 5 detail questions)
        balanced = self._balance_categories(scored, max_questions)
        
        return balanced
    
    def _get_available_questions(
        self,
        graph: SpatialGraph,
        priorities: Dict[str, int]
    ) -> List[Question]:
        """Get questions whose dependencies are satisfied."""
        available = []
        
        for question in self.pool.get_all_questions():
            # Skip already answered
            if question.id in self.answered_questions:
                continue
            
            # Skip already asked (but not answered)
            if question.id in self.asked_questions:
                continue
            
            # Check dependencies
            deps_satisfied = all(
                dep in self.answered_questions
                for dep in question.requires
            )
            
            if deps_satisfied:
                available.append(question)
        
        return available
    
    def _score_question(
        self,
        question: Question,
        graph: SpatialGraph,
        priorities: Dict[str, int],
        current_entropy: float
    ) -> float:
        """
        Score a question by its expected information value.
        
        Factors:
        - Blocking: Critical questions get priority
        - Entropy reduction: How much uncertainty is resolved
        - Category balance: Prefer underrepresented categories
        - Context: Questions related to recent answers
        """
        score = 0.0
        
        # Blocking questions are highest priority
        if question.blocking:
            score += 1000.0
        
        # Expected entropy reduction
        score += question.expected_entropy_reduction * 100
        
        # Category bonus (prefer categories we haven't asked much)
        category_count = sum(
            1 for qid in self.asked_questions
            if self.pool.get_question(qid).category == question.category
        )
        category_bonus = max(0, 3 - category_count) * 10
        score += category_bonus
        
        # Context bonus: related to recent answers
        if self._is_related_to_recent(question):
            score += 20
        
        # Urgency: questions that unblock other questions
        unlocks = self._count_unlocked_questions(question)
        score += unlocks * 15
        
        return score
    
    def _is_related_to_recent(self, question: Question) -> bool:
        """Check if question is related to recently answered questions."""
        # Simple heuristic: shares dependencies with recent answers
        recent = list(self.answered_questions)[-3:]  # Last 3 answered
        
        for recent_id in recent:
            recent_q = self.pool.get_question(recent_id)
            if recent_q and recent_q.target_property:
                # Check if same entity type
                if question.target_property:
                    recent_entity = recent_q.target_property.split('.')[0]
                    this_entity = question.target_property.split('.')[0]
                    if recent_entity == this_entity:
                        return True
        
        return False
    
    def _count_unlocked_questions(self, question: Question) -> int:
        """Count how many questions this unlocks."""
        count = 0
        for q in self.pool.get_all_questions():
            if q.id in self.answered_questions or q.id in self.asked_questions:
                continue
            if question.id in q.requires:
                count += 1
        return count
    
    def _balance_categories(
        self,
        scored: List[Tuple[Question, float]],
        max_questions: int
    ) -> List[Question]:
        """Balance categories to avoid asking too many of one type."""
        result = []
        category_counts = defaultdict(int)
        
        # Dynamic max per category based on total requested
        max_per_category = max(2, max_questions // 3)
        
        for question, score in scored:
            cat = question.category
            if category_counts[cat] < max_per_category:
                result.append(question)
                category_counts[cat] += 1
            
            if len(result) >= max_questions:
                break
        
        return result
    
    def record_answer(self, question_id: str, answer: Any):
        """Record that a question was answered."""
        self.answered_questions.add(question_id)
        self.answer_history[question_id] = answer
        
        # Add follow-up questions to available pool
        question = self.pool.get_question(question_id)
        if question and answer in question.follow_ups:
            # Follow-ups will be available next round
            pass
    
    def record_asked(self, question_id: str):
        """Record that a question was asked (but not yet answered)."""
        self.asked_questions.add(question_id)
    
    def get_follow_up_questions(self, question_id: str, answer: Any) -> List[Question]:
        """Get follow-up questions triggered by a specific answer."""
        question = self.pool.get_question(question_id)
        if not question:
            return []
        
        follow_up_ids = question.follow_ups.get(str(answer), [])
        return [self.pool.get_question(qid) for qid in follow_up_ids if qid]
    
    def get_state(self) -> Dict:
        """Get serializable state."""
        return {
            "answered": list(self.answered_questions),
            "asked": list(self.asked_questions),
            "answers": self.answer_history
        }
    
    def restore_state(self, state: Dict):
        """Restore from serialized state."""
        self.answered_questions = set(state.get("answered", []))
        self.asked_questions = set(state.get("asked", []))
        self.answer_history = state.get("answers", {})


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_entropy_interview() -> EntropyDrivenQuestionGenerator:
    """Create a new entropy-driven interview."""
    return EntropyDrivenQuestionGenerator()


def simulate_entropy_reduction(
    generator: EntropyDrivenQuestionGenerator,
    graph: SpatialGraph,
    priorities: Dict[str, int],
    num_rounds: int = 5
) -> List[Dict]:
    """
    Simulate the interview to see entropy reduction over time.
    
    Returns list of {round, entropy, questions_asked} for analysis.
    """
    history = []
    
    for round_num in range(num_rounds):
        # Calculate current entropy
        uncertainty = calculate_state_entropy(graph, priorities)
        entropy = uncertainty.total_entropy()
        
        # Generate questions
        questions = generator.generate_questions(graph, priorities, max_questions=3)
        
        history.append({
            "round": round_num,
            "entropy": entropy,
            "questions": [q.id for q in questions],
            "categories": [q.category.name for q in questions]
        })
        
        # Simulate answers (in real use, user would answer)
        for q in questions:
            generator.record_answer(q.id, q.default_value)
            
            # Apply to graph (simplified)
            if q.target_property and q.default_value:
                # Would apply fragment here
                pass
    
    return history


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ENTROPY-DRIVEN QUESTION GENERATOR TEST")
    print("=" * 60)
    
    # Create generator
    gen = create_entropy_interview()
    
    # Create empty state
    from room_relationships import SpatialGraph
    graph = SpatialGraph()
    priorities = {
        "natural_light": 5,
        "privacy": 5,
        "open_plan": 5,
        "circulation_efficiency": 5,
        "mep_clustering": 5,
        "structural_simplicity": 5
    }
    
    print("\n--- Round 1: Empty State ---")
    questions = gen.generate_questions(graph, priorities, max_questions=3)
    for q in questions:
        print(f"  [{q.category.name}] {q.text}")
        print(f"      Expected entropy reduction: {q.expected_entropy_reduction}")
        gen.record_asked(q.id)
    
    # Simulate answers
    gen.record_answer("q_building_type", "residential")
    gen.record_answer("q_site_size", "60x120")
    
    print("\n--- Round 2: After Basic Info ---")
    questions = gen.generate_questions(graph, priorities, max_questions=3)
    for q in questions:
        print(f"  [{q.category.name}] {q.text}")
        gen.record_asked(q.id)
    
    # Simulate more answers
    gen.record_answer("q_bedroom_count", 3)
    gen.record_answer("q_garage", "2car")
    
    print("\n--- Round 3: After Room Count ---")
    questions = gen.generate_questions(graph, priorities, max_questions=3)
    for q in questions:
        print(f"  [{q.category.name}] {q.text}")
        gen.record_asked(q.id)
    
    print("\n--- Follow-ups from '3 bedrooms' ---")
    follow_ups = gen.get_follow_up_questions("q_bedroom_count", "3")
    for q in follow_ups:
        if q:
            print(f"  -> {q.text}")
    
    print("\n" + "=" * 60)
    print("ENTROPY SIMULATION")
    print("=" * 60)
    
    # Full simulation
    gen2 = create_entropy_interview()
    history = simulate_entropy_reduction(gen2, graph, priorities, num_rounds=6)
    
    print("\nRound | Entropy | Questions Asked")
    print("-" * 50)
    for h in history:
        print(f"{h['round']:5} | {h['entropy']:7.2f} | {', '.join(h['categories'])}")
