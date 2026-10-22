// Provenance comes from the server. Rendering never promotes a claim to Verified.
export function appendEvidence(message, data = {}) {
    // Social dialogue isn't a factual claim requiring a Verified/Unknown badge.
    if (data.response_kind === 'conversation') return;
    const labels = new Set(['Verified', 'User-provided', 'Inference', 'Unknown']);
    const statements = Array.isArray(data.statements) ? data.statements : [];
    const details = document.createElement('details');
    details.className = 'response-evidence';
    const summary = document.createElement('summary');
    summary.textContent = [...new Set(statements.map(s => labels.has(s.classification) ? s.classification : 'Unknown'))].join(' · ') || 'Unknown';
    details.append(summary);
    for (const statement of statements) {
        const row = document.createElement('p');
        const label = labels.has(statement.classification) ? statement.classification : 'Unknown';
        row.textContent = `${label}: ${statement.text}`;
        details.append(row);
    }
    for (const source of Array.isArray(data.sources) ? data.sources : []) {
        if (source.kind === 'tool') {
            const receipt = document.createElement('p');
            receipt.textContent = `Source: ${source.title || 'Local tool'} (${source.url || 'No receipt URI'})`;
            details.append(receipt);
            continue;
        }
        if (source.kind !== 'external') continue;
        let url;
        try { url = new URL(source.url); } catch { continue; }
        if (url.protocol !== 'https:') continue;
        const link = document.createElement('a');
        link.href = url.href;
        link.textContent = source.title || url.hostname;
        link.target = '_blank'; link.rel = 'noopener noreferrer';
        details.append(link, document.createElement('br'));
    }
    message.append(details);
}
