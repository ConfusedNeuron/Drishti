"""Single advice-refusal filter shared by the MCP server and the dashboard copilot route."""
from __future__ import annotations
import re

_TOKENS = (
    r"buy|sell|hold|invest|recommend|purchase|exit|entry|accumulate|liquidate|"
    r"reallocate|rotate|trim|overweight|underweight|allocate|rebalance"
)
_PHRASES = (
    r"go long|go short|should i|good (?:entry|buy|time)|best (?:stock|return)|"
    r"which (?:stock|share|fund)s? (?:to|should|give)"
)
_RE = re.compile(rf"\b(?:{_TOKENS})\b|(?:{_PHRASES})", re.IGNORECASE)


def is_advice_request(text: str) -> bool:
    return bool(_RE.search(text))


REFUSAL = (
    "I'm a risk analytics tool and cannot provide investment advice. "
    "I can explain your portfolio's risk diagnostics instead."
)
