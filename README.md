# OpenReplay AI Studio (Local Edition)

OpenReplay AI Studio is a 100% local, offline, developer-first session replay, execution tracing, and profiling dashboard for LLM applications and AI agents. It runs entirely on your local machine with **zero cloud dependencies, zero data leakage, and zero hosting costs**.

Think of it as **Chrome DevTools + SQLite + cProfile** custom-tuned for AI workflows.

---

## 🚀 Features

1. **Execution Replay Timeline:** Replay agent steps (planner loops, retriever document reads, tool calls, and LLM queries) chronologically with exact parameters.
2. **AI Flame Graphs:** Visualize duration, token usage, and dollar cost proportions across nested steps to spot hotspots instantly.
3. **Prompt Version Diffing:** Compare prompt inputs side-by-side inside the dashboard with inline diff highlighting.
4. **Shareable Replay Files (`.orp`):** Export traces to a single JSON-based `.orp` file (like browser `.har` files) to share with teammates.
5. **No Telemetry, No Accounts:** Everything stays local in an SQLite database.

---

## 📦 Installation

To install and build the package locally:

```bash
# Clone the repository
cd AIReplay

# Install package in editable/development mode
pip install -e .
```

---

## 🛠️ Usage

### 1. Instrument Your Code

Just import `trace` and decorate your agent steps:

```python
from openreplay_ai import trace, init_openreplay

# Initialize (creates local SQLite DB at .openreplay/traces.db)
init_openreplay()

@trace(name="Knowledge Retrieval", type="retriever")
def search_vector_db(query: str):
    return ["retrieved doc content here"]

@trace(name="SQL Tool", type="tool")
def query_database(sql: str):
    return {"status": "ok", "rows": []}

@trace(name="Summarization Call", type="llm", model="gpt-4o")
def call_llm(prompt: str):
    # Returns raw result (openreplay auto-parses token counts and cost for OpenAI completion structures)
    return completion_payload

@trace(name="Agent Planner", type="agent")
def my_agent(user_question: str):
    docs = search_vector_db(user_question)
    db_res = query_database("SELECT * FROM users")
    answer = call_llm(f"Context: {docs}\nDB: {db_res}\nQuery: {user_question}")
    return answer

if __name__ == "__main__":
    my_agent("Analyze latency patterns")
```

Run your code:
```bash
python my_script.py
```

### 2. Launch the Visual Dashboard

Open your browser to view and scrub through traces:

```bash
openreplay open
```
This runs a local FastAPI server and launches your browser to `http://localhost:8000`.

---

## 💻 CLI Command Reference

* `openreplay open [--port PORT] [--host HOST]`: Starts the local DevTools server and opens the browser.
* `openreplay list`: Displays a neat terminal summary table of recent traces.
* `openreplay export <trace-uuid> <output.orp>`: Save a trace to a portable, shareable `.orp` file.
* `openreplay import <file.orp>`: Load an `.orp` file into your local SQLite database.

---

## 🤝 Contributing

We welcome contributions to OpenReplay AI Studio! To modify the React dashboard:

1. Navigate to the dashboard directory:
   ```bash
   cd openreplay_ai/dashboard
   ```
2. Install Node dependencies:
   ```bash
   npm install
   ```
3. Run the Vite development server (access API routes by proxying to port 8000):
   ```bash
   npm run dev
   ```
4. Build the production static assets (compiles assets into `openreplay_ai/dashboard/dist/` for FastAPI distribution):
   ```bash
   npm run build
   ```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
