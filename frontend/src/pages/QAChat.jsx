/*
 * IntelliDoc — Q&A Chat Page
 * Chat-based interface for RAG-powered document Q&A.
 */

import { useState, useRef, useEffect } from 'react';
import { Send, Brain, User, Sparkles, Search } from 'lucide-react';
import { ragAPI } from '../services/api';
import toast from 'react-hot-toast';

export default function QAChat() {
    const [messages, setMessages] = useState([
        {
            role: 'assistant',
            content: 'Hello! I\'m your IntelliDoc AI assistant. Ask me anything about your uploaded documents. I use RAG (Retrieval-Augmented Generation) to find relevant content and generate accurate answers.',
            sources: [],
        },
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [searchMode, setSearchMode] = useState(false);
    const messagesEndRef = useRef(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    async function handleSend() {
        if (!input.trim() || loading) return;

        const question = input.trim();
        setInput('');

        setMessages((prev) => [
            ...prev,
            { role: 'user', content: question, sources: [] },
        ]);
        setLoading(true);

        try {
            if (searchMode) {
                const res = await ragAPI.search(question, 10);
                setMessages((prev) => [
                    ...prev,
                    {
                        role: 'assistant',
                        content: `Found ${res.data.results.length} relevant passages:`,
                        sources: res.data.results.map((r) => ({
                            text: r.metadata?.chunk_text || '',
                            score: r.score,
                            filename: r.metadata?.filename || '',
                        })),
                    },
                ]);
            } else {
                const res = await ragAPI.ask(question, null, 5);
                setMessages((prev) => [
                    ...prev,
                    {
                        role: 'assistant',
                        content: res.data.answer,
                        sources: res.data.sources || [],
                        confidence: res.data.confidence,
                    },
                ]);
            }
        } catch (err) {
            const errMsg = err.response?.data?.detail || 'Failed to get response. Make sure documents are indexed.';
            setMessages((prev) => [
                ...prev,
                { role: 'assistant', content: `❌ Error: ${errMsg}`, sources: [] },
            ]);
            toast.error('Query failed');
        } finally {
            setLoading(false);
        }
    }

    function handleKeyDown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    }

    return (
        <div style={{ animation: 'fadeIn 0.5s ease' }}>
            <div className="page-header" style={{ marginBottom: '16px' }}>
                <h2>🤖 Ask AI</h2>
                <p>Ask questions about your documents — powered by RAG + LLM</p>
            </div>

            {/* Mode Toggle */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                <button
                    className={`btn ${!searchMode ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                    onClick={() => setSearchMode(false)}
                >
                    <Sparkles size={14} /> Q&A Mode
                </button>
                <button
                    className={`btn ${searchMode ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                    onClick={() => setSearchMode(true)}
                >
                    <Search size={14} /> Search Mode
                </button>
            </div>

            {/* Chat Container */}
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <div className="chat-container">
                    {/* Messages */}
                    <div className="chat-messages">
                        {messages.map((msg, i) => (
                            <div key={i} className={`chat-message ${msg.role}`}>
                                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                                    {msg.role === 'assistant' && (
                                        <Brain size={18} style={{ color: 'var(--accent-purple)', flexShrink: 0, marginTop: '2px' }} />
                                    )}
                                    <div style={{ flex: 1 }}>
                                        <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>

                                        {msg.confidence !== undefined && msg.confidence > 0 && (
                                            <div style={{ marginTop: '8px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                                                Confidence: {(msg.confidence * 100).toFixed(1)}%
                                            </div>
                                        )}

                                        {msg.sources && msg.sources.length > 0 && (
                                            <div className="sources">
                                                <strong>📎 Sources:</strong>
                                                {msg.sources.map((src, j) => (
                                                    <div
                                                        key={j}
                                                        style={{
                                                            margin: '8px 0',
                                                            padding: '10px',
                                                            background: 'var(--bg-glass)',
                                                            borderRadius: 'var(--radius-sm)',
                                                            fontSize: '0.82rem',
                                                            lineHeight: 1.5,
                                                        }}
                                                    >
                                                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                                            <span style={{ color: 'var(--accent-blue)', fontWeight: 600 }}>
                                                                {src.filename || 'Document'}
                                                            </span>
                                                            <span style={{ color: 'var(--text-muted)' }}>
                                                                Score: {(src.score * 100).toFixed(0)}%
                                                            </span>
                                                        </div>
                                                        <div style={{ color: 'var(--text-secondary)' }}>
                                                            {(src.chunk_text || src.text || '').substring(0, 200)}
                                                            {(src.chunk_text || src.text || '').length > 200 && '...'}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}

                        {loading && (
                            <div className="chat-message assistant" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                <Brain size={18} style={{ color: 'var(--accent-purple)' }} />
                                <div className="animate-pulse">Thinking...</div>
                            </div>
                        )}

                        <div ref={messagesEndRef} />
                    </div>

                    {/* Input */}
                    <div className="chat-input-container">
                        <input
                            type="text"
                            className="chat-input"
                            placeholder={searchMode ? 'Search across documents...' : 'Ask a question about your documents...'}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            disabled={loading}
                        />
                        <button
                            className="btn btn-primary"
                            onClick={handleSend}
                            disabled={!input.trim() || loading}
                        >
                            <Send size={18} />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
