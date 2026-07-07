import time
import uuid
import inspect
import contextvars
from functools import wraps
from typing import Optional, Any, Dict
from openreplay_ai.core.db import DBManager

# Context variables to track nested tracer runs
_current_trace_id = contextvars.ContextVar("openreplay_trace_id", default=None)
_current_step_id = contextvars.ContextVar("openreplay_step_id", default=None)

# Simple pricing map: USD per token (Input, Output)
PRICING_MAP = {
    "gpt-4o": (5.00 / 1e6, 15.00 / 1e6),
    "gpt-4": (30.00 / 1e6, 60.00 / 1e6),
    "gpt-3.5-turbo": (0.50 / 1e6, 1.50 / 1e6),
    "claude-3-5-sonnet": (3.00 / 1e6, 15.00 / 1e6),
    "claude-3-opus": (15.00 / 1e6, 75.00 / 1e6),
    "claude-3-haiku": (0.25 / 1e6, 1.25 / 1e6),
    "gemini-1.5-flash": (0.075 / 1e6, 0.30 / 1e6),
    "gemini-1.5-pro": (1.25 / 1e6, 5.00 / 1e6),
}

def init_openreplay(db_path: Optional[str] = None):
    """Optional configuration to override database directory."""
    if db_path:
        DBManager.set_db_path(db_path)
    DBManager.init_db()

def _parse_completion_usage(output: Any, model: Optional[str] = None):
    """
    Tries to automatically parse tokens and calculate cost from typical 
    completion payloads (OpenAI, Anthropic, Gemini, etc.).
    """
    token_count = 0
    cost = 0.0
    model_name = model or ""

    try:
        # 1. Parse OpenAI / standard responses
        if hasattr(output, "usage") and output.usage:
            usage = output.usage
            prompt_tokens = getattr(usage, "prompt_tokens", 0)
            completion_tokens = getattr(usage, "completion_tokens", 0)
            token_count = getattr(usage, "total_tokens", prompt_tokens + completion_tokens)
            
            # Auto-detect model if not provided
            if not model_name and hasattr(output, "model"):
                model_name = getattr(output, "model", "")
            
            cost = _calculate_cost(model_name, prompt_tokens, completion_tokens)
            return token_count, cost, model_name

        # 2. Parse dictionary responses (e.g. LangChain or direct API call output dict)
        if isinstance(output, dict):
            # Check for usage key
            usage = output.get("usage") or output.get("token_usage")
            if isinstance(usage, dict):
                prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0))
                completion_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0))
                token_count = usage.get("total_tokens", prompt_tokens + completion_tokens)
                if not model_name:
                    model_name = output.get("model", "")
                cost = _calculate_cost(model_name, prompt_tokens, completion_tokens)
                return token_count, cost, model_name
    except Exception:
        pass

    return token_count, cost, model_name

def _calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Matches model name against pricing matrix and returns total cost."""
    if not model:
        return 0.0
    
    # Try fuzzy match
    matched_key = None
    model_lower = model.lower()
    for key in PRICING_MAP:
        if key in model_lower:
            matched_key = key
            break
            
    if matched_key:
        in_cost, out_cost = PRICING_MAP[matched_key]
        return (input_tokens * in_cost) + (output_tokens * out_cost)
    
    return 0.0

def add_metadata(key: str, value: Any):
    """Allows manual updates to metadata for the active step in the trace."""
    step_id = _current_step_id.get()
    if step_id:
        try:
            # We fetch existing, merge, and update. For simplicity, we write directly to the DB.
            conn = DBManager.get_connection()
            cursor = conn.execute("SELECT metadata FROM trace_steps WHERE id = ?", (step_id,))
            row = cursor.fetchone()
            metadata = {}
            if row and row["metadata"]:
                metadata = json.loads(row["metadata"])
            metadata[key] = value
            
            with conn:
                conn.execute(
                    "UPDATE trace_steps SET metadata = ? WHERE id = ?",
                    (json.dumps(metadata), step_id)
                )
        except Exception:
            pass

class trace:
    """
    Decorator and Context Manager to record steps of an AI execution.
    Can be used as:
        @trace(name="my_step", type="llm")
        def my_function(): ...
    Or:
        with trace("my_block", type="tool"): ...
    """
    def __init__(self, name: Optional[str] = None, type: str = "custom", model: Optional[str] = None, metadata: Optional[Dict] = None):
        self.name = name
        self.type = type
        self.model = model
        self.metadata = metadata or {}
        
        self.span_id = str(uuid.uuid4())
        self.start_time = None
        
        # Context tokens for restoring state
        self.token_trace_id = None
        self.token_step_id = None
        self.is_root = False

    def __enter__(self):
        self.start_time = time.time()
        
        # Resolve trace ID (top-level vs nested)
        trace_id = _current_trace_id.get()
        if not trace_id:
            # We are the root!
            trace_id = str(uuid.uuid4())
            self.token_trace_id = _current_trace_id.set(trace_id)
            self.is_root = True
            
            # Set trace name to step name if not specified
            trace_name = self.name or "Unnamed Trace"
            DBManager.create_trace(trace_id, name=trace_name, metadata=self.metadata)
        
        parent_step_id = _current_step_id.get()
        self.token_step_id = _current_step_id.set(self.span_id)
        
        # Assign name automatically from type if missing
        step_name = self.name or f"step_{self.type}"
        
        # Save start of step in SQLite
        DBManager.upsert_step(
            step_id=self.span_id,
            trace_id=_current_trace_id.get(),
            parent_step_id=parent_step_id,
            name=step_name,
            type=self.type,
            start_time=self.start_time,
            status="running",
            model_used=self.model,
            metadata=self.metadata
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.time()
        latency = end_time - self.start_time
        
        status = "success"
        error_details = None
        if exc_type:
            status = "error"
            import traceback
            error_details = {
                "error": str(exc_val),
                "type": exc_type.__name__,
                "traceback": "".join(traceback.format_tb(exc_tb))
            }
            
        trace_id = _current_trace_id.get()
        
        # Finalize step details in SQLite
        DBManager.upsert_step(
            step_id=self.span_id,
            trace_id=trace_id,
            parent_step_id=None, # DB handles updates without needing this
            name=self.name or f"step_{self.type}",
            type=self.type,
            start_time=self.start_time,
            end_time=end_time,
            latency=latency,
            status=status,
            error_details=error_details,
            model_used=self.model,
            metadata=self.metadata
        )
        
        # Restore contextvar states
        if self.token_step_id:
            _current_step_id.reset(self.token_step_id)
            
        if self.is_root:
            # We are completing the root execution! Let's aggregate trace totals.
            self._finalize_trace(trace_id, status, latency)
            if self.token_trace_id:
                _current_trace_id.reset(self.token_trace_id)

    def _finalize_trace(self, trace_id: str, status: str, total_latency: float):
        """Aggregates latency, costs, and token usages for the entire trace."""
        try:
            conn = DBManager.get_connection()
            # Fetch all completed steps for this trace
            cursor = conn.execute(
                "SELECT SUM(token_count) as total_tokens, SUM(cost) as total_cost FROM trace_steps WHERE trace_id = ?",
                (trace_id,)
            )
            row = cursor.fetchone()
            total_tokens = row["total_tokens"] or 0
            total_cost = row["total_cost"] or 0.0
            
            DBManager.update_trace(
                trace_id=trace_id,
                status=status,
                total_latency=total_latency,
                total_tokens=total_tokens,
                total_cost=total_cost
            )
        except Exception:
            pass

    def __call__(self, func):
        # Infer function name if span name not defined
        if not self.name:
            self.name = func.__name__

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                with self:
                    # Log inputs
                    inputs = self._serialize_args(args, kwargs)
                    DBManager.upsert_step(
                        step_id=self.span_id,
                        trace_id=_current_trace_id.get(),
                        parent_step_id=None,
                        name=self.name,
                        type=self.type,
                        start_time=self.start_time,
                        inputs=inputs,
                        model_used=self.model
                    )
                    
                    output = await func(*args, **kwargs)
                    
                    # Log output, parse tokens
                    self._process_output(output)
                    return output
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                with self:
                    # Log inputs
                    inputs = self._serialize_args(args, kwargs)
                    DBManager.upsert_step(
                        step_id=self.span_id,
                        trace_id=_current_trace_id.get(),
                        parent_step_id=None,
                        name=self.name,
                        type=self.type,
                        start_time=self.start_time,
                        inputs=inputs,
                        model_used=self.model
                    )
                    
                    output = func(*args, **kwargs)
                    
                    # Log output, parse tokens
                    self._process_output(output)
                    return output
            return sync_wrapper

    def _serialize_args(self, args, kwargs) -> Dict[str, Any]:
        """Converts function args into a JSON-serializable dictionary."""
        inputs = {}
        if args:
            inputs["args"] = [str(a) for a in args]
        if kwargs:
            inputs["kwargs"] = {k: (str(v) if not isinstance(v, (int, float, bool, dict, list)) else v) for k, v in kwargs.items()}
        return inputs

    def _process_output(self, output: Any):
        """Serializes output and checks if token/cost metrics are present."""
        tokens, cost, matched_model = _parse_completion_usage(output, self.model)
        
        # Serialize output
        serialized_output = None
        if isinstance(output, (str, int, float, bool, dict, list)):
            serialized_output = output
        else:
            serialized_output = str(output)
            
        DBManager.upsert_step(
            step_id=self.span_id,
            trace_id=_current_trace_id.get(),
            parent_step_id=None,
            name=self.name,
            type=self.type,
            start_time=self.start_time,
            outputs=serialized_output,
            token_count=tokens,
            cost=cost,
            model_used=matched_model or self.model
        )
