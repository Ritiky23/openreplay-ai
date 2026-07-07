import React, { useState, useEffect } from 'react';
import { 
  Brain, Search, Cpu, Database, Play, Clock, 
  DollarSign, RefreshCw, Layers, FileCode, 
  CheckCircle, XCircle, AlertTriangle, ArrowRight, 
  Upload, Download, Copy, Split, ChevronRight, LayoutGrid
} from 'lucide-react';

const API_BASE = ""; // Hits local FastAPI server directly (proxied or relative)

function App() {
  const [traces, setTraces] = useState([]);
  const [selectedTraceId, setSelectedTraceId] = useState(null);
  const [selectedTrace, setSelectedTrace] = useState(null);
  const [selectedStep, setSelectedStep] = useState(null);
  const [activeTab, setActiveTab] = useState('timeline'); // timeline, flamegraph, promptdiff
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Prompt Diff states
  const [promptV1, setPromptV1] = useState('');
  const [promptV2, setPromptV2] = useState('');
  const [diffResults, setDiffResults] = useState([]);
  const [diffLoading, setDiffLoading] = useState(false);

  // Flame graph states
  const [flameMetric, setFlameMetric] = useState('latency'); // latency, tokens, cost

  // Fetch traces on mount
  useEffect(() => {
    fetchTraces();
  }, []);

  // Fetch trace details when selected
  useEffect(() => {
    if (selectedTraceId) {
      fetchTraceDetails(selectedTraceId);
    }
  }, [selectedTraceId]);

  const fetchTraces = async () => {
    setRefreshing(true);
    try {
      const res = await fetch(`${API_BASE}/api/traces`);
      if (res.ok) {
        const data = await res.json();
        setTraces(data);
        if (data.length > 0 && !selectedTraceId) {
          setSelectedTraceId(data[0].id);
        }
      }
    } catch (err) {
      console.error("Failed to fetch traces", err);
    } finally {
      setRefreshing(false);
    }
  };

  const fetchTraceDetails = async (id) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/traces/${id}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedTrace(data);
        // Default select the root step or first step
        if (data.steps && data.steps.length > 0) {
          // Find root step (parent_step_id is null or empty)
          const rootStep = data.steps.find(s => !s.parent_step_id) || data.steps[0];
          setSelectedStep(rootStep);
          
          // Auto populate prompt diff fields if LLM prompt exists
          const llmStep = data.steps.find(s => s.type === 'llm');
          if (llmStep && llmStep.inputs) {
            const promptStr = typeof llmStep.inputs === 'object' 
              ? JSON.stringify(llmStep.inputs, null, 2) 
              : String(llmStep.inputs);
            setPromptV1(promptStr);
            setPromptV2(promptStr + "\n# Modify this prompt to check the diff");
          }
        } else {
          setSelectedStep(null);
        }
      }
    } catch (err) {
      console.error("Failed to fetch trace details", err);
    } finally {
      setLoading(false);
    }
  };

  const handleComparePrompts = async () => {
    setDiffLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/prompt-diff`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt_v1: promptV1, prompt_v2: promptV2 })
      });
      if (res.ok) {
        const data = await res.json();
        setDiffResults(data.diff || []);
      }
    } catch (err) {
      console.error("Failed to compare prompts", err);
    } finally {
      setDiffLoading(false);
    }
  };

  const handleExportTrace = () => {
    if (!selectedTrace) return;
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(selectedTrace, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `trace_${selectedTrace.id}.orp`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handleImportTrace = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (event) => {
      try {
        const parsed = JSON.parse(event.target.result);
        
        // Post the trace structure to the import database endpoint on local server
        const res = await fetch(`${API_BASE}/api/traces/import`, {
          method: 'POST', // CLI route parses .orp, but let's provide a direct upload helper to server
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(parsed)
        });
        
        // In local edition, we can also simulate it or load it directly in the React state!
        // To be safe and zero-dependency, let's load it directly into React state for viewing.
        setSelectedTrace(parsed);
        setSelectedTraceId(parsed.id);
        if (parsed.steps && parsed.steps.length > 0) {
          setSelectedStep(parsed.steps[0]);
        }
        alert("Trace loaded in-memory successfully!");
      } catch (err) {
        alert("Failed to parse file: " + err.message);
      }
    };
    reader.readAsText(file);
  };

  const getStepTypeIcon = (type) => {
    switch (type) {
      case 'llm': return <Brain size={16} className="text-cyan-400" style={{ color: '#22D3EE' }} />;
      case 'tool': return <Cpu size={16} className="text-amber-400" style={{ color: '#FBBF24' }} />;
      case 'retriever': return <Search size={16} className="text-purple-400" style={{ color: '#C084FC' }} />;
      case 'agent': return <Layers size={16} className="text-blue-400" style={{ color: '#60A5FA' }} />;
      default: return <Database size={16} className="text-slate-400" style={{ color: '#94A3B8' }} />;
    }
  };

  // Filter traces based on search
  const filteredTraces = traces.filter(t => 
    t.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
    t.id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Compute stats for selected trace
  const traceStats = () => {
    if (!selectedTrace) return { latency: 0, cost: 0, tokens: 0, stepsCount: 0 };
    return {
      latency: selectedTrace.total_latency || 0,
      cost: selectedTrace.total_cost || 0.0,
      tokens: selectedTrace.total_tokens || 0,
      stepsCount: selectedTrace.steps ? selectedTrace.steps.length : 0
    };
  };

  const stats = traceStats();

  // Helper to build flame graph tiers
  const buildFlamegraphRows = () => {
    if (!selectedTrace || !selectedTrace.steps || selectedTrace.steps.length === 0) return [];
    
    // Sort steps by start time
    const sorted = [...selectedTrace.steps].sort((a, b) => 
      new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
    );

    // Build parent-child mapping & calculate depths
    const stepMap = {};
    sorted.forEach(s => {
      stepMap[s.id] = { ...s, children: [] };
    });

    const roots = [];
    sorted.forEach(s => {
      if (s.parent_step_id && stepMap[s.parent_step_id]) {
        stepMap[s.parent_step_id].children.push(stepMap[s.id]);
      } else {
        roots.push(stepMap[s.id]);
      }
    });

    const rows = [];
    const traverse = (nodes, depth) => {
      if (nodes.length === 0) return;
      if (!rows[depth]) rows[depth] = [];
      
      nodes.forEach(node => {
        rows[depth].push(node);
        traverse(node.children, depth + 1);
      });
    };

    traverse(roots, 0);
    return rows;
  };

  const flameRows = buildFlamegraphRows();

  // Render pretty JSON or string
  const formatCodeValue = (val) => {
    if (val === null || val === undefined) return "None";
    if (typeof val === 'object') {
      return JSON.stringify(val, null, 2);
    }
    return String(val);
  };

  return (
    <div className="dashboard-container">
      {/* 1. Left Sidebar - Trace List */}
      <div className="sidebar">
        <div className="sidebar-header">
          <div className="logo-container">
            <span className="logo-text">OpenReplay AI</span>
            <span className="logo-badge">Studio</span>
          </div>
          
          <div className="search-box">
            <Search className="search-icon" size={14} />
            <input 
              type="text" 
              placeholder="Search traces..." 
              className="search-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        <div className="trace-list">
          {refreshing && <div className="text-center py-4 text-xs text-slate-500">Refreshing list...</div>}
          {!refreshing && filteredTraces.length === 0 && (
            <div className="text-center py-8 text-sm text-slate-500">No traces recorded yet.</div>
          )}
          {filteredTraces.map((t) => (
            <div 
              key={t.id} 
              className={`trace-item ${selectedTraceId === t.id ? 'active' : ''}`}
              onClick={() => setSelectedTraceId(t.id)}
            >
              <div className="trace-item-header">
                <span className="trace-item-name">{t.name}</span>
                <span className={`badge ${t.status === 'success' ? 'badge-success' : t.status === 'error' ? 'badge-error' : 'badge-running'}`}>
                  {t.status}
                </span>
              </div>
              <div className="trace-item-meta">
                <span>{t.total_latency ? `${t.total_latency.toFixed(2)}s` : 'N/A'}</span>
                <span>•</span>
                <span>{t.total_tokens} tokens</span>
                <span>•</span>
                <span style={{ color: '#10B981' }}>${t.total_cost.toFixed(4)}</span>
              </div>
              <div className="trace-item-time" style={{ marginTop: '0.25rem' }}>
                {new Date(t.created_at).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
        
        {/* Refresh button at bottom of list */}
        <div style={{ padding: '0.75rem', borderTop: '1px solid #1E293B' }}>
          <button className="btn" style={{ width: '100%', justifyContent: 'center' }} onClick={fetchTraces}>
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            Sync Recent Traces
          </button>
        </div>
      </div>

      {/* 2. Main Workspace Viewport */}
      <div className="main-viewport">
        {/* Header */}
        <div className="main-header">
          <div className="header-title-section">
            <span className="header-title">
              {selectedTrace ? selectedTrace.name : "Select a Trace"}
            </span>
          </div>

          <div className="tab-nav">
            <button 
              className={`tab-btn ${activeTab === 'timeline' ? 'active' : ''}`}
              onClick={() => setActiveTab('timeline')}
            >
              <Clock size={14} />
              Replay Timeline
            </button>
            <button 
              className={`tab-btn ${activeTab === 'flamegraph' ? 'active' : ''}`}
              onClick={() => setActiveTab('flamegraph')}
            >
              <Layers size={14} />
              Flame Graph
            </button>
            <button 
              className={`tab-btn ${activeTab === 'promptdiff' ? 'active' : ''}`}
              onClick={() => setActiveTab('promptdiff')}
            >
              <Split size={14} />
              Prompt Diff
            </button>
          </div>

          <div className="actions-section">
            <button className="btn" onClick={handleExportTrace} disabled={!selectedTrace}>
              <Download size={14} />
              Export .orp
            </button>
            <label className="btn" style={{ cursor: 'pointer' }}>
              <Upload size={14} />
              Import
              <input type="file" accept=".orp" onChange={handleImportTrace} style={{ display: 'none' }} />
            </label>
          </div>
        </div>

        {/* Trace Level Summary Stats */}
        {selectedTrace && (
          <div className="summary-cards-container">
            <div className="summary-card">
              <div className="card-icon-box card-icon-blue">
                <Clock size={20} />
              </div>
              <div className="card-content">
                <span className="card-label">Total Latency</span>
                <span className="card-value">{stats.latency.toFixed(2)}s</span>
              </div>
            </div>
            
            <div className="summary-card">
              <div className="card-icon-box card-icon-yellow">
                <DollarSign size={20} />
              </div>
              <div className="card-content">
                <span className="card-label">Run Cost</span>
                <span className="card-value">${stats.cost.toFixed(5)}</span>
              </div>
            </div>

            <div className="summary-card">
              <div className="card-icon-box card-icon-purple">
                <Brain size={20} />
              </div>
              <div className="card-content">
                <span className="card-label">Total Tokens</span>
                <span className="card-value">{stats.tokens.toLocaleString()}</span>
              </div>
            </div>

            <div className="summary-card">
              <div className="card-icon-box card-icon-green">
                <LayoutGrid size={20} />
              </div>
              <div className="card-content">
                <span className="card-label">Span Nodes</span>
                <span className="card-value">{stats.stepsCount} steps</span>
              </div>
            </div>
          </div>
        )}

        {/* Content Tabs */}
        <div className="content-area">
          {!selectedTrace ? (
            <div className="empty-state">
              <span className="empty-title">Select or import a trace to begin replay inspection.</span>
            </div>
          ) : loading ? (
            <div className="empty-state">
              <span className="empty-title">Loading execution details...</span>
            </div>
          ) : (
            <>
              {/* Timeline Pane */}
              {activeTab === 'timeline' && (
                <div className="tab-pane timeline-pane">
                  <div className="timeline-flow">
                    {selectedTrace.steps && selectedTrace.steps.map((step) => {
                      const isSelected = selectedStep && selectedStep.id === step.id;
                      return (
                        <div 
                          key={step.id}
                          className={`timeline-node ${isSelected ? 'selected' : ''}`}
                          onClick={() => setSelectedStep(step)}
                          style={{ paddingLeft: '8px' }}
                        >
                          <div className={`node-border-bar bar-${step.type}`}></div>
                          
                          <div className="timeline-node-header">
                            <div className="node-title-group">
                              {getStepTypeIcon(step.type)}
                              <span className="node-name">{step.name}</span>
                              <span className="logo-badge" style={{ fontSize: '0.55rem', opacity: 0.7 }}>{step.type}</span>
                            </div>
                            
                            <div className="node-meta-group">
                              {step.model_used && (
                                <span style={{ color: '#38BDF8', fontSize: '0.75rem', fontFamily: 'monospace' }}>
                                  {step.model_used}
                                </span>
                              )}
                              {step.token_count > 0 && (
                                <span style={{ color: '#C084FC' }}>
                                  {step.token_count} t
                                </span>
                              )}
                              {step.cost > 0 && (
                                <span style={{ color: '#34D399' }}>
                                  ${step.cost.toFixed(4)}
                                </span>
                              )}
                              <span className="node-latency">
                                {step.latency ? `${step.latency.toFixed(2)}s` : 'N/A'}
                              </span>
                              <span>
                                {step.status === 'success' ? (
                                  <CheckCircle size={14} style={{ color: '#10B981' }} />
                                ) : (
                                  <XCircle size={14} style={{ color: '#EF4444' }} />
                                )}
                              </span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Sidebar Inspector Panel */}
                  <div className="inspector-panel">
                    <div className="inspector-header">
                      <span className="inspector-title">Span Inspector</span>
                      {selectedStep && (
                        <span className="logo-badge">{selectedStep.type}</span>
                      )}
                    </div>
                    
                    {selectedStep ? (
                      <div className="inspector-body">
                        <div>
                          <span style={{ fontSize: '0.7rem', color: '#64748B', fontWeight: 700, textTransform: 'uppercase' }}>Node Name</span>
                          <div style={{ fontSize: '1rem', fontWeight: 700, color: '#F8FAFC', marginTop: '0.15rem' }}>{selectedStep.name}</div>
                        </div>

                        {selectedStep.model_used && (
                          <div>
                            <span style={{ fontSize: '0.7rem', color: '#64748B', fontWeight: 700, textTransform: 'uppercase' }}>Model</span>
                            <div style={{ fontFamily: 'monospace', color: '#38BDF8', marginTop: '0.15rem' }}>{selectedStep.model_used}</div>
                          </div>
                        )}

                        {/* Input Box */}
                        <div>
                          <div className="code-block-header">Input Parameters</div>
                          <pre className="code-preview">
                            {formatCodeValue(selectedStep.inputs)}
                          </pre>
                        </div>

                        {/* Output Box */}
                        <div>
                          <div className="code-block-header">Execution Result / Output</div>
                          <pre className="code-preview" style={{ color: selectedStep.status === 'success' ? '#34D399' : '#F87171' }}>
                            {formatCodeValue(selectedStep.outputs)}
                          </pre>
                        </div>

                        {/* Error stack trace details if failed */}
                        {selectedStep.status === 'error' && selectedStep.error_details && (
                          <div>
                            <div className="code-block-header" style={{ color: '#EF4444' }}>Stack Error Details</div>
                            <pre className="code-preview" style={{ color: '#F87171', borderColor: 'rgba(239, 68, 68, 0.4)' }}>
                              {formatCodeValue(selectedStep.error_details)}
                            </pre>
                          </div>
                        )}

                        {/* Metadata Details */}
                        {selectedStep.metadata && Object.keys(selectedStep.metadata).length > 0 && (
                          <div>
                            <div className="code-block-header">Metadata</div>
                            <pre className="code-preview">
                              {formatCodeValue(selectedStep.metadata)}
                            </pre>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="empty-state">
                        <span className="empty-title">Select a step to inspect payload context.</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Flamegraph Pane */}
              {activeTab === 'flamegraph' && (
                <div className="tab-pane flamegraph-pane">
                  <div className="flamegraph-header">
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontSize: '1rem', fontWeight: 700, color: '#F8FAFC' }}>Trace Execution Flame Graph</span>
                      <span style={{ fontSize: '0.75rem', color: '#64748B' }}>Hover blocks to check execution attributes. Click to inspect step.</span>
                    </div>

                    <div className="tab-nav">
                      <button 
                        className={`tab-btn ${flameMetric === 'latency' ? 'active' : ''}`}
                        onClick={() => setFlameMetric('latency')}
                      >
                        Time Latency
                      </button>
                      <button 
                        className={`tab-btn ${flameMetric === 'tokens' ? 'active' : ''}`}
                        onClick={() => setFlameMetric('tokens')}
                      >
                        Tokens
                      </button>
                      <button 
                        className={`tab-btn ${flameMetric === 'cost' ? 'active' : ''}`}
                        onClick={() => setFlameMetric('cost')}
                      >
                        Cost
                      </button>
                    </div>
                  </div>

                  <div className="flamegraph-chart-box">
                    {flameRows.map((row, rIdx) => (
                      <div key={rIdx} className="flamegraph-row">
                        {row.map((step) => {
                          let widthPct = 0;
                          let leftPct = 0;

                          const traceStartTime = new Date(selectedTrace.created_at).getTime(); // Fallback baseline
                          const totalTraceLatency = selectedTrace.total_latency || 1.0;

                          if (flameMetric === 'latency') {
                            // Calculate width proportional to latency
                            widthPct = ((step.latency || 0.01) / totalTraceLatency) * 100;
                            
                            // Estimate horizontal offset from start time
                            const stepStartTime = new Date(step.start_time).getTime();
                            const firstStepStartTime = new Date(selectedTrace.steps[0].start_time).getTime();
                            const delta = (stepStartTime - firstStepStartTime) / 1000; // in seconds
                            leftPct = (delta / totalTraceLatency) * 100;
                          } else if (flameMetric === 'tokens') {
                            // Proportional token sizes
                            const totalTokens = selectedTrace.total_tokens || 1;
                            widthPct = ((step.token_count || 0) / totalTokens) * 100;
                            // Sequential layout within row
                            leftPct = 0; // Simple layout fallback for tokens
                          } else {
                            // Proportional cost sizes
                            const totalCost = selectedTrace.total_cost || 0.0001;
                            widthPct = ((step.cost || 0) / totalCost) * 100;
                            leftPct = 0;
                          }

                          // Bound dimensions
                          widthPct = Math.max(widthPct, 2); // Minimum 2% visibility
                          if (leftPct + widthPct > 100) {
                            widthPct = 100 - leftPct;
                          }

                          return (
                            <div
                              key={step.id}
                              className={`flamegraph-block block-${step.type}`}
                              style={{ 
                                left: `${leftPct}%`, 
                                width: `${widthPct}%`,
                                position: 'absolute'
                              }}
                              onClick={() => {
                                setSelectedStep(step);
                                setActiveTab('timeline');
                              }}
                              title={`${step.name}\nLatency: ${step.latency ? step.latency.toFixed(3) : 0}s\nTokens: ${step.token_count}\nCost: $${step.cost.toFixed(5)}`}
                            >
                              {step.name} ({step.latency ? `${step.latency.toFixed(2)}s` : '0s'})
                            </div>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Prompt Diff Pane */}
              {activeTab === 'promptdiff' && (
                <div className="tab-pane diff-pane">
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={{ fontSize: '1.1rem', fontWeight: 700, color: '#F8FAFC' }}>Prompt Comparison Hub</span>
                    <span style={{ fontSize: '0.75rem', color: '#64748B' }}>Compare changes in prompt versions and instructions. Hits the local diff parser.</span>
                  </div>

                  <div className="diff-grid">
                    <div className="diff-input-container">
                      <span className="diff-input-title">Prompt Version 1 (Base Line)</span>
                      <textarea
                        className="diff-textarea"
                        value={promptV1}
                        onChange={(e) => setPromptV1(e.target.value)}
                        placeholder="Paste base prompt here..."
                      />
                    </div>
                    <div className="diff-input-container">
                      <span className="diff-input-title">Prompt Version 2 (Modified)</span>
                      <textarea
                        className="diff-textarea"
                        value={promptV2}
                        onChange={(e) => setPromptV2(e.target.value)}
                        placeholder="Paste new prompt to compare here..."
                      />
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                    <button className="btn btn-primary" onClick={handleComparePrompts} disabled={diffLoading}>
                      <RefreshCw size={14} className={diffLoading ? 'animate-spin' : ''} />
                      Compare Prompt Versions
                    </button>
                    {selectedStep && selectedStep.type === 'llm' && (
                      <button className="btn" onClick={() => {
                        const promptStr = typeof selectedStep.inputs === 'object' 
                          ? JSON.stringify(selectedStep.inputs, null, 2) 
                          : String(selectedStep.inputs);
                        setPromptV1(promptStr);
                      }}>
                        Use Prompt from Selected LLM Step
                      </button>
                    )}
                  </div>

                  {diffResults.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#94A3B8' }}>Line Differences</span>
                      <div className="diff-results-box">
                        {diffResults.map((line, idx) => {
                          let lineClass = "diff-line";
                          if (line.startsWith("+ ")) lineClass += " diff-line-added";
                          else if (line.startsWith("- ")) lineClass += " diff-line-removed";
                          else if (line.startsWith("? ")) lineClass += " diff-line-header";
                          return (
                            <div key={idx} className={lineClass}>
                              {line}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
