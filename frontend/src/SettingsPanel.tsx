import { useState, useEffect } from 'react';

const API_BASE = 'http://127.0.0.1:8000';

export default function SettingsPanel() {
  const [settings, setSettings] = useState({
    zlibrary_email: '',
    zlibrary_password: '',
    zlibrary_remix_userid: '',
    zlibrary_remix_userkey: ''
  });
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    fetch(`${API_BASE}/api/settings`)
      .then(res => res.json())
      .then(data => {
        setSettings({
          zlibrary_email: data.email || '',
          zlibrary_password: data.password || '',
          zlibrary_remix_userid: data.remix_userid || '',
          zlibrary_remix_userkey: data.remix_userkey || ''
        });
      });
  }, []);

  const handleSave = async () => {
    setLoading(true);
    try {
      await fetch(`${API_BASE}/api/settings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(settings)
      });
      setMsg('设置已保存');
      setTimeout(() => setMsg(''), 3000);
    } catch (e) {
      setMsg('保存失败！');
    }
    setLoading(false);
  };

  return (
    <section className="glass-panel">
      <h2 style={{ marginBottom: '1.5rem', fontSize: '1.5rem', color: '#f8fafc' }}>Z-Library 账户设置</h2>
      <div className="settings-form">
        <div className="form-group">
          <label>邮箱 (email)</label>
          <input 
            value={settings.zlibrary_email} 
            onChange={e => setSettings(s => ({...s, zlibrary_email: e.target.value}))} 
            placeholder="your_email@example.com" 
          />
        </div>
        <div className="form-group">
          <label>密码 (password)</label>
          <input 
            type="password"
            value={settings.zlibrary_password} 
            onChange={e => setSettings(s => ({...s, zlibrary_password: e.target.value}))} 
            placeholder="••••••••" 
          />
        </div>
        <div className="form-group">
          <label>Remix User ID (备用)</label>
          <input 
            value={settings.zlibrary_remix_userid} 
            onChange={e => setSettings(s => ({...s, zlibrary_remix_userid: e.target.value}))} 
            placeholder="非必填" 
          />
        </div>
        <div className="form-group">
          <label>Remix User Key (备用)</label>
          <input 
            value={settings.zlibrary_remix_userkey} 
            onChange={e => setSettings(s => ({...s, zlibrary_remix_userkey: e.target.value}))} 
            placeholder="非必填" 
          />
        </div>
      </div>
      <div style={{ marginTop: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <button onClick={handleSave} disabled={loading}>
          {loading ? '正在保存...' : '保存设置'}
        </button>
        {msg && <span style={{ color: msg.includes('失败') ? 'var(--danger-color)' : 'var(--success-color)', fontSize: '0.9rem' }}>{msg}</span>}
      </div>
    </section>
  );
}
