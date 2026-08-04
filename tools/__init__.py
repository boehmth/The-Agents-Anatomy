# tools/__init__.py — Registry und Konstanten.

from .base import AgentTool
from .prices import PriceTool, TICKERS
from .calculator import CalculatorTool
from .portfolio import PortfolioTool, PORTFOLIO_FILE, TRADES_FILE


TOOLS = {
    "get_prices": PriceTool(),
    "calculator": CalculatorTool(),
    "portfolio": PortfolioTool(),
}

__all__ = [
    "AgentTool",
    "PriceTool",
    "CalculatorTool",
    "PortfolioTool",
    "TOOLS",
    "TICKERS",
    "PORTFOLIO_FILE",
    "TRADES_FILE",
]
