"""LegiQBD - Conversational Building Design Interface.

The first interface to the Legible Studio system. LegiQBD provides
a natural language conversation for designing homes:

User: "I need a 3 bedroom house with an open kitchen"
LegiQBD: [Applies fragments to QBD, generates follow-up questions]
LegiQBD: "Great! How many bathrooms do you need?"

Architecture:
    User Input
        ↓
    Intent Classification (LLM)
        ↓
    Fragment Emission (LLM → JSON fragments)
        ↓
    QBD Algebra (validation, derivation, solving)
        ↓
    Response Generation (LLM → natural language)
        ↓
    User Output

Quick Start:
    from legiqbd import ConversationEngine, Session

    # Create engine
    engine = ConversationEngine()

    # Start conversation
    response = engine.start_conversation()
    print(response.text)

    # Process user input
    response = engine.process_input("3 bedroom 2 bath house")
    print(response.text)

    # Check if solvable
    if response.is_solvable:
        success, result = engine.solve()
        if success:
            print(f"Solved! Score: {result['score']}")

CLI Usage:
    python -m legiqbd.cli

    Or:
    python -c "from legiqbd.cli import main; main()"
"""

from .session import Session, SessionConfig, SessionPhase, Message
from .engine import ConversationEngine, EngineResponse, IntentResult
from .formatter import ResponseFormatter, OutputFormat, format_response, format_design
from .visualizer import ASCIIVisualizer, render_layout, render_rooms, quick_preview

__all__ = [
    # Session
    "Session",
    "SessionConfig",
    "SessionPhase",
    "Message",

    # Engine
    "ConversationEngine",
    "EngineResponse",
    "IntentResult",

    # Formatter
    "ResponseFormatter",
    "OutputFormat",
    "format_response",
    "format_design",

    # Visualizer
    "ASCIIVisualizer",
    "render_layout",
    "render_rooms",
    "quick_preview",
]


def start_session(provider: str = None) -> ConversationEngine:
    """Convenience function to start a new session.

    Args:
        provider: Optional LLM provider name ("lmstudio", "openai", etc)

    Returns:
        ConversationEngine ready to use
    """
    if provider:
        from llm import LLMConfig
        LLMConfig.set_active(provider)

    return ConversationEngine()


def chat(message: str, engine: ConversationEngine = None) -> str:
    """Simple one-shot chat interface.

    Args:
        message: User message
        engine: Optional existing engine (creates new if None)

    Returns:
        Response text
    """
    if engine is None:
        engine = start_session()
        engine.start_conversation()

    response = engine.process_input(message)
    return response.text
