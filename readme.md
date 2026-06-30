# 🛡️ CivicLens: Autonomous Governance Defense System
### *"Palantir for Potholes"* — Submission Guide
**Convolve 4.0 | Qdrant MAS Track – Round 2 (2026)**

---

## 🎯 The Problem

Governments lose **billions annually** to *Ghost Repairs* — contractors claiming payments for work never done. Citizens report civic issues (potholes, broken streetlights, pipeline leaks) but have no guarantee of action. Manual inspection doesn't scale. There's no system to **detect duplicates, route to the right department, or reward honest reporters**.

---

## 💡 The Solution

**CivicLens** is an AI-powered Autonomous Governance Defense System — a Telegram chatbot + web dashboard that:

- **Accepts civic reports** from anonymous citizens via Telegram
- **Analyzes issues** using Gemini 1.5 Flash Vision AI
- **Detects fraud** via Qdrant vector similarity search (duplicate report blocking)
- **Routes alerts** to the correct government department automatically
- **Calls the contractor** via Twilio autonomous IVR voice agent
- **Rewards reporters** with an anonymous tokenized voucher code
- **Provides oversight** via a real-time web dashboard for administrators

---

## 🗺️ System Architecture

```
Citizen sends photo to Telegram Bot
              ↓
   Extract GPS from EXIF metadata
   or use Telegram location pin
              ↓
   Gemini 1.5 Flash Vision AI
   ↳ Detects: issue type, severity,
     visual fingerprint (11 categories)
              ↓
   text-embedding-004 → 768-dim Vector
              ↓
   Qdrant Vector Database
   ↳ Cosine similarity check (threshold: 90%)
              ↓
   ┌──── Duplicate? ────────────────────────┐
   │ YES → Fraud Blocked, No reward         │
   │ NO  → Save to Qdrant + DB             │
   └────────────────────────────────────────┘
              ↓ (unique reports only)
   Department Router
   ↳ Pothole → PWD | Electricity → SEB
   ↳ Drainage → SDB | Garbage → SWM...
              ↓
   Twilio IVR → Calls responsible dept phone
   ↳ Press 1 (English) / Press 2 (Hindi)
              ↓
   Anonymous Voucher Code → Sent to reporter
   ↳ Reporter notified when contractor ACKs
```

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🤖 **Telegram Bot** | Anonymous citizen reporting via photo + location |
| 👁️ **Gemini Vision AI** | Detects 11 civic issue types + severity |
| 🔍 **Qdrant Duplicate Check** | Vector similarity search blocks recycled evidence |
| 🏛️ **Department Routing** | Auto-routes to PWD, Electricity Board, Water Dept, etc. |
| 📞 **Twilio IVR Call** | Autonomous voice call with bilingual menu (English/Hindi) |
| 🎁 **Voucher Rewards** | Anonymous 8-char token sent to reporter on Telegram |
| 📍 **GPS Detection** | Reads EXIF data OR Telegram location pin |
| 🔒 **Privacy First** | Reporter identity NEVER stored in any database |
| 💻 **Web Dashboard** | Real-time audit ledger, logs console, and simulator |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI + Uvicorn (Python) |
| **AI Vision** | Google Gemini 1.5 Flash |
| **Embeddings** | Google text-embedding-004 (768-dim) |
| **Vector DB** | Qdrant (persistent local or cloud) |
| **Voice Agent** | Twilio Programmable Voice (IVR) |
| **Messaging** | Telegram Bot API (pyTelegramBotAPI) |
| **Location** | Pillow EXIF + OpenStreetMap Nominatim |
| **Persistence** | JSON ledger (`data/reports.json`) |
| **Frontend** | Vanilla HTML/CSS/JS (Glassmorphism UI) |
| **Tunnel** | Ngrok (for Twilio/Telegram webhooks) |

---

## 🚀 Setup Guide (End-to-End)

### Prerequisites

- Python 3.9+
- Ngrok account (free): [ngrok.com](https://ngrok.com)
- Google AI Studio API key: [aistudio.google.com](https://aistudio.google.com)
- *(Optional)* Twilio account: [twilio.com/console](https://www.twilio.com/console)
- *(Optional)* Telegram Bot Token from [@BotFather](https://t.me/BotFather)

---

### Step 1: Clone & Install

```powershell
git clone https://github.com/nihal29055/CivicLens_System.git
cd CivicLens_System

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install all dependencies
pip install -r requirements.txt
```

---

### Step 2: Configure Environment

Copy `.env.example` to `.env` and fill in your values:

```powershell
copy .env.example .env
```

**Minimum required to run (with demo mode):**
```env
GOOGLE_API_KEY=your_gemini_api_key_here
```

**For live calls and Telegram bot:**
```env
GOOGLE_API_KEY=your_gemini_api_key_here
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_FROM_NUMBER=+1234567890
TARGET_PHONE_NUMBER=+919876543210
TELEGRAM_BOT_TOKEN=your_bot_token
NGROK_URL=https://YOUR-NGROK-URL.ngrok-free.app
```

**Department phone routing (optional — falls back to `TARGET_PHONE_NUMBER`):**
```env
DEPT_PWD_PHONE=+91XXXXXXXXXX
DEPT_ELECTRICITY_PHONE=+91XXXXXXXXXX
DEPT_WATER_PHONE=+91XXXXXXXXXX
DEPT_DRAINAGE_PHONE=+91XXXXXXXXXX
DEPT_GARBAGE_PHONE=+91XXXXXXXXXX
DEPT_STREETLIGHT_PHONE=+91XXXXXXXXXX
DEPT_FOREST_PHONE=+91XXXXXXXXXX
DEPT_STORMWATER_PHONE=+91XXXXXXXXXX
```

---

### Step 3: Start Ngrok Tunnel

In **Terminal 1:**
```powershell
ngrok http 8000
```

Copy the forwarding URL (e.g. `https://abc123.ngrok-free.app`) and update `.env`:
```env
NGROK_URL=https://abc123.ngrok-free.app
```

---

### Step 4: Start the FastAPI Server

In **Terminal 2** (with venv activated):
```powershell
.\venv\Scripts\Activate.ps1
uvicorn server:app --reload --port 8000
```

---

### Step 5: Open the Dashboard

Open your browser:
```
http://localhost:8000
```

---

### Step 6: (Optional) Register Telegram Webhook

To receive live Telegram reports:
```powershell
# Replace with your actual values
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" `
     -d "url=https://YOUR-NGROK-URL.ngrok-free.app/telegram-webhook"
```

---

## 🎮 Demo Flow

### Demo A — Web Dashboard Simulation (No API Keys Required)

1. Open `http://localhost:8000`
2. In the **Live Pipeline Simulator**, select `Pothole (test_pothole.jpg)`
3. Click **LAUNCH GOVERNANCE AUDIT**
4. Watch the 6-step progress tracker execute live
5. In the **Audit Ledger** table, click **1 (English)** to simulate contractor acknowledgment
6. The record updates with `English — Acknowledged`
7. Qdrant counter increments to 1

### Demo B — Duplicate Fraud Detection

1. Click **LAUNCH GOVERNANCE AUDIT** again with the same image
2. Qdrant detects `~100% vector similarity`
3. Report is flagged as **❌ Fraud Blocked**
4. No Twilio call is made, no voucher is issued
5. Dashboard shows red **Fraud Blocked (100%)** badge

### Demo C — Telegram Bot (Requires Bot Token)

1. Send `/start` to your Telegram bot
2. Share your 📍 location pin
3. Send a photo of any civic issue (pothole, garbage, flood, etc.)
4. Bot replies with AI analysis and department routing
5. You receive a 🎁 voucher code anonymously
6. When contractor presses 1/2 in Twilio call, you receive an acknowledgment

---

## 🔒 Privacy Architecture

The CivicLens system is designed with privacy-first principles:

- **Reporter identity** is NEVER written to disk or the database
- `chat_id` is stored **only in server RAM** temporarily, purged after reward is sent
- The audit ledger stores: issue type, location, dept, status, voucher — NOT who reported it
- Location data from EXIF is stored, but not linked to any user identity
- All voucher codes are UUID-based and random — not traceable to a person

---

## 📂 Project Structure

```
CivicLens_System/
│
├── server.py               # FastAPI server — main pipeline, API routes
├── main.py                 # CLI worker for Telegram polling mode
├── requirements.txt        # Python dependencies
├── .env                    # API keys (not committed to git)
├── .env.example            # Template for .env setup
│
├── src/
│   ├── vision_engine.py    # Gemini AI image analysis + GPS EXIF extractor
│   ├── memory_engine.py    # Qdrant vector DB — duplicate fraud detection
│   ├── enforcer_engine.py  # Twilio IVR + Telegram voucher sender
│   ├── departments.py      # Issue type → department routing config
│   ├── db.py               # Thread-safe JSON database (reports.json)
│   └── __init__.py
│
├── static/
│   ├── index.html          # Dashboard UI HTML
│   ├── style.css           # Glassmorphism CSS design
│   └── app.js              # Dashboard state & API interactions
│
└── data/
    ├── reports.json         # Audit ledger (auto-created)
    ├── qdrant_db/           # Persistent vector storage (auto-created)
    ├── uploads/             # Uploaded images (auto-created)
    └── test_pothole.jpg     # Sample test image
```

---

## 🏛️ Department Routing Reference

| Issue Type | Department |
|---|---|
| Pothole / Road Damage | 🛣️ Public Works Department (PWD) |
| Electricity Outage | ⚡ State Electricity Board |
| Broken Streetlight | 💡 Municipal Corp — Streetlighting |
| Pipeline Blockage / Water Leakage | 💧 Municipal Water Department |
| Drainage Overflow / Sewage | 🚰 Sewage & Drainage Board |
| Garbage Dumping | 🗑️ Solid Waste Management |
| Tree Fall / Obstruction | 🌳 Urban Forestry Department |
| Water Logging / Flooding | 🌊 Storm Water Drainage Board |

---

## 🧪 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Web dashboard |
| `GET` | `/api/reports` | All audit reports |
| `GET` | `/api/stats` | Dashboard statistics |
| `GET` | `/api/logs` | Server console logs |
| `POST` | `/api/reports/submit` | Submit image for audit |
| `POST` | `/api/reports/simulate-key` | Simulate contractor keypress |
| `POST` | `/voice/start` | Twilio IVR initiation callback |
| `POST` | `/voice/handle-key` | Twilio keypress handler |
| `POST` | `/telegram-webhook` | Telegram bot webhook |

---

## 🏆 Hackathon Track Alignment

**Qdrant MAS (Multi-Agent System) Track:**

CivicLens uses Qdrant as the **fraud-detection memory layer** — the core of the governance defense system. Every verified report is embedded as a 768-dimensional vector using Google's `text-embedding-004` model. On each new submission, Qdrant runs a cosine similarity search to detect recycled/fake evidence with >90% confidence before any contractor is called or payment is approved.

**Why Qdrant is the Backbone:**

1. **Vector Storage** — Persistent cross-session memory of all verified civic reports
2. **Fraud Detection** — Real-time similarity search catches duplicate submissions
3. **Scalable** — Works locally (on-disk) or via Qdrant Cloud with no code changes

---

## 👤 Author

**Nihal Yadav**
Built for Convolve 4.0 | Qdrant MAS Track — Round 2 (2026)

---

## 📄 License

MIT License
