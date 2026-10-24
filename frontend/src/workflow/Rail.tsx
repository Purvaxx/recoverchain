import { STEPS } from './types';

export default function Rail({ idx }: { idx: number }) {
    return (
        <nav aria-label="progress" className="hidden md:block">
            <ol className="space-y-1">
                {STEPS.map((s, i) => {
                    const done = i < idx;
                    const now = i === idx;
                    return (
                        <li
                            key={s.n}
                            className={`flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] transition-colors ${
                                now
                                    ? 'bg-white/[0.06] text-[--ink]'
                                    : done
                                      ? 'text-[--muted]'
                                      : 'text-[--faint]'
                            }`}
                        >
                            <span
                                className={`grid h-6 w-6 shrink-0 place-items-center rounded-full text-[11px] font-semibold ${
                                    now
                                        ? 'bg-[--accent] text-white'
                                        : done
                                          ? 'bg-emerald-500/15 text-emerald-300 ring-1 ring-inset ring-emerald-500/30'
                                          : 'ring-1 ring-inset ring-[--line]'
                                }`}
                            >
                                {done ? '✓' : s.n}
                            </span>
                            <span className={now ? 'font-medium' : ''}>{s.title}</span>
                        </li>
                    );
                })}
            </ol>
        </nav>
    );
}
