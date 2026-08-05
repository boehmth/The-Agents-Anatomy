# tools/__init__.py — Registry der Shop-Controller-Tools.

from .base import AgentTool
from .products import ProductsTool
from .filters import FilterByCategoryTool, FilterByPriceTool
from .aggregates import CountTool, SumTool, AverageTool


TOOLS = {
    "getProducts": ProductsTool(),
    "filterByCategory": FilterByCategoryTool(),
    "filterByPrice": FilterByPriceTool(),
    "count": CountTool(),
    "sum": SumTool(),
    "average": AverageTool(),
}

__all__ = [
    "AgentTool",
    "ProductsTool",
    "FilterByCategoryTool",
    "FilterByPriceTool",
    "CountTool",
    "SumTool",
    "AverageTool",
    "TOOLS",
]
