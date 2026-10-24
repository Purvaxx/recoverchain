import { useNavigate, useLocation } from 'react-router-dom';
import { Lock } from 'lucide-react';
import { useWorkflowDone } from './lib/progress';

/** Top-level switch between the two "models": the guided RecoverChain workflow
 *  and the Insights report. The Insights side is locked until the user has run
 *  the workflow through to the Verified Result step at least once. */
export default function ModeSwitch() {
    const nav = useNavigate();
    const { pathname } = useLocation();
    const done = useWorkflowDone();
    const onReport = pathname.startsWith('/insights') || pathname.startsWith('/cases');

    return (
        <div className="inline-flex rounded-lg border border-[--line] bg-[--panel] p-0.5 text-xs font-semibold">
            <button
                onClick={() => nav('/')}
                className={`rounded-md px-3 py-1.5 transition-colors ${!onReport ? 'bg-[--accent] text-white' : 'text-[--muted] hover:text-[--ink]'}`}
            >
                RecoverChain
            </button>
            {done ? (
                <button
                    onClick={() => nav('/insights')}
                    className={`rounded-md px-3 py-1.5 transition-colors ${onReport ? 'bg-[--accent] text-white' : 'text-[--muted] hover:text-[--ink]'}`}
                >
                    Insights
                </button>
            ) : (
                <span
                    title="Finish the RecoverChain process to unlock the Insights report"
                    className="inline-flex cursor-not-allowed items-center gap-1 rounded-md px-3 py-1.5 text-[--faint]"
                >
                    <Lock size={11} /> Insights
                </span>
            )}
        </div>
    );
}
