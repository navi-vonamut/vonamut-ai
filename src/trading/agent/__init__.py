"""
Trading Agent Core Module (LangGraph + Gemini / Gemma).
"""

from src.trading.agent.config import agent_config, AgentConfig
from src.trading.agent.state import TradingAgentState, TradingDecisionSchema
from src.trading.agent.technical_analysis import TechnicalAnalyzer
from src.trading.agent.localization import LocalizationManager, get_localization_manager
from src.trading.agent.graph import create_trading_agent_graph, run_trading_agent_analysis

__all__ = [
    "agent_config",
    "AgentConfig",
    "TradingAgentState",
    "TradingDecisionSchema",
    "TechnicalAnalyzer",
    "LocalizationManager",
    "get_localization_manager",
    "create_trading_agent_graph",
    "run_trading_agent_analysis",
]
