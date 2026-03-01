/*
 * IntelliDoc — Dashboard Page
 * Overview with stats cards, recent documents, and pipeline status.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    FileText, Brain, Search, CheckCircle,
    Clock, AlertTriangle, Upload, ArrowRight
} from 'lucide-react';
import { documentAPI, ragAPI } from '../services/api';

export default function Dashboard() {
    const [stats, setStats] = useState(null);
    const [ragStats, setRagStats] = useState(null);
    const [recentDocs, setRecentDocs] = useState([]);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    useEffect(() => {
        loadData();
    }, []);

    async function loadData() {
        try {
            const [docStats, ragSt, docList] = await Promise.all([
                documentAPI.getStats().catch(() => ({ data: { total_documents: 0, by_status: {}, by_type: {} } })),
                ragAPI.getStats().catch(() => ({ data: { total_vectors: 0, unique_documents: 0 } })),
                documentAPI.list(1, 5).catch(() => ({ data: { documents: [], total: 0 } })),
            ]);
            setStats(docStats.data);
            setRagStats(ragSt.data);
            setRecentDocs(docList.data.documents || []);
        } catch (err) {
            console.error('Failed to load dashboard data:', err);
        } finally {
            setLoading(false);
        }
    }

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

    if (loading) {
        return (
            <div className="loading-container">
                <div className="spinner" />
                <p>Loading dashboard...</p>
            </div>
        );
    }

    const totalDocs = stats?.total_documents || 0;
    const indexed = stats?.by_status?.indexed || stats?.by_status?.DocumentStatus?.INDEXED || 0;
    const processed = stats?.by_status?.processed || stats?.by_status?.DocumentStatus?.PROCESSED || 0;
    const vectors = ragStats?.total_vectors || 0;

    return (
        <div style={{ animation: 'fadeIn 0.5s ease' }}>
            <div className="page-header">
                <h2>📊 Dashboard</h2>
                <p>Welcome to IntelliDoc — your intelligent document processing platform</p>
            </div>

            {/* Stats Grid */}
            <div className="stats-grid">
                <div className="stat-card">
                    <div className="stat-icon blue"><FileText size={22} /></div>
                    <div className="stat-info">
                        <h3>{totalDocs}</h3>
                        <p>Total Documents</p>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon green"><CheckCircle size={22} /></div>
                    <div className="stat-info">
                        <h3>{processed + indexed}</h3>
                        <p>Processed</p>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon purple"><Brain size={22} /></div>
                    <div className="stat-info">
                        <h3>{vectors}</h3>
                        <p>Vector Embeddings</p>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon orange"><Search size={22} /></div>
                    <div className="stat-info">
                        <h3>{ragStats?.unique_documents || 0}</h3>
                        <p>RAG-Indexed Docs</p>
                    </div>
                </div>
            </div>

            {/* Quick Actions */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '32px' }}>
                <div className="card" onClick={() => navigate('/upload')} style={{ cursor: 'pointer' }}>
                    <div className="card-title">
                        <Upload size={18} style={{ color: 'var(--accent-blue)' }} />
                        Upload Documents
                    </div>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                        Upload PDFs, images, or scanned documents for AI processing
                    </p>
                    <div style={{ marginTop: '12px', color: 'var(--accent-blue)', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem' }}>
                        Get started <ArrowRight size={14} />
                    </div>
                </div>
                <div className="card" onClick={() => navigate('/qa')} style={{ cursor: 'pointer' }}>
                    <div className="card-title">
                        <Brain size={18} style={{ color: 'var(--accent-purple)' }} />
                        Ask AI
                    </div>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                        Ask questions about your documents — powered by RAG + LLM
                    </p>
                    <div style={{ marginTop: '12px', color: 'var(--accent-purple)', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem' }}>
                        Start asking <ArrowRight size={14} />
                    </div>
                </div>
            </div>

            {/* Recent Documents */}
            <div className="card">
                <div className="card-title" style={{ justifyContent: 'space-between' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Clock size={18} style={{ color: 'var(--accent-cyan)' }} />
                        Recent Documents
                    </span>
                    <button className="btn btn-secondary btn-sm" onClick={() => navigate('/documents')}>
                        View All
                    </button>
                </div>

                {recentDocs.length === 0 ? (
                    <div className="empty-state">
                        <div className="empty-icon">📄</div>
                        <h3>No documents yet</h3>
                        <p>Upload your first document to get started</p>
                    </div>
                ) : (
                    <div className="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>Filename</th>
                                    <th>Type</th>
                                    <th>Status</th>
                                    <th>Classification</th>
                                    <th>Uploaded</th>
                                </tr>
                            </thead>
                            <tbody>
                                {recentDocs.map((doc) => (
                                    <tr key={doc.id} onClick={() => navigate(`/documents`)} style={{ cursor: 'pointer' }}>
                                        <td style={{ fontWeight: 500 }}>{doc.filename}</td>
                                        <td><span className="badge badge-uploaded">{doc.file_type}</span></td>
                                        <td><span className={statusBadge(doc.status)}>{doc.status}</span></td>
                                        <td>{doc.classification || '—'}</td>
                                        <td style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                                            {new Date(doc.created_at).toLocaleDateString()}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}
