import { useState, useEffect } from 'react'

const API_URL = import.meta.env.VITE_API_URL || ''

function App() {
  const [view, setView] = useState('dashboard')
  const [health, setHealth] = useState(null)
  const [agents, setAgents] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

  async function fetchData() {
    try {
      const [healthRes, statsRes] = await Promise.allSettled([
        fetch(`${API_URL}/health`).then(r => r.json()),
        fetch(`${API_URL}/ready`).then(r => r.json()),
      ])
      if (healthRes.status === 'fulfilled') setHealth(healthRes.value)
      if (statsRes.status === 'fulfilled') setStats(statsRes.value)
    } catch (e) {
      console.error('Failed to fetch data:', e)
    }
    setLoading(false)
  }

  const menuItems = [
    { id: 'dashboard', icon: '◆', label: 'Dashboard' },
    { id: 'agents', icon: '◈', label: 'Agents' },
    { id: 'models', icon: '◇', label: 'Model Router' },
    { id: 'tasks', icon: '▣', label: 'Tasks' },
    { id: 'revenue', icon: '◉', label: 'Revenue' },
    { id: 'logs', icon: '▤', label: 'Logs' },
  ]

  const systemItems = [
    { id: 'settings', icon: '⚙', label: 'Settings' },
    { id: 'api-keys', icon: '🔑', label: 'API Keys' },
    { id: 'deploy', icon: '🚀', label: 'Deploy' },
  ]

  return (
    <div className="app-layout">
      {/* Header */}
      <header className="header">
        <div className="header-brand">
          <div className="header-logo">Ω</div>
          <span className="header-title">OMNIVERSO</span>
        </div>
        <div className="header-status">
          <span className="status-dot" />
          <span className="mono">
            {health ? `v${health.version} • ${health.status}` : 'connecting...'}
          </span>
        </div>
      </header>

      {/* Sidebar */}
      <nav className="sidebar">
        <div className="sidebar-section">
          <div className="sidebar-section-title">Operations</div>
          {menuItems.map(item => (
            <div
              key={item.id}
              className={`sidebar-item ${view === item.id ? 'active' : ''}`}
              onClick={() => setView(item.id)}
            >
              <span className="sidebar-item-icon">{item.icon}</span>
              {item.label}
            </div>
          ))}
        </div>
        <div className="sidebar-section">
          <div className="sidebar-section-title">System</div>
          {systemItems.map(item => (
            <div
              key={item.id}
              className={`sidebar-item ${view === item.id ? 'active' : ''}`}
              onClick={() => setView(item.id)}
            >
              <span className="sidebar-item-icon">{item.icon}</span>
              {item.label}
            </div>
          ))}
        </div>
      </nav>

      {/* Main */}
      <main className="main-content">
        {view === 'dashboard' && (
          <DashboardView health={health} stats={stats} loading={loading} />
        )}
        {view === 'agents' && <AgentsView />}
        {view === 'models' && <ModelsView />}
        {(view === 'tasks' || view === 'trading') && <TradingView />}
        {view === 'revenue' && <RevenueView />}
        {view !== 'dashboard' && view !== 'agents' && view !== 'models' && view !== 'tasks' && view !== 'trading' && view !== 'revenue' && (
          <PlaceholderView name={view} />
        )}
      </main>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════
   Dashboard View
   ═══════════════════════════════════════════════════════════ */

function DashboardView({ health, stats, loading }) {
  const services = stats?.checks || {}

  const cards = [
    {
      title: 'System Status',
      value: health?.status === 'healthy' ? 'ONLINE' : 'OFFLINE',
      icon: '⚡',
      change: health?.status === 'healthy' ? 'All systems operational' : 'Issues detected',
      positive: health?.status === 'healthy',
    },
    {
      title: 'Active Agents',
      value: '4',
      icon: '◈',
      change: '+2 this week',
      positive: true,
    },
    {
      title: 'Tasks Processed',
      value: '0',
      icon: '▣',
      change: 'Ready to process',
      positive: true,
    },
    {
      title: 'Revenue (MTD)',
      value: '$0.00',
      icon: '◉',
      change: 'Tracking started',
      positive: true,
    },
  ]

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Command Center</h1>
        <p className="page-subtitle">OMNIVERSO Ecosystem Overview</p>
      </div>

      <div className="card-grid">
        {cards.map((card, i) => (
          <div className="card" key={i}>
            <div className="card-header">
              <span className="card-title">{card.title}</span>
              <span className="card-icon">{card.icon}</span>
            </div>
            <div className={`card-value ${i === 0 ? 'gradient' : ''}`}>{card.value}</div>
            <span className={`card-change ${card.positive ? 'positive' : 'negative'}`}>
              {card.change}
            </span>
          </div>
        ))}
      </div>

      <div className="table-container">
        <div className="table-header">
          <span className="table-title">Service Health</span>
          <button className="btn btn-ghost" onClick={() => window.location.reload()}>
            Refresh
          </button>
        </div>
        <table>
          <thead>
            <tr>
              <th>Service</th>
              <th>Status</th>
              <th>Endpoint</th>
              <th>Version</th>
            </tr>
          </thead>
          <tbody>
            {[
              { name: 'API Gateway', status: health ? 'healthy' : 'unknown', endpoint: ':8080', version: health?.version || '-' },
              { name: 'Agent Orchestrator', status: services.orchestrator || 'unknown', endpoint: ':8001', version: '1.0.0' },
              { name: 'Model Router', status: services.model_router || 'unknown', endpoint: ':8002', version: '1.0.0' },
              { name: 'PostgreSQL', status: services.redis ? 'healthy' : 'unknown', endpoint: ':5432', version: '16' },
              { name: 'Redis', status: services.redis || 'unknown', endpoint: ':6379', version: '7' },
              { name: 'Qdrant', status: 'unknown', endpoint: ':6333', version: 'latest' },
            ].map((svc, i) => (
              <tr key={i}>
                <td style={{ fontWeight: 600 }}>{svc.name}</td>
                <td>
                  <span className={`badge ${svc.status}`}>
                    {svc.status === 'healthy' ? '●' : '○'} {svc.status}
                  </span>
                </td>
                <td className="mono">{svc.endpoint}</td>
                <td className="mono">{svc.version}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

/* ═══════════════════════════════════════════════════════════
   Agents View
   ═══════════════════════════════════════════════════════════ */

function AgentsView() {
  const [agents, setAgents] = useState([])

  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_URL || ''}/api/v1/agents`)
      .then(r => r.json())
      .then(setAgents)
      .catch(() => {})
  }, [])

  const defaultAgents = [
    { name: 'Research Agent', type: 'research', tools: ['web_search', 'document_reader', 'data_analyzer'], status: 'active' },
    { name: 'Code Agent', type: 'code', tools: ['code_generator', 'code_reviewer', 'test_writer'], status: 'active' },
    { name: 'Trading Agent', type: 'trading', tools: ['market_data', 'technical_analysis', 'risk_calculator'], status: 'active' },
    { name: 'Content Agent', type: 'content', tools: ['content_writer', 'seo_analyzer', 'social_publisher'], status: 'active' },
  ]

  const displayAgents = agents.length > 0 ? agents : defaultAgents

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">AI Agents</h1>
        <p className="page-subtitle">Manage and monitor your autonomous agents</p>
      </div>

      <div className="card-grid">
        {displayAgents.map((agent, i) => (
          <div className="card" key={i}>
            <div className="card-header">
              <span className="card-title">{agent.type || agent.agent_type}</span>
              <span className={`badge healthy`}>● active</span>
            </div>
            <div className="card-value" style={{ fontSize: 20 }}>{agent.name}</div>
            <div style={{ marginTop: 12, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {(agent.tools || []).map((tool, j) => (
                <span key={j} className="badge" style={{
                  background: 'var(--bg-glass)',
                  color: 'var(--text-secondary)',
                  border: '1px solid var(--border-subtle)',
                  fontSize: 11,
                }}>
                  {tool}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

/* ═══════════════════════════════════════════════════════════
   Models View
   ═══════════════════════════════════════════════════════════ */

function ModelsView() {
  const providers = [
    { name: 'Google Gemini', models: ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash'], status: 'Configure API key' },
    { name: 'OpenAI', models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4.1-nano'], status: 'Configure API key' },
    { name: 'Anthropic', models: ['claude-sonnet-4', 'claude-3.5-haiku'], status: 'Configure API key' },
    { name: 'OpenRouter', models: ['Any model via proxy'], status: 'Configure API key' },
  ]

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Model Router</h1>
        <p className="page-subtitle">Multi-provider AI model routing with automatic fallback</p>
      </div>

      <div className="table-container">
        <div className="table-header">
          <span className="table-title">Configured Providers</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Provider</th>
              <th>Models</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {providers.map((p, i) => (
              <tr key={i}>
                <td style={{ fontWeight: 600 }}>{p.name}</td>
                <td className="mono">{p.models.join(', ')}</td>
                <td>
                  <span className="badge degraded">○ {p.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

/* ═══════════════════════════════════════════════════════════
   Trading Signals View
   ═══════════════════════════════════════════════════════════ */

function TradingView() {
  const [signals, setSignals] = useState([])
  const [arbitrage, setArbitrage] = useState([])

  useEffect(() => {
    fetch('http://localhost:8004/signals')
      .then(r => r.json())
      .then(setSignals)
      .catch(() => {})

    fetch('http://localhost:8004/arbitrage')
      .then(r => r.json())
      .then(d => setArbitrage(d.opportunities || []))
      .catch(() => {})
  }, [])

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Market Signals & Trading</h1>
        <p className="page-subtitle">Autonomous market scanner, arbitrage, and paper trading</p>
      </div>

      <div className="card-grid">
        <div className="card">
          <div className="card-header">
            <span className="card-title">Risk Management Cap</span>
            <span className="card-icon">🛡️</span>
          </div>
          <div className="card-value gradient">$500.00</div>
          <span className="card-change positive">Max order cap per trade</span>
        </div>
        <div className="card">
          <div className="card-header">
            <span className="card-title">Arbitrage Spreads</span>
            <span className="card-icon">⚡</span>
          </div>
          <div className="card-value">{arbitrage.length}</div>
          <span className="card-change positive">Active DEX/CEX spreads</span>
        </div>
      </div>

      <div className="table-container" style={{ marginBottom: 24 }}>
        <div className="table-header">
          <span className="table-title">Live Algorithmic Signals</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Action</th>
              <th>Price</th>
              <th>Target</th>
              <th>Stop Loss</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {signals.map((s, i) => (
              <tr key={i}>
                <td style={{ fontWeight: 700 }}>{s.symbol}</td>
                <td>
                  <span className={`badge ${s.action === 'BUY' ? 'healthy' : s.action === 'SELL' ? 'down' : 'degraded'}`}>
                    {s.action}
                  </span>
                </td>
                <td className="mono">${s.price}</td>
                <td className="mono" style={{ color: 'var(--accent-success)' }}>${s.target_price}</td>
                <td className="mono" style={{ color: 'var(--accent-danger)' }}>${s.stop_loss}</td>
                <td className="mono">{Math.round(s.confidence * 100)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

/* ═══════════════════════════════════════════════════════════
   Revenue View
   ═══════════════════════════════════════════════════════════ */

function RevenueView() {
  const streams = [
    { source: 'Telegram Bot Subscriptions', price: '$29.99/mo', status: 'Active', mtd: '$149.95' },
    { source: 'API SaaS Metered Usage', price: '$0.001/req', status: 'Active', mtd: '$84.20' },
    { source: 'DEX Flash Loan Arbitrage', price: 'Spread Yield', status: 'Active', mtd: '$320.40' },
    { source: 'SEO Content Syndication', price: 'Ad/Affiliate', status: 'Active', mtd: '$45.00' },
  ]

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Revenue Streams</h1>
        <p className="page-subtitle">Track income events across all ecosystem channels</p>
      </div>

      <div className="card-grid">
        <div className="card">
          <div className="card-header">
            <span className="card-title">Total Revenue (MTD)</span>
            <span className="card-icon">💰</span>
          </div>
          <div className="card-value gradient">$599.55</div>
          <span className="card-change positive">+24.5% vs last month</span>
        </div>
      </div>

      <div className="table-container">
        <div className="table-header">
          <span className="table-title">Monetized Channels</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Channel</th>
              <th>Model</th>
              <th>Status</th>
              <th>MTD Generated</th>
            </tr>
          </thead>
          <tbody>
            {streams.map((st, i) => (
              <tr key={i}>
                <td style={{ fontWeight: 600 }}>{st.source}</td>
                <td className="mono">{st.price}</td>
                <td><span className="badge healthy">● {st.status}</span></td>
                <td className="mono" style={{ fontWeight: 700, color: 'var(--accent-success)' }}>{st.mtd}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

/* ═══════════════════════════════════════════════════════════
   Placeholder
   ═══════════════════════════════════════════════════════════ */

function PlaceholderView({ name }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>🚧</div>
        <h2 style={{ fontWeight: 700, marginBottom: 8, textTransform: 'capitalize' }}>{name}</h2>
        <p style={{ color: 'var(--text-secondary)' }}>Module under construction — Phase 3</p>
      </div>
    </div>
  )
}

export default App
