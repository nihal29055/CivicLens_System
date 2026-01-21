🛡️ CivicLens: Autonomous Governance Defense System

"Palantir for Potholes" — An AI-powered audit system that detects infrastructure fraud using Vector Search and enforces repairs via Autonomous Voice Agents.

The Problem

Governments lose billions to "Ghost Repairs"—contractors claiming bills for work they never did. Manual auditing is impossible at scale.

The Solution

CivicLens is a Defense Core that acts as an unbribable bureaucrat.

Ingest: Receives images via Telegram/WhatsApp from citizens.

Analyze: Uses Gemini 1.5 to detect severity and material quality.

Audit: Uses Qdrant Vector Search to detect recycled evidence (fraud).

Enforce: Physically calls the contractor via Twilio (IVR) to demand action.

Architecture

graph TD
    User[Citizen via Telegram] -->|Photo| Server[FastAPI Server]
    Server -->|Vectorize| Vision[Gemini 1.5 Flash]
    Vision -->|768-dim Vector| Memory[Qdrant DB]
    
    Memory -->|Check Fraud| Logic{Is Duplicate?}
    Logic -- Yes --> Fraud[Block Payment & Alert]
    Logic -- No --> Severity{Is Critical?}
    
    Severity -- Yes --> Call[Twilio Voice Agent]
    Call -->|Dial| Contractor[Contractor Phone]


Setup Instructions (End-to-End)

1. Prerequisites

Python 3.9+

Ngrok (For local tunneling to Twilio)

Twilio Account (SID, Auth Token, Phone Number)

Google Gemini API Key (Free Tier is fine)

Telegram Bot Token (From @BotFather)

2. Installation

Clone the repository and install dependencies:

git clone [https://github.com/YOUR_USERNAME/CivicLens.git](https://github.com/YOUR_USERNAME/CivicLens.git)
cd CivicLens
pip install -r requirements.txt


3. Configuration

Create a .env file in the root directory. Copy the structure below and fill in your keys:

# .env file

# AI Core
GOOGLE_API_KEY=your_gemini_api_key_here

# Voice Enforcer (Twilio)
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_FROM_NUMBER=+1234567890
TARGET_PHONE_NUMBER=+919876543210  <-- Your phone number (to receive the demo call)

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Network Tunnel (See Step 4)
NGROK_URL=[https://your-url.ngrok-free.app](https://your-url.ngrok-free.app)


How to Run the Demo

Step 1: Start Ngrok

We need Ngrok so Twilio can talk to your local laptop for the phone call logic.

Open a terminal.

Run: ngrok http 8000

Copy the Forwarding URL (e.g., https://a1b2c3d4.ngrok-free.app).

Paste this URL into your .env file as NGROK_URL.

Note: Ensure no trailing slash / at the end.

Step 2: Start the Backend Server

This handles the Phone Call IVR logic and Telegram inputs.

Open a new terminal.

Run:

uvicorn server:app --reload --port 8000


Step 3: Start the Defense Core (CLI)

This is the visual dashboard for the judges.

Open a third terminal.

Run:

python main.py


The Demo Flow (Script)

Status: The CLI will show "Waiting for Telegram Image...".

Action: Open your Telegram Bot and send a photo of a pothole.

Reaction:

The CLI detects the packet instantly.

Gemini analyzes the image (Severity: Critical).

Qdrant indexes the vector.

The System calls your phone.

Interaction: Answer the call. You will hear an IVR Menu:

"Press 1 for English, 2 for Hindi."

Press a button to verify the system responds in real-time.

Troubleshooting

Q: The call failed immediately.
A: Check your NGROK_URL in .env. It changes every time you restart Ngrok. It must match the running Ngrok session exactly and end in .app or .dev.

Q: "404 Model Not Found" error.
A: The code automatically falls back to compatible models, but ensure your Google API Key has access to gemini-1.5-flash or gemini-pro.

Q: Telegram bot isn't responding.
A: The system uses Polling mode in main.py. Ensure main.py is running. If you get a "Conflict" error, it means a Webhook is still active. The script tries to remove it automatically, but you can force it by visiting https://api.telegram.org/botYOUR_TOKEN/deleteWebhook.

📜 License

MIT License. Built for the Convolve 4.0 | Qdrant - MAS Track - Round 2 2026.