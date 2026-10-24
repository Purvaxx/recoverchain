import React, { useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { BarChart3, ListChecks, Menu, X } from 'lucide-react';
import ModeSwitch from './ModeSwitch';

const NAV = [
    { to: '/insights', label: 'Report', icon: BarChart3 },
    { to: '/cases', label: 'Cases', icon: ListChecks },
];

const linkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
        isActive ? 'bg-[--accent] text-white' : 'text-[--muted] hover:bg-white/5 hover:text-[--ink]'
    }`;

function Nav({ onGo }: { onGo?: () => void }) {
    return (
        <nav className="space-y-1 p-4">
            {NAV.map(({ to, label, icon: Icon }) => (
                <NavLink key={to} to={to} end onClick={onGo} className={linkClass}>
                    <Icon size={17} /> {label}
                </NavLink>
            ))}
        </nav>
    );
}

export default function Shell({ children }: { children: React.ReactNode }) {
    const [open, setOpen] = useState(false);
    return (
        <div className="min-h-screen bg-[--bg] text-[--ink]">
            <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-[--line] bg-[--bg]/90 px-4 backdrop-blur">
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => setOpen(true)}
                        className="rounded-lg p-2 text-[--muted] hover:bg-white/5 lg:hidden"
                    >
                        <Menu size={18} />
                    </button>
                    <Link to="/insights" className="flex items-center gap-2">
                        <span className="grid h-7 w-7 place-items-center rounded-md bg-[--accent] text-xs font-bold text-white">
                            RC
                        </span>
                        <span className="font-semibold">RecoverChain</span>
                    </Link>
                </div>
                <ModeSwitch />
            </header>

            <div className="mx-auto flex max-w-6xl">
                <aside className="hidden w-52 shrink-0 border-r border-[--line] lg:block">
                    <div className="sticky top-14">
                        <Nav />
                    </div>
                </aside>

                {open && (
                    <div className="fixed inset-0 z-40 lg:hidden">
                        <div
                            className="absolute inset-0 bg-black/60"
                            onClick={() => setOpen(false)}
                        />
                        <div className="absolute inset-y-0 left-0 w-64 bg-[--bg]">
                            <div className="flex justify-end p-2">
                                <button
                                    onClick={() => setOpen(false)}
                                    className="rounded-lg p-2 text-[--muted] hover:bg-white/5"
                                >
                                    <X size={18} />
                                </button>
                            </div>
                            <Nav onGo={() => setOpen(false)} />
                        </div>
                    </div>
                )}

                <main className="min-w-0 flex-1 px-4 py-8 sm:px-8">{children}</main>
            </div>
        </div>
    );
}
