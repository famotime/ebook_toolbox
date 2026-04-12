import './App.css';
import SettingsPanel from './SettingsPanel';
import ScriptRunner from './ScriptRunner';

function App() {
  return (
    <div className="app-container">
      <header className="header">
        <h1>Ebook Toolbox</h1>
        <p>您的本地电子书聚合、重命名、批量下载和自动化终极管理中心</p>
      </header>

      <SettingsPanel />
      <ScriptRunner />
    </div>
  );
}

export default App;
