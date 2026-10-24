import React, { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';

export type Tone = 'green' | 'amber' | 'red' | 'blue' | 'gray' | 'violet';

/** GSAP-driven number count-up. `format` maps the raw number to a display string. */
export function CountUp({
    to,
    format,
    motion = true,
    className = '',
}: {
    to: number;
    format: (n: number) => string;
    motion?: boolean;
    className?: string;
}) {
    const [txt, setTxt] = useState(() => format(motion ? 0 : to));
    const box = useRef({ v: 0 });
    useEffect(() => {
        if (!motion) {
            setTxt(format(to));
            return;
        }
        box.current.v = 0;
        const t = gsap.to(box.current, {
            v: to,
            duration: 1.1,
            ease: 'power2.out',
            onUpdate: () => setTxt(format(box.current.v)),
        });
        return () => {
            t.kill();
        };
    }, [to, motion]);
    return <span className={className}>{txt}</span>;
}

const TONE: Record<Tone, string> = {
    green: 'bg-emerald-500/12 text-emerald-300 ring-emerald-500/25',
    amber: 'bg-amber-500/12 text-amber-300 ring-amber-500/25',
    red: 'bg-rose-500/12 text-rose-300 ring-rose-500/25',
    blue: 'bg-sky-500/12 text-sky-300 ring-sky-500/25',
    gray: 'bg-slate-500/12 text-slate-300 ring-slate-500/25',
    violet: 'bg-violet-500/12 text-violet-300 ring-violet-500/25',
};

export function Pill({ tone = 'gray', children }: { tone?: Tone; children: React.ReactNode }) {
    return (
        <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${TONE[tone]}`}
        >
            <span className="h-1.5 w-1.5 rounded-full bg-current opacity-80" />
            {children}
        </span>
    );
}

export function Button({
    variant = 'primary',
    className = '',
    ...p
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' | 'danger' }) {
    const base =
        'inline-flex items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold transition-all disabled:opacity-40 disabled:cursor-not-allowed';
    const v =
        variant === 'primary'
            ? 'bg-[--accent] text-white shadow-lg shadow-sky-900/40 hover:brightness-110'
            : variant === 'danger'
              ? 'bg-rose-600 text-white hover:bg-rose-500'
              : 'border border-[--line] text-slate-300 hover:bg-white/5';
    return <button className={`${base} ${v} ${className}`} {...p} />;
}

export function Spinner({ label }: { label?: string }) {
    return (
        <div className="flex items-center gap-3 text-sm text-[--muted]">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-700 border-t-sky-400" />
            {label || 'Loading…'}
        </div>
    );
}

export function ErrorNote({
    children,
    onRetry,
}: {
    children: React.ReactNode;
    onRetry?: () => void;
}) {
    return (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
            {children}
            {onRetry && (
                <button onClick={onRetry} className="ml-3 font-semibold underline">
                    try again
                </button>
            )}
        </div>
    );
}

/** A honest "this capability isn't in the system yet / is simulated" callout. */
export function Note({ tone = 'gray', children }: { tone?: Tone; children: React.ReactNode }) {
    const ring =
        tone === 'amber'
            ? 'border-amber-500/25 bg-amber-500/[0.06] text-amber-200/90'
            : 'border-[--line] bg-white/[0.02] text-[--muted]';
    return (
        <div className={`rounded-xl border px-4 py-3 text-[13px] leading-relaxed ${ring}`}>
            {children}
        </div>
    );
}

/** label / value row */
export function KV({ k, v }: { k: React.ReactNode; v: React.ReactNode }) {
    return (
        <div className="flex items-baseline justify-between gap-6 py-2.5">
            <span className="text-sm text-[--muted]">{k}</span>
            <span className="text-right text-sm font-medium text-[--ink]">{v}</span>
        </div>
    );
}

export function BigStat({
    label,
    value,
    tone = 'gray',
    sub,
}: {
    label: string;
    value: React.ReactNode;
    tone?: Tone;
    sub?: React.ReactNode;
}) {
    const color =
        tone === 'green'
            ? 'text-emerald-300'
            : tone === 'red'
              ? 'text-rose-300'
              : tone === 'amber'
                ? 'text-amber-300'
                : tone === 'blue'
                  ? 'text-sky-300'
                  : 'text-[--ink]';
    return (
        <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[--faint]">
                {label}
            </div>
            <div className={`mt-1.5 text-4xl font-bold tracking-tight tabular ${color}`}>
                {value}
            </div>
            {sub && <div className="mt-1 text-sm text-[--muted]">{sub}</div>}
        </div>
    );
}

export function Card({
    title,
    subtitle,
    right,
    children,
    className = '',
}: {
    title?: React.ReactNode;
    subtitle?: React.ReactNode;
    right?: React.ReactNode;
    children: React.ReactNode;
    className?: string;
}) {
    return (
        <section className={`rounded-2xl border border-[--line] bg-[--panel] ${className}`}>
            {(title || right) && (
                <header className="flex items-start justify-between gap-3 border-b border-[--line] px-5 py-4">
                    <div>
                        {title && <h2 className="text-base font-semibold text-[--ink]">{title}</h2>}
                        {subtitle && <p className="mt-0.5 text-sm text-[--muted]">{subtitle}</p>}
                    </div>
                    {right}
                </header>
            )}
            <div className="p-5">{children}</div>
        </section>
    );
}

export function Empty({ title, children }: { title: string; children?: React.ReactNode }) {
    return (
        <div className="rounded-2xl border border-dashed border-[--line] p-10 text-center">
            <p className="font-medium text-[--ink]">{title}</p>
            {children && <div className="mt-2 text-sm text-[--muted]">{children}</div>}
        </div>
    );
}

/** a check/warn/dot list item */
export function Row({
    ok,
    warn,
    children,
}: {
    ok?: boolean;
    warn?: boolean;
    children: React.ReactNode;
}) {
    const mark = ok ? (
        <span className="text-emerald-400">✓</span>
    ) : warn ? (
        <span className="text-amber-400">⚠</span>
    ) : (
        <span className="text-[--faint]">•</span>
    );
    return (
        <li className="flex items-start gap-3 py-1.5 text-sm text-[--ink]">
            <span className="mt-0.5">{mark}</span>
            <span>{children}</span>
        </li>
    );
}
