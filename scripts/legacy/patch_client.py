with open('frontend/src/api/client.ts', 'a', encoding='utf-8') as f:
    f.write('''
// Dataset Lab APIs
export async function fetchDatasets() {
    const res = await fetch(`${BASE_URL}/datasets`);
    if (!res.ok) throw new Error("Failed to fetch datasets");
    return res.json();
}

export async function fetchDatasetDetail(datasetId: string) {
    const res = await fetch(`${BASE_URL}/datasets/${datasetId}`);
    if (!res.ok) throw new Error("Failed to fetch dataset detail");
    return res.json();
}

export async function syncDatasets() {
    const res = await fetch(`${BASE_URL}/datasets/sync`, { method: 'POST' });
    if (!res.ok) throw new Error("Failed to sync datasets");
    return res.json();
}

export async function analyzeDataset(datasetId: string) {
    const res = await fetch(`${BASE_URL}/datasets/${datasetId}/analyze`, { method: 'POST' });
    if (!res.ok) throw new Error("Failed to analyze dataset");
    return res.json();
}

export async function uploadDataset(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${BASE_URL}/datasets/upload`, {
        method: 'POST',
        body: formData,
    });
    if (!res.ok) {
        const d = await res.json().catch(()=>({}));
        throw new Error(d.detail || "Failed to upload dataset");
    }
    return res.json();
}
''')
