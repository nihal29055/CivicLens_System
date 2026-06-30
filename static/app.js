// App State
let lastLogCount = 0;
let isPipelineRunning = false;

document.addEventListener("DOMContentLoaded", () => {
    fetchStats();
    fetchReports();
    fetchLogs();

    setInterval(() => {
        if (!isPipelineRunning) { fetchStats(); fetchReports(); }
        fetchLogs();
    }, 1500);

    document.getElementById("btn-refresh")?.addEventListener("click", () => { fetchStats(); fetchReports(); });
    document.getElementById("clear-logs")?.addEventListener("click", () => {
        document.getElementById("log-console").innerHTML = '<div class="log-line system">[SYSTEM] Console cleared.</div>';
        lastLogCount = 0;
    });


    // Image select toggle
    const imageSelect = document.getElementById("image-select");
    const fileUploadWrapper = document.getElementById("file-upload-wrapper");
    imageSelect.addEventListener("change", (e) => {
        fileUploadWrapper.classList.toggle("hidden", e.target.value !== "upload");
    });

    // Drop zone
    const dropZone = document.getElementById("drop-zone");
    const customFileInput = document.getElementById("custom-file");
    dropZone.addEventListener("click", () => customFileInput.click());
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.style.borderColor = "var(--emerald-glow)";
    });
    ["dragleave", "drop"].forEach(ev => {
        dropZone.addEventListener(ev, () => { dropZone.style.borderColor = "rgba(0,242,254,0.3)"; });
    });
    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        if (e.dataTransfer.files.length) {
            customFileInput.files = e.dataTransfer.files;
            dropZone.querySelector(".drop-text").textContent = `Selected: ${e.dataTransfer.files[0].name}`;
            dropZone.querySelector(".upload-icon").textContent = "📸";
        }
    });
    customFileInput.addEventListener("change", () => {
        if (customFileInput.files.length) {
            dropZone.querySelector(".drop-text").textContent = `Selected: ${customFileInput.files[0].name}`;
            dropZone.querySelector(".upload-icon").textContent = "📸";
        }
    });

    // Form submit
    document.getElementById("simulator-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        if (isPipelineRunning) return;
        isPipelineRunning = true;
        setBtnLoading(true);

        const location = document.getElementById("sim-location").value;
        const source = document.getElementById("sim-source").value;
        const imageType = imageSelect.value;

        initPipelineVisuals();

        try {
            updatePipelineStep("ingest", "active", "Uploading...");

            let fileObject = null;
            if (imageType === "test_pothole.jpg") {
                const response = await fetch("/data/test_pothole.jpg");
                const blob = await response.blob();
                fileObject = new File([blob], "test_pothole.jpg", { type: "image/jpeg" });
            } else {
                if (!customFileInput.files.length) {
                    alert("Please select or drop an image file.");
                    isPipelineRunning = false;
                    setBtnLoading(false);
                    return;
                }
                fileObject = customFileInput.files[0];
            }

            updatePipelineStep("ingest", "success", "Uploaded");

            const formData = new FormData();
            formData.append("image", fileObject);
            formData.append("location", location);
            formData.append("source", source);

            const res = await fetch("/api/reports/submit", { method: "POST", body: formData });
            const data = await res.json();
            if (data.status === "error") throw new Error(data.message);

            trackPipelineProgress();

        } catch (err) {
            console.error(err);
            updatePipelineStep("ingest", "failed", "Failed");
            addConsoleLine(`Pipeline error: ${err.message}`, "error");
            isPipelineRunning = false;
            setBtnLoading(false);
        }
    });

    document.getElementById("btn-refresh").addEventListener("click", () => { fetchStats(); fetchReports(); });
    document.getElementById("clear-logs").addEventListener("click", () => {
        document.getElementById("log-console").innerHTML = '<div class="log-line system">[SYSTEM] Console cleared.</div>';
    });

    // Modal close
    const modal = document.getElementById("audit-modal");
    document.querySelector(".close-btn").onclick = () => modal.classList.add("hidden");
    window.onclick = (e) => { if (e.target === modal) modal.classList.add("hidden"); };
});

function initPipelineVisuals() {
    document.getElementById("pipeline-visuals").classList.remove("hidden");
    ["ingest", "gemini", "qdrant", "verification", "twilio"].forEach(s => {
        const el = document.getElementById(`step-${s}`);
        if (el) { el.className = "step"; el.querySelector(".step-status").textContent = "Pending"; }
    });
}

function updatePipelineStep(stepId, status, statusText) {
    const el = document.getElementById(`step-${stepId}`);
    if (el) { el.className = `step ${status}`; el.querySelector(".step-status").textContent = statusText; }
}

function setBtnLoading(isLoading) {
    const btn = document.getElementById("btn-submit");
    btn.disabled = isLoading;
    btn.querySelector(".btn-text").style.opacity = isLoading ? "0.7" : "1";
    btn.querySelector(".loader").classList.toggle("hidden", !isLoading);
}

function trackPipelineProgress() {
    let checkCount = 0;
    const interval = setInterval(async () => {
        checkCount++;
        const logs = await fetchLogs();

        const has = (kw) => logs.some(l => l.message.includes(kw));

        if (has("Gemini Analysis:")) updatePipelineStep("gemini", "success", "Analysis Complete");
        else if (has("Invoking Gemini")) updatePipelineStep("gemini", "active", "Analyzing...");

        if (has("FRAUD DETECTED")) {
            updatePipelineStep("qdrant", "success", "Duplicate Found");
            updatePipelineStep("verification", "failed", "FRAUD BLOCKED");
            updatePipelineStep("twilio", "failed", "Aborted — Fraud");
            endPipeline(interval);
        } else if (has("Evidence unique")) {
            updatePipelineStep("qdrant", "success", "Unique Verified");
            updatePipelineStep("verification", "success", "Evidence Archived");
        } else if (has("Querying Qdrant")) {
            updatePipelineStep("qdrant", "active", "Searching...");
        }

        if (has("Evidence unique")) {
            if (has("Severity Moderate/Low")) {
                updatePipelineStep("twilio", "success", "Logged (Not Critical)");
                endPipeline(interval);
            } else if (has("Simulation Call Sid") || has("Twilio Call Sid")) {
                updatePipelineStep("twilio", "success", "Call Dispatched");
                endPipeline(interval);
            } else if (has("CRITICAL severity")) {
                updatePipelineStep("twilio", "active", "Dialing Contractor...");
            }
        }

        if (checkCount > 90) { endPipeline(interval); }
    }, 1000);
}

function endPipeline(intervalId) {
    clearInterval(intervalId);
    isPipelineRunning = false;
    setBtnLoading(false);
    fetchStats();
    fetchReports();
}

async function fetchStats() {
    try {
        const res = await fetch("/api/stats");
        const data = await res.json();
        document.getElementById("stat-total").textContent = data.total || 0;
        document.getElementById("stat-verified").textContent = data.verified || 0;
        document.getElementById("stat-duplicates").textContent = data.duplicates || 0;
        document.getElementById("stat-calls").textContent = data.active_calls || 0;
        document.getElementById("qdrant-count").textContent = data.qdrant_vectors || 0;
    } catch (e) { console.error(e); }
}

async function fetchReports() {
    try {
        const res = await fetch("/api/reports");
        const reports = await res.json();
        const tbody = document.getElementById("audit-tbody");

        if (!reports.length) {
            tbody.innerHTML = `<tr><td colspan="7" class="table-loading">No reports yet. Launch your first audit above!</td></tr>`;
            return;
        }

        tbody.innerHTML = "";
        reports.forEach(report => {
            const tr = document.createElement("tr");
            const date = new Date(report.timestamp).toLocaleString();

            // ── Status badge (evidence verification only) ──────────────────
            let statusBadge = "";
            if (report.status === "Verified") {
                statusBadge = `<span class="status-pill verified">✓ Verified</span>`;
            } else if (report.status === "Duplicate Fraud") {
                const pct = report.duplicate_score ? ` (${(report.duplicate_score * 100).toFixed(0)}%)` : "";
                statusBadge = `<span class="status-pill fraud">❌ Fraud Blocked${pct}</span>`;
            } else {
                statusBadge = `<span class="status-pill pending">${report.status}</span>`;
            }

            // ── Severity badge ─────────────────────────────────────────────
            let sevBadge = "";
            if (report.severity && report.severity !== "Analyzing...") {
                sevBadge = `<span class="sev-pill ${report.severity.toLowerCase()}">${report.severity}</span>`;
            }

            // ── Acknowledgement Status column ──────────────────────────────
            // Shows the CALL status separately from evidence verification
            let ackHtml = `<span style="color:var(--text-secondary)">—</span>`;
            const action = report.action_taken || "";
            const callerResp = report.caller_response || "";

            if (report.status === "Duplicate Fraud") {
                ackHtml = `<span class="ack-pill blocked">🚫 No Call (Fraud)</span>`;
            } else if (action === "Logged for Maintenance") {
                ackHtml = `<span class="ack-pill maintenance">📋 Logged (Routine)</span>`;
            } else if (callerResp && callerResp !== "None") {
                // Contractor actually responded
                ackHtml = `<span class="ack-pill acknowledged">✅ ${callerResp}</span>`;
            } else if (action === "Twilio Call Dispatched") {
                // Real call sent — waiting for human to pick up
                ackHtml = `<span class="ack-pill awaiting">📞 Call Sent — Awaiting Answer</span>`;
            } else if (action === "Call Dispatched (Simulation)") {
                // Simulation mode — show press buttons
                ackHtml = `
                    <div class="sim-controls">
                        <span class="sim-help">⚠️ Awaiting contractor response:</span>
                        <div class="sim-buttons">
                            <button class="btn-small" onclick="simulateKey('${report.id}', '1')">Press 1 (Eng)</button>
                            <button class="btn-small" onclick="simulateKey('${report.id}', '2')">Press 2 (Hindi)</button>
                        </div>
                    </div>`;
            } else if (action === "None" || !action) {
                ackHtml = `<span class="ack-pill awaiting">⏳ Processing...</span>`;
            }

            // ── Rewards column ─────────────────────────────────────────────
            // Show reward only for verified, non-fraud reports
            let rewardsHtml = `<span style="color:var(--text-secondary)">—</span>`;
            if (report.status === "Verified") {
                rewardsHtml = `<span class="reward-pill">🏅 Civic Points</span>`;
            } else if (report.status === "Duplicate Fraud") {
                rewardsHtml = `<span style="color:var(--danger-glow);font-size:11px;">No Reward</span>`;
            }

            tr.innerHTML = `
                <td>
                    <div class="table-img-wrapper" onclick="openDetailsModal('${report.id}')">
                        <img src="${report.image_path}" class="table-img" alt="Civic Issue">
                    </div>
                </td>
                <td>
                    <div style="font-family:var(--font-mono);font-size:11px;">${date}</div>
                    <div style="font-size:10px;color:var(--text-secondary);">${report.source}</div>
                </td>
                <td>
                    <div class="incident-title">${report.issue_type} ${sevBadge}</div>
                    <div class="incident-loc">📌 ${report.location}</div>
                    <div class="incident-desc">${report.desc}</div>
                </td>
                <td>${statusBadge}</td>
                <td>${ackHtml}</td>
                <td>${rewardsHtml}</td>
                <td>
                    ${callerResp && callerResp !== "None"
                        ? `<span style="color:var(--warning-glow);font-size:12px;">📲 ${callerResp}</span>`
                        : `<span style="color:var(--text-secondary);font-size:12px;">—</span>`
                    }
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) { console.error(e); }
}


async function fetchLogs() {
    try {
        const res = await fetch("/api/logs");
        const logs = await res.json();
        if (logs.length !== lastLogCount) {
            const el = document.getElementById("log-console");
            el.innerHTML = "";
            logs.forEach(log => {
                const div = document.createElement("div");
                div.className = `log-line ${log.level.toLowerCase()}`;
                div.textContent = `[${log.timestamp}] [${log.level}] ${log.message}`;
                el.appendChild(div);
            });
            el.scrollTop = el.scrollHeight;
            lastLogCount = logs.length;
        }
        return logs;
    } catch (e) { return []; }
}

function addConsoleLine(text, level = "info") {
    const el = document.getElementById("log-console");
    const div = document.createElement("div");
    div.className = `log-line ${level}`;
    div.textContent = `[${new Date().toLocaleTimeString()}] [${level.toUpperCase()}] ${text}`;
    el.appendChild(div);
    el.scrollTop = el.scrollHeight;
}

async function clearDatabase() {
    if (!confirm('Clear ALL reports and Qdrant vectors? This cannot be undone.')) return;
    try {
        const res = await fetch('/api/clear-db', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
            addConsoleLine('Database cleared by admin.', 'warning');
            fetchStats();
            fetchReports();
        }
    } catch (e) { addConsoleLine(`Clear failed: ${e.message}`, 'error'); }
}

async function simulateKey(reportId, key) {
    addConsoleLine(`Simulating contractor keypress: ${key}...`);
    try {
        const formData = new FormData();
        formData.append("report_id", reportId);
        formData.append("key", key);
        const res = await fetch("/api/reports/simulate-key", { method: "POST", body: formData });
        const data = await res.json();
        if (data.status === "success") {
            addConsoleLine("Contractor acknowledged!", "success");
            fetchReports();
        } else {
            addConsoleLine(`Failed: ${data.message}`, "error");
        }
    } catch (e) { addConsoleLine(`Request failed: ${e.message}`, "error"); }
}

async function openDetailsModal(reportId) {
    try {
        const reports = await (await fetch("/api/reports")).json();
        const report = reports.find(r => r.id === reportId);
        if (!report) return;
        const modal = document.getElementById("audit-modal");
        const body = modal.querySelector(".modal-body");
        const date = new Date(report.timestamp).toLocaleString();

        body.innerHTML = `
            <h2>Audit Case #CLN-${report.id.substring(0, 8).toUpperCase()}</h2>
            <img src="${report.image_path}" class="modal-detail-img" alt="Issue Evidence">
            <div class="modal-info-grid">
                <div class="modal-info-item"><label>Issue Type</label><span>${report.issue_type}</span></div>
                <div class="modal-info-item"><label>Severity</label><span>${report.severity}</span></div>
                <div class="modal-info-item"><label>Status</label><span style="color:${report.status==='Verified'?'var(--emerald-glow)':'var(--danger-glow)'};">${report.status}</span></div>
                <div class="modal-info-item"><label>Reported At</label><span style="font-size:12px;">${date}</span></div>
                <div class="modal-info-item"><label>Location</label><span>📌 ${report.location}</span></div>
                <div class="modal-info-item"><label>Source</label><span>${report.source}</span></div>
                ${report.caller_response ? `<div class="modal-info-item"><label>Contractor Response</label><span style="color:var(--warning-glow);">📲 ${report.caller_response}</span></div>` : ''}
            </div>
            <div class="modal-info-item">
                <label>Visual Evidence Description</label>
                <div class="modal-desc-box">${report.desc}</div>
            </div>
        `;
        modal.classList.remove("hidden");
    } catch (e) { console.error(e); }
}
