import { useEffect } from 'react';
import { StepProps } from '../types';
import { Pill, Note } from '../../ui';
import { ROLE_OF, ROLE_HINT, NEEDED_ROLES, confidenceTone } from '../../lib/format';

export default function S02Review({ ctx, next, setAction }: StepProps) {
    useEffect(() => {
        setAction({ label: 'Proceed →', onClick: next });
    }, []);

    const d = ctx.detail || {};
    const pv = ctx.preview || {};
    const signals: any[] = ctx.status?.detected_canonical_fields || [];
    const profile: any[] = d.columns_profile || [];

    // every column, with our best guess at what it is
    const byCol: Record<string, any> = {};
    signals.forEach((s) => {
        byCol[s.original_column] = s;
    });
    const columns = profile.length
        ? profile.map((p) => p.column_name)
        : (pv.columns || []).map((c: any) => c.original_name);

    const roleFor = (col: string) => {
        const cf = byCol[col]?.canonical_field;
        return cf && cf !== 'UNKNOWN' ? ROLE_OF[cf] || cf : null;
    };
    const coveredRoles = new Set(columns.map(roleFor).filter(Boolean));
    const missing = NEEDED_ROLES.filter((r) => !coveredRoles.has(r));

    return (
        <div className="max-w-2xl">
            <h1 className="text-3xl font-bold tracking-tight">Here’s what we read</h1>
            <p className="mt-3 text-[--muted]">Straight from your file — nothing filled in.</p>

            <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[
                    ['File', d.name || d.filename],
                    ['Type', (d.file_type || '').toUpperCase()],
                    ['Rows', Number(d.row_count ?? 0).toLocaleString()],
                    ['Columns', String(d.column_count ?? columns.length)],
                ].map(([k, v]) => (
                    <div
                        key={k as string}
                        className="rounded-xl border border-[--line] bg-[--panel] px-3 py-2.5"
                    >
                        <div className="text-[11px] uppercase tracking-wide text-[--faint]">
                            {k}
                        </div>
                        <div className="mt-0.5 truncate text-sm font-medium" title={String(v)}>
                            {v}
                        </div>
                    </div>
                ))}
            </div>

            {/* the 4 things every case needs */}
            <h2 className="mt-8 text-sm font-semibold uppercase tracking-wide text-[--faint]">
                The four things every case needs
            </h2>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                {NEEDED_ROLES.map((role) => {
                    const col = columns.find((c: string) => roleFor(c) === role);
                    return (
                        <li
                            key={role}
                            className={`rounded-xl border px-4 py-3 ${col ? 'border-[--line] bg-[--panel]' : 'border-amber-500/30 bg-amber-500/[0.05]'}`}
                        >
                            <div className="flex items-center gap-2 text-sm font-medium">
                                <span className={col ? 'text-emerald-400' : 'text-amber-400'}>
                                    {col ? '✓' : '?'}
                                </span>
                                {role}
                            </div>
                            <div className="mt-0.5 text-xs text-[--faint]">{ROLE_HINT[role]}</div>
                            <div className="mt-1 font-mono text-sm">
                                {col ? (
                                    col
                                ) : (
                                    <span className="text-amber-300">
                                        you’ll pick this in step 4
                                    </span>
                                )}
                            </div>
                        </li>
                    );
                })}
            </ul>

            {/* every column */}
            <h2 className="mt-8 text-sm font-semibold uppercase tracking-wide text-[--faint]">
                Every column we read
            </h2>
            <ul className="mt-3 space-y-1.5">
                {columns.map((col: string) => {
                    const s = byCol[col];
                    const role = roleFor(col);
                    return (
                        <li
                            key={col}
                            className="flex items-center justify-between rounded-lg border border-[--line] bg-[--panel] px-4 py-2"
                        >
                            <span className="flex items-center gap-2 text-sm">
                                <span className="font-mono">{col}</span>
                                <span className="text-[--faint]">
                                    → {role || 'extra info (not one of the four)'}
                                </span>
                            </span>
                            {s?.confidence && (
                                <Pill tone={confidenceTone(s.confidence)}>
                                    {String(s.confidence).toLowerCase().replace('_', ' ')}
                                </Pill>
                            )}
                        </li>
                    );
                })}
            </ul>

            {pv.rows?.length > 0 && (
                <>
                    <h2 className="mt-8 text-sm font-semibold uppercase tracking-wide text-[--faint]">
                        First rows
                    </h2>
                    <div className="mt-3 overflow-x-auto rounded-xl border border-[--line]">
                        <table className="w-full text-xs">
                            <thead className="bg-white/[0.03] text-left text-[--muted]">
                                <tr>
                                    {pv.columns.map((c: any) => (
                                        <th key={c.original_name} className="px-3 py-2 font-mono">
                                            {c.original_name}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-[--line] text-[--ink]">
                                {pv.rows.slice(0, 5).map((r: any, i: number) => (
                                    <tr key={i}>
                                        {pv.columns.map((c: any) => (
                                            <td key={c.original_name} className="px-3 py-1.5">
                                                {String(r[c.original_name] ?? '')}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </>
            )}

            <div className="mt-8">
                {missing.length === 0 ? (
                    <Note>
                        All four needed columns were found. You’ll confirm them in step&nbsp;4 —
                        change any that look wrong.
                    </Note>
                ) : (
                    <Note tone="amber">
                        We couldn’t confidently spot: <b>{missing.join(', ')}</b>. That’s fine —
                        step&nbsp;4 lets you point at the right column yourself. Nothing is guessed
                        silently.
                    </Note>
                )}
            </div>
        </div>
    );
}
