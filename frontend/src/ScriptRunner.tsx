import { useState, useEffect, useRef } from 'react';

const API_BASE = 'http://127.0.0.1:8000';
const WS_BASE = 'ws://127.0.0.1:8000';

interface ParamDef {
  key: string;
  label: string;
  default: string;
  tooltip: string;
  type?: 'text' | 'checkbox';
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
  const [clipboardTexts, setClipboardTexts] = useState<Record<string, string>>({});

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
            const savedValue = localStorage.getItem(`param_${script.id}_${p.key}`);
            initialParams[script.id][p.key] = savedValue !== null ? savedValue : p.default;
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

  const handleCheckboxChange = (scriptId: string, key: string, checked: boolean) => {
    const val = checked ? 'true' : 'false';
    localStorage.setItem(`param_${scriptId}_${key}`, val);
    setParamValues(prev => ({
      ...prev,
      [scriptId]: {
        ...prev[scriptId],
        [key]: val
      }
    }));
    // 勾选"从剪贴板读取书单"时尝试读取剪贴板
    if (key === 'clipboard_content' && checked) {
      handleReadClipboard(scriptId);
    }
  };

  const handleReadClipboard = async (scriptId: string) => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        setClipboardTexts(prev => ({ ...prev, [scriptId]: text }));
      }
    } catch {
      // 浏览器安全限制，无法自动读取，用户需手动点击按钮或粘贴
    }
  };

  const handleRun = async (scriptId: string) => {
    setTerminalLogs(`[系统] 正在启动 ${scriptId}...\n\n`);
    setTerminalOpen(true);

    // 剪贴板模式下：执行时即时读取剪贴板
    let latestClipboardText = clipboardTexts[scriptId] || '';
    if (paramValues[scriptId]?.['clipboard_content'] === 'true') {
      try {
        const text = await navigator.clipboard.readText();
        if (text) {
          latestClipboardText = text;
          setClipboardTexts(prev => ({ ...prev, [scriptId]: text }));
        }
      } catch {
        // 读取失败，使用已有的内容
      }

      if (!latestClipboardText.trim()) {
        setTerminalLogs(prev => prev + `[错误] 已勾选「从剪贴板读取书单」，但剪贴板内容为空！\n请点击「读取剪贴板」按钮获取内容后再执行。\n`);
        return;
      }
    }

    setTimeout(() => {
        const ws = new WebSocket(`${WS_BASE}/api/ws/run/${scriptId}`);
        wsRef.current = ws;

        ws.onopen = () => {
          const params: Record<string, string> = { ...paramValues[scriptId] };
          if (params.clipboard_content === 'true') {
            params.clipboard_text = latestClipboardText;
            delete params.list_dir;
          }
          ws.send(JSON.stringify({ params }));
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

  const useClipboard = (scriptId: string) =>
    paramValues[scriptId]?.['clipboard_content'] === 'true';

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
                {script.params.map(p => {
                  if (p.type === 'checkbox') {
                    return (
                      <div key={p.key} className="param-checkbox-group">
                        <input
                          type="checkbox"
                          id={`${script.id}_${p.key}`}
                          checked={paramValues[script.id]?.[p.key] === 'true'}
                          onChange={(e) => handleCheckboxChange(script.id, p.key, e.target.checked)}
                        />
                        <label className="checkbox-label" htmlFor={`${script.id}_${p.key}`}>
                          {p.label}
                          <span className="tooltip-icon" data-tooltip={p.tooltip} style={{ marginLeft: '0.5rem' }}>?</span>
                        </label>
                      </div>
                    );
                  }

                  // 剪贴板模式下禁用 list_dir 输入框
                  const isDisabled = p.key === 'list_dir' && useClipboard(script.id);

                  return (
                    <div key={p.key} className="param-input-group">
                      <div className="param-header">
                        <label className="param-label">{p.label}</label>
                        <span className="tooltip-icon" data-tooltip={p.tooltip}>?</span>
                      </div>
                      <input
                        value={paramValues[script.id]?.[p.key] || ''}
                        disabled={isDisabled}
                        onChange={(e) => {
                          const val = e.target.value;
                          localStorage.setItem(`param_${script.id}_${p.key}`, val);
                          setParamValues(prev => ({
                            ...prev,
                            [script.id]: {
                              ...prev[script.id],
                              [p.key]: val
                            }
                          }));
                        }}
                        placeholder={`默认值: ${p.default}`}
                        style={{
                            width: '100%',
                            background: isDisabled ? 'rgba(0,0,0,0.15)' : 'rgba(0,0,0,0.4)',
                            border: '1px solid var(--glass-border)',
                            borderRadius: '6px',
                            padding: '0.65rem',
                            color: isDisabled ? 'rgba(255,255,255,0.3)' : '#fff',
                            fontSize: '0.85rem',
                            fontFamily: 'inherit',
                            transition: 'border-color 0.2s',
                            cursor: isDisabled ? 'not-allowed' : 'text',
                        }}
                        onFocus={(e) => { if (!isDisabled) e.target.style.borderColor = 'var(--accent-color)'; }}
                        onBlur={(e) => e.target.style.borderColor = 'var(--glass-border)'}
                      />
                    </div>
                  );
                })}

                {/* 剪贴板文本区域 */}
                {useClipboard(script.id) && (
                  <div className="param-input-group">
                    <div className="param-header">
                      <label className="param-label">剪贴板书单内容</label>
                      <button
                        type="button"
                        onClick={() => handleReadClipboard(script.id)}
                        style={{
                          background: 'transparent',
                          border: '1px solid var(--glass-border)',
                          borderRadius: '4px',
                          padding: '0.2rem 0.6rem',
                          color: 'var(--accent-color)',
                          fontSize: '0.75rem',
                          cursor: 'pointer',
                          fontWeight: 500,
                        }}
                      >
                        读取剪贴板
                      </button>
                    </div>
                    <textarea
                      className="clipboard-textarea"
                      readOnly
                      value={clipboardTexts[script.id] || ''}
                      placeholder={"点击「读取剪贴板」按钮获取内容，执行脚本时也会自动读取..."}
                    />
                  </div>
                )}
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
