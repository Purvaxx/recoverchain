import { useEffect, useState } from 'react';
import { StepProps } from '../types';
import { useSnap } from './useSnap';
import { decideCase, executeCase } from '../../lib/api';
import { Spinner, ErrorNote, Note, KV, Pill } from '../../ui';
import { ACTION } from '../../lib/format';

export default function S10Recovery({ ctx, patch, next, setAction }: StepProps) {
    const { snap, loading, err, refresh } = useSnap(ctx, patch);
    const [note, setNote] = useState('');
    const [localErr, setLocalErr] = useState('');

    const pol = snap?.policy_decision?.status;
    const exec = snap?.execution_record;
    const top = snap?.recommendation?.top_candidate;
    const actionName = top ? ACTION[top.action_type] || top.action_type : '—';

    async function approveAndRun() {
        setLocalErr('');
        try {
            await decideCase(ctx.activeCaseId!, 'APPROVE', note || '(approved in workflow)');
            await executeCase(ctx.activeCaseId!);
            await refresh();
        } catch (e: any) {
            setLocalErr(e.message);
        }
    }
    async function reject() {
        setLocalErr('');
        try {
            await decideCase(ctx.activeCaseId!, 'REJECT', note || '(rejected in workflow)');
            await refresh();
        } catch (e: any) {
            setLocalErr(e.message);
        }
    }

    useEffect(() => {
        if (!snap) {
            setAction(null);
            return;
        }
        if (exec) {
            setAction({ label: 'Proceed →', onClick: next });
            return;
        }
        if (pol === 'ESCALATE') {
            setAction({
                label: 'Approve & execute recovery →',
                busy: 'Approving and running…',
                onClick: approveAndRun,
                secondary: { label: 'Reject', onClick: reject },
            });
            return;
        }
        // WAIT / DENIED — nothing to execute
        setAction({ label: 'Proceed →', onClick: next });
    }, [snap, exec, pol, note]);

    if (loading || !snap)
        return err ? <ErrorNote onRetry={refresh}>{err}</ErrorNote> : <Spinner label="Loading…" />;

    return (
        <div className="max-w-2xl">
            <h1 className="text-3xl font-bold tracking-tight">Running the recovery</h1>
            <p className="mt-3 text-[--muted]">
                This is where the chosen action actually happens —{' '}
                <b className="text-[--ink]">{actionName}</b>. It runs in a safe test mode: no real
                charge is made and no message is really sent. The next screen checks whether the
                money actually came back.
            </p>

            {exec ? (
                <div className="mt-8 rounded-2xl border border-[--line] bg-[--panel] px-5 py-2">
                    <KV
                        k="Execution status"
                        v={
                            exec.status === 'COMPLETED_SIMULATED' ? (
                                <Pill tone="green">Completed (simulated)</Pill>
                            ) : (
                                <Pill
                                    tone={
                                        exec.status === 'REJECTED' || exec.status === 'FAILED'
                                            ? 'red'
                                            : 'blue'
                                    }
                                >
                                    {exec.status}
                                </Pill>
                            )
                        }
                    />
                    <KV k="Handled by" v={exec.agent_type} />
                    <KV
                        k="Adapter"
                        v={<span className="font-mono text-xs">{exec.adapter_used}</span>}
                    />
                    {exec.result_metadata?.metadata?.message && (
                        <KV k="Message" v={exec.result_metadata.metadata.message} />
                    )}
                </div>
            ) : pol === 'ESCALATE' ? (
                <div className="mt-8">
                    <div className="rounded-2xl border border-amber-500/25 bg-amber-500/[0.05] px-5 py-4 text-sm">
                        This action is above the automated limit. It won’t run until you approve it.
                    </div>
                    <textarea
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        rows={2}
                        placeholder="Note (optional)"
                        className="mt-3 w-full rounded-lg border border-[--line] bg-[--bg] px-3 py-2 text-sm"
                    />
                </div>
            ) : (
                <div className="mt-8 rounded-2xl border border-[--line] bg-[--panel] px-5 py-4 text-sm text-[--muted]">
                    Not executed —{' '}
                    {snap.policy_decision?.reason ||
                        'the policy check did not approve this action.'}
                </div>
            )}

            {localErr && (
                <div className="mt-5">
                    <ErrorNote>{localErr}</ErrorNote>
                </div>
            )}

            <div className="mt-8">
                <Note tone="amber">
                    Execution is <b>simulated</b> (MockExecutionAdapter). No real payment is retried
                    and no message is actually sent. Swapping in a real payment/communication
                    adapter is future work.
                </Note>
            </div>
        </div>
    );
}
