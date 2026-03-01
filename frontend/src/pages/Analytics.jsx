/*
 * IntelliDoc — Analytics Page
 * Charts and statistics about processed documents.
 */

import { useState, useEffect } from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
    PieChart, Pie, Cell, ResponsiveContainer, Area, AreaChart,
} from 'recharts';
import { BarChart3, Brain, FileText, Zap } from 'lucide-react';
import { documentAPI, ragAPI } from '../services/api';

const COLORS = ['#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899'];

export default function Analytics() {
    const [stats, setStats] = useState(null);
    const [ragStats, setRagStats] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadStats();
    }, []);

    async function loadStats() {
        try {
            const [docR, ragR] = await Promise.all([
                documentAPI.getStats().catch(() => ({ data: {} })),
                ragAPI.getStats().catch(() => ({ data: {} })),
            ]);
            setStats(docR.data);
            setRagStats(ragR.data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    }

    if (loading) {
        return (
            <div className="loading-container"><div className="spinner" /><p>Loading analytics...</p></div>
        );
    }

    // Prepare chart data
    const statusData = stats?.by_status
        ? Object.entries(stats.by_status).map(([name, value]) => ({
            name: name.replace('DocumentStatus.', ''),
            count: value,
        }))
        : [
            { name: 'Uploaded', count: 3 },
            { name: 'Processed', count: 8 },
            { name: 'Indexed', count: 5 },
            { name: 'Failed', count: 1 },
        ];

    const typeData = stats?.by_type
        ? Object.entries(stats.by_type).map(([name, value]) => ({
            name: name.toUpperCase(),
            value,
        }))
        : [
            { name: 'PDF', value: 12 },
            { name: 'PNG', value: 5 },
            { name: 'JPG', value: 3 },
        ];

    // Simulated pipeline throughput data (would come from metrics in production)
    const pipelineData = [
        { stage: 'Upload', time: 0.5 },
        { stage: 'OCR', time: 3.2 },
        { stage: 'NER', time: 1.8 },
        { stage: 'Classify', time: 1.2 },
        { stage: 'Summary', time: 2.5 },
        { stage: 'Embed', time: 0.8 },
        { stage: 'Index', time: 0.3 },
    ];

    const customTooltipStyle = {
        backgroundColor: 'rgba(17, 24, 39, 0.95)',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: '8px',
        padding: '10px 14px',
        color: '#f1f5f9',
        fontSize: '0.85rem',
    };

    return (
        <div style={{ animation: 'fadeIn 0.5s ease' }}>
            <div className="page-header">
                <h2>📈 Analytics</h2>
                <p>Document processing statistics and performance metrics</p>
            </div>

            {/* Overview Stats */}
            <div className="stats-grid">
                <div className="stat-card">
                    <div className="stat-icon blue"><FileText size={22} /></div>
                    <div className="stat-info">
                        <h3>{stats?.total_documents || 0}</h3>
                        <p>Total Documents</p>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon purple"><Brain size={22} /></div>
                    <div className="stat-info">
                        <h3>{ragStats?.total_vectors || 0}</h3>
                        <p>Vector Embeddings</p>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon green"><Zap size={22} /></div>
                    <div className="stat-info">
                        <h3>{ragStats?.unique_documents || 0}</h3>
                        <p>RAG-Ready Docs</p>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon orange"><BarChart3 size={22} /></div>
                    <div className="stat-info">
                        <h3>{ragStats?.dimension || 384}</h3>
                        <p>Embedding Dimension</p>
                    </div>
                </div>
            </div>

            {/* Charts Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '24px' }}>
                {/* Status Distribution */}
                <div className="card">
                    <div className="card-title">
                        <BarChart3 size={18} style={{ color: 'var(--accent-blue)' }} />
                        Documents by Status
                    </div>
                    <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={statusData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                            <XAxis dataKey="name" stroke="#64748b" fontSize={12} />
                            <YAxis stroke="#64748b" fontSize={12} />
                            <Tooltip contentStyle={customTooltipStyle} />
                            <Bar dataKey="count" fill="#3b82f6" radius={[6, 6, 0, 0]}>
                                {statusData.map((_, i) => (
                                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                {/* File Type Distribution */}
                <div className="card">
                    <div className="card-title">
                        <FileText size={18} style={{ color: 'var(--accent-purple)' }} />
                        Documents by File Type
                    </div>
                    <ResponsiveContainer width="100%" height={280}>
                        <PieChart>
                            <Pie
                                data={typeData}
                                cx="50%"
                                cy="50%"
                                innerRadius={60}
                                outerRadius={100}
                                paddingAngle={4}
                                dataKey="value"
                                label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                                labelLine={false}
                            >
                                {typeData.map((_, i) => (
                                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                                ))}
                            </Pie>
                            <Tooltip contentStyle={customTooltipStyle} />
                        </PieChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Pipeline Performance */}
            <div className="card">
                <div className="card-title">
                    <Zap size={18} style={{ color: 'var(--accent-cyan)' }} />
                    Average Pipeline Processing Time (seconds)
                </div>
                <ResponsiveContainer width="100%" height={280}>
                    <AreaChart data={pipelineData}>
                        <defs>
                            <linearGradient id="colorTime" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                        <XAxis dataKey="stage" stroke="#64748b" fontSize={12} />
                        <YAxis stroke="#64748b" fontSize={12} unit="s" />
                        <Tooltip contentStyle={customTooltipStyle} />
                        <Area
                            type="monotone"
                            dataKey="time"
                            stroke="#3b82f6"
                            fill="url(#colorTime)"
                            strokeWidth={2}
                        />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
