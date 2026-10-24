import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Shell from './Shell';
import Workflow from './workflow/Workflow';
import Insights from './pages/Insights';
import CasesList from './pages/CasesList';
import CaseView from './pages/CaseView';
import { workflowDone } from './lib/progress';

/** Model 2 (the Insights report and its exploration views) is only reachable
 *  once the RecoverChain workflow has been completed at least once. */
function Report({ children }: { children: React.ReactNode }) {
    if (!workflowDone()) return <Navigate to="/" replace />;
    return <Shell>{children}</Shell>;
}

export default function App() {
    return (
        <BrowserRouter>
            <Routes>
                {/* model 1 — the guided RecoverChain workflow (own full-screen chrome) */}
                <Route path="/" element={<Workflow />} />

                {/* model 2 — the Insights report + its exploration views (gated) */}
                <Route
                    path="/insights"
                    element={
                        <Report>
                            <Insights />
                        </Report>
                    }
                />
                <Route
                    path="/cases"
                    element={
                        <Report>
                            <CasesList />
                        </Report>
                    }
                />
                <Route
                    path="/cases/:caseId"
                    element={
                        <Report>
                            <CaseView />
                        </Report>
                    }
                />

                <Route path="/overview" element={<Navigate to="/insights" replace />} />
                <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
        </BrowserRouter>
    );
}
