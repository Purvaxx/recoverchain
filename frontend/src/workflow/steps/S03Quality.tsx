import React, { useEffect, useState } from 'react';
import { StepProps } from '../types';
import { BigStat, Note } from '../../ui';
import { ROLE_OF, NEEDED_ROLES } from '../../lib/format';

function Line({ good, children }: { good: boolean; children: React.ReactNode }) {
    return (
        <li className="flex items-start gap-3 py-2 text-sm">
            <span className={good ? 'text-emerald-400' : 'text-amber-400'}>{good ? '✓' : '!'}</span>
            <span className="text-[--ink]">{children}</span>
        </li>
    );
}

export default function S03Quality({ ctx, next, setAction }: StepProps) {
    const [detail, setDetail] = useState(false);
    useEffect(() => {
        setAction({ label: 'Proceed →', onClick: next });
    }, []);

    const d = ctx.detail || {};
    const q = d.data_quality_report || {};
    const cols: any[] = d.columns_profile || [];
    const leakage: any[] = d.leakage_detection || [];
    const rows = Number(d.row_count ?? 0);

    const score = typeof q.score === 'number' ? Math.round(q.score) : null;
    const verdict =
        score === null
            ? { w: '—', t: 'gray' }
            : score >= 85
              ? { w: 'Good — ready to use', t: 'green' }
              : score >= 60
                ? { w: 'Usable, with a few gaps', t: 'amber' }
                : { w: 'Needs a closer look', t: 'red' };

    // completeness
    const totalCells = rows * cols.length;
    const missingCells = cols.reduce((s, c) => s + (c.missing_count || 0), 0);
    const filledPct =
        totalCells > 0 ? Math.round(((totalCells - missingCells) / totalCells) * 100) : 100;
    const gappy = cols
        .filter((c) => (c.missing_count || 0) > 0)
        .sort((a, b) => (b.missing_rate || 0) - (a.missing_rate || 0));

    // constant (zero-signal) columns
    const constants = cols.filter((c) => c.is_constant);

    // which of the 4 needed roles are present at all (name-detected)
    const detected: any[] = ctx.status?.detected_canonical_fields || [];
    const coveredRoles = new Set(
        detected
            .map((s) =>
                s.canonical_field && s.canonical_field !== 'UNKNOWN'
                    ? ROLE_OF[s.canonical_field]
                    : null,
            )
            .filter(Boolean),
    );
    const missingRoles = NEEDED_ROLES.filter((r) => !coveredRoles.has(r));

    return (
        <div className="max-w-2xl">
            <h1 className="text-3xl font-bold tracking-tight">Is this data any good?</h1>
            <p className="mt-3 text-[--muted]">
                A quick health check on all {rows.toLocaleString()} rows before we build cases.
            </p>

            <div className="mt-8">
                <BigStat
                    label="Data health score"
                    value={score === null ? '—' : `${score} / 100`}
                    tone={verdict.t as any}
                    sub={verdict.w}
                />
            </div>

            {/* 1. is it filled in */}
            <h2 className="mt-8 text-sm font-semibold uppercase tracking-wide text-[--faint]">
                Is it filled in?
            </h2>
            <ul className="mt-1 divide-y divide-[--line] rounded-xl border border-[--line] bg-[--panel] px-4">
                <Line good={filledPct >= 98}>
                    <b>{filledPct}%</b> of all cells have a value
                    {missingCells > 0 && <> — {missingCells.toLocaleString()} are blank</>}.
                </Line>
                {gappy.length > 0 ? (
                    <Line good={false}>
                        Columns with blanks:{' '}
                        {gappy.slice(0, 4).map((c) => (
                            <span key={c.column_name} className="whitespace-nowrap">
                                <span className="font-mono">{c.column_name}</span> (
                                {Math.round((c.missing_rate || 0) * 100)}% empty)
                                {gappy.indexOf(c) < Math.min(gappy.length, 4) - 1 ? ', ' : ''}
                            </span>
                        ))}
                        {gappy.length > 4 && <> +{gappy.length - 4} more</>}. Blank cells are filled
                        with a safe default before scoring.
                    </Line>
                ) : (
                    <Line good>No blank cells anywhere.</Line>
                )}
            </ul>

            {/* 2. is anything missing */}
            <h2 className="mt-8 text-sm font-semibold uppercase tracking-wide text-[--faint]">
                Is anything important missing?
            </h2>
            <ul className="mt-1 divide-y divide-[--line] rounded-xl border border-[--line] bg-[--panel] px-4">
                {missingRoles.length === 0 ? (
                    <Line good>
                        All four needed columns were found: customer, amount, date, result.
                    </Line>
                ) : (
                    <Line good={false}>
                        We haven’t clearly found: <b>{missingRoles.join(', ')}</b>. You point at the
                        right column in step&nbsp;4 — it won’t be guessed.
                    </Line>
                )}
                {constants.length > 0 ? (
                    <Line good={false}>
                        Same value in every row (tells the model nothing, so it’s dropped):{' '}
                        {constants.map((c) => (
                            <span key={c.column_name} className="font-mono">
                                {c.column_name}{' '}
                            </span>
                        ))}
                    </Line>
                ) : (
                    <Line good>No dead columns — every column varies across rows.</Line>
                )}
            </ul>

            {/* 3. could anything leak */}
            <h2 className="mt-8 text-sm font-semibold uppercase tracking-wide text-[--faint]">
                Could anything “leak” the answer?
            </h2>
            <ul className="mt-1 divide-y divide-[--line] rounded-xl border border-[--line] bg-[--panel] px-4">
                {leakage.length === 0 ? (
                    <Line good>
                        Nothing found. No column here reveals whether the money came back before the
                        model would actually know.
                    </Line>
                ) : (
                    leakage.map((l: any) => (
                        <Line key={l.column} good={false}>
                            <span className="font-mono">{l.column}</span> is filled in only{' '}
                            <i>after</i> the outcome is known. Letting the model see it would make
                            its score fake — so it’s hidden from the model.
                        </Line>
                    ))
                )}
            </ul>

            <button
                onClick={() => setDetail((v) => !v)}
                className="mt-5 text-sm font-medium text-sky-400 hover:underline"
            >
                {detail ? 'Hide the column-by-column table' : 'Show the column-by-column table'}
            </button>
            {detail && (
                <div className="mt-3 overflow-x-auto rounded-xl border border-[--line]">
                    <table className="w-full text-xs">
                        <thead className="bg-white/[0.03] text-left text-[--muted]">
                            <tr>
                                <th className="px-3 py-2">Column</th>
                                <th className="px-3 py-2">Kind</th>
                                <th className="px-3 py-2">Different values</th>
                                <th className="px-3 py-2">Blank</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-[--line] text-[--ink]">
                            {cols.map((c) => (
                                <tr key={c.column_name}>
                                    <td className="px-3 py-1.5 font-mono">{c.column_name}</td>
                                    <td className="px-3 py-1.5 text-[--muted]">
                                        {String(c.dtype).includes('int') ||
                                        String(c.dtype).includes('float')
                                            ? 'number'
                                            : String(c.dtype).includes('date')
                                              ? 'date'
                                              : 'text'}
                                    </td>
                                    <td className="px-3 py-1.5 tabular">{c.unique_count}</td>
                                    <td className="px-3 py-1.5 tabular">
                                        {Math.round((c.missing_rate || 0) * 100)}%
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    {Array.isArray(q.breakdown) && (
                        <div className="border-t border-[--line] px-3 py-2 text-[11px] text-[--faint]">
                            score notes: {q.breakdown.join(' · ')}
                        </div>
                    )}
                </div>
            )}

            <div className="mt-8">
                <Note>
                    This checks the whole file. The row-by-row check — bad amounts, unreadable
                    dates, rows that were already paid — runs when cases are built in step&nbsp;6,
                    and you’ll see those counts there.
                </Note>
            </div>
        </div>
    );
}
