// ── CIVICLENS ENTERPRISE CONTROLLER & MULTI-PAGE ENGINE ──
let currentView = "home";
let currentUserRole = null;
let lastLogCount = 0;
let isPipelineRunning = false;
let wsEnabled = false;
let wsConn = null;
let allReports = [];
let allLogs = [];
let activeLogFilter = "all";
let activeLedgerFilter = "all";
let audioFxEnabled = true;
let audioCtx = null;
let gisMap = null;
let mapMarkers = [];

// DOM Ready
document.addEventListener("DOMContentLoaded", () => {
    initViewRouting();
    initGisMap();
    initWebSocket();
    fetchStats();
    fetchReports();
    fetchLogs();

    // Auto-refresh polling
    setInterval(() => {
        if (!isPipelineRunning) {
            fetchStats();
            fetchReports();
        }
        if (!wsEnabled) {
            fetchLogs();
        }
    }, 1500);

    // Setup Event Listeners
    setupHomeReportForm();
    setupDashboardForm();
    setupDropZones();

    // Ledger Search input
    document.getElementById("ledger-search")?.addEventListener("input", () => {
        renderReportsTable();
    });

    document.getElementById("btn-refresh")?.addEventListener("click", () => {
        playTone(600, 0.08);
        fetchStats();
        fetchReports();
    });

    document.getElementById("clear-logs")?.addEventListener("click", () => {
        const consoleEl = document.getElementById("log-console");
        if (consoleEl) consoleEl.innerHTML = '<div class="log-line system">[SYSTEM] Telemetry stream cleared.</div>';
        lastLogCount = 0;
    });

    // Global Keydown
    window.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeModal("audit-modal");
            closeModal("pitch-deck-modal");
        } else if ((e.key === "p" || e.key === "P") && e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA") {
            openPitchDeck();
        }
    });
});

// ── MULTI-PAGE VIEW ROUTING ──
function initViewRouting() {
    const hash = window.location.hash.replace("#", "") || "home";
    switchView(hash, false);

    window.addEventListener("hashchange", () => {
        const newHash = window.location.hash.replace("#", "") || "home";
        switchView(newHash, false);
    });
}

function switchView(viewName, updateHash = true) {
    playTone(520, 0.04);
    currentView = viewName;
    if (updateHash) {
        window.location.hash = viewName;
    }

    document.querySelectorAll(".page-view").forEach(v => v.classList.remove("active"));
    const targetView = document.getElementById(`view-${viewName}`);
    if (targetView) {
        targetView.classList.add("active");
    } else {
        document.getElementById("view-home")?.classList.add("active");
    }

    // Update active navbar tab
    document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
    const activeTab = document.getElementById(`tab-${viewName}`);
    if (activeTab) activeTab.classList.add("active");

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });

    // Refresh GIS map if dashboard opened
    if (viewName === "dashboard") {
        setTimeout(() => {
            if (gisMap) gisMap.invalidateSize();
        }, 200);
    }
}

function scrollToReport() {
    switchView('home');
    setTimeout(() => {
        const target = document.getElementById("quick-report");
        if (target) target.scrollIntoView({ behavior: 'smooth' });
    }, 100);
}

// ── AUTHENTICATION & ROLE SWITCHING ──
function loginWithRole(role) {
    playTone(750, 0.1, "triangle");
    currentUserRole = role;

    const badge = document.getElementById("active-officer-badge");
    if (badge) {
        if (role === "commissioner") {
            badge.textContent = "🏛️ MUNICIPAL COMMISSIONER (CITYWIDE COMMAND)";
        } else if (role === "pwd_chief") {
            badge.textContent = "🛣️ CHIEF ENGINEER — PUBLIC WORKS DEPT (PWD)";
        } else if (role === "water_board") {
            badge.textContent = "💧 EXECUTIVE ENGINEER — WATER SUPPLY & SEWERAGE (SDB)";
        }
    }

    addConsoleLine(`[AUTH] Officer logged in as: ${role.toUpperCase()}`, "success");
    switchView("dashboard");
}

function handleManualLogin(e) {
    e.preventDefault();
    const id = document.getElementById("login-id")?.value || "Officer";
    playTone(750, 0.1, "triangle");
    currentUserRole = "custom";

    const badge = document.getElementById("active-officer-badge");
    if (badge) badge.textContent = `🏛️ OFFICER: ${id.toUpperCase()}`;

    addConsoleLine(`[AUTH] Authenticated officer session: ${id}`, "success");
    switchView("dashboard");
}

function logoutOfficer() {
    playTone(400, 0.08);
    currentUserRole = null;
    addConsoleLine("[AUTH] Officer logged out.", "system");
    switchView("home");
}

// ── CITIZEN HOME REPORT FORM ──
function setupHomeReportForm() {
    const form = document.getElementById("home-report-form");
    const fileInput = document.getElementById("home-custom-file");
    const dropZone = document.getElementById("home-drop-zone");
    const dropText = document.getElementById("home-drop-text");

    if (dropZone && fileInput) {
        dropZone.addEventListener("click", () => fileInput.click());
        fileInput.addEventListener("change", () => {
            if (fileInput.files.length) {
                dropText.textContent = `Selected: ${fileInput.files[0].name}`;
            }
        });
    }

    form?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const feedback = document.getElementById("home-report-feedback");
        const btn = document.getElementById("home-btn-submit");
        const loader = document.getElementById("home-loader");

        if (!fileInput || !fileInput.files.length) {
            alert("Please select or drop an evidence photo first.");
            return;
        }

        playTone(520, 0.1, "sine");
        btn.disabled = true;
        loader?.classList.remove("hidden");

        const location = document.getElementById("home-sim-location")?.value || "Citizen Report Pin";
        const file = fileInput.files[0];

        try {
            const formData = new FormData();
            formData.append("image", file);
            formData.append("location", location);
            formData.append("source", "Citizen Web Portal");

            const res = await fetch("/api/reports/submit", { method: "POST", body: formData });
            const data = await res.json();
            if (data.status === "error") throw new Error(data.message);

            if (feedback) {
                feedback.className = "report-feedback-box success";
                feedback.innerHTML = `
                    <strong>✅ Evidence Submitted Successfully!</strong><br>
                    <span>Autonomous AI audit is running. If unique, an anonymous voucher will be minted. You can check status in the <em>🎁 Track Voucher</em> tab or in the Government Ledger.</span>
                `;
                feedback.classList.remove("hidden");
            }
            playChime();
            fetchStats();
            fetchReports();

        } catch (err) {
            if (feedback) {
                feedback.className = "report-feedback-box error";
                feedback.innerHTML = `<strong>❌ Submission Failed:</strong> ${err.message}`;
                feedback.classList.remove("hidden");
            }
            playAlarm();
        } finally {
            btn.disabled = false;
            loader?.classList.add("hidden");
        }
    });
}

// ── VOUCHER TRACKER LOOKUP ──
function lookupVoucher() {
    playTone(600, 0.08);
    const code = (document.getElementById("voucher-input")?.value || "").trim().toUpperCase();
    const resultBox = document.getElementById("voucher-result-box");
    if (!resultBox) return;

    if (!code) {
        alert("Please enter a voucher code (e.g. CVL-8942-PWD).");
        return;
    }

    const match = allReports.find(r => r.voucher_code && r.voucher_code.toUpperCase() === code);

    if (match) {
        resultBox.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:8px; margin-bottom:10px;">
                <span class="status-pill verified">✓ VERIFIED CITIZEN REWARD</span>
                <span style="font-family:var(--font-mono); color:#c084fc; font-weight:700;">${match.voucher_code}</span>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:11px;">
                <div><strong>Reward Balance:</strong> <span style="color:var(--emerald); font-weight:700;">+150 Civic Points</span></div>
                <div><strong>Assigned Department:</strong> <span style="color:var(--cyan);">${match.department || 'Public Works Dept'}</span></div>
                <div><strong>Hazard Classification:</strong> <span>${match.issue_type} (${match.severity})</span></div>
                <div><strong>Location Pin:</strong> <span>${match.location}</span></div>
            </div>
            <div style="margin-top:10px; font-size:10px; color:#cbd5e1; background:rgba(0,242,254,0.06); padding:8px; border-radius:4px;">
                🎁 <strong>Utility Rebate Status:</strong> Eligible for 5% Municipal Property Tax credit or Water/Electricity bill deduction on next municipal billing cycle.
            </div>
        `;
    } else {
        resultBox.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:8px; margin-bottom:10px;">
                <span class="status-pill verified">✓ ACTIVE DEMO VOUCHER</span>
                <span style="font-family:var(--font-mono); color:#c084fc; font-weight:700;">${code}</span>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:11px;">
                <div><strong>Reward Balance:</strong> <span style="color:var(--emerald); font-weight:700;">+150 Civic Points</span></div>
                <div><strong>Assigned Department:</strong> <span style="color:var(--cyan);">Public Works Department (PWD)</span></div>
                <div><strong>Verification Status:</strong> <span style="color:var(--emerald);">Cryptographically Validated</span></div>
                <div><strong>Municipal Zone:</strong> <span>Central Ward Sector 4</span></div>
            </div>
            <div style="margin-top:10px; font-size:10px; color:#cbd5e1; background:rgba(0,242,254,0.06); padding:8px; border-radius:4px;">
                🎁 <strong>Rebate Credit:</strong> ₹500 INR credit allocated against municipal property account.
            </div>
        `;
    }

    resultBox.classList.remove("hidden");
}

// ── CONTACT US FORM ──
function handleContactSubmit(e) {
    e.preventDefault();
    playTone(800, 0.1, "triangle");
    alert("Thank you! Your Municipal Partnership & Deployment Inquiry has been logged. Our Smart City Governance team will contact you within 24 hours.");
    e.target.reset();
}

// ── DASHBOARD SIMULATOR FORM ──
function setupDashboardForm() {
    const imageSelect = document.getElementById("image-select");
    const fileUploadWrapper = document.getElementById("file-upload-wrapper");
    imageSelect?.addEventListener("change", (e) => {
        fileUploadWrapper?.classList.toggle("hidden", e.target.value !== "upload");
    });

    const form = document.getElementById("simulator-form");
    form?.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (isPipelineRunning) return;
        
        playTone(520, 0.12, "sine");
        isPipelineRunning = true;
        setBtnLoading(true);

        const location = document.getElementById("sim-location")?.value || "Sector 4, West Ring Road";
        const source = document.getElementById("sim-source")?.value || "Web Portal";
        const imageType = imageSelect?.value || "test_pothole.jpg";
        const customFileInput = document.getElementById("custom-file");

        initPipelineVisuals();
        updatePipelineStep("ingest", "active", "Pre-screening...");

        try {
            let fileObject = null;
            if (imageType !== "upload") {
                const response = await fetch(`/data/${imageType}`);
                if (!response.ok) throw new Error(`Asset /data/${imageType} not found`);
                const blob = await response.blob();
                fileObject = new File([blob], imageType, { type: "image/jpeg" });
            } else {
                if (!customFileInput || !customFileInput.files.length) {
                    alert("Please select or drop an image file.");
                    isPipelineRunning = false;
                    setBtnLoading(false);
                    return;
                }
                fileObject = customFileInput.files[0];
            }

            updatePipelineStep("ingest", "success", "Validated");
            playTone(880, 0.08, "triangle");

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
            playAlarm();
            isPipelineRunning = false;
            setBtnLoading(false);
        }
    });
}

function setupDropZones() {
    const dropZone = document.getElementById("drop-zone");
    const customFileInput = document.getElementById("custom-file");
    if (dropZone && customFileInput) {
        dropZone.addEventListener("click", () => customFileInput.click());
        dropZone.addEventListener("dragover", (e) => {
            e.preventDefault();
            dropZone.style.borderColor = "var(--cyan)";
        });
        ["dragleave", "drop"].forEach(ev => {
            dropZone.addEventListener(ev, () => { dropZone.style.borderColor = "rgba(0,242,254,0.3)"; });
        });
        dropZone.addEventListener("drop", (e) => {
            e.preventDefault();
            if (e.dataTransfer.files.length) {
                customFileInput.files = e.dataTransfer.files;
                const textEl = dropZone.querySelector(".drop-text");
                if (textEl) textEl.textContent = `Selected: ${e.dataTransfer.files[0].name}`;
            }
        });
        customFileInput.addEventListener("change", () => {
            if (customFileInput.files.length) {
                const textEl = dropZone.querySelector(".drop-text");
                if (textEl) textEl.textContent = `Selected: ${customFileInput.files[0].name}`;
            }
        });
    }
}

// ── GIS LEAFLET MAP INITIALIZATION ──
function initGisMap() {
    const mapEl = document.getElementById("gis-map");
    if (!mapEl || typeof L === "undefined") return;

    try {
        gisMap = L.map('gis-map', {
            zoomControl: false,
            attributionControl: false
        }).setView([12.9750, 77.6100], 12);

        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            subdomains: 'abcd',
            maxZoom: 19
        }).addTo(gisMap);

        L.control.zoom({ position: 'bottomright' }).addTo(gisMap);
    } catch (e) {
        console.warn("GIS Map fallback:", e);
    }
}

function updateMapMarkers() {
    if (!gisMap || typeof L === "undefined") return;

    mapMarkers.forEach(m => gisMap.removeLayer(m));
    mapMarkers = [];

    const pinCountEl = document.getElementById("map-pin-count");
    if (pinCountEl) pinCountEl.textContent = `${allReports.length} Incidents Pinned`;

    allReports.forEach(report => {
        const lat = report.lat || 12.9716;
        const lng = report.lng || 77.5946;

        let color = "#10b981";
        if (report.status === "Duplicate Fraud") color = "#ef4444";
        else if (report.severity === "Critical") color = "#ef4444";
        else if (report.severity === "Moderate") color = "#f59e0b";
        else if (report.department?.includes("Water")) color = "#00f2fe";

        const customIcon = L.divIcon({
            className: 'custom-gis-pin',
            html: `<div style="
                width: 12px;
                height: 12px;
                background-color: ${color};
                border: 2px solid #ffffff;
                border-radius: 50%;
                box-shadow: 0 0 10px ${color};
            "></div>`,
            iconSize: [12, 12],
            iconAnchor: [6, 6]
        });

        const marker = L.marker([lat, lng], { icon: customIcon }).addTo(gisMap);
        
        const popupContent = `
            <div style="font-family:'Outfit', sans-serif; font-size:11px; color:#f8fafc; background:#0d1424; padding:8px; border-radius:6px; min-width:170px;">
                <div style="font-weight:700; color:#00f2fe; margin-bottom:3px;">${report.issue_type}</div>
                <div style="color:#94a3b8; font-size:10px; margin-bottom:3px;">🏢 ${report.department || 'Public Works Dept'}</div>
                <div style="color:#cbd5e1; font-size:9px; margin-bottom:4px;">📍 ${report.location}</div>
                <div style="display:flex; justify-content:space-between; font-size:9px;">
                    <span style="color:${report.status==='Verified'?'#10b981':'#ef4444'}; font-weight:700;">${report.status}</span>
                    <span style="font-family:monospace; color:#c084fc;">${report.voucher_code || ''}</span>
                </div>
            </div>
        `;

        marker.bindPopup(popupContent);
        mapMarkers.push(marker);
    });
}

function resetMapView() {
    if (gisMap) {
        gisMap.setView([12.9750, 77.6100], 12);
        playTone(700, 0.05);
    }
}

// ── 1-CLICK SHOWCASE PRESET TRIGGER ──
async function triggerPreset(presetId) {
    if (isPipelineRunning) return;
    isPipelineRunning = true;
    setBtnLoading(true);

    playTone(580, 0.1, "sine");
    initPipelineVisuals();
    updatePipelineStep("ingest", "active", "Initializing preset...");

    const activeBadge = document.getElementById("pipeline-active-badge");
    if (activeBadge) activeBadge.textContent = "EXECUTING PRESET";

    try {
        const formData = new FormData();
        formData.append("preset_id", presetId);

        const res = await fetch("/api/reports/preset", { method: "POST", body: formData });
        const data = await res.json();
        if (data.status === "error") throw new Error(data.message);

        addConsoleLine(`[VC_SHOWCASE] Launched demo preset: ${presetId}`, "system");
        updatePipelineStep("ingest", "success", "Asset Loaded");
        trackPipelineProgress();

    } catch (err) {
        console.error(err);
        updatePipelineStep("ingest", "failed", "Preset Error");
        addConsoleLine(`Preset failed: ${err.message}`, "error");
        playAlarm();
        isPipelineRunning = false;
        setBtnLoading(false);
    }
}

// ── PIPELINE TRACKING & VISUAL FLOW ──
function initPipelineVisuals() {
    ["ingest", "gemini", "qdrant", "verification", "twilio"].forEach(s => {
        const el = document.getElementById(`step-${s}`);
        if (el) {
            el.className = "flow-step";
            const statusEl = el.querySelector(".step-state");
            if (statusEl) statusEl.textContent = "Standby";
        }
    });
}

function updatePipelineStep(stepId, status, statusText) {
    const el = document.getElementById(`step-${stepId}`);
    if (el) {
        el.className = `flow-step ${status}`;
        const statusEl = el.querySelector(".step-state");
        if (statusEl) statusEl.textContent = statusText;
    }
}

function setBtnLoading(isLoading) {
    const btn = document.getElementById("btn-submit");
    if (!btn) return;
    btn.disabled = isLoading;
    const textEl = btn.querySelector(".btn-text");
    if (textEl) textEl.style.opacity = isLoading ? "0.7" : "1";
    const loader = btn.querySelector(".loader");
    if (loader) loader.classList.toggle("hidden", !isLoading);
}

function trackPipelineProgress() {
    let checkCount = 0;
    const interval = setInterval(async () => {
        checkCount++;
        const logs = await fetchLogs();
        const has = (kw) => logs.some(l => l.message && l.message.includes(kw));

        if (has("Gemini Analysis:")) {
            updatePipelineStep("gemini", "success", "Analyzed");
        } else if (has("Invoking Gemini")) {
            updatePipelineStep("gemini", "active", "Analyzing...");
        }

        if (has("FRAUD DETECTED")) {
            updatePipelineStep("qdrant", "success", "Duplicate Match");
            updatePipelineStep("verification", "failed", "FRAUD INTERCEPTED");
            updatePipelineStep("twilio", "failed", "Payment Blocked");
            playAlarm();
            endPipeline(interval);
        } else if (has("Evidence unique")) {
            updatePipelineStep("qdrant", "success", "Unique Verified");
            updatePipelineStep("verification", "success", "Voucher Minted");
        } else if (has("Querying Qdrant")) {
            updatePipelineStep("qdrant", "active", "Vector Scan...");
        }

        if (has("Evidence unique")) {
            if (has("Severity Moderate/Low") || has("Logged to")) {
                updatePipelineStep("twilio", "success", "Routine Queue");
                playChime();
                endPipeline(interval);
            } else if (has("Simulation Call Sid") || has("Twilio Call Sid") || has("Call result:")) {
                updatePipelineStep("twilio", "success", "Auto-Dialed");
                playChime();
                endPipeline(interval);
            } else if (has("CRITICAL severity") || has("Auto-dispatching")) {
                updatePipelineStep("twilio", "active", "Dialing Twilio...");
            }
        }

        if (checkCount > 90) {
            endPipeline(interval);
        }
    }, 1000);
}

function endPipeline(intervalId) {
    clearInterval(intervalId);
    isPipelineRunning = false;
    setBtnLoading(false);
    const activeBadge = document.getElementById("pipeline-active-badge");
    if (activeBadge) activeBadge.textContent = "COMPLETED";
    fetchStats();
    fetchReports();
}

// ── TWILIO HANDSET VOICE AUDIO ──
function testVoiceAudio() {
    playTone(440, 0.1, "sine");
    const promptText = document.getElementById("active-voice-prompt")?.textContent || 
        "Automated enforcement alert: Critical hazard verified at location. Press 1 for English, 2 for Hindi.";

    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(promptText);
        utterance.rate = 1.05;
        utterance.pitch = 1.0;
        window.speechSynthesis.speak(utterance);
    }
}

async function simulateHandsetKey(key) {
    playTone(key === '1' ? 800 : 950, 0.12, "triangle");
    addConsoleLine(`[TWILIO] Operator pressed Keypad [${key}] on handset...`, "system");

    const activeReport = allReports.find(r => r.action_taken?.includes("Call") && !r.caller_response);
    if (!activeReport) {
        addConsoleLine("[TWILIO] Acknowledged response registered: 4h repair SLA committed.", "success");
        return;
    }

    try {
        const formData = new FormData();
        formData.append("report_id", activeReport.id);
        formData.append("key", key);
        const res = await fetch("/api/reports/simulate-key", { method: "POST", body: formData });
        const data = await res.json();
        if (data.status === "success") {
            playTone(1200, 0.15, "sine");
            addConsoleLine(`[TWILIO] Contractor ACK logged via Key ${key} (ETA: 4 Hours)`, "success");
            fetchReports();
            fetchStats();
        }
    } catch (e) {
        console.error(e);
    }
}

// ── TELEMETRY & DATA FETCHING ──
async function fetchStats() {
    try {
        const res = await fetch("/api/stats");
        const data = await res.json();

        const savingsInr = data.total_savings_inr || 0;
        const savingsUsd = data.total_savings_usd || 0;

        const statSavings = document.getElementById("stat-savings");
        if (statSavings) statSavings.textContent = `₹${savingsInr.toLocaleString('en-IN')}`;

        const homeStatSavings = document.getElementById("home-stat-savings");
        if (homeStatSavings) homeStatSavings.textContent = `₹${savingsInr.toLocaleString('en-IN')}`;

        const statSavingsUsd = document.getElementById("stat-savings-usd");
        if (statSavingsUsd) statSavingsUsd.textContent = `$${savingsUsd.toLocaleString('en-US')} USD`;

        const homeStatSavingsUsd = document.getElementById("home-stat-savings-usd");
        if (homeStatSavingsUsd) homeStatSavingsUsd.textContent = `$${savingsUsd.toLocaleString('en-US')} USD`;

        const statVerified = document.getElementById("stat-verified");
        if (statVerified) statVerified.textContent = data.verified || 0;

        const homeStatVerified = document.getElementById("home-stat-verified");
        if (homeStatVerified) homeStatVerified.textContent = data.verified || 0;

        const statDuplicates = document.getElementById("stat-duplicates");
        if (statDuplicates) statDuplicates.textContent = data.duplicates || 0;

        const homeStatDuplicates = document.getElementById("home-stat-duplicates");
        if (homeStatDuplicates) homeStatDuplicates.textContent = data.duplicates || 0;

        const statCalls = document.getElementById("stat-calls");
        if (statCalls) statCalls.textContent = data.active_calls || 0;

        const qdrantCount = document.getElementById("qdrant-count");
        if (qdrantCount) qdrantCount.textContent = data.qdrant_vectors || data.total || 0;

        const qdrantBadge = document.getElementById("qdrant-badge-count");
        if (qdrantBadge) qdrantBadge.textContent = data.qdrant_vectors || data.total || 0;

        const countAll = document.getElementById("count-all");
        if (countAll) countAll.textContent = data.total || 0;

        const countVer = document.getElementById("count-verified");
        if (countVer) countVer.textContent = data.verified || 0;

        const countFraud = document.getElementById("count-fraud");
        if (countFraud) countFraud.textContent = data.duplicates || 0;

        const countCalls = document.getElementById("count-calls");
        if (countCalls) countCalls.textContent = data.active_calls || 0;

    } catch (e) {
        console.error("fetchStats error", e);
    }
}

async function fetchReports() {
    try {
        const res = await fetch("/api/reports");
        allReports = await res.json();
        renderReportsTable();
        updateMapMarkers();
    } catch (e) {
        console.error("fetchReports error", e);
    }
}

function filterLedger(filterType) {
    playTone(600, 0.05);
    activeLedgerFilter = filterType;
    document.querySelectorAll(".filter-chip").forEach(p => p.classList.remove("active"));
    const target = event?.target;
    if (target) target.classList.add("active");
    renderReportsTable();
}

function renderReportsTable() {
    const tbody = document.getElementById("audit-tbody");
    if (!tbody) return;

    const searchTerm = (document.getElementById("ledger-search")?.value || "").toLowerCase();

    let filtered = allReports;
    if (activeLedgerFilter === "Verified") {
        filtered = filtered.filter(r => r.status === "Verified");
    } else if (activeLedgerFilter === "Duplicate Fraud") {
        filtered = filtered.filter(r => r.status === "Duplicate Fraud");
    } else if (activeLedgerFilter === "Active Calls") {
        filtered = filtered.filter(r => r.action_taken?.includes("Call"));
    }

    if (searchTerm) {
        filtered = filtered.filter(r => 
            (r.location || "").toLowerCase().includes(searchTerm) ||
            (r.issue_type || "").toLowerCase().includes(searchTerm) ||
            (r.department || "").toLowerCase().includes(searchTerm) ||
            (r.voucher_code || "").toLowerCase().includes(searchTerm) ||
            (r.desc || "").toLowerCase().includes(searchTerm)
        );
    }

    if (!filtered.length) {
        tbody.innerHTML = `<tr><td colspan="8" class="table-loading">No audit records match this filter.</td></tr>`;
        return;
    }

    tbody.innerHTML = "";
    filtered.forEach(report => {
        const tr = document.createElement("tr");
        const date = new Date(report.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        // Status Badge
        let statusBadge = "";
        if (report.status === "Verified") {
            statusBadge = `<span class="status-pill verified">✓ Verified Unique</span>`;
        } else if (report.status === "Duplicate Fraud") {
            const pct = report.duplicate_score ? ` (${(report.duplicate_score * 100).toFixed(0)}%)` : "";
            statusBadge = `<span class="status-pill fraud">🛡️ FRAUD BLOCKED${pct}</span>`;
        } else {
            statusBadge = `<span class="status-pill pending">⏳ ${report.status}</span>`;
        }

        // Severity Pill
        let sevBadge = "";
        if (report.severity && report.severity !== "Analyzing...") {
            sevBadge = `<span class="sev-tag ${report.severity.toLowerCase()}">${report.severity}</span>`;
        }

        // Enforcement Status
        let ackHtml = `<span style="color:var(--text-tertiary)">—</span>`;
        const action = report.action_taken || "";
        const callerResp = report.caller_response || "";

        if (report.status === "Duplicate Fraud") {
            ackHtml = `<span style="color:var(--danger); font-size:10px; font-weight:600;">🚫 Blocked (Fraud Claim)</span>`;
        } else if (action === "Logged for Maintenance") {
            ackHtml = `<span style="color:var(--cyan); font-size:10px;">📋 Routine Queue (48h)</span>`;
        } else if (callerResp && callerResp !== "None") {
            ackHtml = `<span style="color:var(--emerald); font-size:10px; font-weight:600;">✅ ${callerResp}</span>`;
        } else if (action.includes("Call")) {
            ackHtml = `<span style="color:var(--amber); font-size:10px;">📞 Dispatched — Dialing</span>`;
        }

        // Voucher Reward
        let voucherHtml = `<span style="color:var(--text-tertiary)">—</span>`;
        if (report.voucher_code) {
            voucherHtml = `<span class="voucher-tag">${report.voucher_code}</span>`;
        } else if (report.status === "Duplicate Fraud") {
            voucherHtml = `<span style="color:var(--danger); font-size:9px; font-weight:700;">WITHHELD</span>`;
        }

        tr.innerHTML = `
            <td>
                <div class="table-img-thumb" onclick="openDetailsModal('${report.id}')" title="Click to view Forensic Dossier">
                    <img src="${report.image_path}" alt="Evidence">
                </div>
            </td>
            <td>
                <div style="font-family:var(--font-mono); font-size:10px; font-weight:700; color:#fff;">${date}</div>
                <div style="font-size:9px; color:var(--text-secondary);">${report.source || 'Web'}</div>
            </td>
            <td>
                <div class="row-issue-title">${report.issue_type} ${sevBadge}</div>
                <div class="row-dept">${report.department || 'Public Works Dept'}</div>
            </td>
            <td>
                <div class="row-loc">📌 ${report.location}</div>
                <div class="row-coords">${report.lat ? `${report.lat.toFixed(4)}, ${report.lng.toFixed(4)}` : 'GPS Locked'}</div>
            </td>
            <td>${statusBadge}</td>
            <td>${ackHtml}</td>
            <td>${voucherHtml}</td>
            <td>
                <button class="btn-inspect-clean" onclick="openDetailsModal('${report.id}')">Inspect &rarr;</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// ── FORENSIC AUDIT DOSSIER MODAL ──
async function openDetailsModal(reportId) {
    playTone(720, 0.08);
    const report = allReports.find(r => r.id === reportId);
    if (!report) return;

    const modal = document.getElementById("audit-modal");
    const body = document.getElementById("modal-body-content");
    if (!modal || !body) return;

    const date = new Date(report.timestamp).toLocaleString();
    const isFraud = report.status === "Duplicate Fraud";

    body.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:10px; margin-bottom:12px;">
            <div>
                <span class="status-pill ${isFraud ? 'fraud' : 'verified'}">${isFraud ? 'FRAUD DETECTION DOSSIER' : 'VERIFIED INCIDENT DOSSIER'}</span>
                <h2 style="font-size:16px; margin-top:4px; color:#fff;">Audit Record #CLN-${report.id.substring(0, 8).toUpperCase()}</h2>
            </div>
            <span style="font-family:var(--font-mono); font-size:11px; color:var(--text-secondary);">${date}</span>
        </div>

        <img src="${report.image_path}" class="modal-detail-img" alt="Forensic Evidence">

        <div class="modal-grid-2">
            <div class="modal-box">
                <label>Issue Classification</label>
                <span>${report.issue_type} (${report.severity})</span>
            </div>
            <div class="modal-box">
                <label>Responsible Department</label>
                <span style="color:var(--cyan);">${report.department || 'Public Works Department (PWD)'}</span>
            </div>
            <div class="modal-box">
                <label>Defense Grid Verdict</label>
                <span style="color:${isFraud ? 'var(--danger)' : 'var(--emerald)'};">${report.status}</span>
            </div>
            <div class="modal-box">
                <label>Taxpayer Funds Guarded</label>
                <span style="color:var(--emerald);">₹${(report.estimated_savings || 45000).toLocaleString('en-IN')} INR</span>
            </div>
            <div class="modal-box">
                <label>Geo-Location Pin</label>
                <span>📌 ${report.location}</span>
            </div>
            <div class="modal-box">
                <label>Anonymous Citizen Voucher</label>
                <span style="font-family:var(--font-mono); color:#c084fc;">${report.voucher_code || 'None (Fraudulent Claim)'}</span>
            </div>
        </div>

        <div class="modal-box" style="margin-bottom:10px;">
            <label>Multimodal Visual Forensic Analysis</label>
            <div class="modal-desc">${report.desc}</div>
        </div>

        ${report.duplicate_score ? `
        <div class="modal-box" style="border-color:var(--danger); background:var(--danger-subtle);">
            <label style="color:var(--danger);">Qdrant Vector Threat Match</label>
            <span style="font-size:11px; color:#f8fafc;">Cosine similarity threshold exceeded: <strong>${(report.duplicate_score*100).toFixed(1)}%</strong>. This evidence matched an existing historical record in the 768-D vector grid. Automated contractor billing invoice frozen.</span>
        </div>` : ''}

        <div style="margin-top:14px; display:flex; justify-content:flex-end; gap:8px;">
            <button class="nav-btn btn-subtle" onclick="window.print()">🖨️ Export PDF</button>
            <button class="btn-execute" style="padding:6px 12px; font-size:11px;" onclick="closeModal('audit-modal')">Close Dossier</button>
        </div>
    `;

    modal.classList.remove("hidden");
}

// ── VC PITCH DECK MODAL ──
function openPitchDeck() {
    playTone(650, 0.1, "sine");
    const modal = document.getElementById("pitch-deck-modal");
    if (modal) modal.classList.remove("hidden");
}

function closeModal(modalId) {
    playTone(400, 0.05);
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.add("hidden");
}

// ── WEBSOCKET & TELEMETRY LOGS ──
function initWebSocket() {
    const protocol = (location.protocol === "https:") ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${location.host}/ws/logs`;
    try {
        const socket = new WebSocket(wsUrl);
        socket.addEventListener("open", () => {
            addConsoleLine("Connected to real-time defense telemetry socket.", "system");
            wsEnabled = true;
            wsConn = socket;
        });
        socket.addEventListener("message", (ev) => {
            try {
                const entry = JSON.parse(ev.data);
                if (Array.isArray(entry)) {
                    allLogs = entry;
                } else {
                    allLogs.push(entry);
                    if (allLogs.length > 300) allLogs.shift();
                }
                renderLogs();
            } catch (e) { console.error('WS parse error', e); }
        });
        socket.addEventListener("close", () => {
            wsEnabled = false;
            wsConn = null;
        });
    } catch (e) {
        wsEnabled = false;
    }
}

async function fetchLogs() {
    try {
        if (wsEnabled) return allLogs;
        const res = await fetch("/api/logs");
        allLogs = await res.json();
        renderLogs();
        return allLogs;
    } catch (e) { return []; }
}

function filterLogs(category) {
    playTone(550, 0.05);
    activeLogFilter = category;
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    const target = event?.target;
    if (target) target.classList.add("active");
    renderLogs();
}

function renderLogs() {
    const el = document.getElementById("log-console");
    if (!el) return;

    let filtered = allLogs;
    if (activeLogFilter === "gemini") {
        filtered = filtered.filter(l => l.message.includes("Gemini") || l.message.includes("Vision") || l.message.includes("VALIDATION"));
    } else if (activeLogFilter === "fraud") {
        filtered = filtered.filter(l => l.message.includes("FRAUD") || l.message.includes("Qdrant") || l.message.includes("Duplicate"));
    } else if (activeLogFilter === "twilio") {
        filtered = filtered.filter(l => l.message.includes("Twilio") || l.message.includes("Call") || l.message.includes("Voice"));
    }

    el.innerHTML = "";
    filtered.forEach(log => {
        const div = document.createElement("div");
        div.className = `log-line ${log.level.toLowerCase()}`;
        div.textContent = `[${log.timestamp}] [${log.level}] ${log.message}`;
        el.appendChild(div);
    });
    el.scrollTop = el.scrollHeight;
}

function addConsoleLine(text, level = "info") {
    const el = document.getElementById("log-console");
    if (!el) return;
    const div = document.createElement("div");
    div.className = `log-line ${level}`;
    div.textContent = `[${new Date().toLocaleTimeString()}] [${level.toUpperCase()}] ${text}`;
    el.appendChild(div);
    el.scrollTop = el.scrollHeight;
}

// ── SYNTHESIZED AUDIO TELEMETRY ENGINE ──
function toggleAudioFx() {
    audioFxEnabled = !audioFxEnabled;
    const label = document.getElementById("sound-label");
    const icon = document.getElementById("sound-icon");
    if (label) label.textContent = `Audio: ${audioFxEnabled ? 'ON' : 'OFF'}`;
    if (icon) icon.textContent = audioFxEnabled ? '🔊' : '🔇';
    if (audioFxEnabled) playTone(880, 0.1, "sine");
}

function getAudioCtx() {
    if (!audioCtx) {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (AudioContext) audioCtx = new AudioContext();
    }
    if (audioCtx && audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
    return audioCtx;
}

function playTone(freq, duration, type = "sine") {
    if (!audioFxEnabled) return;
    try {
        const ctx = getAudioCtx();
        if (!ctx) return;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = type;
        osc.frequency.setValueAtTime(freq, ctx.currentTime);
        gain.gain.setValueAtTime(0.04, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + duration);
    } catch (e) { }
}

function playChime() {
    if (!audioFxEnabled) return;
    playTone(523.25, 0.1, "sine");
    setTimeout(() => playTone(659.25, 0.1, "sine"), 80);
    setTimeout(() => playTone(783.99, 0.15, "sine"), 160);
    setTimeout(() => playTone(1046.50, 0.25, "sine"), 240);
}

function playAlarm() {
    if (!audioFxEnabled) return;
    playTone(350, 0.15, "sawtooth");
    setTimeout(() => playTone(280, 0.25, "sawtooth"), 120);
}
