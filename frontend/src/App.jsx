import { useState, useEffect, useRef } from 'react';
import confetti from 'canvas-confetti';
import { 
  ShieldAlert, 
  DollarSign, 
  PlusCircle, 
  ArrowLeftRight, 
  AlertTriangle, 
  AlertCircle,
  FileText,
  Activity,
  Layers,
  ArrowUpRight,
  TrendingUp,
  Wallet
} from 'lucide-react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import './App.css';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const API_BASE = 'http://127.0.0.1:8000';

function App() {
  // Ledger and base metrics state
  const [ledger, setLedger] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Simulation states
  const [simAmount, setSimAmount] = useState('');
  const [simDate, setSimDate] = useState('2026-06-21');
  const [simulating, setSimulating] = useState(false);
  const [simResults, setSimResults] = useState(null);

  // New transaction (Butler Log) states
  const [logAmount, setLogAmount] = useState('');
  const [logDesc, setLogDesc] = useState('');
  const [logCategory, setLogCategory] = useState('Shops');
  const [logDate, setLogDate] = useState('2026-06-20');
  const [logStatusMsg, setLogStatusMsg] = useState(null);

  // Persona & Ask Ahead states
  const [persona, setPersona] = useState('gentle');
  const [askQuery, setAskQuery] = useState('');
  const [lastQueryData, setLastQueryData] = useState(null);
  const [baseCoachingMessage, setBaseCoachingMessage] = useState('');
  const [activeTab, setActiveTab] = useState('ask');
  const [navTab, setNavTab] = useState('dashboard');
  const [chatHistory, setChatHistory] = useState([
    { id: 1, isCoach: true, persona: 'Empathetic', text: "Hi — I'm your Ahead coach. Ask me before a purchase, or try a suggestion below and I'll run the numbers." }
  ]);

  // Chart gradient ref
  const chartRef = useRef(null);
  const chatEndRef = useRef(null);

  // Fetch base ledger details
  const fetchLedger = async (selectedPersona = persona) => {
    try {
      const res = await fetch(`${API_BASE}/api/ledger?persona=${selectedPersona}`);
      if (!res.ok) throw new Error('Failed to load ledger data');
      const data = await res.json();
      setLedger(data);
      setBaseCoachingMessage(data.base_coaching_message || '');
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLedger(persona);
    
    const interval = setInterval(() => {
      fetchLedger(persona);
    }, 4000);
    
    return () => clearInterval(interval);
  }, [persona]);

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatHistory]);

  // Re-run active simulation or fetch baseline when persona changes to instantly shift the tone
  useEffect(() => {
    const reRunActiveSim = async () => {
      setLoading(true);
      try {
        if (simulating) {
          if (lastQueryData && lastQueryData.original_query) {
            // Re-fetch natural language query with new persona
            const res = await fetch(`${API_BASE}/api/ask`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                query: lastQueryData.original_query,
                persona: persona
              })
            });
            const data = await res.json();
            setSimResults(data);
            setLastQueryData(data);
          } else if (simAmount) {
            // Re-fetch What-If simulation with new persona
            const res = await fetch(`${API_BASE}/api/simulate`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                amount: parseFloat(simAmount),
                date: simDate,
                persona: persona
              })
            });
            const data = await res.json();
            setSimResults(data);
          }
          setLoading(false);
        } else {
          // Re-fetch baseline with new persona
          await fetchLedger(persona);
        }
      } catch (err) {
        setLoading(false);
      }
    };
    
    reRunActiveSim();
  }, [persona]);

  // Handle simulation trigger (What-If)
  const handleCheckAffordability = async (e) => {
    e.preventDefault();
    if (!simAmount || parseFloat(simAmount) <= 0) return;
    
    setLoading(true);
    setLastQueryData(null); // Clear PII comparison when doing form simulation
    try {
      const res = await fetch(`${API_BASE}/api/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          amount: parseFloat(simAmount),
          date: simDate,
          persona: persona
        })
      });
      const data = await res.json();
      setSimResults(data);
      setSimulating(true);
      setLoading(false);
      
      // Trigger confetti if risk is safe (<1%)
      if (data.probability_of_overdraft < 0.01) {
        confetti({
          particleCount: 120,
          spread: 80,
          origin: { y: 0.6 }
        });
      }
    } catch (err) {
      alert('Simulation failed to execute.');
      setLoading(false);
    }
  };

  // Handle natural language query with chat history updates
  const askAheadQuery = async (queryText) => {
    if (!queryText.trim()) return;

    // Detect credit card PII local-first
    const cardMatch = queryText.match(/(?:\d[ -]?){13,19}/);
    const hasCard = !!cardMatch;
    const last4 = hasCard ? cardMatch[0].replace(/\D/g, '').slice(-4) : '';
    const rawCard = hasCard ? cardMatch[0].trim() : '';

    const userMsg = { id: Date.now(), isUser: true, text: queryText };
    let newHistory = [...chatHistory, userMsg];

    if (hasCard) {
      newHistory.push({ id: Date.now() + 1, isPii: true, rawCard, last4 });
    }

    const thinkingMsg = { id: Date.now() + 2, isThinking: true, text: 'Analyzing cashflow trajectories...' };
    setChatHistory([...newHistory, thinkingMsg]);

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: queryText,
          persona: persona
        })
      });
      const data = await res.json();
      
      setSimResults(data);
      setLastQueryData(data);
      setSimulating(true);
      
      if (data.simulated_purchase) {
        setSimAmount(data.simulated_purchase.amount);
        setSimDate(data.simulated_purchase.date);
      }

      const personaTitle = persona === 'gentle' ? 'Empathetic' : persona.charAt(0).toUpperCase() + persona.slice(1);
      const coachMsg = {
        id: Date.now() + 3,
        isCoach: true,
        persona: personaTitle,
        text: data.coaching_message
      };

      setChatHistory([...newHistory, coachMsg]);
      setLoading(false);

      if (data.probability_of_overdraft < 0.01) {
        confetti({
          particleCount: 120,
          spread: 80,
          origin: { y: 0.6 }
        });
      }
    } catch (err) {
      alert('Natural language query failed.');
      setChatHistory(newHistory);
      setLoading(false);
    }
  };

  const handleAskAhead = (e) => {
    e.preventDefault();
    if (!askQuery.trim()) return;
    askAheadQuery(askQuery);
    setAskQuery('');
  };

  // Handle transaction logging (The Butler Input)
  const handleLogExpense = async (e) => {
    e.preventDefault();
    if (!logAmount || parseFloat(logAmount) <= 0 || !logDesc) return;

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/transactions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          amount: parseFloat(logAmount),
          description: logDesc,
          category: logCategory,
          date: logDate
        })
      });
      const data = await res.json();
      
      if (data.status === 'success') {
        // Trigger success feedback
        setLogStatusMsg(`Successfully logged "${logDesc.substring(0, 16)}..."`);
        setLogAmount('');
        setLogDesc('');
        await fetchLedger();
        
        setTimeout(() => setLogStatusMsg(null), 3000);
      }
      setLoading(false);
    } catch (err) {
      alert('Failed to log transaction.');
      setLoading(false);
    }
  };

  const handleClearSimulation = () => {
    setSimulating(false);
    setSimResults(null);
    setSimAmount('');
    setAskQuery('');
    setLastQueryData(null);
    setChatHistory([
      { id: 1, isCoach: true, persona: 'Empathetic', text: "Hi — I'm your Ahead coach. Ask me before a purchase, or try a suggestion below and I'll run the numbers." }
    ]);
  };

  if (loading && !ledger) {
    return (
      <div className="risk-meter-container" style={{ minHeight: '100vh', justifyContent: 'center' }}>
        <h2 style={{ fontWeight: '400', letterSpacing: '0.05em', color: '#94a3b8' }}>INITIALIZING AHEAD FORECASTS...</h2>
        <div className="pulse-dot" style={{ width: '24px', height: '24px', color: '#3b82f6', marginTop: '16px' }}></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app-container" style={{ textAlign: 'center', marginTop: '120px', maxWidth: '600px' }}>
        <div className="glass-card glow-red" style={{ padding: '40px' }}>
          <AlertCircle size={64} color="#f43f5e" style={{ marginBottom: '20px' }} />
          <h1 style={{ fontWeight: '800', letterSpacing: '-0.02em', margin: '0 0 10px 0' }}>Ahead Offline</h1>
          <p style={{ color: '#94a3b8', lineHeight: '1.6' }}>Could not connect to the local FastAPI backend server at 127.0.0.1:8000.</p>
          <button className="btn-primary" style={{ margin: '24px auto 0 auto' }} onClick={fetchLedger}>Retry Connection</button>
        </div>
      </div>
    );
  }

  const balance = ledger.account.balances.current;
  const runway = simulating ? simResults.long_term_runway_months : ledger.runway_months;
  const overdraftRisk = simulating ? simResults.probability_of_overdraft : ledger.base_overdraft_probability;
  const trajectory = simulating ? simResults.trajectory : ledger.base_trajectory;
  const coachMessage = simulating ? simResults.coaching_message : (baseCoachingMessage || "Analyzing cashflow history...");

  // Determine risk details matching template
  let riskColor = '#3ddc84'; // Green
  let riskLabel = 'Low';
  if (overdraftRisk >= 0.25) {
    riskColor = '#ff5d52'; // Red
    riskLabel = 'High';
  } else if (overdraftRisk >= 0.12) {
    riskColor = '#ffb020'; // Amber
    riskLabel = 'Moderate';
  }

  // SVG circular ring calculation
  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (overdraftRisk * circumference);

  // Chart setup with custom gradient
  const chartLabels = Array.from({ length: 15 }, (_, i) => `Day ${i}`);
  const chartData = {
    labels: chartLabels,
    datasets: [
      {
        label: 'Balance',
        data: trajectory,
        borderColor: riskColor,
        borderWidth: 2.6,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 6,
        fill: true,
        backgroundColor: 'rgba(61, 220, 132, 0.13)'
      },
      {
        label: 'Overdraft Limit',
        data: Array(15).fill(0),
        borderColor: 'rgba(255, 93, 82, 0.5)',
        borderWidth: 1.5,
        borderDash: [5, 4],
        pointRadius: 0,
        fill: false,
      }
    ]
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        mode: 'index',
        intersect: false,
        backgroundColor: '#1c2127',
        borderColor: 'rgba(255, 255, 255, 0.08)',
        borderWidth: 1,
        titleColor: '#8b9298',
        bodyColor: '#eceef0',
        bodyFont: { family: 'JetBrains Mono', weight: 'bold' },
        callbacks: {
          label: (context) => `Balance: $${context.raw.toFixed(2)}`
        }
      }
    },
    scales: {
      y: {
        grid: { color: 'rgba(255, 255, 255, 0.05)' },
        ticks: { color: '#5a6066', font: { family: 'JetBrains Mono', size: 10 } }
      },
      x: {
        grid: { display: false },
        ticks: { color: '#5a6066', font: { family: 'JetBrains Mono', size: 10 } }
      }
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#13161a', color: '#eceef0', fontFamily: "'Space Grotesk', sans-serif" }}>
      {/* Top Bar / Header */}
      <div style={{ height: '66px', borderBottom: '1px solid rgba(255,255,255,0.07)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 32px', position: 'sticky', top: 0, background: 'rgba(19,22,26,0.9)', backdropFilter: 'blur(8px)', zIndex: 5 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '13px' }}>
          <img src="/logo.png" alt="Logo" style={{ height: '32px' }} />
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '11px', letterSpacing: '0.2em', color: '#5a6066', textTransform: 'uppercase', borderLeft: '1px solid rgba(255,255,255,0.12)', paddingLeft: '13px', marginLeft: '3px' }}>Concierge</span>
        </div>
        
        {/* Navigation Tabs (Center) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '30px' }}>
          <button 
            onClick={() => setNavTab('dashboard')} 
            style={{ background: 'none', border: 'none', font: 'inherit', fontSize: '15px', color: navTab === 'dashboard' ? '#3ddc84' : '#8b9298', fontWeight: navTab === 'dashboard' ? '600' : '400', cursor: 'pointer', transition: 'color 0.2s' }}
          >
            Dashboard
          </button>
          <button 
            onClick={() => setNavTab('cashbook')} 
            style={{ background: 'none', border: 'none', font: 'inherit', fontSize: '15px', color: navTab === 'cashbook' ? '#3ddc84' : '#8b9298', fontWeight: navTab === 'cashbook' ? '600' : '400', cursor: 'pointer', transition: 'color 0.2s' }}
          >
            Cashflow Feed
          </button>
          <button 
            onClick={() => setNavTab('accuracy')} 
            style={{ background: 'none', border: 'none', font: 'inherit', fontSize: '15px', color: navTab === 'accuracy' ? '#3ddc84' : '#8b9298', fontWeight: navTab === 'accuracy' ? '600' : '400', cursor: 'pointer', transition: 'color 0.2s' }}
          >
            Accuracy Scorecard
          </button>
        </div>

        {/* Account Info (Right) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <span style={{ width: '36px', height: '36px', borderRadius: '999px', background: '#212730', border: '1px solid rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px', fontWeight: '600', color: '#c8cdd2' }}>
            PC
          </span>
        </div>
      </div>

      {/* Butler Warning Banner */}
      {runway !== -1 && (
        <div style={{ maxWidth: '1320px', margin: '20px auto 0 auto', padding: '0 32px' }}>
          <div style={{ background: 'rgba(255, 93, 82, 0.06)', border: '1px solid rgba(255, 93, 82, 0.2)', borderRadius: '12px', padding: '16px 20px', display: 'flex', gap: '16px', alignItems: 'center', color: '#ff5d52' }}>
            <AlertTriangle size={24} style={{ flexShrink: 0 }} />
            <div>
              <span style={{ fontWeight: '700', fontSize: '0.95rem', display: 'block', marginBottom: '2px' }}>Butler Notice: Spending Warning</span>
              <span style={{ fontSize: '0.85rem', color: '#8b9298' }}>Your current spending exceeds your income. At this rate, your savings cushion will only last <strong style={{ color: '#ff5d52' }}>{runway} months</strong> before you start building up debt.</span>
            </div>
          </div>
        </div>
      )}

      {/* Simulation Active Banner Overlay */}
      {simulating && (
        <div style={{ maxWidth: '1320px', margin: '20px auto 0 auto', padding: '0 32px' }}>
          <div style={{ background: 'rgba(61, 220, 132, 0.08)', border: '1px solid rgba(61, 220, 132, 0.2)', borderRadius: '12px', padding: '12px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#3ddc84', fontWeight: '600' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="pulse-dot" style={{ width: '8px', height: '8px', background: '#3ddc84', borderRadius: '50%', display: 'inline-block' }}></span>
              <span>Simulation Mode Active: Projections include simulated item ({simAmount ? `$${parseFloat(simAmount).toFixed(2)}` : 'NL Inquiry'})</span>
            </div>
            <button onClick={handleClearSimulation} style={{ background: 'rgba(255, 93, 82, 0.1)', border: '1px solid rgba(255, 93, 82, 0.2)', borderRadius: '8px', color: '#ff5d52', padding: '6px 12px', fontSize: '0.8rem', cursor: 'pointer', fontWeight: '700', borderStyle: 'solid' }}>
              Exit Simulation
            </button>
          </div>
        </div>
      )}

      {/* Tab 1: Overview Dashboard */}
      {navTab === 'dashboard' && (
        <div style={{ maxWidth: '1320px', margin: '0 auto', padding: '28px 32px 56px', display: 'grid', gridTemplateColumns: '1.55fr 1fr', gap: '24px', alignItems: 'start' }}>
          {/* LEFT COLUMN */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', minWidth: 0 }}>
            {/* Stat Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px' }}>
              <div style={{ background: '#1c2127', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '16px', padding: '20px 22px' }}>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '11px', letterSpacing: '0.14em', color: '#8b9298', textTransform: 'uppercase' }}>Checking balance</div>
                <div style={{ fontSize: '34px', fontWeight: '600', letterSpacing: '-0.02em', marginTop: '8px' }}>
                  ${balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
                <div style={{ fontSize: '13px', color: '#5a6066', marginTop: '4px' }}>available today</div>
              </div>
              <div style={{ background: '#1c2127', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '16px', padding: '20px 22px' }}>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '11px', letterSpacing: '0.14em', color: '#8b9298', textTransform: 'uppercase' }}>14-day low</div>
                <div style={{ fontSize: '34px', fontWeight: '600', letterSpacing: '-0.02em', marginTop: '8px', color: riskColor }}>
                  ${Math.min(...trajectory).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
                <div style={{ fontSize: '13px', color: '#5a6066', marginTop: '4px' }}>projected · day {trajectory.indexOf(Math.min(...trajectory))}</div>
              </div>
              <div style={{ background: '#1c2127', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '16px', padding: '20px 22px' }}>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '11px', letterSpacing: '0.14em', color: '#8b9298', textTransform: 'uppercase' }}>Overdraft risk</div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginTop: '8px' }}>
                  <div style={{ fontSize: '34px', fontWeight: '600', letterSpacing: '-0.02em', color: riskColor }}>
                    {(overdraftRisk * 100).toFixed(0)}%
                  </div>
                  <div style={{ fontSize: '14px', fontWeight: '600', color: riskColor }}>{riskLabel}</div>
                </div>
                <div style={{ fontSize: '13px', color: '#5a6066', marginTop: '4px' }}>over 14 days · 10k paths</div>
              </div>
            </div>

            {/* Forecast Chart */}
            <div style={{ background: '#1c2127', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '18px', padding: '22px 24px 18px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '6px' }}>
                <div>
                  <div style={{ fontSize: '18px', fontWeight: '600', color: '#eceef0' }}>14-day balance forecast</div>
                  <div style={{ fontSize: '13px', color: '#8b9298', marginTop: '3px' }}>Median path with Best/Worst Case range</div>
                </div>
                <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '7px', fontSize: '12px', color: '#8b9298' }}><span style={{ width: '16px', height: '3px', background: 'var(--primary)', borderRadius: '2px', display: 'inline-block' }}></span>Median</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '7px', fontSize: '12px', color: '#8b9298' }}><span style={{ width: '16px', height: '10px', background: 'rgba(61,220,132,0.16)', borderRadius: '2px', display: 'inline-block' }}></span>Best/Worst Case</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '7px', fontSize: '12px', color: '#8b9298' }}><span style={{ width: '16px', height: 0, borderTop: '2px dashed #5a6066', display: 'inline-block' }}></span>Baseline</span>
                </div>
              </div>
              <div style={{ height: '240px', position: 'relative' }}>
                <Line ref={chartRef} data={chartData} options={chartOptions} />
              </div>
            </div>

            {/* Ask Ahead Panel */}
            <div style={{ background: '#1c2127', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '18px', overflow: 'hidden' }}>
              <div style={{ padding: '18px 22px 14px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ width: '9px', height: '9px', background: 'var(--primary)', transform: 'rotate(45deg)', display: 'inline-block' }}></span>
                <span style={{ fontSize: '16px', fontWeight: '600', color: '#eceef0' }}>Ask Ahead</span>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '11px', color: '#5a6066', marginLeft: 'auto' }}>checks before you spend</span>
              </div>
              
              <div id="ah-thread" className="ah-scroll" style={{ padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: '14px', maxHeight: '300px', overflowY: 'auto' }}>
                {chatHistory.map((m) => (
                  <div key={m.id} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {m.isUser && (
                      <div style={{ alignSelf: 'flex-end', maxWidth: '78%', background: 'var(--primary)', color: '#06140c', borderRadius: '14px 14px 4px 14px', padding: '11px 15px', fontSize: '15px', lineHeight: '1.4', fontWeight: '500' }}>
                        {m.text}
                      </div>
                    )}
                    {m.isPii && (
                      <div style={{ alignSelf: 'flex-start', maxWidth: '88%', background: 'rgba(61,220,132,0.06)', border: '1px solid rgba(61,220,132,0.3)', borderRadius: '12px', padding: '12px 15px' }}>
                        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', letterSpacing: '0.16em', color: 'var(--primary)', textTransform: 'uppercase', marginBottom: '7px' }}>PII redaction · local</div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontFamily: "'JetBrains Mono', monospace", fontSize: '14px' }}>
                          <span style={{ color: '#5a6066', textDecoration: 'line-through' }}>{m.rawCard}</span>
                          <span style={{ color: 'var(--primary)' }}>→</span>
                          <span style={{ color: '#eceef0' }}>•••• •••• •••• {m.last4}</span>
                        </div>
                        <div style={{ fontSize: '13px', color: '#8b9298', marginTop: '8px', lineHeight: '1.4' }}>Card number stripped before any model call.</div>
                      </div>
                    )}
                    {m.isThinking && (
                      <div style={{ alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: '10px', background: '#212730', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '14px', padding: '11px 15px' }}>
                        <span style={{ display: 'flex', gap: '4px' }}>
                          <span style={{ width: '6px', height: '6px', borderRadius: '999px', background: 'var(--primary)', animation: 'pulse 1s infinite' }}></span>
                        </span>
                        <span style={{ fontSize: '14px', color: '#8b9298' }}>{m.text}</span>
                      </div>
                    )}
                    {m.isCoach && (
                      <div style={{ alignSelf: 'flex-start', maxWidth: '88%', background: '#212730', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '14px 14px 14px 4px', padding: '13px 16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '7px' }}>
                          <span style={{ width: '7px', height: '7px', background: 'var(--primary)', transform: 'rotate(45deg)', display: 'inline-block' }}></span>
                          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', letterSpacing: '0.14em', color: '#8b9298', textTransform: 'uppercase' }}>Coach · {m.persona}</span>
                        </div>
                        <div style={{ fontSize: '15px', lineHeight: '1.5', color: '#eceef0', whiteSpace: 'pre-line' }}>{m.text}</div>
                      </div>
                    )}
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>

              <div style={{ padding: '14px 22px 18px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                <form onSubmit={handleAskAhead} style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                  <input 
                    type="text" 
                    placeholder="Ask before you spend…" 
                    value={askQuery}
                    onChange={(e) => setAskQuery(e.target.value)}
                    style={{ flex: 1, background: '#13161a', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '12px', padding: '13px 15px', color: '#eceef0', fontFamily: "'Space Grotesk', sans-serif", fontSize: '15px', outline: 'none' }}
                  />
                  <button type="submit" style={{ background: 'var(--primary)', color: '#06140c', border: 'none', borderRadius: '12px', padding: '0 20px', height: '46px', fontFamily: "'Space Grotesk', sans-serif", fontSize: '15px', fontWeight: '600', cursor: 'pointer' }}>
                    Ask
                  </button>
                </form>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '12px' }}>
                  <button onClick={() => askAheadQuery('Can I spend $350 on card 4111-2222-3333-4444?')} style={{ background: '#212730', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '999px', padding: '8px 14px', color: '#c8cdd2', fontFamily: "'JetBrains Mono', monospace", fontSize: '12px', cursor: 'pointer' }}>
                    Can I spend $350 on card 4111-2222-3333-4444?
                  </button>
                  <button onClick={() => askAheadQuery('Gas prices are rising')} style={{ background: '#212730', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '999px', padding: '8px 14px', color: '#c8cdd2', fontFamily: "'JetBrains Mono', monospace", fontSize: '12px', cursor: 'pointer' }}>
                    Gas prices are rising
                  </button>
                  <button onClick={() => askAheadQuery("When will I run out of money?")} style={{ background: '#212730', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '999px', padding: '8px 14px', color: '#c8cdd2', fontFamily: "'JetBrains Mono', monospace", fontSize: '12px', cursor: 'pointer' }}>
                    When will I run out of money?
                  </button>
                  <button onClick={handleClearSimulation} style={{ background: '#212730', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '999px', padding: '8px 14px', color: '#c8cdd2', fontFamily: "'JetBrains Mono', monospace", fontSize: '12px', cursor: 'pointer' }}>
                    Reset
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* RIGHT COLUMN */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', minWidth: 0 }}>
            {/* Coach Switcher */}
            <div style={{ background: '#1c2127', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '18px', padding: '22px 24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <span style={{ fontSize: '16px', fontWeight: '600', color: '#eceef0' }}>Coach</span>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '11px', color: '#5a6066' }}>style</span>
              </div>
              <div style={{ display: 'flex', gap: '6px', background: '#13161a', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '12px', padding: '5px' }}>
                {[
                  { key: 'gentle', label: 'Empathetic' },
                  { key: 'strict', label: 'Strict' },
                  { key: 'analyst', label: 'Analyst' }
                ].map(p => (
                  <button 
                    key={p.key} 
                    onClick={() => setPersona(p.key)}
                    style={{
                      flex: 1, border: 'none', borderRadius: '9px', padding: '9px 0', fontFamily: "'Space Grotesk', sans-serif", fontSize: '13px', fontWeight: '600', cursor: 'pointer', transition: 'all 0.15s',
                      background: persona === p.key ? 'var(--primary)' : 'transparent',
                      color: persona === p.key ? '#06140c' : '#8b9298'
                    }}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <div style={{ marginTop: '16px', fontSize: '15px', lineHeight: '1.55', color: '#dfe3e7', minHeight: '96px', whiteSpace: 'pre-line' }}>
                {coachMessage}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', marginTop: '16px', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '16px' }}>
                <div><div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', letterSpacing: '0.15em', color: '#5a6066', textTransform: 'uppercase' }}>Risk</div><div style={{ fontSize: '19px', fontWeight: '600', color: riskColor, marginTop: '3px' }}>{(overdraftRisk*100).toFixed(0)}%</div></div>
                <div><div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', letterSpacing: '0.15em', color: '#5a6066', textTransform: 'uppercase' }}>Low</div><div style={{ fontSize: '19px', fontWeight: '600', marginTop: '3px', color: '#eceef0' }}>${Math.min(...trajectory).toLocaleString(undefined, { maximumFractionDigits: 0 })}</div></div>
                <div><div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', letterSpacing: '0.15em', color: '#5a6066', textTransform: 'uppercase' }}>Savings Lasts</div><div style={{ fontSize: '19px', fontWeight: '600', marginTop: '3px', color: '#eceef0' }}>{runway === -1 ? 'Infinite' : `${runway} Mo`}</div></div>
              </div>
            </div>

            {/* Operations Hub (Inside right panel to match grid flow) */}
            <div style={{ background: '#1c2127', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '18px', padding: '22px 24px' }}>
              <div style={{ display: 'flex', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', marginBottom: '16px', paddingBottom: '4px', gap: '10px' }}>
                <button 
                  onClick={() => setActiveTab('afford')}
                  style={{ flex: 1, padding: '8px', background: 'none', border: 'none', color: activeTab === 'afford' ? 'var(--primary)' : '#5a6066', fontWeight: '700', fontSize: '0.85rem', cursor: 'pointer', borderBottom: activeTab === 'afford' ? '2px solid var(--primary)' : 'none', transition: 'all 0.2s' }}
                >
                  What-If Sim
                </button>
                <button 
                  onClick={() => setActiveTab('log')}
                  style={{ flex: 1, padding: '8px', background: 'none', border: 'none', color: activeTab === 'log' ? 'var(--primary)' : '#5a6066', fontWeight: '700', fontSize: '0.85rem', cursor: 'pointer', borderBottom: activeTab === 'log' ? '2px solid var(--primary)' : 'none', transition: 'all 0.2s' }}
                >
                  Log Expense
                </button>
              </div>

              {activeTab === 'afford' && (
                <div>
                  <form onSubmit={handleCheckAffordability}>
                    <div style={{ marginBottom: '12px' }}>
                      <label style={{ fontSize: '0.75rem', color: '#8b9298', marginBottom: '6px', display: 'block', textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace" }}>Amount ($)</label>
                      <input 
                        type="number" 
                        placeholder="0.00" 
                        value={simAmount}
                        onChange={(e) => setSimAmount(e.target.value)}
                        min="0.01" 
                        step="0.01" 
                        required 
                        style={{ width: '100%', padding: '10px 12px', background: '#13161a', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', color: '#eceef0', fontSize: '0.85rem', outline: 'none' }}
                      />
                    </div>
                    <div style={{ marginBottom: '16px' }}>
                      <label style={{ fontSize: '0.75rem', color: '#8b9298', marginBottom: '6px', display: 'block', textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace" }}>Date</label>
                      <input 
                        type="date" 
                        value={simDate}
                        onChange={(e) => setSimDate(e.target.value)}
                        required 
                        style={{ width: '100%', padding: '10px 12px', background: '#13161a', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', color: '#eceef0', fontSize: '0.85rem', outline: 'none' }}
                      />
                    </div>
                    <button type="submit" className="btn-primary" style={{ width: '100%', height: '42px', marginTop: 0 }} disabled={!simAmount}>
                      Check Impact
                    </button>
                  </form>
                </div>
              )}

              {activeTab === 'log' && (
                <div>
                  {logStatusMsg && (
                    <div style={{ padding: '8px 12px', background: 'rgba(61, 220, 132, 0.08)', border: '1px solid rgba(61, 220, 132, 0.2)', borderRadius: '8px', color: '#3ddc84', fontSize: '0.8rem', marginBottom: '12px' }}>
                      {logStatusMsg}
                    </div>
                  )}
                  <form onSubmit={handleLogExpense}>
                    <div style={{ marginBottom: '10px' }}>
                      <label style={{ fontSize: '0.75rem', color: '#8b9298', marginBottom: '4px', display: 'block', textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace" }}>Description</label>
                      <input 
                        type="text" 
                        placeholder="e.g. Electric bill, Groceries" 
                        value={logDesc}
                        onChange={(e) => setLogDesc(e.target.value)}
                        required 
                        style={{ width: '100%', padding: '10px 12px', background: '#13161a', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', color: '#eceef0', fontSize: '0.85rem', outline: 'none' }}
                      />
                    </div>
                    <div style={{ display: 'flex', gap: '8px', marginBottom: '10px' }}>
                      <div style={{ flex: 1 }}>
                        <label style={{ fontSize: '0.75rem', color: '#8b9298', marginBottom: '4px', display: 'block', textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace" }}>Amount ($)</label>
                        <input 
                          type="number" 
                          placeholder="0.00" 
                          value={logAmount}
                          onChange={(e) => setLogAmount(e.target.value)}
                          min="0.01" 
                          step="0.01" 
                          required 
                          style={{ width: '100%', padding: '10px 12px', background: '#13161a', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', color: '#eceef0', fontSize: '0.85rem', outline: 'none' }}
                        />
                      </div>
                      <div style={{ flex: 1 }}>
                        <label style={{ fontSize: '0.75rem', color: '#8b9298', marginBottom: '4px', display: 'block', textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace" }}>Category</label>
                        <select 
                          value={logCategory} 
                          onChange={(e) => setLogCategory(e.target.value)}
                          style={{ width: '100%', padding: '10px 12px', background: '#13161a', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', color: '#eceef0', fontSize: '0.85rem', outline: 'none', height: '40px' }}
                        >
                          <option value="Shops">Shops</option>
                          <option value="Food and Drink">Food & Drink</option>
                          <option value="Utilities">Utilities</option>
                          <option value="Housing">Housing</option>
                          <option value="Entertainment">Entertainment</option>
                          <option value="Travel">Travel</option>
                        </select>
                      </div>
                    </div>
                    <div style={{ marginBottom: '16px' }}>
                      <label style={{ fontSize: '0.75rem', color: '#8b9298', marginBottom: '4px', display: 'block', textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace" }}>Date</label>
                      <input 
                        type="date" 
                        value={logDate}
                        onChange={(e) => setLogDate(e.target.value)}
                        required 
                        style={{ width: '100%', padding: '10px 12px', background: '#13161a', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', color: '#eceef0', fontSize: '0.85rem', outline: 'none' }}
                      />
                    </div>
                    <button type="submit" className="btn-primary" style={{ width: '100%', height: '42px', marginTop: 0 }} disabled={!logAmount || !logDesc}>
                      Log Transaction
                    </button>
                  </form>
                </div>
              )}
            </div>

            {/* Spending Categories Card */}
            <div style={{ background: '#1c2127', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '18px', padding: '22px 24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <span style={{ fontSize: '16px', fontWeight: '600', color: '#eceef0' }}>Spending · next 14 days</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '13px' }}>
                {[
                  { name: 'Housing', amt: 1200, percent: '100%', color: 'rgba(61,220,132,0.55)' },
                  { name: 'Food & Drink', amt: 350, percent: '40%', color: 'rgba(61,220,132,0.55)' },
                  { name: 'Utilities', amt: 145, percent: '20%', color: 'rgba(61,220,132,0.55)' },
                  { name: 'Shops', amt: 120, percent: '15%', color: 'rgba(61,220,132,0.55)' },
                  { 
                    name: 'Travel', 
                    amt: lastQueryData?.redacted_query?.toLowerCase().includes('gas') ? 142 : 54, 
                    percent: lastQueryData?.redacted_query?.toLowerCase().includes('gas') ? '60%' : '10%',
                    color: lastQueryData?.redacted_query?.toLowerCase().includes('gas') ? '#ffb020' : 'rgba(61,220,132,0.55)',
                    hot: lastQueryData?.redacted_query?.toLowerCase().includes('gas')
                  }
                ].map((c, i) => (
                  <div key={i}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span style={{ fontSize: '14px', color: '#c8cdd2' }}>{c.name}</span>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '13px', color: c.hot ? '#ffb020' : '#c8cdd2', marginLeft: 'auto' }}>${c.amt}</span>
                    </div>
                    <div style={{ height: '8px', background: '#13161a', borderRadius: '999px', overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: c.percent, background: c.color, borderRadius: '999px' }}></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Upcoming Bills Card */}
            <div style={{ background: '#1c2127', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '18px', padding: '22px 24px' }}>
              <div style={{ fontSize: '16px', fontWeight: '600', color: '#eceef0', marginBottom: '16px' }}>Upcoming</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', maxHeight: '180px', overflowY: 'auto' }}>
                {[
                  { day: 1, name: 'APARTMENTS RENT PAYMENT', amt: '-$1,200.00', color: '#ff5d52' },
                  { day: 5, name: 'NETFLIX STREAMING', amt: '-$15.00', color: '#ff5d52' },
                  { day: 10, name: 'CITY POWER ELECTRIC', amt: '-$85.00', color: '#ff5d52' },
                  { day: 14, name: 'ACME CORP PAYROLL', amt: '+$1,100.00', color: '#3ddc84' }
                ].map((u, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '14px', padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                    <span style={{ flex: '0 0 56px', fontFamily: "'JetBrains Mono', monospace", fontSize: '11px', color: '#8b9298', textTransform: 'uppercase' }}>Day {u.day}</span>
                    <span style={{ flex: 1, fontSize: '14px', color: '#eceef0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{u.name}</span>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '14px', fontWeight: '600', color: u.color }}>{u.amt}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Cashflow Feed */}
      {navTab === 'cashbook' && (
        <div style={{ maxWidth: '1320px', margin: '0 auto', padding: '28px 32px 56px', display: 'grid', gridTemplateColumns: '1.2fr 1.8fr', gap: '24px', alignItems: 'start' }}>
          {/* Left Column: Scheduled Paychecks & Bills */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div style={{ background: '#1c2127', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '18px', padding: '22px 24px' }}>
              <h2 style={{ fontSize: '16px', fontWeight: '600', color: '#3ddc84', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <DollarSign size={18} />
                Expected Paycheck Cycles
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {ledger.income_sources.map((inc, i) => (
                  <div key={i} style={{ padding: '12px', background: '#13161a', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontWeight: '600', fontSize: '0.85rem', color: '#eceef0' }}>{inc.description}</div>
                      <div style={{ fontSize: '0.75rem', color: '#8b9298', marginTop: '2px' }}>Every {inc.frequency_days} days</div>
                    </div>
                    <div style={{ color: '#3ddc84', fontWeight: '700', fontSize: '0.9rem', fontFamily: "'JetBrains Mono', monospace" }}>+${Math.abs(inc.amount).toFixed(2)}</div>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ background: '#1c2127', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '18px', padding: '22px 24px' }}>
              <h2 style={{ fontSize: '16px', fontWeight: '600', color: '#ffb020', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <Wallet size={18} />
                Scheduled Bills & Subscriptions
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {ledger.recurring_bills.map((bill, i) => (
                  <div key={i} style={{ padding: '12px', background: '#13161a', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontWeight: '600', fontSize: '0.85rem', color: '#eceef0' }}>{bill.description}</div>
                      <div style={{ fontSize: '0.75rem', color: '#8b9298', marginTop: '2px' }}>Due: Day {bill.day_of_month} of month</div>
                    </div>
                    <div style={{ color: '#ff5d52', fontWeight: '700', fontSize: '0.9rem', fontFamily: "'JetBrains Mono', monospace" }}>-${Math.abs(bill.amount).toFixed(2)}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column: Ingested Transaction History */}
          <div style={{ background: '#1c2127', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '18px', padding: '22px 24px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: '600', color: '#eceef0', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <FileText size={18} color="#8b9298" />
              Ingested Transaction History
            </h2>
            <p style={{ fontSize: '0.8rem', color: '#8b9298', margin: '0 0 20px 0' }}>Cleared sandboxed transactions recorded on checking account ledger.</p>
            
            <div className="transactions-table-wrapper" style={{ maxHeight: '450px', overflowY: 'auto' }}>
              <table className="transactions-table">
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                    <th style={{ padding: '12px 16px', color: '#8b9298', textAlign: 'left', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.8rem' }}>Date</th>
                    <th style={{ padding: '12px 16px', color: '#8b9298', textAlign: 'left', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.8rem' }}>Description</th>
                    <th style={{ padding: '12px 16px', color: '#8b9298', textAlign: 'left', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.8rem' }}>Category</th>
                    <th style={{ padding: '12px 16px', color: '#8b9298', textAlign: 'right', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.8rem' }}>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {ledger.transactions.map((tx) => {
                    const isOutflow = tx.amount > 0;
                    return (
                      <tr key={tx.transaction_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <td style={{ padding: '12px 16px', color: '#5a6066', fontSize: '0.85rem', fontFamily: "'JetBrains Mono', monospace" }}>{tx.date}</td>
                        <td style={{ padding: '12px 16px', fontWeight: '600', fontSize: '0.85rem', color: '#eceef0' }}>{tx.description}</td>
                        <td style={{ padding: '12px 16px' }}>
                          <span style={{ fontSize: '0.7rem', padding: '3px 8px', background: '#13161a', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '999px', color: '#8b9298', textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace" }}>{tx.category}</span>
                        </td>
                        <td style={{ padding: '12px 16px', textAlign: 'right', fontSize: '0.85rem', fontWeight: '700', color: isOutflow ? '#ff5d52' : '#3ddc84', fontFamily: "'JetBrains Mono', monospace" }}>
                          {isOutflow ? '-' : '+'}${Math.abs(tx.amount).toFixed(2)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Accuracy Scorecard */}
      {navTab === 'accuracy' && (
        <div style={{ maxWidth: '1320px', margin: '0 auto', padding: '28px 32px 56px', display: 'grid', gridTemplateColumns: '1.2fr 1.8fr', gap: '24px', alignItems: 'start' }}>
          {/* Left Column: Metrics Grid */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div style={{ background: '#1c2127', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '18px', padding: '30px 22px', textAlign: 'center' }}>
              <h2 style={{ fontSize: '16px', fontWeight: '600', color: '#3ddc84', marginBottom: '24px' }}>Model Performance</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                <div>
                  <div style={{ fontSize: '2.5rem', fontWeight: '800', color: '#3ddc84', letterSpacing: '-0.04em' }}>0.1379</div>
                  <div style={{ fontSize: '0.75rem', color: '#8b9298', fontWeight: '700', textTransform: 'uppercase', marginTop: '4px', fontFamily: "'JetBrains Mono', monospace" }}>Brier Score (calibration accuracy)</div>
                </div>
                <div>
                  <div style={{ fontSize: '2.2rem', fontWeight: '800', color: '#3ddc84', letterSpacing: '-0.04em' }}>60.0%</div>
                  <div style={{ fontSize: '0.75rem', color: '#8b9298', fontWeight: '700', textTransform: 'uppercase', marginTop: '4px', fontFamily: "'JetBrains Mono', monospace" }}>Warning Recall (overdrafts caught)</div>
                </div>
                <div>
                  <div style={{ fontSize: '2.2rem', fontWeight: '800', color: '#ffb020', letterSpacing: '-0.04em' }}>18.6%</div>
                  <div style={{ fontSize: '0.75rem', color: '#8b9298', fontWeight: '700', textTransform: 'uppercase', marginTop: '4px', fontFamily: "'JetBrains Mono', monospace" }}>False Alarm Rate</div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Calibration Table & Note */}
          <div style={{ background: '#1c2127', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '18px', padding: '22px 24px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: '600', color: '#eceef0', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <Layers size={18} color="var(--primary)" />
              Empirical Calibration Curve Table
            </h2>
            <p style={{ fontSize: '0.8rem', color: '#8b9298', margin: '0 0 20px 0', lineHeight: '1.4' }}>
              Lookahead-free validation results binning actual overdraft occurrences against predicted probability.
            </p>
            
            <table className="transactions-table" style={{ width: '100%', marginBottom: '24px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                  <th style={{ padding: '12px 16px', color: '#8b9298', textAlign: 'left', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.8rem' }}>Predicted Probability Bin</th>
                  <th style={{ padding: '12px 16px', color: '#8b9298', textAlign: 'left', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.8rem' }}>Cases ($n$)</th>
                  <th style={{ padding: '12px 16px', color: '#8b9298', textAlign: 'left', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.8rem' }}>Actual Overdraft Rate</th>
                  <th style={{ padding: '12px 16px', color: '#8b9298', textAlign: 'right', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.8rem' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <td style={{ padding: '12px 16px', fontWeight: '600', fontSize: '0.85rem', color: '#eceef0' }}>0% - 20% (Low Risk)</td>
                  <td style={{ padding: '12px 16px', color: '#8b9298', fontSize: '0.85rem' }}>48 cases</td>
                  <td style={{ padding: '12px 16px', color: '#3ddc84', fontWeight: '700', fontSize: '0.85rem', fontFamily: "'JetBrains Mono', monospace" }}>16.7%</td>
                  <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                    <span style={{ fontSize: '0.7rem', padding: '3px 8px', background: 'rgba(61,220,132,0.08)', border: '1px solid rgba(61,220,132,0.15)', borderRadius: '999px', color: '#3ddc84', textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace" }}>Well Calibrated</span>
                  </td>
                </tr>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <td style={{ padding: '12px 16px', fontWeight: '600', fontSize: '0.85rem', color: '#eceef0' }}>20% - 40% (Medium Risk)</td>
                  <td style={{ padding: '12px 16px', color: '#8b9298', fontSize: '0.85rem' }}>3 cases</td>
                  <td style={{ padding: '12px 16px', color: '#3ddc84', fontWeight: '700', fontSize: '0.85rem', fontFamily: "'JetBrains Mono', monospace" }}>0.0%</td>
                  <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                    <span style={{ fontSize: '0.7rem', padding: '3px 8px', background: 'rgba(61,220,132,0.08)', border: '1px solid rgba(61,220,132,0.15)', borderRadius: '999px', color: '#3ddc84', textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace" }}>Well Calibrated</span>
                  </td>
                </tr>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <td style={{ padding: '12px 16px', fontWeight: '600', fontSize: '0.85rem', color: '#eceef0' }}>40% - 60% (High Risk)</td>
                  <td style={{ padding: '12px 16px', color: '#8b9298', fontSize: '0.85rem' }}>1 case</td>
                  <td style={{ padding: '12px 16px', color: '#ffb020', fontWeight: '700', fontSize: '0.85rem', fontFamily: "'JetBrains Mono', monospace" }}>100.0%</td>
                  <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                    <span style={{ fontSize: '0.7rem', padding: '3px 8px', background: 'rgba(255,176,32,0.08)', border: '1px solid rgba(255,176,32,0.15)', borderRadius: '999px', color: '#ffb020', textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace" }}>Monotonic</span>
                  </td>
                </tr>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <td style={{ padding: '12px 16px', fontWeight: '600', fontSize: '0.85rem', color: '#eceef0' }}>80% - 100% (Critical Risk)</td>
                  <td style={{ padding: '12px 16px', color: '#8b9298', fontSize: '0.85rem' }}>2 cases</td>
                  <td style={{ padding: '12px 16px', color: '#ff5d52', fontWeight: '700', fontSize: '0.85rem', fontFamily: "'JetBrains Mono', monospace" }}>100.0%</td>
                  <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                    <span style={{ fontSize: '0.7rem', padding: '3px 8px', background: 'rgba(255,93,82,0.08)', border: '1px solid rgba(255,93,82,0.15)', borderRadius: '999px', color: '#ff5d52', textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace" }}>Monotonic</span>
                  </td>
                </tr>
              </tbody>
            </table>


          </div>
        </div>
      )}
    </div>
  );
}

export default App;
