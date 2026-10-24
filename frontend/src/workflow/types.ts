export const STEPS = [
    { n: '01', title: 'Upload data' },
    { n: '02', title: 'Data review' },
    { n: '03', title: 'Data quality' },
    { n: '04', title: 'Data mapping' },
    { n: '05', title: 'Data connection' },
    { n: '06', title: 'Revenue risk detection' },
    { n: '07', title: 'AI analysis' },
    { n: '08', title: 'Decision & policy' },
    { n: '09', title: 'Recovery' },
    { n: '10', title: 'Verified result' },
] as const;

export interface Ctx {
    importId?: string;
    detail?: any; // GET /datasets/{id}
    status?: any; // GET /datasets/{id}/workflow-status
    preview?: any; // GET /datasets/{id}/preview
    readiness?: any; // POST /datasets/{id}/ml-readiness
    build?: any; // POST /datasets/{id}/generate-cases
    caseIds?: string[];
    caseCount?: number;
    activeCaseId?: string;
    snap?: any; // GET /system/cases/{activeCaseId}
}

export interface StepProps {
    ctx: Ctx;
    patch: (p: Partial<Ctx>) => void;
    next: () => void;
    back: () => void;
    setAction: (a: Action | null) => void;
}

export interface Action {
    label: string;
    onClick: () => void | Promise<void>;
    disabled?: boolean;
    busy?: string;
    secondary?: { label: string; onClick: () => void | Promise<void> };
}
