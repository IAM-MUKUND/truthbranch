import type {
  ChangeRequest,
  ChangeRequestDetail,
  EntityData,
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

export async function fetchEntities(): Promise<EntityData> {
  const res = await fetch(`${API_BASE}/api/entities`);
  if (!res.ok) {
    throw new Error('Failed to fetch entities');
  }
  return res.json();
}

export async function sendChatMessage(messages: { role: string; content: string }[]): Promise<{ role: string; content: string; citations: string[] }> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Chat request failed');
  }
  return res.json();
}

export async function fetchDatasetCatalog(): Promise<{ active_dataset: string; catalog: any[] }> {
  const res = await fetch(`${API_BASE}/api/admin/datasets/catalog`);
  if (!res.ok) {
    throw new Error('Failed to fetch dataset catalog');
  }
  return res.json();
}

export async function activateDataset(datasetId: string, forceReseed = false): Promise<any> {
  const res = await fetch(`${API_BASE}/api/admin/datasets/activate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_id: datasetId, force_reseed: forceReseed }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to activate dataset');
  }
  return res.json();
}

export async function ingestCustomDataset(payload: any): Promise<any> {
  const res = await fetch(`${API_BASE}/api/admin/datasets/ingest?activate=true`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to ingest custom dataset');
  }
  return res.json();
}

