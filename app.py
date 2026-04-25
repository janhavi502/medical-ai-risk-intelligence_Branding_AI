import os
import json
import re
from datetime import datetime
from typing import List, Dict, Any
from html import unescape

import streamlit as st
import feedparser
import requests


# -----------------------------
# Config
# -----------------------------

MODEL_NAME = "claude-haiku-4-5-20251001"  # Small, fast, widely available model


TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """
    Remove basic HTML tags and unescape entities from RSS fields.
    """
    if not text:
        return ""
    text = unescape(str(text))
    return TAG_RE.sub("", text).strip()


@st.cache_data(show_spinner=False)
def fetch_rss_feed(url: str, source_name: str, limit: int) -> List[Dict[str, Any]]:
    """
    Fetch and normalize items from a single RSS feed.
    """
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:limit]:
        title = strip_html(entry.get("title", ""))
        summary = (
            strip_html(entry.get("summary"))
            or strip_html(entry.get("description"))
            or strip_html(entry.get("content", [{}])[0].get("value", ""))
        )
        link = entry.get("link", "").strip()
        published = entry.get("published") or entry.get("updated") or ""

        if not title or not link:
            continue

        items.append(
            {
                "source_name": source_name,
                "title": title,
                "summary": summary,
                "url": link,
                "published_at": published,
            }
        )
    return items


def get_anthropic_api_key() -> str:
    """
    Read Anthropic (Claude) API key.

    For simplicity (and to avoid local Streamlit warnings), we only read
    from the environment variable `ANTHROPIC_API_KEY`.

    On Streamlit Cloud, set this in the app's "Environment variables"
    settings. Locally, export it in your terminal before running:

        export ANTHROPIC_API_KEY="your-key-here"
    """
    return os.getenv("ANTHROPIC_API_KEY", "")


def build_claude_prompt(article: Dict[str, Any]) -> str:
    """
    Reuse the core A4 logic: structured JSON output for medical AI risk analysis.
    """
    return (
        "Analyze this healthcare/AI news article for medical AI safety and risk signals.\n\n"
        f"Article Details:\n"
        f"- Title: {article['title']}\n"
        f"- Source: {article['source_name']}\n"
        f"- Content: {article['summary'][:800]}\n\n"
        "Provide analysis in JSON format with:\n"
        "1. risk_score: Number 1-10\n"
        "2. risk_category: One of "
        "[patient_safety, data_privacy, bias_fairness, regulatory, "
        "clinical_accuracy, deployment_risk, ethical_concern, market_signal]\n"
        "3. medical_domain: One of "
        "[general_healthcare, diagnostics, treatment, surgery, mental_health, "
        "pharmaceuticals, medical_devices, health_tech, research]\n"
        "4. key_insights: List of 2-3 brief insights\n"
        "5. relevance_to_ai_safety: Brief explanation\n"
        "6. actionable: Boolean\n\n"
        "Respond ONLY with valid JSON, no other text."
    )


def call_claude(article: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    """
    Call Claude via HTTP API, mirroring your A4 prompt format.
    """
    prompt = build_claude_prompt(article)

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    body = {
        "model": MODEL_NAME,
        "max_tokens": 500,
        "messages": [{"role": "user", "content": prompt}],
    }

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        data=json.dumps(body),
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    # Extract text content
    text = ""
    if isinstance(data.get("content"), list) and data["content"]:
        part = data["content"][0]
        if isinstance(part, dict):
            text = part.get("text", "") or part.get("content", "") or ""
        else:
            text = str(part)
    else:
        text = data.get("content", "") or ""

    # Strip markdown code fences if present
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].strip()

    try:
        analysis = json.loads(text)
    except Exception as e:
        analysis = {
            "risk_score": 0,
            "risk_category": "unknown",
            "medical_domain": "unknown",
            "key_insights": [f"Analysis failed: {e}"],
            "relevance_to_ai_safety": "Could not parse Claude response.",
            "actionable": False,
        }

    usage = data.get("usage") or {}
    return {
        "ai_analysis": analysis,
        "claude_tokens": {
            "input": usage.get("input_tokens", 0),
            "output": usage.get("output_tokens", 0),
        },
    }


def compute_stats(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not items:
        return {
            "total": 0,
            "avgRisk": 0.0,
            "highRisk": 0,
            "mediumRisk": 0,
            "lowRisk": 0,
            "actionable": 0,
            "totalTokens": 0,
            "estimatedCost": 0.0,
        }

    total = len(items)
    scores = [i["ai_analysis"].get("risk_score", 0) or 0 for i in items]

    high = sum(1 for s in scores if s >= 7)
    med = sum(1 for s in scores if 4 <= s < 7)
    low = sum(1 for s in scores if s < 4)

    actionable = sum(1 for i in items if i["ai_analysis"].get("actionable"))
    total_tokens = sum(
        (i["claude_tokens"]["input"] + i["claude_tokens"]["output"]) for i in items
    )
    # Very rough cost estimate using similar rates as in your A4
    estimated_cost = sum(
        i["claude_tokens"]["input"] * 0.000003
        + i["claude_tokens"]["output"] * 0.000015
        for i in items
    )

    return {
        "total": total,
        "avgRisk": round(sum(scores) / total, 2),
        "highRisk": high,
        "mediumRisk": med,
        "lowRisk": low,
        "actionable": actionable,
        "totalTokens": total_tokens,
        "estimatedCost": round(estimated_cost, 4),
    }


def format_date(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        return datetime.fromisoformat(date_str).strftime("%Y-%m-%d")
    except Exception:
        return date_str[:10]


def main() -> None:
    st.set_page_config(
        page_title="Medical AI Risk Intelligence (A4 Wrapper)",
        page_icon="⚕️",
        layout="wide",
    )

    st.title("Medical AI Risk Intelligence")
    st.write(
        "An assignment A4 workflow wrapped in a friendly interface. "
        "This tool scans recent healthcare / AI news and uses Claude to "
        "score medical AI risk, categorize issues, and surface key safety insights."
    )

    st.markdown(
        """
**About this tool**

- **What it does**: Fetches recent articles from selected tech and healthcare sources and asks Claude to score each one for medical AI risk.
- **Who it's for**: Product managers, policy students, and healthcare innovators who want a quick view of emerging AI risk signals.
- **Tech stack**: Streamlit, Python, Claude API, RSS feeds (The Verge, Fierce Healthcare, arXiv cs.AI).
"""
    )

    # Sidebar inputs
    st.sidebar.header("Inputs")

    sources = st.sidebar.multiselect(
        "Sources to monitor",
        options=[
            "The Verge (tech / AI)",
            "Fierce Healthcare (healthcare)",
            "arXiv cs.AI (research)",
        ],
        default=[
            "The Verge (tech / AI)",
            "Fierce Healthcare (healthcare)",
        ],
    )

    per_source = st.sidebar.slider(
        "Articles per source", min_value=3, max_value=15, value=5
    )

    keyword_filter = st.sidebar.text_input(
        "Optional keyword filter",
        placeholder="e.g., 'clinical AI', 'FDA', 'risk', 'patient safety'",
    )

    run_button = st.sidebar.button("Run Analysis")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Created by**: Janhavi Patil")
    st.sidebar.markdown(
        "Portfolio/contact: *(add your link here in the README / app once ready)*"
    )

    api_key = get_anthropic_api_key()
    if not api_key:
        st.warning(
            "No Anthropic API key found. "
            "Set `ANTHROPIC_API_KEY` in Streamlit secrets or environment to enable analysis."
        )

    if run_button:
        if not sources:
            st.error("Please select at least one source.")
            return

        if not api_key:
            st.error("Claude API is not configured. Cannot run analysis.")
            return

        # Map UI labels to URLs and internal source names
        source_map = {
            "The Verge (tech / AI)": (
                "https://www.theverge.com/rss/index.xml",
                "theverge",
            ),
            "Fierce Healthcare (healthcare)": (
                "https://www.fiercehealthcare.com/rss/xml",
                "fiercehealthcare",
            ),
            "arXiv cs.AI (research)": ("https://rss.arxiv.org/rss/cs.AI", "arxiv_csAI"),
        }

        with st.spinner("Fetching articles and calling Claude..."):
            all_articles: List[Dict[str, Any]] = []
            for label in sources:
                url, internal_name = source_map[label]
                items = fetch_rss_feed(url, internal_name, per_source)
                all_articles.extend(items)

            if keyword_filter:
                k = keyword_filter.lower()
                all_articles = [
                    a
                    for a in all_articles
                    if k in a["title"].lower() or k in a["summary"].lower()
                ]

            # Limit to 10 items to stay close to your A4 behavior and keep cost reasonable
            all_articles = all_articles[:10]

            enriched_items: List[Dict[str, Any]] = []
            for idx, art in enumerate(all_articles, start=1):
                st.write(f"Analyzing article {idx}/{len(all_articles)}: {art['title']}")
                try:
                    result = call_claude(art, api_key)
                except Exception as e:
                    result = {
                        "ai_analysis": {
                            "risk_score": 0,
                            "risk_category": "error",
                            "medical_domain": "unknown",
                            "key_insights": [f"Error calling Claude: {e}"],
                            "relevance_to_ai_safety": "API error",
                            "actionable": False,
                        },
                        "claude_tokens": {"input": 0, "output": 0},
                    }
                enriched_items.append({**art, **result})

        if not enriched_items:
            st.info("No articles matched your filters.")
            return

        # Separate items that have a meaningful structured analysis (for metrics)
        # from those where the model fell back to our error placeholder.
        valid_items_for_stats = [
            item
            for item in enriched_items
            if isinstance(item.get("ai_analysis"), dict)
            and item["ai_analysis"].get("risk_category") != "error"
            and item["ai_analysis"].get("medical_domain") not in ("unknown", "", None)
            and item["ai_analysis"].get("risk_score") not in (None, 0)
        ]

        # Sort all items by risk score (so UI is stable), falling back to 0.
        enriched_items.sort(
            key=lambda x: x.get("ai_analysis", {}).get("risk_score", 0) or 0,
            reverse=True,
        )

        stats = compute_stats(valid_items_for_stats or enriched_items)

        # Top-level metrics
        st.subheader("Risk Overview")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Articles analyzed", stats["total"])
        col2.metric("Average risk score", stats["avgRisk"])
        col3.metric("High-risk articles (7–10)", stats["highRisk"])
        col4.metric("Actionable items", stats["actionable"])

        col5, col6, col7, col8 = st.columns(4)
        col5.metric("Medium-risk (4–6)", stats["mediumRisk"])
        col6.metric("Low-risk (1–3)", stats["lowRisk"])
        col7.metric("Total tokens", f"{stats['totalTokens']:,}")
        col8.metric("Est. Claude cost (USD)", stats["estimatedCost"])

        # Table-style summary
        st.subheader("Article Summary Table")
        table_rows = []
        for item in enriched_items:
            a = item["ai_analysis"]
            score = a.get("risk_score", 0)
            display_score = "" if a.get("risk_category") == "error" else score
            display_domain = (
                "" if a.get("medical_domain") in ("unknown", "", None) else a.get("medical_domain", "")
            )

            table_rows.append(
                {
                    "Title": item["title"][:80] + ("..." if len(item["title"]) > 80 else ""),
                    "Source": item["source_name"],
                    "Risk score": display_score,
                    "Risk category": a.get("risk_category", ""),
                    "Domain": display_domain,
                    "Actionable": "Yes" if a.get("actionable") else "No",
                }
            )
        st.dataframe(table_rows, use_container_width=True)

        # Detailed per-article view
        st.subheader("Detailed AI Safety Insights")
        for idx, item in enumerate(enriched_items, start=1):
            a = item["ai_analysis"]
            score = a.get("risk_score", 0) or 0
            if score >= 7:
                badge = "🔴 HIGH RISK"
            elif score >= 4:
                badge = "🟠 MEDIUM RISK"
            else:
                badge = "🟢 LOW RISK"

            with st.expander(f"{idx}. {item['title']}  |  {badge} ({score}/10)"):
                st.markdown(
                    f"**Source**: {item['source_name']}  \n"
                    f"**Published**: {format_date(item.get('published_at', ''))}  \n"
                    f"**URL**: [{item['url']}]({item['url']})"
                )

                st.markdown("**Article summary**")
                st.write(item["summary"] or "_No summary available_")

                st.markdown("---")
                st.markdown(
                    f"**Risk category**: `{a.get('risk_category', '')}`   "
                    f"**Medical domain**: `{a.get('medical_domain', '')}`"
                )

                st.markdown("**Key insights from Claude**")
                for insight in a.get("key_insights", []):
                    st.write(f"- {insight}")

                st.markdown("**Relevance to AI safety**")
                st.write(a.get("relevance_to_ai_safety", ""))

                st.markdown("**Actionable?**")
                st.write("✅ Yes" if a.get("actionable") else "⚪ No")


if __name__ == "__main__":
    main()

