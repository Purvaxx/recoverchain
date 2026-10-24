import { useEffect, useState } from 'react';

export const prefersReducedMotion = () =>
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

const KEY = 'rc-motion';

/** Whether rich (3D / GSAP) motion is enabled. Default: on, unless the OS asks
 *  for reduced motion. Persisted per browser; toggle in the workflow top bar. */
export function useMotionPref(): [boolean, (v: boolean) => void] {
    const [on, setOn] = useState<boolean>(() => {
        try {
            const s = localStorage.getItem(KEY);
            if (s === '0') return false;
            if (s === '1') return true;
        } catch {
            /* ignore */
        }
        return !prefersReducedMotion();
    });
    useEffect(() => {
        try {
            localStorage.setItem(KEY, on ? '1' : '0');
        } catch {
            /* ignore */
        }
    }, [on]);
    return [on, setOn];
}
