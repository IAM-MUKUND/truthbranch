import type {
  ChangeRequest,
  ChangeRequestDetail,
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export async function fetchHealth(): Promise<{ status: string; falkordb: string; agent_mode: string }> {
  const res = await fetch(`${API_BASE}/api/health`);
  return res.json();
}

export async function fetchChangeRequests(): Promise<ChangeRequest[]> {
  const res = await fetch(`${API_BASE}/api/change-requests`);
  return res.json();
}

export async function fetchChangeRequestDetail(id: string): Promise<ChangeRequestDetail> {
  const res = await fetch(`${API_BASE}/api/change-requests/${id}`);
  if (!res.ok) {
    throw new Error(`Failed to load Change Request '${id}'`);
  }
  return res.json();
}

export async function createChangeRequest(payload: {
  title: string;
  fact_key: string;
  new_value: any;
  source_id?: string;
  created_by?: string;
}): Promise<ChangeRequest> {
  const res = await fetch(`${API_BASE}/api/change-requests`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to create Change Request');
  }
  return res.json();
}

export async function runAgentReview(id: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/change-requests/${id}/agent-review`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Agent review failed');
  }
  return res.json();
}

export async function analyzeChangeRequest(id: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/change-requests/${id}/analyze`, {
    method: 'POST',
  });
  return res.json();
}

export async function proposeEdits(id: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/change-requests/${id}/propose-edits`, {
    method: 'POST',
  });
  return res.json();
}

export async function submitChangeRequest(id: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/change-requests/${id}/submit`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Submission failed');
  }
  return res.json();
}

export async function approveChangeRequest(id: string, reviewer = 'Admin'): Promise<any> {
  const res = await fetch(`${API_BASE}/api/change-requests/${id}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reviewer }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Approval failed');
  }
  return res.json();
}

export async function rejectChangeRequest(id: string, reviewer = 'Admin', reason = 'Rejected by reviewer'): Promise<any> {
  const res = await fetch(`${API_BASE}/api/change-requests/${id}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reviewer, reason }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Rejection failed');
  }
  return res.json();
}

export async function mergeChangeRequest(id: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/change-requests/${id}/merge`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Merge failed');
  }
  return res.json();
}

export async function resetDemo(withContradiction = false): Promise<any> {
  const res = await fetch(`${API_BASE}/api/admin/reset-demo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ with_contradiction: withContradiction }),
  });
  return res.json();
}
