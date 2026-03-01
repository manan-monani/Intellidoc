/*
 * IntelliDoc — Upload Page
 * Drag-and-drop document upload with progress tracking.
 */

import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload as UploadIcon, FileText, CheckCircle, AlertTriangle, X } from 'lucide-react';
import { documentAPI } from '../services/api';
import toast from 'react-hot-toast';

export default function UploadPage() {
    const [uploads, setUploads] = useState([]);

    const onDrop = useCallback((acceptedFiles) => {
        acceptedFiles.forEach((file) => {
            const uploadItem = {
                id: Date.now() + Math.random(),
                file,
                name: file.name,
                size: file.size,
                progress: 0,
                status: 'uploading', // uploading | success | error
                result: null,
                error: null,
            };

            setUploads((prev) => [uploadItem, ...prev]);
            uploadFile(uploadItem);
        });
    }, []);

    async function uploadFile(item) {
        try {
            const response = await documentAPI.upload(
                item.file,
                (progressEvent) => {
                    const pct = Math.round((progressEvent.loaded * 100) / progressEvent.total);
                    setUploads((prev) =>
                        prev.map((u) => (u.id === item.id ? { ...u, progress: pct } : u))
                    );
                }
            );

            setUploads((prev) =>
                prev.map((u) =>
                    u.id === item.id
                        ? { ...u, status: 'success', progress: 100, result: response.data }
                        : u
                )
            );

            toast.success(`${item.name} uploaded successfully!`);
        } catch (err) {
            const errorMsg = err.response?.data?.detail || 'Upload failed';
            setUploads((prev) =>
                prev.map((u) =>
                    u.id === item.id ? { ...u, status: 'error', error: errorMsg } : u
                )
            );
            toast.error(`Failed to upload ${item.name}`);
        }
    }

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: {
            'application/pdf': ['.pdf'],
            'image/png': ['.png'],
            'image/jpeg': ['.jpg', '.jpeg'],
            'image/tiff': ['.tiff', '.tif'],
        },
        maxSize: 50 * 1024 * 1024, // 50 MB
    });

    function removeUpload(id) {
        setUploads((prev) => prev.filter((u) => u.id !== id));
    }

    function formatSize(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    return (
        <div style={{ animation: 'fadeIn 0.5s ease' }}>
            <div className="page-header">
                <h2>📤 Upload Documents</h2>
                <p>Upload PDFs, images, or scanned documents for AI processing</p>
            </div>

            {/* Dropzone */}
            <div
                {...getRootProps()}
                className={`upload-zone ${isDragActive ? 'active' : ''}`}
            >
                <input {...getInputProps()} />
                <div className="upload-icon">
                    <UploadIcon size={48} />
                </div>
                <h3>
                    {isDragActive
                        ? 'Drop your files here!'
                        : 'Drag & drop files here, or click to browse'}
                </h3>
                <p>Supports PDF, PNG, JPG, TIFF — Max 50MB per file</p>
            </div>

            {/* Upload List */}
            {uploads.length > 0 && (
                <div className="card" style={{ marginTop: '24px' }}>
                    <div className="card-title">Upload Queue</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        {uploads.map((item) => (
                            <div
                                key={item.id}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '16px',
                                    padding: '14px 16px',
                                    background: 'var(--bg-glass)',
                                    borderRadius: 'var(--radius-sm)',
                                    border: '1px solid var(--border-color)',
                                }}
                            >
                                <FileText size={20} style={{ color: 'var(--accent-blue)', flexShrink: 0 }} />
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                        {item.name}
                                    </div>
                                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                                        {formatSize(item.size)}
                                    </div>
                                    {item.status === 'uploading' && (
                                        <div className="progress-bar" style={{ marginTop: '8px' }}>
                                            <div className="progress-bar-fill" style={{ width: `${item.progress}%` }} />
                                        </div>
                                    )}
                                </div>
                                {item.status === 'uploading' && (
                                    <span style={{ color: 'var(--accent-blue)', fontSize: '0.85rem', fontWeight: 600 }}>
                                        {item.progress}%
                                    </span>
                                )}
                                {item.status === 'success' && (
                                    <CheckCircle size={20} style={{ color: 'var(--accent-green)', flexShrink: 0 }} />
                                )}
                                {item.status === 'error' && (
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                        <AlertTriangle size={20} style={{ color: 'var(--accent-red)', flexShrink: 0 }} />
                                        <span style={{ color: 'var(--accent-red)', fontSize: '0.8rem' }}>
                                            {item.error}
                                        </span>
                                    </div>
                                )}
                                <button
                                    onClick={() => removeUpload(item.id)}
                                    style={{
                                        background: 'none', border: 'none', cursor: 'pointer',
                                        color: 'var(--text-muted)', padding: '4px',
                                    }}
                                >
                                    <X size={16} />
                                </button>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Tips */}
            <div className="card" style={{ marginTop: '24px' }}>
                <div className="card-title">💡 Tips</div>
                <ul style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 2, paddingLeft: '20px' }}>
                    <li>After uploading, use the <strong>ML Processing</strong> tab to run OCR, classification, NER, and summarization</li>
                    <li>Index documents for <strong>RAG</strong> to enable AI-powered question answering</li>
                    <li>Supported formats: PDF (multi-page), PNG, JPG, JPEG, TIFF</li>
                    <li>Higher resolution scans produce better OCR results</li>
                </ul>
            </div>
        </div>
    );
}
