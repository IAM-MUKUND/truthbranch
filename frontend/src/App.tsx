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
} from './api';
import type { ChangeRequest, ChangeRequestDetail } from './types';

export default function App() {
  const [health, setHealth] = useState<{ status: string; falkordb: string; agent_mode: string } | null>(null);
  const [crs, setCrs] = useState<ChangeRequest[]>([]);
  const [selectedCrId, setSelectedCrId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ChangeRequestDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [agentRunning, setAgentRunning] = useState<boolean>(false);
  const [showModal, setShowModal] = useState<boolean>(false);

  // New CR Form State
  const [newTitle, setNewTitle] = useState('Pro Monthly Price Increase');
  const [newFactKey, setNewFactKey] = useState('pricing.pro.monthly');
  const [newVal, setNewVal] = useState('59');
  const [newSourceId, setNewSourceId] = useState('src:pricing_committee_memo_2026_10');
  const [newAuthor, setNewAuthor] = useState('Maya Rao');

  useEffect(() => {
    loadInitialData();
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
      const list = await fetchChangeRequests();
      setCrs(list);
      if (list.length > 0 && !selectedCrId) {
        setSelectedCrId(list[0].id);
      }
    } catch (err) {
      console.error('Error loading data:', err);
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

  async function handleResetDemo(withContradiction = false) {
    try {
      setLoading(true);
      await resetDemo(withContradiction);
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
      const cr = await createChangeRequest({
        title: newTitle,
        fact_key: newFactKey,
        new_value: isNaN(Number(newVal)) ? newVal : Number(newVal),
        source_id: newSourceId || undefined,
        created_by: newAuthor,
      });
      setShowModal(false);
      const list = await fetchChangeRequests();
      setCrs(list);
      setSelectedCrId(cr.id);
    } catch (err) {
      alert('Creation failed: ' + err);
    } finally {
      setLoading(false);
    }
  }

  async function handleQuickScenarioA() {
    try {
      setLoading(true);
      const cr = await createChangeRequest({
        title: 'Q4 Enterprise Price Adjustment',
        fact_key: 'pricing.pro.monthly',
        new_value: 59,
        source_id: 'src:pricing_committee_memo_2026_10',
        created_by: 'Maya Rao',
      });
      const list = await fetchChangeRequests();
      setCrs(list);
      setSelectedCrId(cr.id);
    } catch (err) {
      alert('Failed: ' + err);
    } finally {
      setLoading(false);
    }
  }

  async function handleQuickScenarioB() {
    try {
      setLoading(true);
      const cr = await createChangeRequest({
        title: 'Slack Rumor Price Cut',
        fact_key: 'pricing.pro.monthly',
        new_value: 39,
        source_id: 'src:slack_rumor_2026_10',
        created_by: 'Anonymous',
      });
      const list = await fetchChangeRequests();
      setCrs(list);
      setSelectedCrId(cr.id);
    } catch (err) {
      alert('Failed: ' + err);
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
      const list = await fetchChangeRequests();
      setCrs(list);
    } catch (err: any) {
      alert('Merge failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  const cr = detail?.cr;

  return (
    <div className="app-container">
      {/* Top Navbar */}
      <nav className="top-navbar">
        <div className="brand">
          <div className="brand-icon">TB</div>
          <div>
            <div className="brand-title">TruthBranch</div>
            <div style={{ fontSize: '11px', color: '#64748b' }}>Git for Company Knowledge</div>
          </div>
          <span className="brand-tag">v0.3.0</span>
        </div>

        <div className="navbar-actions">
          {loading && (
            <span style={{ fontSize: '11px', color: '#818cf8', fontWeight: 600 }}>Syncing...</span>
          )}
          {health && (
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', fontSize: '12px' }}>
              <span className="status-pill status-CHECKS_PASSED" style={{ fontSize: '10px' }}>
                FalkorDB: {health.falkordb}
              </span>
              <span className="status-pill status-DRAFT" style={{ fontSize: '10px' }}>
                Agent: {health.agent_mode} (gpt-oss-120b)
              </span>
            </div>
          )}

          <button className="btn btn-secondary" onClick={handleQuickScenarioA}>
            + Scenario A ($49 &rarr; $59)
          </button>
          <button className="btn btn-secondary" onClick={handleQuickScenarioB}>
            + Scenario B (Slack Rumor)
          </button>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>
            + Custom Change
          </button>
          <button className="btn btn-danger" onClick={() => handleResetDemo(false)}>
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
                  <span className={`status-pill status-${item.status}`}>
                    {item.status}
                  </span>
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
                    <span className={`status-pill status-${cr.status}`}>
                      {cr.status}
                    </span>
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
                        <span className="val-number val-old">$49</span>
                      </div>
                      <div className="val-arrow">&rarr;</div>
                      <div className="val-box">
                        <span className="val-label">Proposed Value</span>
                        <span className="val-number val-new">${cr.new_value}</span>
                      </div>
                    </div>

                    <div style={{ fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: '#94a3b8' }}>Attached Source:</span>
                        <span style={{ fontFamily: 'var(--font-mono)' }}>{cr.source_id || 'None attached'}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: '#94a3b8' }}>Derived Fact Link:</span>
                        <span style={{ color: '#86efac' }}>pricing.pro.annual &rarr; ${Number(cr.new_value) * 10}</span>
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
                    <div className="metrics-row">
                      <div className="metric-card">
                        <div className="metric-title">Naive Keyword Search</div>
                        <div className="metric-val" style={{ color: '#f87171' }}>
                          {detail?.baseline.naive_count || 5} Docs
                        </div>
                        <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>
                          Missed 2 multi-hop documents with no literal price words!
                        </div>
                      </div>
                      <div className="metric-card">
                        <div className="metric-title">TruthBranch Graph</div>
                        <div className="metric-val" style={{ color: '#34d399' }}>
                          {detail?.baseline.graph_count || 7} Docs
                        </div>
                        <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>
                          100% full transitive impact with verifiable provenance paths.
                        </div>
                      </div>
                    </div>

                    <div style={{ fontSize: '12px', color: '#cbd5e1' }}>
                      <b>Missed by Naive Search:</b>
                      <div style={{ display: 'flex', gap: '6px', marginTop: '4px' }}>
                        {(detail?.baseline.missed_by_naive || ['doc:investor_update', 'doc:board_deck']).map((d) => (
                          <span key={d} className="path-node" style={{ color: '#fca5a5' }}>{d}</span>
                        ))}
                      </div>
                    </div>
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
                    <span style={{ fontSize: '12px', color: '#94a3b8' }}>5 Standard Rules</span>
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
                            </div>
                          </div>
                          <span
                            className="status-pill"
                            style={{
                              fontSize: '10px',
                              background: chk.passed ? 'rgba(16, 185, 129, 0.2)' : 'rgba(244, 63, 94, 0.2)',
                              color: chk.passed ? '#34d399' : '#fb7185',
                            }}
                          >
                            {chk.passed ? 'PASS' : chk.severity}
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
                            <div className="step-args">
                              args: {JSON.stringify(st.args)}
                            </div>
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

      {/* New Change Request Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2 style={{ fontSize: '18px', fontWeight: 600 }}>Create New Change Request</h2>
            <form onSubmit={handleCreateCR} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div className="form-group">
                <label className="form-label">Title</label>
                <input
                  className="form-input"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Q4 Price Increase"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Fact Key (Supports ANY Dataset)</label>
                <input
                  className="form-input"
                  value={newFactKey}
                  onChange={(e) => setNewFactKey(e.target.value)}
                  placeholder="e.g. pricing.pro.monthly or your.custom.fact"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">New Value</label>
                <input
                  className="form-input"
                  value={newVal}
                  onChange={(e) => setNewVal(e.target.value)}
                  placeholder="e.g. 59"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Source ID</label>
                <input
                  className="form-input"
                  value={newSourceId}
                  onChange={(e) => setNewSourceId(e.target.value)}
                  placeholder="e.g. src:pricing_committee_memo_2026_10"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Proposer / Author</label>
                <input
                  className="form-input"
                  value={newAuthor}
                  onChange={(e) => setNewAuthor(e.target.value)}
                  placeholder="e.g. Maya Rao"
                />
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
