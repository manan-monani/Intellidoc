/*
 * IntelliDoc — Sidebar Layout Component
 * Navigation sidebar with app branding and route links.
 */

import { NavLink, Outlet } from 'react-router-dom';
import {
    LayoutDashboard,
    Upload,
    FileText,
    MessageSquare,
    BarChart3,
    Settings,
    Brain,
} from 'lucide-react';

const navItems = [
    { path: '/', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/upload', label: 'Upload', icon: Upload },
    { path: '/documents', label: 'Documents', icon: FileText },
    { path: '/qa', label: 'Ask AI', icon: MessageSquare },
    { path: '/analytics', label: 'Analytics', icon: BarChart3 },
];

export default function Layout() {
    return (
        <div className="app-layout">
            {/* Sidebar */}
            <aside className="sidebar">
                <div className="sidebar-header">
                    <div className="sidebar-logo">
                        <div className="logo-icon">
                            <Brain size={20} color="white" />
                        </div>
                        <h1>IntelliDoc</h1>
                    </div>
                </div>

                <nav className="sidebar-nav">
                    {navItems.map((item) => (
                        <NavLink
                            key={item.path}
                            to={item.path}
                            end={item.path === '/'}
                            className={({ isActive }) =>
                                `nav-item ${isActive ? 'active' : ''}`
                            }
                        >
                            <item.icon size={18} />
                            {item.label}
                        </NavLink>
                    ))}
                </nav>

                <div style={{ padding: '16px 12px', borderTop: '1px solid var(--border-color)' }}>
                    <div className="nav-item" style={{ opacity: 0.6 }}>
                        <Settings size={18} />
                        Settings
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="main-content">
                <Outlet />
            </main>
        </div>
    );
}
