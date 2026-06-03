from typing import Literal, Optional, List
from pydantic import BaseModel, Field

Intent = Literal[
    "schedule_block",
    "reserve_bandwidth",
    "unblock",
    "pause_internet",
    "query_status",
    "set_priority"
]

Priority = Literal["low", "normal", "high"]

class RouterAction(BaseModel):
    intent: Optional[Intent] = None
    target_device: Optional[str] = None
    target_profile: Optional[str] = None
    service: Optional[str] = None
    domains: List[str] = Field(default_factory=list)
    days: List[str] = Field(default_factory=list)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    bandwidth_mbps: Optional[int] = None
    priority: Optional[Priority] = None
    clarification_needed: bool = False
    questions: List[str] = Field(default_factory=list)