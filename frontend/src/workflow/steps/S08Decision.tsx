import { useEffect } from 'react';
import { StepProps } from '../types';
import { useSnap } from './useSnap';
import { Spinner, ErrorNote, Note, Row, BigStat } from '../../ui';
import { money, pct, ACTION, WHY_FAILED, RULE_LABEL, policyVerdict } from '../../lib/format';

/** Merged "Decision & policy" — what the rules engine proposes AND whether the
 *  PolicyEngine authorises it, on one screen. */
export default function S08Decision({ ctx, patch, next, setAction }: StepProps) {
    const { snap, loading, err, refresh } = useSnap(ctx, patch);
    useEffect(() => {
        setAction(snap ? { label: 'Proceed →', onClick: next } : null);
    }, [snap]);

    if (loading || !snap)
        return err ? (
            <ErrorNote onRetry={refresh}>{err}</ErrorNote>
        ) : (
            <Spinner label="Loading the decision…" />
        );

    const rec = snap.recommendation;
    const top = rec?.top_candidate;
    const dx = snap.diagnosis;
    const pol = snap.policy_decision;
    const ccy = snap.currency || 'INR';
    const v = policyVerdict(pol?.status);
    const rules = pol?.rules_evaluated || [];

    const headline = top ? ACTION[top.action_type] || top.action_type : 'No action available';
    const also = (rec?.candidates || []).filter((c: any) => c.action_type !== top?.action_type);

    return (
        <div className="max-w-2xl">
            <h1 className="text-3xl font-bold tracking-tight">
                What we’d do — and are we allowed?
            </h1>
            <p className="mt-3 text-[--muted]">
                Two separate things. First the <b className="text-[--ink]">rulebook suggests</b> an
                action. Then the <b className="text-[--ink]">policy check</b> decides if it’s safe
                to run automatically, or if a person must approve it. The suggestion can’t skip the
                check.
            </p>

            <div className="mt-8 text-[11px] font-semibold uppercase tracking-[0.14em] text-[--faint]">
                Suggested action
            </div>
            <div className="mt-1 text-2xl font-bold tracking-tight">{headline}</div>

            {/* the proposal */}
            {top ? (
                <ul className="mt-6">
                    {dx && (
                        <Row ok>Cause: {WHY_FAILED[dx.cause_category] || dx.cause_category}</Row>
                    )}
                    <Row ok>
                        Recovery estimate for this action: {pct(top.estimated_probability)}
                    </Row>
                    <Row ok>
                        Expected value recovered: {money(top.expected_recoverable_value, ccy)}
                    </Row>
                    {top.rationale && <Row>{top.rationale}</Row>}
                </ul>
            ) : (
                <p className="mt-4 text-[--muted]">
                    {rec?.rationale || 'The evaluator found no viable action for this case.'}
                </p>
            )}

            {also.length > 0 && (
                <>
                    <div className="mt-6 text-sm font-semibold text-[--faint]">Also considered</div>
                    <ul className="mt-2 space-y-1 text-sm text-[--muted]">
                        {also.map((c: any) => (
                            <li key={c.action_type}>
                                {ACTION[c.action_type] || c.action_type} — est. value{' '}
                                {money(c.expected_recoverable_value, ccy)}
                            </li>
                        ))}
                    </ul>
                </>
            )}

            {/* the policy gate — same screen */}
            <h2 className="mt-10 text-sm font-semibold uppercase tracking-wide text-[--faint]">
                Policy check
            </h2>
            <ul className="mt-2 divide-y divide-[--line] rounded-xl border border-[--line]">
                {rules.length === 0 && (
                    <li className="px-4 py-3 text-sm text-[--muted]">No rules were applicable.</li>
                )}
                {rules.map((r: any, i: number) => (
                    <li key={i} className="flex items-start gap-3 px-4 py-3 text-sm">
                        <span className={r.passed ? 'text-emerald-400' : 'text-amber-400'}>
                            {r.passed ? '✓' : '⚠'}
                        </span>
                        <span>
                            <span className="font-medium">
                                {RULE_LABEL[r.rule_name] || r.rule_name}
                            </span>
                            <span className="block text-[--muted]">{r.details}</span>
                        </span>
                    </li>
                ))}
            </ul>

            <div className="mt-6">
                <BigStat
                    label="Policy result"
                    value={v.label}
                    tone={v.tone as any}
                    sub={pol?.reason || v.note}
                />
            </div>

            <div className="mt-8">
                <Note>
                    The <b>rules engine</b> ({rec?.engine_version}) proposes an action — it never
                    runs one. The
                    <b> PolicyEngine</b> ({pol?.policy_version}) is the only thing that can
                    authorise it, and execution only happens after approval. No component bypasses
                    this.
                </Note>
            </div>
        </div>
    );
}
