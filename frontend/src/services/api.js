/*
 * IntelliDoc API Service
 * ======================
 * Centralized API client for communicating with the FastAPI backend.
 * 
 * Uses Axios for HTTP requests with:
 * - Base URL configuration
 * - JWT token auto-injection
 * - Error interceptors
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Create Axios instance with defaults
const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// ── Request Interceptor: Attach JWT token ─────────────────
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('intellidoc_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// ── Response Interceptor: Handle errors ───────────────────
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('intellidoc_token');
            localStorage.removeItem('intellidoc_user');
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);

// ── Document APIs ─────────────────────────────────────────

export const documentAPI = {
    upload: (file, onProgress) => {
        const formData = new FormData();
        formData.append('file', file);
        return api.post('/api/documents/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            onUploadProgress: onProgress,
        });
    },

    list: (page = 1, pageSize = 20, status = null) => {
        const params = { page, page_size: pageSize };
        if (status) params.status = status;
        return api.get('/api/documents/', { params });
    },

    get: (id) => api.get(`/api/documents/${id}`),

    getStatus: (id) => api.get(`/api/documents/${id}/status`),

    getDownloadUrl: (id) => api.get(`/api/documents/${id}/download`),

    delete: (id) => api.delete(`/api/documents/${id}`),

    getStats: () => api.get('/api/documents/stats/overview'),
};

// ── ML Processing APIs ────────────────────────────────────

export const mlAPI = {
    runOCR: (docId) => api.post(`/api/ml/${docId}/ocr`),

    classify: (docId) => api.post(`/api/ml/${docId}/classify`),

    extractEntities: (docId) => api.post(`/api/ml/${docId}/ner`),

    summarize: (docId) => api.post(`/api/ml/${docId}/summarize`),

    analyzeImage: (docId) => api.post(`/api/ml/${docId}/analyze`),

    processAll: (docId) => api.post(`/api/ml/${docId}/process`),
};

// ── RAG Q&A APIs ──────────────────────────────────────────

export const ragAPI = {
    ask: (question, documentIds = null, topK = 5) =>
        api.post('/api/rag/ask', {
            question,
            document_ids: documentIds,
            top_k: topK,
        }),

    search: (query, topK = 10) =>
        api.post('/api/rag/search', { query, top_k: topK }),

    indexDocument: (docId) => api.post(`/api/rag/${docId}/index`),

    removeFromIndex: (docId) => api.delete(`/api/rag/${docId}/index`),

    getStats: () => api.get('/api/rag/stats'),
};

// ── Auth APIs ─────────────────────────────────────────────

export const authAPI = {
    register: (data) => api.post('/api/auth/register', data),

    login: (username, password) =>
        api.post('/api/auth/login', { username, password }),

    getMe: () => api.get('/api/auth/me'),
};

export default api;
