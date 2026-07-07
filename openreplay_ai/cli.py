import sys
import os
import json
import argparse
import uvicorn
import webbrowser
from openreplay_ai.core.db import DBManager

def list_traces():
    try:
        traces = DBManager.get_all_traces()
        if not traces:
            print("No traces found in local SQLite database.")
            return
        
        print("\n--- Recent OpenReplay AI Traces ---")
        print(f"{'Trace ID':<38} | {'Name':<25} | {'Status':<10} | {'Latency':<8} | {'Cost':<8} | {'Tokens':<6}")
        print("-" * 105)
        for t in traces[:15]: # Show top 15
            tid = t.get("id", "")
            name = t.get("name", "")[:25]
            status = t.get("status", "")
            latency = f"{t.get('total_latency', 0.0):.2f}s" if t.get('total_latency') is not None else "N/A"
            cost = f"${t.get('total_cost', 0.0):.4f}"
            tokens = str(t.get("total_tokens", 0))
            
            print(f"{tid:<38} | {name:<25} | {status:<10} | {latency:<8} | {cost:<8} | {tokens:<6}")
        print(f"Total: {len(traces)} traces recorded.\n")
    except Exception as e:
        print(f"Error fetching traces: {e}")

def export_trace(trace_id: str, output_path: str):
    try:
        trace_data = DBManager.get_trace_tree(trace_id)
        if not trace_data:
            print(f"Error: Trace with ID {trace_id} not found.")
            return
            
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(trace_data, f, indent=2)
            
        print(f"Successfully exported trace {trace_id} to {output_path}")
    except Exception as e:
        print(f"Error exporting trace: {e}")

def import_trace(file_path: str):
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist.")
        return
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        trace_id = data.get("id")
        name = data.get("name")
        status = data.get("status")
        total_latency = data.get("total_latency")
        total_tokens = data.get("total_tokens", 0)
        total_cost = data.get("total_cost", 0.0)
        metadata = data.get("metadata", {})
        
        if not trace_id or not name:
            print("Error: Invalid .orp trace format (missing trace_id or name).")
            return
            
        # 1. Insert/update trace record
        DBManager.init_db()
        with DBManager.get_connection() as conn:
            # Check if trace already exists
            cursor = conn.execute("SELECT 1 FROM traces WHERE id = ?", (trace_id,))
            if cursor.fetchone():
                print(f"Trace {trace_id} already exists in database. Overwriting...")
                conn.execute("DELETE FROM trace_steps WHERE trace_id = ?", (trace_id,))
                conn.execute("DELETE FROM traces WHERE id = ?", (trace_id,))
                
            # Create trace
            conn.execute(
                "INSERT INTO traces (id, name, status, total_latency, total_tokens, total_cost, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (trace_id, name, status, total_latency, total_tokens, total_cost, json.dumps(metadata), data.get("created_at", "N/A"))
            )
            
            # 2. Insert trace steps
            steps = data.get("steps", [])
            for step in steps:
                conn.execute("""
                    INSERT INTO trace_steps (
                        id, trace_id, parent_step_id, name, type, start_time, end_time, latency, status,
                        inputs, outputs, token_count, cost, model_used, error_details, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    step.get("id"), trace_id, step.get("parent_step_id"), step.get("name"), step.get("type"),
                    step.get("start_time"), step.get("end_time"), step.get("latency"), step.get("status"),
                    json.dumps(step.get("inputs")) if step.get("inputs") else None,
                    json.dumps(step.get("outputs")) if step.get("outputs") else None,
                    step.get("token_count", 0), step.get("cost", 0.0), step.get("model_used"),
                    json.dumps(step.get("error_details")) if step.get("error_details") else None,
                    json.dumps(step.get("metadata", {}))
                ))
            conn.commit()
            
        print(f"Successfully imported trace '{name}' ({trace_id}) into your local database.")
    except Exception as e:
        print(f"Error importing trace: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="OpenReplay AI Studio - Local trace observer & replay CLI"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # openreplay open [--port PORT] [--host HOST]
    open_parser = subparsers.add_parser("open", help="Launch the local replay dashboard in your browser")
    open_parser.add_argument("--port", type=int, default=8000, help="Port to run the dashboard on (default: 8000)")
    open_parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    
    # openreplay list
    subparsers.add_parser("list", help="List recent recorded traces in the terminal")
    
    # openreplay export <trace-id> <file.orp>
    export_parser = subparsers.add_parser("export", help="Export a trace to a shareable .orp file")
    export_parser.add_argument("trace_id", type=str, help="UUID of the trace to export")
    export_parser.add_argument("output_file", type=str, help="Output file path (e.g. run.orp)")
    
    # openreplay import <file.orp>
    import_parser = subparsers.add_parser("import", help="Import an exported .orp trace file into local database")
    import_parser.add_argument("file_path", type=str, help="Path to the .orp file to import")
    
    args = parser.parse_args()
    
    if args.command == "open":
        url = f"http://{args.host}:{args.port}"
        print(f"Launching OpenReplay AI Studio dashboard...")
        print(f"Server starting on {url} (Ctrl+C to quit)")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        uvicorn.run("openreplay_ai.server:app", host=args.host, port=args.port, reload=False, log_level="info")
        
    elif args.command == "list":
        list_traces()
        
    elif args.command == "export":
        export_trace(args.trace_id, args.output_file)
        
    elif args.command == "import":
        import_trace(args.file_path)
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
