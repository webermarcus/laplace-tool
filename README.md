# Laplace Tool

A Laplace / inverse Laplace transform calculator with AI-generated step-by-step explanations.

**How it works.** SymPy computes the actual transform — it's the source of truth and always correct. Claude writes the step-by-step explanation, but it's shown the SymPy answer up front and instructed to derive toward it. The LLM narrates, it doesn't calculate.

```
┌─────────────┐      ┌───────────────────┐      ┌──────────────┐
│  React UI   │─────▶│  FastAPI + SymPy  │─────▶│  Claude API  │
│   (Vite)    │◀─────│   (the math)      │◀─────│ (the prose)  │
└─────────────┘      └───────────────────┘      └──────────────┘
```

---

## Project layout

```
laplace-tool/
├── backend/         # FastAPI + SymPy + Claude
│   ├── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── fly.toml
│   └── .env.example
└── frontend/        # React + Vite + KaTeX
    ├── src/
    │   ├── App.jsx
    │   ├── main.jsx
    │   └── index.css
    ├── index.html
    ├── vite.config.js
    └── package.json
```

---

## Local dev

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # then paste your Anthropic key into .env
uvicorn main:app --reload
```

Backend runs on `http://localhost:8000`. Check it's alive: `curl http://localhost:8000/api/health`.

### Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173` and proxies `/api/*` to the backend automatically (see `vite.config.js`).

Try it with `sin(t)` forward, or `1/(s^2 + 1)` inverse — they're inverses of each other and a good sanity check.

---

## Deploy

### Backend → Fly.io

Install the Fly CLI, then:

```bash
cd backend
fly launch --no-deploy       # walk through prompts; it'll use the existing fly.toml
fly secrets set ANTHROPIC_API_KEY=sk-ant-...
fly deploy
```

You'll also want to edit `fly.toml` and change the `app` name to something unique (e.g. `laplace-tool-<yourname>`). Note the resulting URL — something like `https://laplace-tool-<yourname>.fly.dev`.

**Cost control:** the app is configured with `auto_stop_machines = "stop"` and `min_machines_running = 0`, so it scales to zero when idle. First request after idle will have a ~2s cold start. This keeps it effectively free on Fly's free allowance.

### Frontend → Vercel or Netlify

```bash
cd frontend
npm run build     # outputs to dist/
```

Then either:

- **Vercel:** `vercel deploy` (install the CLI first), or push to GitHub and connect the repo. Set the build command to `npm run build` and output directory to `dist`.
- **Netlify:** `netlify deploy --prod --dir=dist`, or connect the repo. Same build settings.

Set an environment variable `VITE_API_BASE` to your Fly backend URL (e.g. `https://laplace-tool-<yourname>.fly.dev`) in the Vercel/Netlify dashboard, then redeploy. Without it, the frontend will try to hit `/api` on its own origin, which won't work in prod.

---

## Cost controls (important)

This app calls a paid API on every transform request. A few guardrails:

1. **Set a monthly spend cap in the Anthropic console.** Console → Billing → Usage limits. Pick a number you're willing to lose ($10–$20 is plenty for casual use). When you hit it, the API returns errors and the calculator still works in degraded mode (result without explanation).
2. **Lock down CORS before going public.** In `backend/main.py`, change `allow_origins=["*"]` to your actual frontend URL. Otherwise anyone can hit your backend from any website and burn through your budget.
3. **Consider adding basic rate limiting** (e.g. `slowapi`) if the site ever gets linked anywhere. Not needed for day one.

---

## Scope notes

**Currently supported:** functions SymPy can handle out of the box — polynomials, exponentials, trig, Heaviside, DiracDelta, products/sums of these. Partial fractions happen automatically for inverse transforms.

**Not supported (intentionally):** MathQuill-style equation editor, user accounts, saved history, Fourier/Z-transforms, convolution walkthroughs, custom theming. Add later if you want; the MVP doesn't need them.

---

## What Claude might get wrong

The LLM's final answer is always correct (it's fed the SymPy result), but intermediate reasoning can occasionally cite the wrong property or skip a step. For a study tool this is acceptable; for a rigorous reference it isn't. If you want to harden this, the next move is to detect common function patterns in the backend and include the relevant transform rules in the prompt as hints.
