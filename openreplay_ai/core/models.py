from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class TraceStepResponse(BaseModel):
    id: str
    trace_id: str
    parent_step_id: Optional[str] = None
    name: str
    type: str
    start_time: str
    end_time: Optional[str] = None
    latency: Optional[float] = None
    status: str
    inputs: Optional[Any] = None
    outputs: Optional[Any] = None
    token_count: int = 0
    cost: float = 0.0
    model_used: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = {}

class TraceResponse(BaseModel):
    id: str
    name: str
    status: str
    total_latency: Optional[float] = None
    total_tokens: int = 0
    total_cost: float = 0.0
    metadata: Dict[str, Any] = {}
    created_at: str

class TraceTreeResponse(TraceResponse):
    steps: List[TraceStepResponse] = []

class PromptDiffRequest(BaseModel):
    prompt_v1: str
    prompt_v2: str

class SimulationRequest(BaseModel):
    step_id: str
    model: Optional[str] = None
    prompt_override: Optional[str] = None
    inputs_override: Optional[Dict[str, Any]] = None
