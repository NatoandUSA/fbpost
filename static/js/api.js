export async function apiRequest(endpoint, options = {}) {
    const res = await fetch(endpoint, {
        headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
        ...options,
    });
    if (!res.ok) {
        let errMessage = `HTTP error ${res.status}`;
        try {
            const errData = await res.json();
            errMessage = errData.error || errData.message || errMessage;
        } catch (_) {}
        throw new Error(errMessage);
    }
    return res.json();
}

export const API = {
    getStatus: () => apiRequest('/api/status'),
    getAppInfo: () => apiRequest('/api/app-info'),
    getJobs: (limit = 20) => apiRequest(`/api/jobs?limit=${limit}`),
    getJob: (id) => apiRequest(`/api/jobs/${id}`),
    cancelJob: (id) => apiRequest(`/api/jobs/${id}/cancel`, { method: 'POST' }),
    cancelActive: () => apiRequest('/api/cancel', { method: 'POST' }),
    backupDatabase: () => apiRequest('/api/backup', { method: 'POST' }),
};
