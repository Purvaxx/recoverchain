import { useEffect, useState } from 'react';

/** Tracks whether the user has run the RecoverChain workflow through to the
 *  Verified Result step at least once. The Insights report (model 2) stays
 *  locked until this is true. */
const KEY = 'rc-workflow-done';
const listeners = new Set<() => void>();

export function workflowDone(): boolean {
    try {
        return localStorage.getItem(KEY) === '1';
    } catch {
        return false;
    }
}

export function markWorkflowDone(): void {
    try {
        localStorage.setItem(KEY, '1');
    } catch {
        /* private mode / storage disabled — Insights stays locked, no crash */
    }
    listeners.forEach((fn) => fn());
}

export function resetWorkflow(): void {
    try {
        localStorage.removeItem(KEY);
    } catch {
        /* ignore */
    }
    listeners.forEach((fn) => fn());
}

export function useWorkflowDone(): boolean {
    const [done, setDone] = useState(workflowDone);
    useEffect(() => {
        const sync = () => setDone(workflowDone());
        listeners.add(sync);
        window.addEventListener('storage', sync);
        return () => {
            listeners.delete(sync);
            window.removeEventListener('storage', sync);
        };
    }, []);
    return done;
}
