# HoLo 🏨
### *Verified Stays for the Lagos Professional*
> Built for the **Innovate Hospitality Hackathon 2026**

---

## What is HoLo?
HoLo is a **Truth-Led Booking Platform** that uses Generative AI + real-time SMS guest verification to give Lagos professionals honest hotel scores before they book. No fake reviews. No gen surprises.

**Tagline:** *"Verified Stays for the Lagos Professional"*

---

## Tech Stack
| Layer | Technology | Purpose |
|---|---|---|
| Interface | Africa's Talking SMS API | Conversational search & booking |
| Brain | Gemini 1.5 Pro | NLU parsing + honest review scoring |
| Backend | FastAPI (Python) | Webhooks, logic, API |
| Database | SQLite (SQLAlchemy) | Hotels, users, votes |
| Payments | Paystack Test Mode | Booking payment links |
| Rewards | Africa's Talking Airtime API | ₦100 reward for verified votes |
| Dashboard | Vanilla HTML/CSS/JS | Real-time Honesty Dashboard |

---

## Setup (Run This on Your Machine)

### 1. Prerequisites
- Python 3.10+
- [ngrok](https://ngrok.com/download) (for SMS webhooks)
- API accounts (see step 3)

### 2. Install Dependencies
```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Mac/Linux
# OR: venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

### 3. Get Your API Keys
| Service | Link | What to grab |
|---|---|---|
| Africa's Talking | [account.africastalking.com](https://account.africastalking.com) | username + API key (use Sandbox) |
| Google Gemini | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) | GEMINI_API_KEY |
| Paystack | [dashboard.paystack.com](https://dashboard.paystack.com/#/settings/developer) | sk_test_... key |

### 4. Configure Environment
```bash
cp .env.example .env
# Then edit .env with your actual keys
```

### 5. Start the Backend
```bash
cd backend
source venv/bin/activate
python main.py
```
Server starts at: `http://localhost:8000`
API docs at: `http://localhost:8000/docs`

### 6. Open the Dashboard
Open `dashboard/index.html` directly in your browser.
*(Works standalone — falls back to demo data if backend isn't running)*

### 7. Set Up SMS Webhook (ngrok)
```bash
# In a new terminal:
ngrok http 8000
```
Copy the `https://xxxx.ngrok.io` URL.

In your [Africa's Talking dashboard](https://account.africastalking.com):
- Go to **SMS > Settings > Callback URL**
- Set it to: `https://xxxx.ngrok.io/sms/incoming`

---

## Test the Full Flow

### SMS Conversation Test
1. Open Africa's Talking Sandbox simulator
2. Send: "I'm looking for a quiet place in Yaba."
3. Receive honest recommendation with Truth Scores
4. Reply with the hotel name to get a Paystack link
5. (Next morning) Reply to the post-stay audit → receive ₦100 airtime

### API Endpoints
```
GET  /health              — Health check
POST /sms/incoming        — Africa's Talking SMS webhook
GET  /dashboard/hotels    — All hotels + scores
GET  /dashboard/stats     — Platform aggregate stats
GET  /dashboard/activity  — Latest guest votes
POST /payments/webhook    — Paystack payment webhook
GET  /payments/verify/:ref — Verify payment
GET  /docs               — Auto-generated API docs (FastAPI)
```

---

## Project Structure
```
veria/
├── backend/
│   ├── main.py              ← FastAPI app entry
│   ├── config.py            ← Environment settings
│   ├── seed_data.py         ← 12 Lagos hotels seeded on startup
│   ├── requirements.txt
│   ├── .env.example         ← Copy to .env and fill in keys
│   ├── routers/
│   │   ├── sms.py           ← SMS conversation state machine
│   │   ├── dashboard.py     ← Dashboard data API
│   │   └── payments.py      ← Paystack webhook
│   ├── services/
│   │   ├── gemini_engine.py ← AI NLU + recommendation engine
│   │   ├── at_service.py    ← Africa's Talking SMS + Airtime
│   │   └── payment_service.py ← Paystack integration
│   └── models/
│       ├── database.py      ← SQLAlchemy async setup
│       ├── hotel.py         ← Hotel model
│       ├── user.py          ← User session model
│       └── vote.py          ← Guest verification votes
└── dashboard/
    ├── index.html           ← Honesty Dashboard UI
    ├── style.css            ← Premium dark-mode styles
    └── main.js              ← Live data + animations
```

---

## Hackathon Demo Script
1. **Show dashboard** — Judges see the live Lagos Vibe Map
2. **Send test SMS** — "I need a 15k room in Yaba" (use AT sandbox)
3. **Show AI response** — Honest upsell: Caritas Inn ₦19.5k (Truth Score 91)
4. **Reply 1** — Get Paystack link in SMS
5. **Show post-stay flow** — Reply "2" (power issues) → dashboard score drops live
6. **Show airtime reward** — ₦100 sent automatically

---

*Built with ❤️ for Lagos. Where honesty is the product.*
