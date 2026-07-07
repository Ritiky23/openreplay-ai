import time
import random
from openreplay_ai import trace, init_openreplay

# Initialize OpenReplay to local SQLite DB
init_openreplay()

# Mock class representing an OpenAI-like ChatCompletion object
class MockChatCompletion:
    def __init__(self, content: str, model: str, prompt_tokens: int, completion_tokens: int):
        self.choices = [MockChoice(content)]
        self.model = model
        self.usage = MockUsage(prompt_tokens, completion_tokens)

class MockChoice:
    def __init__(self, content: str):
        self.message = MockMessage(content)

class MockMessage:
    def __init__(self, content: str):
        self.content = content

class MockUsage:
    def __init__(self, prompt_tokens: int, completion_tokens: int):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens


@trace(name="Semantic Vector Search", type="retriever")
def search_vector_db(query: str):
    time.sleep(0.15) # Mock DB search latency
    return [
        {"doc_id": 1, "title": "Redis configuration guidelines", "content": "Set redis timeout limits to 20ms under high loads."},
        {"doc_id": 2, "title": "Latency troubleshooting", "content": "Check active connection count and slow log outputs."}
    ]

@trace(name="Redis Log Checker", type="tool")
def check_redis_logs():
    time.sleep(0.05) # Mock tool latency
    # Simulate database retrieval or log parsing
    return {
        "status": "warning",
        "slow_queries": 4,
        "average_read_latency_ms": 25.4,
        "max_latency_ms": 120.0
    }

@trace(name="OpenAI Chat API Call", type="llm", model="gpt-4o")
def call_llm(system_prompt: str, user_prompt: str):
    time.sleep(1.2) # Mock LLM API call latency
    
    # Return a simulated completion object with token usage details
    # This matches the structure that openreplay_ai parses automatically
    return MockChatCompletion(
        content="Based on retrieval, Redis average latency is 25.4ms with queries spiking to 120ms. This exceeds the 20ms configuration guideline.",
        model="gpt-4o",
        prompt_tokens=420,
        completion_tokens=85
    )

@trace(name="Planner Agent Executor", type="agent")
def run_agent(question: str):
    print(f"Agent received question: {question}")
    
    # 1. Search vector DB for context
    print("Executing Vector DB search...")
    context = search_vector_db(question)
    
    # 2. Check logs using Redis tool
    print("Checking Redis database logs...")
    redis_metrics = check_redis_logs()
    
    # 3. Call LLM to summarize findings
    print("Formulating prompt and invoking LLM...")
    prompt_context = f"Vector context: {context}\nRedis status: {redis_metrics}"
    system = "You are a senior reliability engineer diagnosing database bottlenecks."
    
    response = call_llm(system, prompt_context)
    
    print("Agent execution completed.")
    return response.choices[0].message.content

if __name__ == "__main__":
    print("--- Starting Agent Run ---")
    answer = run_agent("Why is Redis latency spiking and what was the query latency?")
    print(f"Final Answer: {answer}")
    print("--- Trace Recorded Locally in .openreplay/traces.db ---")
