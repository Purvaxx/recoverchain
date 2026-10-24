import { useEffect } from 'react';
import { StepProps } from '../types';
import { Note, Pill } from '../../ui';
import { PLAIN } from '../../lib/format';
import { useMotionPref } from '../../lib/motion';

const SPLIT_LABEL: Record<string, string> = {
    TEMPORAL_WITH_ENTITY_ISOLATION:
        'Older rows train the model, newer rows test it — and no customer appears in both.',
    TEMPORAL_CHRONOLOGICAL: 'Older rows train the model, newer rows test it.',
    RANDOM_SHUFFLE: 'Rows split at random — no date column was available to split by time.',
};

const EXCL_PLAIN: Record<string, string> = {
    TARGET: 'this is the answer itself',
    IDENTIFIER: 'just an ID — no pattern to learn',
    CONSTANT: 'the same in every row',
    HIGH_CARDINALITY: 'free text, too many unique values',
};
const exclText = (reason = '') =>
    EXCL_PLAIN[reason] ||
    (reason.startsWith('POST_OUTCOME')
        ? 'only known after the outcome — would leak the answer'
        : 'not useful to the model');

/** A small connection diagram: file → the 4 inputs → engine → shadow model. */
function Diagram({ animate }: { animate: boolean }) {
    const dash = animate ? 'diagram-flow' : '';
    return (
        <svg
            viewBox="0 0 640 220"
            className="w-full"
            role="img"
            aria-label="How your data connects to RecoverChain"
        >
            <defs>
                <style>{`
                    .diagram-flow { stroke-dasharray: 6 6; animation: dashmove 1.1s linear infinite; }
                    @keyframes dashmove { to { stroke-dashoffset: -24; } }
                    @media (prefers-reduced-motion: reduce) { .diagram-flow { animation: none; } }
                `}</style>
            </defs>
            {/* file */}
            <rect
                x="8"
                y="86"
                width="120"
                height="48"
                rx="10"
                fill="var(--panel)"
                stroke="var(--line)"
            />
            <text x="68" y="107" textAnchor="middle" fontSize="12" fill="var(--muted)">
                your file
            </text>
            <text x="68" y="123" textAnchor="middle" fontSize="11" fill="var(--faint)">
                one row per payment
            </text>
            {/* 4 inputs */}
            {['Customer', 'Amount', 'Date', 'Result'].map((t, i) => (
                <g key={t}>
                    <rect
                        x="200"
                        y={20 + i * 46}
                        width="120"
                        height="34"
                        rx="8"
                        fill="var(--panel)"
                        stroke="var(--line)"
                    />
                    <text
                        x="260"
                        y={41 + i * 46}
                        textAnchor="middle"
                        fontSize="12"
                        fill="var(--ink)"
                    >
                        {t}
                    </text>
                    <line
                        x1="128"
                        y1="110"
                        x2="200"
                        y2={37 + i * 46}
                        stroke="var(--accent)"
                        strokeWidth="1.5"
                        className={dash}
                        opacity="0.7"
                    />
                </g>
            ))}
            {/* engine */}
            <rect
                x="392"
                y="78"
                width="128"
                height="64"
                rx="12"
                fill="var(--accent)"
                opacity="0.14"
            />
            <rect
                x="392"
                y="78"
                width="128"
                height="64"
                rx="12"
                fill="none"
                stroke="var(--accent)"
            />
            <text
                x="456"
                y="104"
                textAnchor="middle"
                fontSize="12.5"
                fill="var(--ink)"
                fontWeight="600"
            >
                RecoverChain
            </text>
            <text x="456" y="122" textAnchor="middle" fontSize="11" fill="var(--muted)">
                the fixed rulebook
            </text>
            {[0, 1, 2, 3].map((i) => (
                <line
                    key={i}
                    x1="320"
                    y1={37 + i * 46}
                    x2="392"
                    y2="110"
                    stroke="var(--accent)"
                    strokeWidth="1.5"
                    className={dash}
                    opacity="0.7"
                />
            ))}
            {/* shadow model */}
            <rect
                x="392"
                y="164"
                width="128"
                height="40"
                rx="10"
                fill="var(--panel)"
                stroke="var(--line)"
                strokeDasharray="4 4"
            />
            <text x="456" y="188" textAnchor="middle" fontSize="11.5" fill="var(--muted)">
                shadow model — a second opinion
            </text>
            <line
                x1="456"
                y1="142"
                x2="456"
                y2="164"
                stroke="var(--faint)"
                strokeWidth="1.4"
                className={dash}
                opacity="0.6"
            />
        </svg>
    );
}

export default function S05Connection({ ctx, next, setAction }: StepProps) {
    useEffect(() => {
        setAction({ label: 'Proceed →', onClick: next });
    }, []);
    const [motion] = useMotionPref();

    const r = ctx.readiness || {};
    const cmap: Record<string, string> = r.canonical_feature_mapping || {};
    const reasons: Record<string, string> = r.exclusion_reasons || {};
    const feats: string[] = r.feature_columns || [];
    const excl: string[] = r.excluded_columns || [];
    const cb = r.class_balance || {};
    const split = r.temporal_split || {};

    const byCanon = (cf: string) => Object.keys(cmap).find((k) => cmap[k] === cf);
    const idCol = Object.keys(reasons).find((k) => reasons[k] === 'IDENTIFIER');
    const core = [
        { label: 'Customer', col: idCol, note: 'who owes the money' },
        { label: 'Amount', col: byCanon('AMOUNT'), note: 'how much is at stake' },
        {
            label: 'Date',
            col: split.split_column || byCanon('TIMESTAMP'),
            note: 'when it failed or was due',
        },
        { label: 'Result', col: r.target_column, note: 'paid, or failed' },
    ];

    const status: string = r.readiness_status || ctx.status?.ml_readiness_status || 'UNKNOWN';
    const warnings: string[] = r.warnings || [];
    const readyTone = status.includes('READY') ? (warnings.length ? 'amber' : 'green') : 'red';

    return (
        <div className="max-w-2xl">
            <h1 className="text-3xl font-bold tracking-tight">How your data connects</h1>
            <p className="mt-3 text-[--muted]">
                Your columns are now plugged into RecoverChain. Here’s the wiring, in plain terms.
            </p>

            <div className="mt-6 rounded-2xl border border-[--line] bg-[--panel] p-4">
                <Diagram animate={motion} />
            </div>

            {/* the four inputs */}
            <h2 className="mt-8 text-sm font-semibold uppercase tracking-wide text-[--faint]">
                The four inputs — what every case is built from
            </h2>
            <div className="mt-3 divide-y divide-[--line] rounded-xl border border-[--line] bg-[--panel] px-4">
                {core.map((f) => (
                    <div key={f.label} className="flex items-baseline justify-between gap-4 py-3">
                        <div>
                            <span className="text-sm font-medium">{f.label}</span>
                            <span className="ml-2 text-xs text-[--faint]">{f.note}</span>
                        </div>
                        <span className="font-mono text-sm">
                            {f.col || <span className="text-rose-300">not set</span>}
                        </span>
                    </div>
                ))}
            </div>

            {/* features vs held out */}
            <div className="mt-8 grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-[--line] bg-[--panel] p-4">
                    <div className="text-sm font-semibold">Clues the model studies</div>
                    <p className="mt-1 text-xs text-[--faint]">{PLAIN.features}</p>
                    <ul className="mt-2 space-y-1">
                        {feats.length === 0 && <li className="text-sm text-[--muted]">none</li>}
                        {feats.map((c) => (
                            <li key={c} className="font-mono text-sm">
                                {c}
                            </li>
                        ))}
                    </ul>
                </div>
                <div className="rounded-xl border border-[--line] bg-[--panel] p-4">
                    <div className="text-sm font-semibold">Hidden from the model</div>
                    <p className="mt-1 text-xs text-[--faint]">{PLAIN.heldout}</p>
                    <ul className="mt-2 space-y-1.5">
                        {excl.map((c) => (
                            <li key={c} className="text-sm">
                                <span className="font-mono">{c}</span>
                                <span className="block text-xs text-[--faint]">
                                    {exclText(reasons[c])}
                                </span>
                            </li>
                        ))}
                    </ul>
                </div>
            </div>

            {/* how it's tested */}
            <h2 className="mt-8 text-sm font-semibold uppercase tracking-wide text-[--faint]">
                How the score is kept honest
            </h2>
            <ul className="mt-2 space-y-1.5 rounded-xl border border-[--line] bg-[--panel] px-4 py-3 text-sm">
                <li className="flex gap-2">
                    <span className="text-emerald-400">✓</span>
                    {SPLIT_LABEL[split.strategy] ||
                        'The data is split into a training part and a testing part.'}
                </li>
                {cb.positive_rate != null && (
                    <li className="flex gap-2">
                        <span className="text-[--faint]">•</span>
                        Of the rows, <b>{cb.positive_rate}%</b> failed and{' '}
                        <b>{cb.negative_rate}%</b> were paid
                        {cb.imbalance_ratio ? ` (${cb.imbalance_ratio})` : ''}.
                    </li>
                )}
            </ul>

            {/* verdict */}
            <div className="mt-8 flex flex-wrap items-center gap-3">
                <Pill tone={readyTone as any}>{status.replace(/_/g, ' ').toLowerCase()}</Pill>
                <span className="text-sm text-[--muted]">
                    {status.includes('READY')
                        ? 'This file can be turned into recovery cases.'
                        : 'This file is missing something the model needs.'}
                </span>
            </div>
            {warnings.length > 0 && (
                <ul className="mt-3 rounded-xl border border-amber-500/25 bg-amber-500/[0.06] px-4 py-2 text-sm">
                    {warnings.map((w, i) => (
                        <li key={i} className="flex gap-2 py-0.5">
                            <span className="text-amber-400">!</span>
                            {w}
                        </li>
                    ))}
                </ul>
            )}

            <div className="mt-8">
                <Note>
                    <b>Shadow model</b> = {PLAIN.shadowModel} One file per run — joining several
                    files on a shared key isn’t built yet.
                </Note>
            </div>
        </div>
    );
}
