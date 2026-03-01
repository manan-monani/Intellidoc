/*
 * IntelliDoc — Documents Page
 * List, view, and manage documents with ML processing actions.
 */

import { useState, useEffect } from 'react';
import {
    FileText, Trash2, Download, Eye, Play,
    RefreshCw, Search, Filter
} from 'lucide-react';
import { documentAPI, mlAPI, ragAPI } from '../services/api';
import toast from 'react-hot-toast';

export default function Documents() {
    const [documents, setDocuments] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('');
    const [processingIds, setProcessingIds] = useState(new Set());
    const [selectedDoc, setSelectedDoc] = useState(null);

    useEffect(() => {
        loadDocuments();
    }, [page, filter]);

    async function loadDocuments() {
        setLoading(true);
        try {
            const res = await documentAPI.list(page, 20, filter || null);
            setDocuments(res.data.documents || []);
            setTotal(res.data.total || 0);
        } catch (err) {
            toast.error('Failed to load documents');
        } finally {
            setLoading(false);
        }
    }

    async function handleDelete(id, filename) {
        if (!confirm(`Delete "${filename}"?`)) return;
        try {
            await documentAPI.delete(id);
            toast.success('Document deleted');
            loadDocuments();
        } catch (err) {
            toast.error('Failed to delete document');
        }
    }

    async function handleDownload(id) {
        try {
            const res = await documentAPI.getDownloadUrl(id);
            window.open(res.data.download_url, '_blank');
        } catch (err) {
            toast.error('Failed to get download URL');
        }
    }

    async function handleRunML(id, type) {
        setProcessingIds((prev) => new Set(prev).add(`${id}-${type}`));
        try {
            let res;
            switch (type) {
                case 'ocr': res = await mlAPI.runOCR(id); break;
                case 'classify': res = await mlAPI.classify(id); break;
                case 'ner': res = await mlAPI.extractEntities(id); break;
                case 'summarize': res = await mlAPI.summarize(id); break;
                case 'index': res = await ragAPI.indexDocument(id); break;
                default: return;
            }
            toast.success(`${type.toUpperCase()} completed!`);
            loadDocuments();
            if (selectedDoc?.id === id) {
                setSelectedDoc((prev) => ({ ...prev, lastResult: { type, data: res.data } }));
            }
        } catch (err) {
            toast.error(`${type} failed: ${err.response?.data?.detail || 'Unknown error'}`);
        } finally {
            setProcessingIds((prev) => {
                const next = new Set(prev);
                next.delete(`${id}-${type}`);
                return next;
            });
        }
    }

    const isProcessing = (id, type) => processingIds.has(`${id}-${type}`);

    const statusBadge = (status) => {
        const map = {
            uploaded: 'badge-uploaded',
            processing: 'badge-processing',
            processed: 'badge-processed',
            indexed: 'badge-indexed',
            failed: 'badge-failed',
        };
        return `badge ${map[status] || 'badge-uploaded'}`;
    };

    function formatSize(bytes) {
        if (!bytes) return '—';
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    return (
        <div style={{ animation: 'fadeIn 0.5s ease' }}>
            <div className="page-header">
                <h2>📄 Documents</h2>
                <p>Manage your documents and run ML processing</p>
            </div>

            {/* Filters */}
            <div style={{ display: 'flex', gap: '12px', marginBottom: '24px', flexWrap: 'wrap' }}>
                <select
                    value={filter}
                    onChange={(e) => { setFilter(e.target.value); setPage(1); }}
                    className="form-input"
                    style={{ width: 'auto', minWidth: '160px' }}
                >
                    <option value="">All Statuses</option>
                    <option value="uploaded">Uploaded</option>
                    <option value="processing">Processing</option>
                    <option value="processed">Processed</option>
                    <option value="indexed">Indexed</option>
                    <option value="failed">Failed</option>
                </select>
                <button className="btn btn-secondary" onClick={loadDocuments}>
                    <RefreshCw size={16} /> Refresh
                </button>
                <span style={{ alignSelf: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                    {total} documents total
                </span>
            </div>

            {loading ? (
                <div className="loading-container"><div className="spinner" /><p>Loading...</p></div>
            ) : documents.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-icon">📄</div>
                    <h3>No documents found</h3>
                    <p>Upload documents to get started</p>
                </div>
            ) : (
                <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                    <div className="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>Filename</th>
                                    <th>Type</th>
                                    <th>Size</th>
                                    <th>Status</th>
                                    <th>Class</th>
                                    <th>ML Actions</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {documents.map((doc) => (
                                    <tr key={doc.id}>
                                        <td style={{ fontWeight: 500, maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            {doc.filename}
                                        </td>
                                        <td><span className="badge badge-uploaded">{doc.file_type}</span></td>
                                        <td style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{formatSize(doc.file_size)}</td>
                                        <td><span className={statusBadge(doc.status)}>{doc.status}</span></td>
                                        <td style={{ fontSize: '0.85rem' }}>{doc.classification || '—'}</td>
                                        <td>
                                            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                                <button
                                                    className="btn btn-secondary btn-sm"
                                                    onClick={() => handleRunML(doc.id, 'ocr')}
                                                    disabled={isProcessing(doc.id, 'ocr')}
                                                    title="Run OCR"
                                                >
                                                    {isProcessing(doc.id, 'ocr') ? '⏳' : '🔤'} OCR
                                                </button>
                                                <button
                                                    className="btn btn-secondary btn-sm"
                                                    onClick={() => handleRunML(doc.id, 'classify')}
                                                    disabled={isProcessing(doc.id, 'classify')}
                                                    title="Classify"
                                                >
                                                    {isProcessing(doc.id, 'classify') ? '⏳' : '🏷️'} Class
                                                </button>
                                                <button
                                                    className="btn btn-secondary btn-sm"
                                                    onClick={() => handleRunML(doc.id, 'ner')}
                                                    disabled={isProcessing(doc.id, 'ner')}
                                                    title="Extract Entities"
                                                >
                                                    {isProcessing(doc.id, 'ner') ? '⏳' : '📍'} NER
                                                </button>
                                                <button
                                                    className="btn btn-secondary btn-sm"
                                                    onClick={() => handleRunML(doc.id, 'summarize')}
                                                    disabled={isProcessing(doc.id, 'summarize')}
                                                    title="Summarize"
                                                >
                                                    {isProcessing(doc.id, 'summarize') ? '⏳' : '📝'} Sum
                                                </button>
                                                <button
                                                    className="btn btn-secondary btn-sm"
                                                    onClick={() => handleRunML(doc.id, 'index')}
                                                    disabled={isProcessing(doc.id, 'index')}
                                                    title="Index for RAG"
                                                    style={{ borderColor: 'var(--accent-purple-glow)' }}
                                                >
                                                    {isProcessing(doc.id, 'index') ? '⏳' : '🧠'} RAG
                                                </button>
                                            </div>
                                        </td>
                                        <td>
                                            <div style={{ display: 'flex', gap: '8px' }}>
                                                <button className="btn btn-secondary btn-sm" onClick={() => handleDownload(doc.id)} title="Download">
                                                    <Download size={14} />
                                                </button>
                                                <button className="btn btn-sm" onClick={() => handleDelete(doc.id, doc.filename)} title="Delete"
                                                    style={{ background: 'rgba(239,68,68,0.15)', color: 'var(--accent-red)', border: 'none' }}>
                                                    <Trash2 size={14} />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Pagination */}
            {total > 20 && (
                <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', marginTop: '24px' }}>
                    <button className="btn btn-secondary btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                        Previous
                    </button>
                    <span style={{ alignSelf: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                        Page {page} of {Math.ceil(total / 20)}
                    </span>
                    <button className="btn btn-secondary btn-sm" disabled={page >= Math.ceil(total / 20)} onClick={() => setPage(page + 1)}>
                        Next
                    </button>
                </div>
            )}
        </div>
    );
}
