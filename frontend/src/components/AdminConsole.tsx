import React, { useEffect, useState } from 'react';
import {
  fetchHealth,
  fetchChangeRequests,
  fetchChangeRequestDetail,
  createChangeRequest,
  runAgentReview,
  submitChangeRequest,
  approveChangeRequest,
  rejectChangeRequest,
  mergeChangeRequest,
  resetDemo,
  fetchEntities,
  fetchDatasetCatalog,
  activateDataset,
} from '../api';
import type {
  ChangeRequest,
  ChangeRequestDetail,
  EntityData,
  FactEntity,
  PersonEntity,
  SourceEntity,
  CatalogEntry,
} from '../types';

export function formatValueWithUnit(val: any, unit?: string): string {
  if (val === undefined || val === null || val === '') return '-';
  if (!unit || unit === 'USD') {
    return `$${val}`;
  }
  if (unit === 'kUSD') return `$${val}k`;
  if (unit === 'MUSD') return `$${val}M`;
  if (unit === 'percent') return `${val}%`;
  if (unit === 'chars') return `${val} characters`;
  if (unit === 'per_min') return `${val}/min`;

  const singularUnits: Record<string, string> = {
    days: 'day',
    hours: 'hour',
    minutes: 'minute',
    weeks: 'week',
    months: 'month',
    years: 'year',
    seats: 'seat',
    codes: 'code',
    people: 'person',
  };

  const num = Number(val);
  if (!isNaN(num) && num === 1 && singularUnits[unit]) {
    return `1 ${singularUnits[unit]}`;
  }
  return `${val} ${unit}`;
}

interface AdminConsoleProps {
  onSwitchToChat: () => void;
}

export default function AdminConsole({ onSwitchToChat }: AdminConsoleProps) {
  const [health, setHealth] = useState<{ status: string; falkordb: string; agent_mode: string } | null>(null);
  const [crs, setCrs] = useState<ChangeRequest[]>([]);
  const [selectedCrId, setSelectedCrId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ChangeRequestDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [agentRunning, setAgentRunning] = useState<boolean>(false);
  const [showModal, setShowModal] = useState<boolean>(false);

  // Multi-Company Dataset Catalog State
  const [catalog, setCatalog] = useState<CatalogEntry[]>([]);
  const [activeDataset, setActiveDataset] = useState<string>('lumen');
  const [switchFeedback, setSwitchFeedback] = useState<string | null>(null);

  // Dynamic Entities State
  const [entities, setEntities] = useState<EntityData>({ people: [], facts: [], sources: [], documents: [] });

  // Custom Change Form State
  const [selectedFactKey, setSelectedFactKey] = useState<string>('');
  const [customFactKey, setCustomFactKey] = useState<string>('');
  const [currentFactVal, setCurrentFactVal] = useState<string>('-');
  const [newVal, setNewVal] = useState<string>('');
  const [selectedPersonId, setSelectedPersonId] = useState<string>('');
  const [customAuthor, setCustomAuthor] = useState<string>('');
  const [selectedSourceId, setSelectedSourceId] = useState<string>('');
  const [customSourceId, setCustomSourceId] = useState<string>('');
  const [newTitle, setNewTitle] = useState<string>('');

  useEffect(() => {
    loadInitialData();
    loadEntities();
  }, []);

  useEffect(() => {
    if (selectedCrId) {
      loadDetail(selectedCrId);
    }
  }, [selectedCrId]);

  async function loadInitialData() {
    try {
      const h = await fetchHealth();
      setHealth(h);
      const cat = await fetchDatasetCatalog();
      setCatalog(cat.catalog);
      setActiveDataset(cat.active_dataset);
      const list = await fetchChangeRequests();
      setCrs(list);
      if (list.length > 0 && !selectedCrId) {
        setSelectedCrId(list[0].id);
      }
    } catch (err) {
      console.error('Error loading initial data:', err);
    }
  }

  async function handleSwitchDataset(newId: string) {
    try {
      setLoading(true);
      const res = await activateDataset(newId, false);
      setActiveDataset(newId);
      setSwitchFeedback(res.message);
      setTimeout(() => setSwitchFeedback(null), 4000);

      // Reload entities, catalog, and change requests
      await loadEntities();
      const cat = await fetchDatasetCatalog();
      setCatalog(cat.catalog);
      const list = await fetchChangeRequests();
      setCrs(list);
      setSelectedCrId(list.length > 0 ? list[0].id : null);
      if (list.length === 0) {
        setDetail(null);
      }
    } catch (err: any) {
      alert('Failed to switch dataset: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadEntities() {
    try {
      const data = await fetchEntities();
      setEntities(data);
      if (data.facts.length > 0) {
        const first = data.facts[0];
        setSelectedFactKey(first.key);
        setCurrentFactVal(formatValueWithUnit(first.value, first.unit));
        setNewTitle(`Update ${first.key}`);
      }
      if (data.people.length > 0) {
        setSelectedPersonId(data.people[0].id);
      }
      if (data.sources.length > 0) {
        setSelectedSourceId(data.sources[0].id);
      }
    } catch (err) {
      console.error('Error loading entities:', err);
    }
  }

  async function loadDetail(id: string) {
    try {
      setLoading(true);
      const d = await fetchChangeRequestDetail(id);
      setDetail(d);
    } catch (err) {
      console.error('Error loading detail:', err);
    } finally {
      setLoading(false);
    }
  }

  function handleFactChange(key: string) {
    setSelectedFactKey(key);
    if (key !== '__custom__') {
      const matched = entities.facts.find((f) => f.key === key);
      if (matched) {
        setCurrentFactVal(formatValueWithUnit(matched.value, matched.unit));
        setNewTitle(`Update ${matched.key}`);
      }
    } else {
      setCurrentFactVal('N/A (New Fact)');
      setNewTitle('Custom Fact Update');
    }
  }

  async function handleResetDemo(withContradiction = false) {
    try {
      setLoading(true);
      await resetDemo(withContradiction);
      await loadEntities();
      const list = await fetchChangeRequests();
      setCrs(list);
      if (list.length > 0) {
        setSelectedCrId(list[0].id);
      } else {
        setSelectedCrId(null);
        setDetail(null);
      }
    } catch (err) {
      alert('Reset failed: ' + err);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateCR(e: React.FormEvent) {
    e.preventDefault();
    try {
      setLoading(true);

      const targetKey = selectedFactKey === '__custom__' ? customFactKey : selectedFactKey;
      let authorName = customAuthor;
      if (selectedPersonId !== '__custom__') {
        const p = entities.people.find((item) => item.id === selectedPersonId);
        authorName = p ? p.name : selectedPersonId;
      }
      const sourceId = selectedSourceId === '__custom__' ? customSourceId : selectedSourceId;

      const cr = await createChangeRequest({
        title: newTitle || `Update ${targetKey}`,
        fact_key: targetKey,
        new_value: isNaN(Number(newVal)) ? newVal : Number(newVal),
        source_id: sourceId || undefined,
        created_by: authorName || 'Knowledge Governor',
      });

      setShowModal(false);
      const list = await fetchChangeRequests();
      setCrs(list);
      setSelectedCrId(cr.id);
    } catch (err: any) {
      alert('Creation failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleQuickScenarioA() {
    try {
      setLoading(true);
      const isCloud = activeDataset === 'cloudgrid';
      const isMeridian = activeDataset === 'meridian';
      const cr = await createChangeRequest(
        isCloud
          ? {
              title: 'Raise H100 hourly rate to $4.25',
              fact_key: 'compute.h100.hourly',
              new_value: 4.25,
              source_id: 'src:infra_board_resolution_2026',
              created_by: 'Dave Ross',
            }
          : isMeridian
          ? {
              title: 'Update Support Refund Window to 25 Days',
              fact_key: 'support.refund.days',
              new_value: 25,
              source_id: 'src:pricing_committee_memo_2026_10',
              created_by: 'Lucy Evans',
            }
          : {
              title: 'Q4 Enterprise Price Adjustment',
              fact_key: 'pricing.pro.monthly',
              new_value: 59,
              source_id: 'src:pricing_committee_memo_2026_10',
              created_by: 'Maya Rao',
            }
      );
      const list = await fetchChangeRequests();
      setCrs(list);
      setSelectedCrId(cr.id);
    } catch (err: any) {
      alert('Failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleQuickScenarioB() {
    try {
      setLoading(true);
      const isCloud = activeDataset === 'cloudgrid';
      const isMeridian = activeDataset === 'meridian';
      const cr = await createChangeRequest(
        isCloud
          ? {
              title: 'Raise H100 hourly rate to $4.25 (Discord leak)',
              fact_key: 'compute.h100.hourly',
              new_value: 4.25,
              source_id: 'src:discord_rumor_2026',
              created_by: 'Anonymous',
            }
          : isMeridian
          ? {
              title: 'Unverified Refund Policy Rumor (15 Days)',
              fact_key: 'support.refund.days',
              new_value: 15,
              source_id: 'src:slack_rumor_2026_10',
              created_by: 'Anonymous',
            }
          : {
              title: 'Slack Rumor Price Cut',
              fact_key: 'pricing.pro.monthly',
              new_value: 39,
              source_id: 'src:slack_rumor_2026_10',
              created_by: 'Anonymous',
            }
      );
      const list = await fetchChangeRequests();
      setCrs(list);
      setSelectedCrId(cr.id);
    } catch (err: any) {
      alert('Failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleRunAgent() {
    if (!selectedCrId) return;
    try {
      setAgentRunning(true);
      await runAgentReview(selectedCrId);
      await loadDetail(selectedCrId);
      const list = await fetchChangeRequests();
      setCrs(list);
    } catch (err: any) {
      alert('Agent Review Error: ' + err.message);
    } finally {
      setAgentRunning(false);
    }
  }

  async function handleSubmit() {
    if (!selectedCrId) return;
    try {
      setLoading(true);
      await submitChangeRequest(selectedCrId);
      await loadDetail(selectedCrId);
      const list = await fetchChangeRequests();
      setCrs(list);
    } catch (err: any) {
      alert('Submission failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleApprove() {
    if (!selectedCrId) return;
    try {
      setLoading(true);
      await approveChangeRequest(selectedCrId, 'Lead Admin');
      await loadDetail(selectedCrId);
      const list = await fetchChangeRequests();
      setCrs(list);
    } catch (err: any) {
      alert('Approval failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleReject() {
    if (!selectedCrId) return;
    const reason = prompt('Please enter rejection reason:', 'Policy non-compliance');
    if (!reason) return;
    try {
      setLoading(true);
      await rejectChangeRequest(selectedCrId, 'Lead Admin', reason);
      await loadDetail(selectedCrId);
      const list = await fetchChangeRequests();
      setCrs(list);
    } catch (err: any) {
      alert('Rejection failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleMerge() {
    if (!selectedCrId) return;
    try {
      setLoading(true);
      await mergeChangeRequest(selectedCrId);
      await loadDetail(selectedCrId);
      await loadEntities();
      const list = await fetchChangeRequests();
      setCrs(list);
    } catch (err: any) {
      alert('Merge failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  const cr = detail?.cr;

  // Generic dynamic facts & values for currently selected CR
  const primaryDiff = detail?.diff?.facts?.find((f: any) => f.key === cr?.fact_key);
  const entityFact = entities.facts.find((f: any) => f.key === cr?.fact_key);
  const opFact = cr?.ops?.find((op: any) => op.key === cr?.fact_key);

  const factUnit = primaryDiff?.unit || opFact?.unit || entityFact?.unit || '';
  const oldValue = primaryDiff?.old_value !== undefined 
    ? primaryDiff.old_value 
    : (entityFact?.value !== undefined ? entityFact.value : '-');
  const newValue = cr?.new_value;

  const derivedDiffFacts = (detail?.diff?.facts || []).filter((f: any) => f.key !== cr?.fact_key);
  const derivedOps = (cr?.ops || []).filter((op: any) => op.derived);

  return (
    <div className="app-container">
      {/* Top Navbar */}
      <nav className="top-navbar">
        <a
          href="/"
          className="brand brand-clickable"
          onClick={(e) => {
            if (!e.ctrlKey && !e.metaKey && !e.shiftKey) {
              e.preventDefault();
              onSwitchToChat?.();
            }
          }}
          title="Return to Customer Portal (Home /)"
        >
          <div className="brand-icon">TB</div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <div className="brand-title">TruthBranch Governance</div>
            <div className="brand-subtitle" style={{ fontSize: '11px', color: '#64748b', whiteSpace: 'nowrap', lineHeight: '1.2' }}>
              Operations Console & Branch Manager
            </div>
          </div>
          <span className="brand-tag">Admin</span>
        </a>

        {/* Route Navigation Segmented Control */}
        <div className="route-nav-group">
          <a
            href="/"
            className="route-nav-tab"
            onClick={(e) => {
              if (!e.ctrlKey && !e.metaKey && !e.shiftKey) {
                e.preventDefault();
                onSwitchToChat?.();
              }
            }}
            title="Navigate to Customer Portal (/)"
          >
            <span className="route-nav-icon">💬</span>
            <span className="route-nav-text">Customer Portal</span>
            <span className="route-nav-badge">/</span>
          </a>
          <a
            href="/admin"
            className="route-nav-tab active"
            onClick={(e) => e.preventDefault()}
            title="Current Page: Admin Console (/admin)"
          >
            <span className="route-nav-icon">🛡️</span>
            <span className="route-nav-text">Admin Console</span>
            <span className="route-nav-badge">/admin</span>
          </a>
        </div>

        {/* Company Dataset Switcher */}
        <div className="active-brain-selector" style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(30, 41, 59, 0.8)', padding: '4px 8px', borderRadius: '8px', border: '1px solid #334155', flexShrink: 0 }}>
          <span className="active-brain-label" style={{ fontSize: '10px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 700, whiteSpace: 'nowrap' }}>
            Active Brain:
          </span>
          <select
            value={activeDataset}
            onChange={(e) => handleSwitchDataset(e.target.value)}
            disabled={loading}
            style={{
              background: '#0f172a',
              color: '#38bdf8',
              border: '1px solid #475569',
              borderRadius: '6px',
              padding: '3px 6px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              outline: 'none',
              maxWidth: '165px',
            }}
          >
            {catalog.map((entry) => (
              <option key={entry.id} value={entry.id}>
                {entry.name} {entry.is_seeded ? '⚡' : ''}
              </option>
            ))}
          </select>
          {switchFeedback && (
            <span style={{ fontSize: '11px', color: '#10b981', fontWeight: 600, whiteSpace: 'nowrap' }}>
              {switchFeedback}
            </span>
          )}
        </div>

        <div className="navbar-actions">
          {loading && (
            <span style={{ fontSize: '11px', color: '#818cf8', fontWeight: 600, whiteSpace: 'nowrap' }}>Syncing...</span>
          )}
          {health && (
            <span className="status-pill status-CHECKS_PASSED" style={{ fontSize: '10px', padding: '2px 7px', flexShrink: 0 }}>
              FalkorDB: {health.falkordb}
            </span>
          )}

          <button className="btn btn-secondary" onClick={handleQuickScenarioA} title="Quick Preset: Scenario A">
            {activeDataset === 'cloudgrid' 
              ? '+ Scenario A ($4.25)' 
              : activeDataset === 'meridian' 
              ? '+ Scenario A (25 Days)' 
              : '+ Scenario A ($59)'}
          </button>
          <button className="btn btn-secondary" onClick={handleQuickScenarioB} title="Quick Preset: Scenario B">
            {activeDataset === 'cloudgrid' 
              ? '+ Scenario B (Discord)' 
              : activeDataset === 'meridian' 
              ? '+ Scenario B (Slack Leak)' 
              : '+ Scenario B (Slack)'}
          </button>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>
            + Custom Change
          </button>
          <button className="btn btn-danger" onClick={() => handleResetDemo(false)} title="Reset Database to Clean State">
            Reset Demo
          </button>
        </div>
      </nav>

      {/* Main Layout */}
      <div className="main-layout">
        {/* Sidebar */}
        <aside className="sidebar">
          <div className="sidebar-header">
            <span className="sidebar-title">Change Requests</span>
            <span style={{ fontSize: '12px', color: '#94a3b8' }}>{crs.length} total</span>
          </div>

          <div className="sidebar-list">
            {crs.map((item) => (
              <div
                key={item.id}
                className={`cr-list-item ${selectedCrId === item.id ? 'active' : ''}`}
                onClick={() => setSelectedCrId(item.id)}
              >
                <div className="cr-item-top">
                  <span className="cr-item-id">{item.id}</span>
                  <span className={`status-pill status-${item.status}`}>{item.status}</span>
                </div>
                <div className="cr-item-title">{item.title}</div>
                <div className="cr-item-meta">
                  <span>{item.fact_key}</span>
                  <span>{item.created_at ? item.created_at.slice(11, 16) : ''}</span>
                </div>
              </div>
            ))}

            {crs.length === 0 && (
              <div style={{ textAlign: 'center', padding: '32px 16px', color: '#64748b', fontSize: '13px' }}>
                No active change requests. Click <b>Scenario A</b> or <b>Custom Change</b> to get started.
              </div>
            )}
          </div>
        </aside>

        {/* Detail Workspace */}
        <main className="workspace">
          {cr ? (
            <>
              {/* Header Action Banner */}
              <div className="cr-header">
                <div className="cr-header-info">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span className="cr-item-id" style={{ fontSize: '13px' }}>{cr.id}</span>
                    <span className={`status-pill status-${cr.status}`}>{cr.status}</span>
                  </div>
                  <h1 style={{ fontSize: '20px', fontWeight: 600 }}>{cr.title}</h1>
                  <div className="cr-meta-chips">
                    <span>Target: <b>{cr.fact_key}</b></span>
                    <span>&bull;</span>
                    <span>Proposer: <b>{cr.created_by}</b></span>
                    <span>&bull;</span>
                    <span>Base Rev: <b>{cr.base_revision}</b></span>
                    <span>&bull;</span>
                    <span>Branch: <code>{cr.branch_graph}</code></span>
                  </div>
                </div>

                {/* State-driven Action Bar */}
                <div className="cr-actions">
                  <button
                    className="btn btn-primary"
                    onClick={handleRunAgent}
                    disabled={agentRunning || cr.status === 'MERGED' || cr.status === 'REJECTED'}
                  >
                    {agentRunning ? 'Agent Running (gpt-oss-120b)...' : 'Run Agent Review'}
                  </button>

                  <button
                    className="btn btn-secondary"
                    onClick={handleSubmit}
                    disabled={cr.status !== 'CHECKS_PASSED'}
                  >
                    Submit for Approval
                  </button>

                  <button
                    className="btn btn-success"
                    onClick={handleApprove}
                    disabled={cr.status !== 'READY_FOR_REVIEW'}
                  >
                    Approve (Human Gate)
                  </button>

                  <button
                    className="btn btn-success"
                    onClick={handleMerge}
                    disabled={cr.status !== 'APPROVED'}
                  >
                    Merge to Main
                  </button>

                  <button
                    className="btn btn-danger"
                    onClick={handleReject}
                    disabled={cr.status === 'MERGED' || cr.status === 'REJECTED'}
                  >
                    Reject
                  </button>
                </div>
              </div>

              {/* 8 Cards Grid */}
              <div className="cards-grid">
                {/* 1. Proposed Change Card */}
                <div className="card">
                  <div className="card-header">
                    <div className="card-title">Proposed Change</div>
                    <span className="status-pill status-DRAFT">{cr.fact_key}</span>
                  </div>
                  <div className="card-body">
                    <div className="value-comparison">
                      <div className="val-box">
                        <span className="val-label">Current Value</span>
                        <span className="val-number val-old">
                          {formatValueWithUnit(oldValue, factUnit)}
                        </span>
                      </div>
                      <div className="val-arrow">&rarr;</div>
                      <div className="val-box">
                        <span className="val-label">Proposed Value</span>
                        <span className="val-number val-new">
                          {formatValueWithUnit(newValue, factUnit)}
                        </span>
                      </div>
                    </div>

                    <div style={{ fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: '#94a3b8' }}>Attached Source:</span>
                        <span style={{ fontFamily: 'var(--font-mono)' }}>{cr.source_id || 'None attached'}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ color: '#94a3b8' }}>Derived Fact Link:</span>
                        {derivedDiffFacts.length > 0 ? (
                          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px' }}>
                            {derivedDiffFacts.map((df: any) => (
                              <span key={df.key} style={{ color: '#86efac', fontFamily: 'var(--font-mono)' }}>
                                {df.key} &rarr; {formatValueWithUnit(df.new_value, df.unit || factUnit)}
                              </span>
                            ))}
                          </div>
                        ) : derivedOps.length > 0 ? (
                          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px' }}>
                            {derivedOps.map((op: any) => (
                              <span key={op.key || op.op_id} style={{ color: '#86efac', fontFamily: 'var(--font-mono)' }}>
                                {op.key} &rarr; {formatValueWithUnit(op.new_value, op.unit || factUnit)}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span style={{ color: '#64748b', fontStyle: 'italic' }}>None (Direct change only)</span>
                        )}
                      </div>
                      {cr.rejected_reason && (
                        <div style={{ color: '#fda4af', marginTop: '6px' }}>
                          <b>Rejection Reason:</b> {cr.rejected_reason}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* 2. Baseline Comparison Card */}
                <div className="card">
                  <div className="card-header">
                    <div className="card-title">Keyword vs Graph Provenance</div>
                    <span className="status-pill status-CHECKS_PASSED">Benchmark Proof</span>
                  </div>
                  <div className="card-body">
                    {(() => {
                      const naiveCount = detail?.baseline?.naive_search?.found_count ?? detail?.baseline?.naive_count ?? 0;
                      const graphCount = detail?.baseline?.graph_traversal?.found_count ?? detail?.baseline?.graph_count ?? (detail?.impact?.length || 0);
                      const missedDocs = detail?.baseline?.exact_regex?.missed_multi_hop ?? detail?.baseline?.missed_by_naive ?? [];
                      const missedCount = missedDocs.length;
                      const summary = detail?.baseline?.summary || '100% full transitive impact with verifiable provenance paths.';

                      return (
                        <>
                          <div className="metrics-row">
                            <div className="metric-card">
                              <div className="metric-title">Naive Keyword Search</div>
                              <div className="metric-val" style={{ color: '#f87171' }}>
                                {naiveCount} Docs
                              </div>
                              <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>
                                {missedCount > 0
                                  ? `Missed ${missedCount} multi-hop document${missedCount === 1 ? '' : 's'} with no literal match!`
                                  : 'Matched all direct mentions in indexed documents.'}
                              </div>
                            </div>
                            <div className="metric-card">
                              <div className="metric-title">TruthBranch Graph</div>
                              <div className="metric-val" style={{ color: '#34d399' }}>
                                {graphCount} Docs
                              </div>
                              <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>
                                {summary}
                              </div>
                            </div>
                          </div>

                          <div style={{ fontSize: '12px', color: '#cbd5e1' }}>
                            <b>Missed by Naive Search:</b>
                            {missedDocs.length > 0 ? (
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '4px' }}>
                                {missedDocs.map((d) => (
                                  <span key={d} className="path-node" style={{ color: '#fca5a5' }}>{d}</span>
                                ))}
                              </div>
                            ) : (
                              <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px', fontStyle: 'italic' }}>
                                None (Direct keyword search found all affected documents)
                              </div>
                            )}
                          </div>
                        </>
                      );
                    })()}
                  </div>
                </div>

                {/* 3. Impact Table Card (Full Width) */}
                <div className="card full-width">
                  <div className="card-header">
                    <div className="card-title">Impact Set & Shortest Provenance Paths</div>
                    <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                      {detail?.impact.length || 0} Affected Documents
                    </span>
                  </div>
                  <div className="card-body table-container">
                    <table className="tb-table">
                      <thead>
                        <tr>
                          <th>Document</th>
                          <th>Owner</th>
                          <th>System</th>
                          <th>Reason</th>
                          <th>Provenance Path</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail?.impact.map((item) => (
                          <tr key={item.doc_id}>
                            <td style={{ fontWeight: 500 }}>
                              <div>{item.title}</div>
                              <div style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: '#64748b' }}>
                                {item.doc_id}
                              </div>
                            </td>
                            <td>{item.owner_name || item.owner_id || '-'}</td>
                            <td>{item.system_name || '-'}</td>
                            <td>
                              <span className="status-pill status-DRAFT" style={{ fontSize: '10px' }}>
                                {item.reason}
                              </span>
                            </td>
                            <td>
                              <div className="path-chain">
                                {item.path.map((node, i) => (
                                  <React.Fragment key={i}>
                                    <span className="path-node">{node}</span>
                                    {i < item.path.length - 1 && <span className="path-sep">&rarr;</span>}
                                  </React.Fragment>
                                ))}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* 4. Quality Checks Panel */}
                <div className="card">
                  <div className="card-header">
                    <div className="card-title">Deterministic Quality Checks</div>
                    <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                      {detail?.checks.length || 0} Rules Evaluated
                    </span>
                  </div>
                  <div className="card-body">
                    <div className="checks-list">
                      {detail?.checks.map((chk) => (
                        <div
                          key={chk.code}
                          className={`check-item ${chk.passed ? 'pass' : chk.severity === 'BLOCK' ? 'block' : 'warn'}`}
                        >
                          <div className="check-left">
                            <span className="check-icon">
                              {chk.passed ? '✓' : chk.severity === 'BLOCK' ? '✕' : '⚠'}
                            </span>
                            <div>
                              <div className="check-name">{chk.code}</div>
                              <div className="check-msg">{chk.message}</div>
                              {!chk.passed && chk.code === 'LITERAL_VALUE_LEAK' && chk.evidence && (
                                <div style={{ fontSize: '11px', color: '#fbbf24', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                                  <span style={{ fontWeight: 600 }}>Unlinked Shadow Doc:</span>
                                  {chk.evidence.map((docId: string) => (
                                    <code key={docId} style={{ background: 'rgba(245, 158, 11, 0.18)', padding: '1px 6px', borderRadius: '4px', color: '#fde68a', fontFamily: 'var(--font-mono)' }}>
                                      {docId} {docId === 'doc:partner_faq' ? '(Partner FAQ)' : ''}
                                    </code>
                                  ))}
                                  <span style={{ color: '#94a3b8' }}>&bull; Advisory warning (does not block review or merge)</span>
                                </div>
                              )}
                            </div>
                          </div>
                          <span
                            className="status-pill"
                            style={{
                              fontSize: '10px',
                              background: chk.passed 
                                ? 'rgba(16, 185, 129, 0.2)' 
                                : chk.severity === 'WARN' 
                                ? 'rgba(245, 158, 11, 0.2)' 
                                : 'rgba(244, 63, 94, 0.2)',
                              color: chk.passed 
                                ? '#34d399' 
                                : chk.severity === 'WARN' 
                                ? '#fbbf24' 
                                : '#fb7185',
                              border: chk.passed 
                                ? '1px solid rgba(16, 185, 129, 0.3)' 
                                : chk.severity === 'WARN' 
                                ? '1px solid rgba(245, 158, 11, 0.35)' 
                                : '1px solid rgba(244, 63, 94, 0.3)',
                            }}
                          >
                            {chk.passed ? 'PASS' : chk.severity === 'WARN' ? 'WARN (ADVISORY)' : chk.severity}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* 5. Agent Reasoning Timeline */}
                <div className="card">
                  <div className="card-header">
                    <div className="card-title">Agent Tool Execution Timeline</div>
                    <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                      {detail?.steps.length || 0} Steps
                    </span>
                  </div>
                  <div className="card-body">
                    <div className="timeline">
                      {detail?.steps.map((st) => (
                        <div key={st.id || st.idx} className="timeline-step">
                          <div className="step-num">#{st.idx}</div>
                          <div className="step-content">
                            <div className="step-tool">{st.tool}</div>
                            <div className="step-summary">{st.result_summary}</div>
                            <div className="step-args">args: {JSON.stringify(st.args)}</div>
                          </div>
                        </div>
                      ))}

                      {detail?.steps.length === 0 && (
                        <div style={{ textAlign: 'center', padding: '24px 0', color: '#64748b', fontSize: '13px' }}>
                          No agent steps logged yet. Click <b>Run Agent Review</b> to execute the autonomous evaluation loop.
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* 6. Proposed Edits & Diff Viewer (Full Width) */}
                <div className="card full-width">
                  <div className="card-header">
                    <div className="card-title">Candidate Branch Proposed Edits (Diff)</div>
                    <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                      {detail?.diff.edits.length || 0} Drafted Revisions
                    </span>
                  </div>
                  <div className="card-body">
                    {detail?.diff.edits.map((edit) => (
                      <div key={edit.edit_id} className="diff-card">
                        <div className="diff-header">
                          <span>{edit.doc_title} ({edit.doc_id})</span>
                          <span className="status-pill status-READY_FOR_REVIEW">{edit.status}</span>
                        </div>
                        <div className="diff-body">
                          <div className="diff-pane before">
                            <div style={{ fontWeight: 600, marginBottom: '6px', color: '#f87171' }}>
                              - Before (kb_main)
                            </div>
                            {edit.before}
                          </div>
                          <div className="diff-pane after">
                            <div style={{ fontWeight: 600, marginBottom: '6px', color: '#4ade80' }}>
                              + After (Candidate Branch)
                            </div>
                            {edit.after}
                          </div>
                        </div>
                      </div>
                    ))}

                    {detail?.diff.edits.length === 0 && (
                      <div style={{ textAlign: 'center', padding: '24px 0', color: '#64748b', fontSize: '13px' }}>
                        No drafted edits on this candidate branch yet.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div style={{ textAlign: 'center', marginTop: '100px', color: '#94a3b8' }}>
              Select or create a Change Request to view details.
            </div>
          )}
        </main>
      </div>

      {/* Enhanced Modal with Dynamic Entity Dropdowns */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2 style={{ fontSize: '18px', fontWeight: 600 }}>Create New Change Request</h2>
            <form onSubmit={handleCreateCR} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div className="form-group">
                <label className="form-label">Change Title</label>
                <input
                  className="form-input"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Q4 Price Increase"
                  required
                />
              </div>

              {/* Dynamic Fact Dropdown */}
              <div className="form-group">
                <label className="form-label">
                  Target Fact / Policy to Change <span style={{ color: '#818cf8' }}>({currentFactVal})</span>
                </label>
                <select
                  className="form-select"
                  value={selectedFactKey}
                  onChange={(e) => handleFactChange(e.target.value)}
                >
                  {entities.facts.map((f: FactEntity) => (
                    <option key={f.id} value={f.key}>
                      {f.key} (Current: {formatValueWithUnit(f.value, f.unit)})
                    </option>
                  ))}
                  <option value="__custom__">+ Enter Custom Fact Key...</option>
                </select>

                {selectedFactKey === '__custom__' && (
                  <input
                    className="form-input"
                    style={{ marginTop: '6px' }}
                    value={customFactKey}
                    onChange={(e) => setCustomFactKey(e.target.value)}
                    placeholder="e.g. infra.aws.region or custom.metric"
                    required
                  />
                )}
              </div>

              {/* New Value */}
              <div className="form-group">
                <label className="form-label">New Proposed Value</label>
                <input
                  className="form-input"
                  value={newVal}
                  onChange={(e) => setNewVal(e.target.value)}
                  placeholder="e.g. 25"
                  required
                />
              </div>

              {/* Dynamic Proposer Dropdown */}
              <div className="form-group">
                <label className="form-label">Proposer / Author</label>
                <select
                  className="form-select"
                  value={selectedPersonId}
                  onChange={(e) => setSelectedPersonId(e.target.value)}
                >
                  {entities.people.map((p: PersonEntity) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.role})
                    </option>
                  ))}
                  <option value="__custom__">+ Enter Custom Proposer Name...</option>
                </select>

                {selectedPersonId === '__custom__' && (
                  <input
                    className="form-input"
                    style={{ marginTop: '6px' }}
                    value={customAuthor}
                    onChange={(e) => setCustomAuthor(e.target.value)}
                    placeholder="e.g. Alice Smith"
                    required
                  />
                )}
              </div>

              {/* Dynamic Verification Source Dropdown */}
              <div className="form-group">
                <label className="form-label">Verification Source</label>
                <select
                  className="form-select"
                  value={selectedSourceId}
                  onChange={(e) => setSelectedSourceId(e.target.value)}
                >
                  {entities.sources.map((s: SourceEntity) => (
                    <option key={s.id} value={s.id}>
                      {s.title} [Trust: {Math.round(s.trust * 100)}% - {s.valid ? 'Verified' : 'UNTRUSTED'}]
                    </option>
                  ))}
                  <option value="__custom__">+ Enter Custom Source ID...</option>
                </select>

                {selectedSourceId === '__custom__' && (
                  <input
                    className="form-input"
                    style={{ marginTop: '6px' }}
                    value={customSourceId}
                    onChange={(e) => setCustomSourceId(e.target.value)}
                    placeholder="e.g. src:board_resolution_2026"
                  />
                )}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Create Change Request
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
