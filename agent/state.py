from typing import TypedDict, List, Optional
from langchain_core.messages import AnyMessage

class AgentState(TypedDict, total=False):
    messages: List[AnyMessage]
    research: Optional[str]
    plan: Optional[str]
    critique: Optional[str]
    poster: Optional[str]
    revision_number: int