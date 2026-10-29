## Medical AI Risk Intelligence – A4 Wrapper 

This app wraps your Assignment 4 Madison / n8n workflow in a public, user‑friendly interface using **Streamlit**.

It fetches recent healthcare / AI news articles and uses **Claude** to score each one for **medical AI risk**, categorize issues, and surface key safety insights.

### What it does

- Pulls recent articles from:
  - `The Verge` (tech / AI),
  - `Fierce Healthcare` (healthcare news),
  - `arXiv cs.AI` (research).
- Normalizes title, summary, URL, and published date.
- Sends each article to **Claude** with a structured JSON prompt (same structure as your A4 workflow).
- Returns:
  - Risk score (1–10),
  - Risk category & medical domain,
  - 2–3 key insights,
  - Relevance to AI safety,
  - Whether the item is actionable.
- Aggregates results into a dashboard:
  - Article table,
  - High/medium/low risk counts,
  - Average risk score,
  - Estimated token cost.

### Who it’s for

- Students and practitioners exploring **medical AI safety**.
- Policy / product people who need a quick view of **risk signals** in current AI news.
- Instructors evaluating your A4 workflow wrapped in a usable interface.

### Tech stack

- **Frontend / UI**: Streamlit
- **Data sources**: RSS feeds (The Verge, Fierce Healthcare, arXiv cs.AI)
- **AI model**: Claude via Anthropic HTTP API
- **Language**: Python 3

---

## Running the app locally

1. **Clone or open this repo** (e.g., in VS Code / Cursor).

2. **Create a virtual environment** (recommended) and install dependencies:

```bash
pip install -r requirements.txt
```

3. **Set your Claude API key** as an environment variable:

```bash
export ANTHROPIC_API_KEY="your-claude-key-here"
```

> Important: Do **not** hard‑code your key in `app.py` or commit it to GitHub.

4. **Run the Streamlit app**:

```bash
streamlit run app.py
```

5. Open the local URL (usually `http://localhost:8501`) in your browser.

---

## Deploying to Streamlit Cloud (for Assignment 5)

1. Push this folder (`brandingAI` with `app.py`, `requirements.txt`, and `README.md`) to a **public GitHub repo**.
2. Go to `https://share.streamlit.io` and log in.
3. Click **“New app”**, select your repo, branch, and `app.py` as the entry point.
4. Under **Advanced settings** (or in the Streamlit dashboard), add your secret:

```toml
[secrets]
ANTHROPIC_API_KEY = "your-claude-key-here"
```

5. Deploy. You’ll get a **public URL** you can use for:
   - Assignment 5 submission,
   - User testing with non‑technical people.

---

## Where this connects to Assignment 4

- The Streamlit app:
  - Uses **the same article fields** (title, summary, source, URL) you standardized in A4.
  - Reuses the **same Claude JSON output schema** you defined in your A4 `Claude: Intelligent Analysis` node.
  - Computes **very similar stats** to your HTML/PDF report (high/medium/low risk counts, average risk, estimated cost).
- The main difference is:
  - Instead of generating a PDF, it presents the results as an **interactive dashboard** with:
    - Inputs (source selection, article count, keyword filter),
    - Readable outputs (metrics, table, per‑article expanders).

---

## Customization notes (for your assignment write‑up)

- **Tool name**: In your PDF, you can refer to this as a temporary working name, e.g., *“Medical AI Risk Radar”* or *“ClinAI Risk Watch”* (you’ll refine branding in Assignment 6).
- **About section**: The text at the top of `app.py` and in this README can be reused almost directly in your A5 PDF under:
  - Tool name,
  - One‑sentence description,
  - About: what it does, who it’s for, tech stack.
- **Future work**:
  - Add more sources or a CSV upload,
  - Save results to a database,
  - Export PDF again using the same HTML→PDF pattern from A4.

