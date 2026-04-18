# models.py
from typing import List, Optional
from pydantic import BaseModel

class ActionItem(BaseModel):
    title: str
    assignee: Optional[str] = None
    deadline: Optional[str] = None

class MeetingMetadata(BaseModel):
    topic: Optional[str] = None
    date: Optional[str] = None

class RiskyActionItem(BaseModel):
    title: str
    reason: List[str]

class RepeatedTopic(BaseModel):
    topic: str
    count: int

class Priorities(BaseModel):
    high: List[str]
    medium: List[str]
    low: List[str]

class Workload(BaseModel):
    assignee: str
    task_count: int

class MeetingDecoderOutput(BaseModel):
    meeting_metadata: MeetingMetadata
    decisions: List[str]
    tasks: List[ActionItem]
    ambiguities: List[str]
    risky_action_items: List[RiskyActionItem]
    unassigned_tasks: List[str]
    repeated_topics: List[RepeatedTopic]
    decision_conflicts: List[str]
    open_topics: List[str]
    closed_topics: List[str]
    priorities: Priorities
    workload: List[Workload]
