import { useState, useEffect, useRef } from 'react';

const API_BASE = 'http://127.0.0.1:8000';
const WS_BASE = 'ws://127.0.0.1:8000';

interface ParamDef {
  key: string;
  label: string;
  default: string;
  tooltip: string;
}

interface ScriptDef {
  id: string;
  name: string;
  description: string;
  params: ParamDef[];
}

export default function ScriptRunner() {
  const [scripts, setScripts] = useState<ScriptDef[]>([]);
  const [paramValues, setParamValues] = useState<Record<string, Record<string, string>>>({});
  
  const [terminalOpen, setTerminalOpen] = useState(false);
  const [TerminalLogs, setTerminalLogs] = useState<string>("");
  const wsRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/scripts`)
      .then(res => res.json())
      .then((data: ScriptDef[]) => {
        setScripts(data);
        const initialParams: Record<string, Record<string, string>> = {};
        data.forEach(script => {
          initialParams[script.id] = {};
          script.params.forEach(p => {
            initialParams[script.id][p.key] = p.default;
          });
        });
        setParamValues(initialParams);
      });
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [TerminalLogs]);

  const handleRun = (scriptId: string) => {
    setTerminalLogs(`[系统] 正在启动 ${scriptId}...\n\n`);
    setTerminalOpen(true);
    
    setTimeout(() => {
        const ws = new WebSocket(`${WS_BASE}/api/ws/run/${scriptId}`);
        wsRef.current = ws;
    
        ws.onopen = () => {
          ws.send(JSON.stringify({
            params: paramValues[scriptId]
          }));
        };
    
        ws.onmessage = (event) => {
          setTerminalLogs(prev => prev + event.data);
        };
    
        ws.onclose = () => {
          setTerminalLogs(prev => prev + "\n[WebSocket 连接已断开]");
        };
    }, 100);
  };

  const closeTerminal = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }
    setTerminalOpen(false);
  };

  return (
    <>
      <section className="glass-panel" style={{ padding: '2rem' }}>
        <h2 style={{ marginBottom: '1.5rem', fontSize: '1.5rem', color: '#f8fafc' }}>自动化工作流</h2>
        <div className="scripts-grid">
          {scripts.map(script => (
            <div key={script.id} className="glass-panel script-card" style={{ marginBottom: 0, padding: '1.5rem' }}>
              <h3 style={{ color: '#fff' }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent-color)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polygon points="5 3 19 12 5 21 5 3"></polygon>
                  </svg>
                  {script.name}
              </h3>
              <p>{script.description}</p>
              
              <div className="script-params">
                {script.params.map(p => (
                  <div key={p.key} className="param-input-group">
                    <div className="param-header">
                      <label className="param-label">{p.label}</label>
                      <span className="tooltip-icon" data-tooltip={p.tooltip}>?</span>
                    </div>
                    <input 
                      value={paramValues[script.id]?.[p.key] || ''} 
                      onChange={(e) => {
                        setParamValues(prev => ({
                          ...prev,
                          [script.id]: {
                            ...prev[script.id],
                            [p.key]: e.target.value
                          }
                        }));
                      }}
                      placeholder={`默认值: ${p.default}`}
                      style={{ 
                          width: '100%', 
                          background: 'rgba(0,0,0,0.4)', 
                          border: '1px solid var(--glass-border)', 
                          borderRadius: '6px', 
                          padding: '0.65rem', 
                          color: '#fff', 
                          fontSize: '0.85rem',
                          fontFamily: 'inherit',
                          transition: 'border-color 0.2s'
                      }}
                      onFocus={(e) => e.target.style.borderColor = 'var(--accent-color)'}
                      onBlur={(e) => e.target.style.borderColor = 'var(--glass-border)'}
                    />
                  </div>
                ))}
              </div>

              <div style={{ marginTop: 'auto', textAlign: 'right' }}>
                <button onClick={() => handleRun(script.id)}>
                  执行脚本
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {terminalOpen && (
        <div className="terminal-overlay">
          <div className="terminal-window">
            <div className="terminal-header">
              <span className="terminal-title">终端控制台 - 运行中</span>
              <button className="terminal-close" onClick={closeTerminal}>✖ 关闭</button>
            </div>
            <div className="terminal-content" ref={scrollRef}>
              {TerminalLogs}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
