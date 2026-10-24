import { useEffect, useState, useCallback } from 'react';
import { getCase } from '../../lib/api';
import { Ctx } from '../types';

/** Load / refresh the active case snapshot (GET /system/cases/{id}). */
export function useSnap(ctx: Ctx, patch: (p: Partial<Ctx>) => void) {
    const [loading, setLoading] = useState(false);
    const [err, setErr] = useState('');

    const refresh = useCallback(async () => {
        if (!ctx.activeCaseId) return;
        setLoading(true);
        setErr('');
        try {
            const snap = await getCase(ctx.activeCaseId);
            patch({ snap });
        } catch (e: any) {
            setErr(e.message);
        }
        setLoading(false);
    }, [ctx.activeCaseId, patch]);

    useEffect(() => {
        if (!ctx.snap || ctx.snap.case_id !== ctx.activeCaseId) refresh();
    }, [ctx.activeCaseId]);

    return {
        snap: ctx.snap?.case_id === ctx.activeCaseId ? ctx.snap : null,
        loading,
        err,
        refresh,
    };
}
