from __future__ import annotations

import os
import base64
from io import StringIO
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from sklearn.linear_model import LinearRegression
try:
    from google.genai import types
except ImportError:
    types = None

try:
    from google import genai
except ImportError:
    genai = None


st.set_page_config(page_title="Mehengaai Mitra", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

if "household_profile" not in st.session_state:
    st.session_state.household_profile = {
        "locality": "Indiranagar", "pincode": "", "family_size": 4, "budget": 5000, "diet": "Vegetarian",
        "health_conditions": [], "available_funds": 5000
    }
if "mitra_view" not in st.session_state:
    st.session_state.mitra_view = "home"
if "mitra_chats" not in st.session_state:
    st.session_state.mitra_chats = []
if "active_chat_id" not in st.session_state:
    st.session_state.active_chat_id = ""
if "shopping_stage" not in st.session_state:
    st.session_state.shopping_stage = None
if "shopping_preferences" not in st.session_state:
    st.session_state.shopping_preferences = {}
if "shopping_items" not in st.session_state:
    st.session_state.shopping_items = []
if "uploaded_price_file" not in st.session_state:
    st.session_state.uploaded_price_file = None

requested_view = st.query_params.get("view")
if requested_view in {"home", "chat"}:
    st.session_state.mitra_view = requested_view

SAMPLE_DATA = """month,item,price_inr,quantity,unit,locality
2026-02,Milk,62,10,L,Indiranagar
2026-03,Milk,64,10,L,Indiranagar
2026-04,Milk,65,10,L,Indiranagar
2026-05,Milk,66,10,L,Indiranagar
2026-06,Milk,67,10,L,Indiranagar
2026-07,Milk,68,10,L,Indiranagar
2026-02,Sugar,44,3,kg,Indiranagar
2026-03,Sugar,45,3,kg,Indiranagar
2026-04,Sugar,46,3,kg,Indiranagar
2026-05,Sugar,48,3,kg,Indiranagar
2026-06,Sugar,55,3,kg,Indiranagar
2026-07,Sugar,62,3,kg,Indiranagar
2026-02,Rice,58,5,kg,Indiranagar
2026-03,Rice,59,5,kg,Indiranagar
2026-04,Rice,60,5,kg,Indiranagar
2026-05,Rice,61,5,kg,Indiranagar
2026-06,Rice,62,5,kg,Indiranagar
2026-07,Rice,63,5,kg,Indiranagar
2026-02,Toor Dal,155,2,kg,Indiranagar
2026-03,Toor Dal,158,2,kg,Indiranagar
2026-04,Toor Dal,156,2,kg,Indiranagar
2026-05,Toor Dal,160,2,kg,Indiranagar
2026-06,Toor Dal,164,2,kg,Indiranagar
2026-07,Toor Dal,166,2,kg,Indiranagar
2026-02,Eggs,78,2,dozen,Indiranagar
2026-03,Eggs,80,2,dozen,Indiranagar
2026-04,Eggs,82,2,dozen,Indiranagar
2026-05,Eggs,84,2,dozen,Indiranagar
2026-06,Eggs,86,2,dozen,Indiranagar
2026-07,Eggs,88,2,dozen,Indiranagar
"""
REQUIRED_COLUMNS = {"month", "item", "price_inr", "quantity", "unit", "locality"}


def image_data_uri(relative_path: str) -> str:
    image_path = Path(__file__).parent / relative_path
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def load_data(uploaded_file) -> pd.DataFrame:
    source = uploaded_file if uploaded_file is not None else StringIO(SAMPLE_DATA)
    df = pd.read_csv(source)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing: {', '.join(sorted(missing))}")
    df = df.copy()
    df["month"] = pd.to_datetime(df["month"], format="%Y-%m", errors="coerce")
    df["price_inr"] = pd.to_numeric(df["price_inr"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df = df.dropna(subset=["month", "item", "price_inr", "quantity"])
    df = df[(df["price_inr"] > 0) & (df["quantity"] > 0)]
    df["monthly_cost"] = df["price_inr"] * df["quantity"]
    return df.sort_values(["month", "item"])


def forecast_next_budget(df: pd.DataFrame) -> tuple[float, float]:
    monthly = df.groupby("month", as_index=False)["monthly_cost"].sum().sort_values("month")
    if len(monthly) < 3:
        return float(monthly["monthly_cost"].iloc[-1]), 0.0
    x = np.arange(len(monthly)).reshape(-1, 1)
    model = LinearRegression().fit(x, monthly["monthly_cost"])
    prediction = max(0.0, float(model.predict([[len(monthly)]])[0]))
    return prediction, float(model.score(x, monthly["monthly_cost"]))


def detect_shopping_list(question: str, known_items: list[str]) -> bool:
    q = question.lower()
    actions = ["buy", "need", "get", "shop", "shopping", "grocery list", "ration", "basket", "for this month", "for the month", "monthly", "budget", "plan", "afford", "how much would", "what can i buy", "money i have", "salary", "spend"]
    items = ["atta", "flour", "rice", "egg", "eggs", "milk", "sugar", "toor dal", "arhar dal", "tuvar dal", "dal", "lentils", "pulses", "oil", "cooking oil", "vegetable", "vegetables", "sabzi", "greens", "salt", "namak", "potato", "potatoes", "aloo", "onion", "onions", "pyaz", "tomato", "tomatoes"]
    has_action = any(x in q for x in actions)
    has_item = any(x in q for x in items)
    budget_only = any(x in q for x in ["budget", "afford", "how much would", "plan", "salary", "spend"])
    return (has_action and has_item) or (has_action and budget_only)


def extract_shopping_items(question: str) -> list[str]:
    q = question.lower()
    patterns = [("atta", ["atta", "flour", "wheat flour"]),("rice", ["rice"]),("eggs", ["egg", "eggs"]),("milk", ["milk"]),("sugar", ["sugar"]),("toor dal", ["toor dal", "arhar dal", "tuvar dal"]),("dal / pulses", ["dal", "lentils", "pulses"]),("cooking oil", ["oil", "cooking oil"]),("vegetables", ["vegetable", "vegetables", "sabzi", "greens"]),("salt", ["salt", "namak"]),("potatoes", ["potato", "potatoes", "aloo"]),("onions", ["onion", "onions", "pyaz"]),("tomatoes", ["tomato", "tomatoes"])]
    return [label for label, aliases in patterns if any(alias in q for alias in aliases)]


def advisor_prompt(df: pd.DataFrame, profile: dict, forecast: float, question: str = "", history_text: str = "") -> str:
    mentioned = extract_shopping_items(question)
    relevant = df[df["item"].str.lower().isin([x.lower() for x in mentioned])] if mentioned else df
    context = relevant[["month", "item", "price_inr", "monthly_cost"]].to_csv(index=False)
    conditions = ", ".join(profile.get("health_conditions", [])) or "none specified"
    return f"""You are Mehengaai Mitra, a calm, practical Indian household grocery budget companion.
Household: {profile['family_size']} people in {profile['locality']}; monthly grocery budget ₹{profile['budget']:,.0f}; dietary preference: {profile['diet']}; health conditions to keep in mind: {conditions}.
The model's next-month household-cost estimate is ₹{forecast:,.0f}.

USER'S CURRENT QUESTION:
{question or 'No question yet.'}

RELEVANT HOUSEHOLD PRICE HISTORY:
{context}

CONVERSATION SO FAR:
{history_text}

STRICT RELEVANCE:
Answer the user's current question first. Discuss only grocery items explicitly mentioned by the user or necessary to answer it. Do NOT volunteer unrelated items, price shocks, controversies, or news. If the user asks about rice, atta and eggs, do not bring up sugar merely because sugar exists in the household dataset. Do not claim live prices or market causes. This normal-chat mode uses household history only. Do not produce a dashboard, table, or generic end-of-chat report. Continue as a normal conversation.
If a health condition is listed (e.g. diabetes, high blood pressure, high cholesterol, kidney issues), quietly factor it into any food-related suggestion (e.g. flag high-sugar or high-salt items) without turning the reply into a medical lecture, and note you are not a doctor if it becomes relevant.

PLAIN-LANGUAGE FIRST:
Assume the user has little patience for jargon. Open with ONE short, plain sentence that directly answers them — no financial jargon, no filler. Only add a second short sentence of context if truly necessary. Skip disclaimers unless asked."""


def shopping_prompt(df: pd.DataFrame, profile: dict, forecast: float, question: str, history_text: str, preferences: dict, items: list[str]) -> str:
    requested = ", ".join(items)
    conditions = ", ".join(profile.get("health_conditions", [])) or "none specified"
    return f"""You are Mehengaai Mitra, a household grocery shopping co-pilot for an Indian family.
The user explicitly started a monthly shopping list. Requested items: {requested}. Original request: {question}.
Household: {profile['family_size']} people in {profile['locality']}; monthly grocery budget ₹{profile['budget']:,.0f}; dietary preference: {profile['diet']}; health conditions: {conditions}. PIN code: {profile.get('pincode', 'not provided')}.
Shopping preferences: priority={preferences.get('priority','not specified')}; channel={preferences.get('channel','not specified')}; brand={preferences.get('brand','not specified')}.

HOUSEHOLD HISTORY FOR REQUESTED ITEMS:
{df[df['item'].str.lower().isin([x.lower() for x in items])][['month','item','price_inr','quantity','unit']].to_csv(index=False)}

CONVERSATION SO FAR:
{history_text}

LIVE-PRICE RULES:
Use Google Search grounding because this is shopping mode. Search current public listings relevant to the locality/PIN code. Compare like-for-like pack sizes and calculate unit prices. Prefer identifiable retailer/product pages or reputable current listings. Do not use news articles as a substitute for a product price. Never invent a local-market price; if it cannot be verified, say not verified. Do not call a price live unless you found a recent web listing. If possible compare online grocery, supermarket/mall and local-market options. Respect the selected priority.

HEALTH-AWARE CURATION:
If a health condition is listed (diabetes, high blood pressure/hypertension, high cholesterol, kidney issues, etc.), quietly steer choices accordingly — e.g. lower-sugar or whole-grain swaps for diabetes, low-sodium options for hypertension — and mention it in one short line, not a lecture. Note you are not a doctor if the condition materially changed a pick.

RELEVANCE:
Only discuss requested items and directly relevant budget trade-offs. Do not introduce sugar, sugar controversies, unrelated price shocks, or other household items unless explicitly requested.

OUTPUT FORMAT (STRICT, for a reader with little patience for jargon):
Line 1: one plain sentence — total estimated cost, and whether it fits the budget. No jargon, no hedging.
Line 2 (only if health conditions were given): one plain sentence on how the picks were adjusted for that condition.
Then write exactly the marker "###DETAILS###" on its own line.
After the marker, put everything else: the comparison table (Item | Best verified option | Pack/quantity | Price | Approx. basket cost | Why), estimated total and budget remaining/overage, quality/brand/local-market trade-offs, and sources/retailers used. Do not append the household dashboard or repeat the line-1 summary."""


def get_gemini_advice(prompt: str, use_search: bool = False) -> tuple[str, list[dict]]:
    api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))
    if not api_key or genai is None:
        return ("Add `GEMINI_API_KEY` to Streamlit secrets to activate the personalised Gemini Budget Advisor. The dashboard and ML estimate still work without it.", [])
    client = genai.Client(api_key=api_key)
    try:
        config = None
        if use_search and types is not None:
            config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=config)
        citations = []
        try:
            gm = response.candidates[0].grounding_metadata
            for chunk in (gm.grounding_chunks or []):
                web = getattr(chunk, "web", None)
                if web and getattr(web, "uri", None):
                    citations.append({"title": getattr(web, "title", "Source"), "uri": web.uri})
        except Exception:
            pass
        return (response.text or "I couldn't get a useful response just now.", citations)
    except Exception as error:
        return (f"I couldn't complete that request right now: {error}", [])

def price_pulse_campaign(item: str, change_pct: float) -> tuple[str, str, str]:
    campaigns = {
        "Sugar": (
            "🍬 Sweetness alert: sugar is sprinting upward.",
            "Your basket noticed a sugar price jump. Try smaller packs, compare nearby kiranas, or swap one sweet treat for a seasonal fruit this week.",
            "View the practical response →",
        ),
        "Cooking Oil": (
            "🫗 Oil watch: keep your kitchen budget from slipping.",
            "Compare unit prices—not just bottle prices—and plan frying-heavy meals around your best local deal.",
            "Review the oil trend →",
        ),
        "Milk": (
            "🥛 Milk-meter is up. Time for a tiny pantry rethink.",
            "A small rise matters for regular essentials. Review quantity before changing a family staple.",
            "Check essential-spend tips →",
        ),
    }
    headline, tip, cta = campaigns.get(
        item,
        (f"⚡ Price pulse: {item} just moved the most.", "A local price change is affecting your basket. Compare unit prices and plan the next shop with the forecast in mind.", "Review the price trend →"),
    )
    return headline, f"{tip} ({change_pct:+.1f}% month-on-month)", cta


def pantry_fact(item: str) -> str:
    facts = {
        "Milk": "Milk is a familiar source of calcium and protein.",
        "Rice": "Rice is an accessible energy staple for many households.",
        "Toor Dal": "Toor dal contributes plant protein and dietary fibre.",
        "Eggs": "Eggs are a practical source of protein and choline.",
        "Sugar": "Sugar is best treated as an occasional pantry extra, not a nutrient source.",
        "Cooking Oil": "Cooking oil is calorie-dense, so unit-price comparisons matter.",
    }
    return facts.get(item, f"{item} is currently one of the lighter-cost entries in this household basket.")


def create_chat(question: str = "") -> str:
    chat_id = f"chat_{len(st.session_state.mitra_chats) + 1}"
    title = question.strip()[:34] if question.strip() else "New chat"
    st.session_state.mitra_chats.append({"id": chat_id, "title": title, "messages": [], "shopping": {"stage": None, "items": [], "preferences": {}}})
    st.session_state.active_chat_id = chat_id
    st.session_state.shopping_stage = None
    st.session_state.shopping_preferences = {}
    st.session_state.shopping_items = []
    return chat_id


def active_chat() -> dict:
    for chat in st.session_state.mitra_chats:
        if chat["id"] == st.session_state.active_chat_id:
            chat.setdefault("shopping", {"stage": None, "items": [], "preferences": {}})
            return chat
    create_chat()
    return st.session_state.mitra_chats[-1]


def _history_text(chat: dict) -> str:
    return "\n".join(f"{m['role'].upper()}: {m['content']}" for m in chat["messages"][-12:])


def _avatar(role: str) -> str:
    return "🙋" if role == "user" else "🍅"


def render_shopping_tiles():
    stage = st.session_state.shopping_stage
    if stage == "priority":
        title, copy = "What should I prioritise?", "Like a good shopkeeper, Mitra asks this before choosing where you buy."
        options, prefix = [("Lowest price", "price"), ("Best value", "value"), ("Quality first", "quality"), ("Local first", "local")], "priority"
    elif stage == "channel":
        title, copy = "Where would you rather shop?", "Mitra will compare what it can verify instead of assuming online is always cheapest."
        options, prefix = [("Online grocery", "online"), ("Supermarket / mall", "supermarket"), ("Local market / kirana", "local"), ("Compare everything", "all")], "channel"
    elif stage == "brand":
        title, copy = "What about brands?", "This changes the comparison when a branded pack costs more than a generic or loose option."
        options, prefix = [("Trusted brands", "brand"), ("Generic / loose is fine", "generic"), ("Show me both", "both")], "brand"
    else:
        return
    st.markdown(f'<div class="shopping-prompt"><div class="shopping-kicker">Before I build your basket</div><h3>{title}</h3><p>{copy}</p></div>', unsafe_allow_html=True)
    cols = st.columns(len(options))
    for col, (label, value) in zip(cols, options):
        with col:
            if st.button(label, key=f"{prefix}_{value}", use_container_width=True):
                st.session_state.shopping_preferences[prefix] = label
                st.session_state.shopping_stage = {"priority": "channel", "channel": "brand", "brand": "ready"}[prefix]
                chat = active_chat()
                chat["shopping"]["stage"] = st.session_state.shopping_stage
                chat["shopping"]["preferences"] = dict(st.session_state.shopping_preferences)
                st.rerun()


def render_chat_workspace(df: pd.DataFrame, profile: dict, forecast: float, latest_cost: float, shock_item: str, shock_pct: float) -> None:
    chat = active_chat()
    with st.sidebar:
        st.markdown('<div class="sidebar-brand">Mehengaai<span>Mitra</span></div>', unsafe_allow_html=True)
        if st.button("＋  New chat", use_container_width=True, type="primary"):
            create_chat()
            st.rerun()
        st.markdown('<div class="sidebar-section">Your conversations</div>', unsafe_allow_html=True)
        for old_chat in st.session_state.mitra_chats[::-1]:
            if st.button(old_chat["title"] or "New chat", key=f"select_{old_chat['id']}", use_container_width=True):
                st.session_state.active_chat_id = old_chat["id"]
                shopping = old_chat.get("shopping", {})
                st.session_state.shopping_stage = shopping.get("stage")
                st.session_state.shopping_preferences = shopping.get("preferences", {})
                st.session_state.shopping_items = shopping.get("items", [])
                st.rerun()
        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
        with st.expander("⚙ Household settings"):
            with st.form("household_profile_form_chat"):
                locality = st.text_input("Locality", profile["locality"])
                pincode = st.text_input("PIN code (optional)", profile.get("pincode", ""))
                family_size = st.slider("Family size", 1, 10, profile["family_size"])
                budget = st.number_input("Monthly grocery budget (₹)", min_value=1000, value=int(profile["budget"]), step=500)
                diets = ["Vegetarian", "Non-vegetarian", "Vegan", "No preference"]
                diet = st.selectbox("Dietary preference", diets, index=diets.index(profile["diet"]))
                condition_options = ["Diabetes", "High blood pressure", "High cholesterol", "Kidney condition", "None"]
                health_conditions = st.multiselect("Any health conditions Mitra should factor in? (optional)", condition_options, default=profile.get("health_conditions", []))
                save = st.form_submit_button("Save household profile", use_container_width=True)
            if save:
                st.session_state.household_profile = {"locality": locality, "pincode": pincode, "family_size": family_size, "budget": budget, "diet": diet, "health_conditions": [c for c in health_conditions if c != "None"], "available_funds": budget}
                st.success("Saved.")
                st.rerun()
            uploaded = st.file_uploader("Price history CSV", type="csv")
            if uploaded is not None:
                st.session_state.uploaded_price_file = uploaded
        with st.expander("✎ Rename chat"):
            name = st.text_input("Chat title", value=chat["title"], key=f"rename_{chat['id']}")
            if st.button("Save name", use_container_width=True):
                chat["title"] = name.strip() or "New chat"
                st.rerun()
        if st.button("←  Back to home", use_container_width=True):
            st.session_state.mitra_view = "home"
            st.query_params.clear()
            st.rerun()

    st.markdown(
        '<div class="chat-home-row"><a href="?view=home" class="chat-home-btn">🏠 Home</a></div>',
        unsafe_allow_html=True,
    )
    st.markdown("""
<div class="grocery-pattern">
    <span>🍅</span><span>🥬</span><span>🧅</span><span>🧄</span>
    <span>🥕</span><span>🌶️</span><span>🍚</span><span>🥚</span>
    <span>🧈</span><span>🥛</span><span>🍞</span><span>🧀</span>
    <span>🥩</span><span>🐟</span><span>🥗</span><span>🍎</span>
    <span>🍌</span><span>🍇</span><span>🍊</span><span>🍋</span>
    <span>🥝</span><span>🍉</span><span>🍓</span><span>🍑</span>
</div>
""", unsafe_allow_html=True)
    if not chat["messages"]:
        st.markdown('<div class="chat-welcome"><div class="welcome-icon">✦</div><h3>What are we planning today?</h3><p>Ask about a price, your budget, a saving idea, or tell Mitra what you want to buy for the month.</p><div class="welcome-pantry"><span>🥛 Milk</span><span>🍚 Rice</span><span>🌾 Atta</span><span>🥚 Eggs</span><span>🫘 Dal</span><span>🥔 Ration</span></div></div>', unsafe_allow_html=True)
    for message in chat["messages"]:
        with st.chat_message(message["role"], avatar=_avatar(message["role"])):
            st.markdown(message["content"])

    if st.session_state.shopping_stage in {"priority", "channel", "brand"}:
        render_shopping_tiles()

    if st.session_state.shopping_stage == "ready":
        with st.chat_message("assistant", avatar=_avatar("assistant")):
            with st.spinner("Mitra is checking current prices and comparing your options…"):
                question = st.session_state.shopping_preferences.get("_question", "")
                answer, citations = get_gemini_advice(
                    shopping_prompt(df, profile, forecast, question, _history_text(chat), st.session_state.shopping_preferences, st.session_state.shopping_items),
                    use_search=True,
                )
            if "###DETAILS###" in answer:
                summary, details = answer.split("###DETAILS###", 1)
            else:
                summary, details = answer, ""
            st.markdown(f'<div class="quick-answer">{summary.strip()}</div>', unsafe_allow_html=True)
            if details.strip():
                with st.expander("See the full comparison, table and sources"):
                    st.markdown(details.strip())
                    if citations:
                        st.markdown('<div class="sources-label">Verified web sources</div>', unsafe_allow_html=True)
                        for source in citations[:6]:
                            st.markdown(f"- [{source['title']}]({source['uri']})")
        chat["messages"].append({"role": "assistant", "content": answer.replace("###DETAILS###", "\n\n---\n**Full details:**\n\n")})
        chat["shopping"] = {"stage": None, "items": list(st.session_state.shopping_items), "preferences": dict(st.session_state.shopping_preferences)}
        st.session_state.shopping_stage = None
        st.session_state.shopping_preferences = {}
        st.session_state.shopping_items = []
        st.rerun()

    question = st.session_state.pop("pending_question", "") or st.chat_input("Ask Mitra about your basket, prices, or what to buy…")
    if question and question.strip():
        question = question.strip()
        chat["messages"].append({"role": "user", "content": question})
        if detect_shopping_list(question, df["item"].unique().tolist()):
            items = extract_shopping_items(question) or list(df["item"].unique())
            st.session_state.shopping_items = items
            st.session_state.shopping_preferences = {"_question": question}
            st.session_state.shopping_stage = "priority"
            chat["shopping"] = {"stage": "priority", "items": items, "preferences": dict(st.session_state.shopping_preferences)}
            if chat["title"] == "New chat":
                chat["title"] = question[:34]
            st.rerun()
        with st.chat_message("assistant", avatar=_avatar("assistant")):
            with st.spinner("Mitra is thinking…"):
                answer, _ = get_gemini_advice(advisor_prompt(df, profile, forecast, question, _history_text(chat)))
            st.markdown(answer)
        chat["messages"].append({"role": "assistant", "content": answer})
        if chat["title"] == "New chat":
            chat["title"] = question[:34]
        st.rerun()

st.markdown("""<style>
 #MainMenu, header, footer {display:none !important;} .stApp, [data-testid="stAppViewContainer"] {background:radial-gradient(circle at 18% 15%,#133d4a 0,#081d2a 38%,#071521 100%);background-size:180% 180%;animation:ambient 18s ease-in-out infinite;color:#e7f1ef;} .block-container {padding:1.4rem 4rem 4rem; max-width:1320px;}
 h2, h3 {color:#edf7f5; letter-spacing:-.04em; font-family:Georgia,serif;} [data-testid="stMetric"] {background:rgba(20,52,62,.55); padding:18px; border-radius:16px; border:1px solid rgba(137,214,204,.25); box-shadow:0 12px 28px rgba(0,0,0,.14);backdrop-filter:blur(16px);}
 [data-testid="stMetricLabel"] {color:#a9c5c2;} [data-testid="stMetricValue"] {color:#f1fbf8;} [data-testid="stMetricDelta"] {font-family:monospace;}
 .brand-strip {display:flex;align-items:center;gap:28px;padding:6px 0 26px;}.brand-mark {font:500 36px Georgia,serif;letter-spacing:-.075em;color:#eaf7f4;white-space:nowrap;}.brand-mark b {color:#87ddcf;font-weight:normal;}.brand-note {font:10px monospace;letter-spacing:.16em;color:#a7c6c2;text-transform:uppercase;}.brand-links {display:flex;gap:30px;margin-left:auto;font:14px monospace;}.brand-links a {color:#d9ebe7;text-decoration:none;padding:10px 4px;opacity:.9;}.brand-links a:hover {color:#86e0d1;}
 .market-brief {min-height:calc(100vh - 86px);border-radius:0;background-position:center;background-size:cover;overflow:hidden;position:relative;isolation:isolate;margin:0 -4rem 64px;border:0;box-shadow:none;}.market-brief:after {content:"";position:absolute;inset:-20%;z-index:-1;background:radial-gradient(circle at 15% 40%,rgba(83,198,202,.28),transparent 30%),radial-gradient(circle at 70% 35%,rgba(129,108,218,.2),transparent 33%),linear-gradient(90deg,rgba(5,23,34,.87) 0%,rgba(5,23,34,.58) 54%,rgba(5,23,34,.15) 100%);animation:aurora 16s ease-in-out infinite alternate;}.market-brief:before {content:"";position:absolute;inset:0;z-index:0;pointer-events:none;background:repeating-linear-gradient(0deg,transparent 0,transparent 7px,rgba(167,241,235,.05) 8px);animation:scan 9s linear infinite;}.brief-copy {position:relative;z-index:1;max-width:720px;padding:clamp(70px,15vh,150px) 10vw 40px;}.brief-kicker {font:600 11px monospace;letter-spacing:.19em;color:#99e5dc;}.brief-title {font:400 clamp(3.2rem,6vw,6.5rem) Georgia,serif;letter-spacing:-.082em;line-height:.89;color:#f5fffd;margin:15px 0 18px;}.brief-title em {font-style:normal;color:#8de6d7;}.brief-body {font-size:17px;line-height:1.65;max-width:550px;color:#e0efec;}.typing-shell {display:flex;align-items:center;gap:11px;width:min(590px,90vw);margin-top:28px;padding:15px 18px;border-radius:14px;background:rgba(11,48,58,.44);border:1px solid rgba(148,226,216,.46);backdrop-filter:blur(14px);font:14px monospace;color:#f5fffd;overflow:hidden;}.typing-label {color:#8de6d7;white-space:nowrap;}.typing-text {display:inline-block;overflow:hidden;white-space:nowrap;border-right:2px solid #8de6d7;width:0;animation:type-erase 7s steps(58,end) infinite;}.hero-actions {display:flex;align-items:center;gap:18px;margin-top:22px;}.try-link {display:inline-block;background:#8de6d7;color:#082b37;text-decoration:none;border-radius:999px;padding:12px 20px;font:600 12px monospace;letter-spacing:.04em;box-shadow:0 8px 30px rgba(103,228,212,.25);}.hero-note {font:12px monospace;color:#c9e1de;}.brief-rail {display:flex;gap:10px;margin-top:28px;flex-wrap:wrap;}.brief-chip {background:rgba(20,65,72,.45);border:1px solid rgba(151,229,216,.38);border-radius:12px;padding:11px 13px;min-width:150px;backdrop-filter:blur(10px);}.brief-chip label{display:block;font:10px monospace;letter-spacing:.1em;color:#b9d9d4;text-transform:uppercase;}.brief-chip b{display:block;color:#f5fffd;margin-top:4px;font-size:14px;}.brief-chip.fact {min-width:245px;max-width:360px;}.dashboard-label {font:600 11px monospace;letter-spacing:.18em;color:#8de6d7;text-transform:uppercase;margin:0 0 10px;}
 @keyframes ambient {0%,100%{background-position:0% 20%}50%{background-position:100% 80%}} @keyframes aurora {0%{transform:translate3d(-2%,-1%,0) scale(1)}100%{transform:translate3d(3%,2%,0) scale(1.08)}} @keyframes scan {0%{transform:translateY(-20%)}100%{transform:translateY(20%)}} @keyframes type-erase {0%{width:0} 35%{width:57ch} 65%{width:57ch} 100%{width:0}}
 [data-testid="stPopover"] button {border-radius:999px;border:1px solid #5b9c9d;color:#e4f8f5;background:rgba(16,57,68,.48);padding:10px 18px;backdrop-filter:blur(12px);} [data-testid="stFileUploader"] {background:rgba(16,57,68,.48);border-radius:12px;padding:8px;} [data-testid="stVerticalBlockBorderWrapper"] {border-radius:16px;border-color:rgba(137,214,204,.25);background:rgba(20,52,62,.48);} .stAltairChart {background:rgba(20,52,62,.48);border-radius:16px;padding:8px;} [data-testid="stForm"] {background:rgba(16,57,68,.38);border:1px solid rgba(137,214,204,.35);border-radius:18px;padding:12px 16px;backdrop-filter:blur(14px);}
 .workspace-title {font:500 26px Georgia,serif;color:#e7fbf8;padding:8px 0;}.workspace-title span {font:11px monospace;letter-spacing:.09em;color:#a8c9c5;margin-left:12px;}.history-label,.chat-insight-label {font:10px monospace;text-transform:uppercase;letter-spacing:.16em;color:#8de6d7;margin:18px 0 10px;}.chat-heading {font:500 38px Georgia,serif;color:#effefd;letter-spacing:-.05em;margin-top:10px;}.chat-subheading {color:#b2ceca;margin:8px 0 20px;}.empty-chat {padding:42px 26px;border:1px dashed #43777a;border-radius:18px;color:#bfdbd7;background:rgba(16,57,68,.36);text-align:center;margin-bottom:16px;}.stChatMessage {background:rgba(16,57,68,.42);border:1px solid rgba(137,214,204,.28);border-radius:16px;padding:8px 14px;margin:10px 0;backdrop-filter:blur(10px);}
 @media (prefers-reduced-motion: reduce) {.price-pulse,.market-brief:before,.typing-text {animation:none;width:auto;border:0;}} @media(max-width:700px){.block-container{padding:1rem}.brief-copy{padding:90px 24px 30px}.market-brief{min-height:calc(100vh - 70px);margin:0 -1rem 44px}.brand-note,.hero-note,.brand-links{display:none}.typing-shell{font-size:12px}.workspace-title span{display:none}}
</style>""", unsafe_allow_html=True)
if st.session_state.mitra_view == "chat":
    st.markdown("""<style>
    [data-testid="stSidebar"]{display:block!important;visibility:visible!important;width:300px!important;min-width:300px!important;transform:none!important;background:#071d17!important;border-right:1px solid rgba(137,214,204,.18)!important}
    [data-testid="stSidebar"]>div:first-child{background:#071d17!important}
    .brand-strip{display:none!important}
    [data-testid="stPopover"]{display:none!important}
    .block-container{max-width:1180px!important;padding:1.4rem 3rem 4rem!important}
    </style>""",unsafe_allow_html=True)
else:
    st.markdown('<style>[data-testid="stSidebar"]{display:none!important}</style>',unsafe_allow_html=True)

st.markdown("""<style>


/* ---- base canvas ---- */
.stApp, [data-testid="stAppViewContainer"] {
  background:#061f13 !important;
  background-image:
    radial-gradient(circle at 14% 6%, rgba(35,150,95,.32) 0, transparent 32%),
    radial-gradient(circle at 82% 78%, rgba(30,120,80,.18) 0, transparent 40%),
    linear-gradient(150deg,#072a1b 0%,#082517 55%,#03170d 100%) !important;
  background-size:140% 140% !important;
  animation:ambient-green 22s ease-in-out infinite !important;
  color:#eafaf1 !important;
}
@keyframes ambient-green {0%,100%{background-position:0% 20%}50%{background-position:100% 80%}}
.block-container { color:#eafaf1 !important; }
h1,h2,h3,h4,p,label { color:#eafaf1; }

/* ---- nav ---- */
.brand-mark { color:#eafaf1 !important; }
.brand-mark b { color:#8de6a7 !important; }
.brand-links a { color:#dcf3e3 !important; }
.brand-links a:hover { color:#8de6a7 !important; }

/* ---- hero ---- */
.brief-kicker { color:#8de6a7 !important; }
.brief-title { color:#f5fffa !important; text-shadow:0 4px 28px rgba(0,0,0,.35) !important; white-space:nowrap !important; font-size:clamp(2.1rem, 4.4vw, 4.3rem) !important; line-height:1.05 !important; }
.brief-title em { color:#8de6a7 !important; }
.brief-body { color:#f0fbf4 !important; text-shadow:0 1px 10px rgba(0,0,0,.18) !important; }
.typing-shell { background:rgba(3,28,18,.82) !important; border-color:rgba(181,240,205,.58) !important; color:#ffffff !important; box-shadow:0 8px 26px rgba(0,0,0,.12) !important; }
.typing-text { color:#ffffff !important; }
.typing-text { border-right:0 !important; }
.typing-shell .typing-caret { display:inline-block; animation:caret-bounce .5s ease-in-out infinite alternate; margin-left:2px; }
@keyframes caret-bounce { 0%{transform:translateY(0) rotate(-6deg)} 100%{transform:translateY(-3px) rotate(6deg)} }
.typing-label { color:#8de6a7 !important; }
.try-link { background:#8de6a7 !important; color:#07301e !important; box-shadow:0 8px 30px rgba(141,230,167,.25) !important; }
.hero-note { color:#c9e6d4 !important; }
.brief-chip { background:rgba(7,46,29,.55) !important; border-color:rgba(141,230,167,.35) !important; }
.brief-chip label { color:#a9d9bb !important; }
.brief-chip b { color:#f5fffa !important; }
.dashboard-label { color:#8de6a7 !important; }

/* pantry floating labels */
.pantry-float { background:rgba(4,30,19,.55) !important; border-color:rgba(141,230,167,.25) !important; color:rgba(224,247,232,.85) !important; }
.pantry-float strong { color:#b8f1c9 !important; }

/* ---- metrics / cards ---- */
[data-testid="stMetric"] { background:rgba(7,46,29,.55) !important; border-color:rgba(141,230,167,.28) !important; }
[data-testid="stMetricLabel"] { color:#a9d9bb !important; }
[data-testid="stMetricValue"] { color:#f1fff6 !important; }
[data-testid="stVerticalBlockBorderWrapper"] { border-color:rgba(141,230,167,.25) !important; background:rgba(7,46,29,.48) !important; }
.stAltairChart { background:rgba(7,46,29,.48) !important; border-radius:16px; padding:8px; }
[data-testid="stDataFrame"] { background:rgba(7,46,29,.5) !important; border:1px solid rgba(141,230,167,.25) !important; border-radius:12px; }
[data-testid="stDataFrame"] * { color:#eafaf1 !important; }
[data-testid="stExpander"] { background:rgba(7,46,29,.4) !important; border:1px solid rgba(141,230,167,.25) !important; border-radius:14px; }
[data-testid="stExpander"] summary { color:#eafaf1 !important; }

/* ---- forms / inputs / buttons (covers landing search + settings + household form) ---- */
[data-testid="stForm"] { background:rgba(8,45,30,.5) !important; border:1px solid rgba(141,230,167,.35) !important; }
.stTextInput input, .stNumberInput input, textarea {
  background:rgba(4,26,17,.75) !important; color:#f5fffa !important;
  border:1px solid rgba(141,230,167,.4) !important;
}
.stTextInput input::placeholder, textarea::placeholder { color:#8fb6a0 !important; }
.stButton button {
  background:rgba(141,230,167,.12) !important; color:#eafaf1 !important;
  border:1px solid rgba(141,230,167,.48) !important; border-radius:10px !important;
}
.stButton button:hover { background:rgba(141,230,167,.26) !important; border-color:#8de6a7 !important; }
[data-testid="stFormSubmitButton"] button, [data-testid="baseButton-primary"] {
  background:#8de6a7 !important; color:#07301e !important; font-weight:600 !important; border:none !important;
}
[data-testid="stPopover"] button { border:1px solid #4c9d6f !important; color:#eafaf1 !important; background:rgba(7,46,29,.5) !important; }
[data-testid="stFileUploader"] { background:rgba(7,46,29,.5) !important; border-radius:12px; padding:8px; }

/* ---- sidebar (chat view) ---- */
[data-testid="stSidebar"] { background:#04160e !important; border-right:1px solid rgba(141,230,167,.18) !important; }
[data-testid="stSidebar"] * { color:#e7f9ef !important; }
.sidebar-brand { font:500 24px Georgia,serif; color:#f0fff6; padding:6px 4px 18px; }
.sidebar-brand span { color:#8de6a7; }
.sidebar-section { font:10px monospace; letter-spacing:.14em; text-transform:uppercase; color:#8de6a7 !important; margin:16px 0 6px; }
.sidebar-divider { height:1px; background:rgba(141,230,167,.18); margin:14px 0; }

/* ---- grocery pattern background ---- */
.grocery-pattern {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    z-index: 1 !important;
    pointer-events: none !important;
    opacity: 0.055 !important;
    display: grid !important;
    grid-template-columns: repeat(8, 1fr) !important;
    gap: 30px !important;
    padding: 40px !important;
    overflow: hidden !important;
}

.grocery-pattern span {
    font-size: 35px !important;
    text-align: center !important;
    animation: float-slow 25s ease-in-out infinite !important;
}

.grocery-pattern span:nth-child(even) {
    animation-delay: -8s !important;
    font-size: 28px !important;
}

.grocery-pattern span:nth-child(3n) {
    animation-delay: -15s !important;
    font-size: 42px !important;
}

@keyframes float-slow {
    0%, 100% { transform: translateY(0px) rotate(0deg); }
    50% { transform: translateY(-20px) rotate(10deg); }
}

/* Keep the actual chat content above the decorative pattern. */
[data-testid="stAppViewContainer"] .block-container {
    position: relative !important;
    z-index: 2 !important;
}

/* ---- chat home button ---- */
.chat-home-row {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 16px;
    position: relative;
    z-index: 2;
}

.chat-home-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: linear-gradient(135deg, #ffd700, #e6b800);
    color: #07301e !important;
    padding: 8px 18px;
    border-radius: 999px;
    text-decoration: none !important;
    font-weight: 600;
    font-size: 14px;
    box-shadow: 0 4px 15px rgba(255, 215, 0, 0.2);
    transition: all 0.3s ease;
}

.chat-home-btn:hover {
    transform: translateY(-2px);
    color: #07301e !important;
    box-shadow: 0 6px 25px rgba(255, 215, 0, 0.35);
}

/* ---- chat workspace ---- */
.workspace-title { color:#f5fffa !important; }
.workspace-subtitle { color:#a9d9bb !important; font:11px monospace; letter-spacing:.06em; margin-left:12px; }
.chat-heading { color:#f5fffa !important; }
.chat-subheading { color:#b6ddc7 !important; }
.chat-welcome { background:rgba(7,46,29,.5) !important; border:1px dashed rgba(141,230,167,.35) !important; border-radius:18px; padding:34px; text-align:center; margin-bottom:16px; }
.chat-welcome h3 { color:#f5fffa !important; margin:8px 0; }
.chat-welcome p { color:#c9e6d4 !important; }
.welcome-icon { font-size:26px; color:#8de6a7; }
.welcome-pantry span { display:inline-block; background:rgba(141,230,167,.12); border:1px solid rgba(141,230,167,.3); border-radius:999px; padding:6px 13px; margin:4px; color:#e7f9ef !important; font-size:13px; }

.stChatMessage { background:rgba(7,46,29,.75) !important; border:1px solid rgba(141,230,167,.28) !important; border-radius:16px !important; }
.stChatMessage p, .stChatMessage li, .stChatMessage span, .stChatMessage div,
[data-testid="stChatMessageContent"] { color:#f1fff6 !important; }
/* ---- chat input - CLEAN & CONTRAST ---- */
[data-testid="stChatInput"] { 
  background: rgba(10, 45, 28, 0.95) !important; 
  border: 2px solid rgba(255, 215, 0, 0.4) !important;
  border-radius: 12px !important;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3) !important;
  padding: 4px 6px !important;
  min-height: 52px !important;
  max-width: 100% !important;
}

/* Force Streamlit's inner input wrapper away from the default white */
[data-testid="stChatInput"] > div,
[data-testid="stChatInput"] [data-baseweb="base-input"] {
  background: rgba(10, 45, 28, 0.95) !important;
  border-radius: 10px !important;
  box-shadow: none !important;
}

[data-testid="stChatInput"]:focus-within {
  border-color: #ffd700 !important;
  box-shadow: 0 4px 30px rgba(255, 215, 0, 0.1) !important;
}

[data-testid="stChatInput"] textarea { 
  color: #ffffff !important; 
  font-size: 14px !important;
  background: rgba(10, 45, 28, 0.95) !important;
  padding: 8px 12px !important;
  min-height: 36px !important;
}

[data-testid="stChatInput"] textarea::placeholder { 
  color: #a8d5b8 !important;
  opacity: 0.8 !important;
  font-size: 14px !important;
}

[data-testid="stChatInput"] textarea:focus {
  color: #ffffff !important;
  background: rgba(10, 45, 28, 0.95) !important;
}

/* Chat input send button */
[data-testid="stChatInput"] button {
  background: linear-gradient(135deg, #ffd700, #e6b800) !important;
  color: #07301e !important;
  font-weight: 700 !important;
  border-radius: 8px !important;
  padding: 6px 16px !important;
  border: none !important;
  box-shadow: 0 4px 15px rgba(255, 215, 0, 0.25) !important;
  transition: all 0.3s ease !important;
  min-height: 36px !important;
  margin-right: 4px !important;
}

[data-testid="stChatInput"] button:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 25px rgba(255, 215, 0, 0.4) !important;
}

.sources-label { font:10px monospace; letter-spacing:.12em; text-transform:uppercase; color:#8de6a7 !important; margin:14px 0 6px; }

/* ---- shopping preference tiles ---- */
.shopping-prompt { background:linear-gradient(135deg,#0c5b3d,#08301f) !important; border:1px solid rgba(141,230,167,.4) !important; border-radius:18px; padding:20px 24px; margin:16px 0; }
.shopping-kicker { font:600 10px monospace; letter-spacing:.16em; text-transform:uppercase; color:#8de6a7 !important; }
.shopping-prompt h3 { color:#f5fffa !important; margin:6px 0; }
.shopping-prompt p { color:#c9e6d4 !important; margin:0; }

/* ---- about section - wide left-to-right layout ---- */
.about-mitra {
  margin: 70px 0 20px;
  width: 100%;
  max-width: none;
  padding: 44px 5vw;
  border-radius: 24px;
  background: rgba(4, 42, 26, 0.6);
  border: 1px solid rgba(45, 180, 100, 0.2);
  box-shadow: 0 18px 45px rgba(0,0,0,.2), 0 0 60px rgba(45,180,100,.03);
  backdrop-filter: blur(10px);
}

.about-kicker {
  font: 600 12px monospace;
  letter-spacing: .18em;
  color: #ffd700 !important;
  text-transform: uppercase;
  margin-bottom: 10px;
}

.about-mitra h3 {
  margin: 0 0 28px 0;
  font-size: 34px;
  color: #f5fffa !important;
  line-height: 1.2;
}

.about-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 22px;
  margin: 20px 0 32px;
}

.about-card {
  background: rgba(7, 46, 29, 0.5);
  border: 1px solid rgba(45, 180, 100, 0.15);
  border-radius: 16px;
  padding: 24px 26px;
  transition: all 0.3s ease;
  cursor: default;
}

.about-card:hover {
  transform: translateY(-4px);
  background: rgba(7, 46, 29, 0.8);
  border-color: rgba(45, 180, 100, 0.4);
  box-shadow: 0 12px 30px rgba(0,0,0,.2), 0 0 40px rgba(45,180,100,.05);
}

.about-icon {
  font-size: 30px;
  margin-bottom: 12px;
}

.about-card h4 {
  margin: 0 0 10px 0;
  font-size: 18px;
  color: #f5fffa !important;
  font-weight: 600;
}

.about-card p {
  margin: 0;
  font-size: 15px;
  line-height: 1.65;
  color: #c9e6d4 !important;
}

.about-footer {
  margin-top: 20px;
  padding-top: 22px;
  border-top: 1px solid rgba(45, 180, 100, 0.15);
}

.about-footer p {
  margin: 0;
  font-size: 15px;
  line-height: 1.65;
  color: #d4ece0 !important;
}

/* ---- responsive ---- */
@media(max-width:700px) {
  .about-mitra {
    width: auto;
    padding: 28px 20px;
    margin: 40px 10px 20px;
  }
  .about-grid {
    grid-template-columns: 1fr;
    gap: 14px;
  }
  .about-mitra h3 {
    font-size: 24px;
  }
  .about-card p,
  .about-footer p {
    font-size: 14px;
  }
}
/* ---- corner illustration + speech bubbles ----
   Rebuilt as a flex column pinned to the right side of the hero.
   Bubbles stack top-to-bottom with real spacing, so they can
   never overlap the left-side headline no matter how long the
   copy is or how the panel resizes. */
.market-brief { min-height:calc(100vh - 86px); border-radius:28px; overflow:hidden; position:relative; isolation:isolate; margin:12px 0 56px; border:1px solid rgba(141,230,167,.28); box-shadow:0 28px 70px rgba(0,0,0,.3); }
.market-brief:after { content:""; position:absolute; inset:0; z-index:0; background:radial-gradient(circle at 82% 22%,rgba(120,210,150,.16),transparent 32%), linear-gradient(90deg,rgba(4,22,14,.85) 0%,rgba(4,22,14,.5) 55%,rgba(4,22,14,.1) 100%); }
.brief-copy { position:relative; z-index:2; max-width:56%; padding:clamp(60px,13vh,130px) 5vw 40px; }

/* Illustration kept purely decorative, anchored low-right so it never reaches
   the headline height. No text is ever positioned over it. */
.corner-duo { position:absolute; right:2%; bottom:-2%; height:58%; max-width:34%; object-fit:contain; z-index:1; }

/* The "distressed → calm" exchange is now a standalone card in normal
   document flow under the CTA row, never overlaid on the photo, so it
   can't land on anyone's head and text/background contrast is guaranteed. */
/* The "distressed → calm" exchange - PUSHED FAR RIGHT */
.mini-convo {
  position: absolute;
  right: -75%;
  top: -5%;
  width: 55%;
  height: 70%;
  z-index: 4;
  pointer-events: none;
  display: flex;
  flex-direction: column;
  justify-content: space-evenly;
  align-items: flex-end;
  padding-right: 50px;
}
.mini-convo .convo-line {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 18px;
  background: rgba(247, 255, 250, 0.97);
  border: 1px solid rgba(160, 215, 184, 0.82);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.20);
  max-width: 300px;
  min-width: 180px;
  pointer-events: none;
  animation: dialogue-float 4.5s ease-in-out infinite;
  position: relative;
  width: fit-content;
  margin: 2px 0;
}

/* First bubble - worried person (left side of the right panel) */
.mini-convo .convo-line.worried {
  top: 3%;
  align-self: flex-start;
  margin-left: 5%;
  margin-right: 20%;  
  background: rgba(255, 248, 240, 0.97);
  border-color: rgba(200, 180, 160, 0.6);
  max-width: 260px;
}


.mini-convo .convo-line.worried::after {
  content: "";
  position: absolute;
  width: 12px;
  height: 12px;
  background: rgba(255, 248, 240, 0.97);
  border-right: 1px solid rgba(200, 180, 160, 0.6);
  border-bottom: 1px solid rgba(200, 180, 160, 0.6);
  transform: rotate(45deg);
  bottom: -6px;
  left: 20px;
}
/* Calm bubbles - Mitra responses (pushed far right) */
.mini-convo .convo-line.calm {
  align-self: flex-end;
  margin-right: -10%;
  margin-left: 20%;  
  background: rgba(247, 255, 250, 0.97);
  border-color: rgba(141, 230, 167, 0.6);
  max-width: 280px;
}

.mini-convo .convo-line.calm::after {
  content: "";
  position: absolute;
  width: 12px;
  height: 12px;
  background: rgba(247, 255, 250, 0.97);
  border-right: 1px solid rgba(141, 230, 167, 0.6);
  border-bottom: 1px solid rgba(141, 230, 167, 0.6);
  transform: rotate(45deg);
  bottom: -6px;
  right: 20px;
}
.mini-convo .convo-line.calm:nth-of-type(2) {
  animation-delay: 0.7s;
}

.mini-convo .convo-line.calm:nth-of-type(3) {
  animation-delay: 1.4s;
}

.mini-convo .convo-avatar {
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  object-fit: contain;
  display: block;
  border-radius: 50%;
}

.mini-convo p {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.3;
  color: #123a28 !important;
  max-width: 200px;
}

@keyframes dialogue-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}
/* Responsive fix for mobile */
@media(max-width:900px) {
  .mini-convo {
    position: relative;
    right: auto;
    top: auto;
    width: 100%;
    height: auto;
    margin-top: 20px;
    padding: 10px;
    align-items: center;
  }
  .mini-convo .convo-line {
    max-width: 90%;
    min-width: 0;
    margin: 6px auto;
  }
  .mini-convo .convo-line.worried {
    align-self: center;
    margin-left: 0;
  }
  .mini-convo .convo-line.calm {
    align-self: center;
    margin-right: 0;
  }
}

/* Streamlit's sticky bottom bar sometimes keeps its own white background
   behind the chat input — force it dark so the input never flashes white. */
[data-testid="stBottom"], [data-testid="stBottomBlockContainer"], [data-testid="stChatInputContainer"] {
  background:#04160e !important;
}

/* Shopping-preference tiles: Streamlit gives short-label buttons a lot of
   empty vertical padding by default — tighten them up. */
.shopping-prompt ~ div .stButton button, .shopping-prompt + div .stButton button {
  padding:10px 14px !important; min-height:0 !important; font-size:13.5px !important;
}

/* Quick-answer line shown above the collapsible jargon/table for shopping replies */
.quick-answer { background:rgba(141,230,167,.14); border:1px solid rgba(141,230,167,.4); border-radius:14px; padding:14px 18px; font-size:15px; color:#f1fff6 !important; margin-bottom:4px; }
</style>""", unsafe_allow_html=True)

# Upload widget value defaults to None when the Settings panel is not rendered.
uploaded = None

# Only show settings in chat view
if st.session_state.mitra_view == "chat":
    brand_col, settings_col = st.columns([8, 1])
    with brand_col:
        home_href, how_href, signals_href, about_href = "?view=chat#home", "?view=chat#how-it-works", "?view=chat#price-signals", "?view=chat#about-mitra"
        st.markdown(
            f'''<div class="brand-strip"><div class="brand-mark">Mehengaai<b>Mitra</b></div><div class="brand-links">
            <a href="{home_href}">Home</a><a href="{how_href}">How it works</a><a href="{signals_href}">Price signals</a><a href="{about_href}">About Mitra</a>
            </div></div>''',
            unsafe_allow_html=True,
        )
    with settings_col:
        with st.popover("Settings", use_container_width=True):
            st.subheader("Household profile")
            with st.form("household_profile_form"):
                locality = st.text_input("Locality", st.session_state.household_profile["locality"])
                family_size = st.slider("Family size", 1, 10, st.session_state.household_profile["family_size"])
                budget = st.number_input("Monthly grocery budget (₹)", min_value=1000, value=st.session_state.household_profile["budget"], step=500)
                diet_options = ["Vegetarian", "Non-vegetarian", "Vegan", "No preference"]
                diet = st.selectbox("Dietary preference", diet_options, index=diet_options.index(st.session_state.household_profile["diet"]))
                condition_options = ["Diabetes", "High blood pressure", "High cholesterol", "Kidney condition", "None"]
                health_conditions = st.multiselect("Any health conditions Mitra should factor in? (optional)", condition_options, default=st.session_state.household_profile.get("health_conditions", []))
                save_profile = st.form_submit_button("Save household profile")
            if save_profile:
                st.session_state.household_profile = {"locality": locality, "pincode": st.session_state.household_profile.get("pincode", ""), "family_size": family_size, "budget": budget, "diet": diet, "health_conditions": [c for c in health_conditions if c != "None"], "available_funds": budget}
                st.success("Saved.")
            st.divider()
            uploaded = st.file_uploader("Upload price history CSV", type="csv", help="Columns: month,item,price_inr,quantity,unit,locality")
            st.download_button("Sample CSV", SAMPLE_DATA, "sample_grocery_prices.csv", "text/csv")
else:
    # Home page - no Settings button
    st.markdown(
        f'''<div class="brand-strip"><div class="brand-mark">Mehengaai<b>Mitra</b></div><div class="brand-links">
        <a href="#home">Home</a><a href="#price-signals">Price signals</a><a href="#about-mitra">About Mitra</a>
        </div></div>''',
        unsafe_allow_html=True,
    )

profile = st.session_state.household_profile
locality = profile["locality"]
pincode = profile.get("pincode", "")
family_size = profile["family_size"]
budget = profile["budget"]
diet = profile["diet"]

try:
    df = load_data(st.session_state.get("uploaded_price_file") or uploaded)
except Exception as error:
    st.error(f"Could not read your data: {error}")
    st.stop()

months = sorted(df["month"].unique())
latest_month, previous_month = months[-1], months[-2] if len(months) > 1 else months[-1]
latest_cost = df.loc[df.month == latest_month, "monthly_cost"].sum()
previous_cost = df.loc[df.month == previous_month, "monthly_cost"].sum()
change_pct = ((latest_cost / previous_cost) - 1) * 100 if previous_cost else 0
latest_items = df[df.month == latest_month].set_index("item")
prev_items = df[df.month == previous_month].set_index("item")
item_changes = ((latest_items["price_inr"] / prev_items["price_inr"] - 1) * 100).dropna()
shock_item = item_changes.idxmax() if not item_changes.empty else "—"
shock_pct = item_changes.max() if not item_changes.empty else 0
forecast, r2 = forecast_next_budget(df)

value_row = breakdown = df[df.month == latest_month].sort_values("monthly_cost")
value_item = value_row.iloc[0]["item"]
value_cost = value_row.iloc[0]["monthly_cost"]
campaign_headline, campaign_tip, _ = price_pulse_campaign(shock_item, shock_pct)
if st.session_state.mitra_view == "chat":
    render_chat_workspace(df, profile, forecast, latest_cost, shock_item, shock_pct)
    st.stop()
corner_duo_uri = image_data_uri("assets/budget-duo-corner.png")
man_avatar_uri = image_data_uri("mitra-man-avatar.png")
woman_avatar_uri = image_data_uri("mitra-woman-avatar.png")
st.markdown(f"""<section id="home" class="market-brief">
<div class="brief-copy"><div class="brief-kicker">YOUR HOUSEHOLD PRICE COMPASS</div>
<div class="brief-title">Mehengaai<em>Mitra</em></div>
<div class="brief-body">Know your basket before it gets expensive. Mitra turns local grocery prices into calm, practical choices.</div>
<div class="typing-shell"><span class="typing-label">Ask Mitra ›</span><span class="typing-text">Will this month’s grocery basket stay within my ₹5,000 budget?</span><span class="typing-caret">🍅</span></div>
<div class="hero-actions"><a class="try-link" href="?view=chat">TRY MITRA →</a><span class="hero-note">Built around your own price history</span></div>
<div class="brief-rail"><div class="brief-chip"><label>Latest local signal</label><b>{shock_item} {shock_pct:+.1f}% MoM</b></div><div class="brief-chip"><label>Basket watch</label><b>{value_item} · ₹{value_cost:,.0f}/month</b></div></div>
<div class="mini-convo">
<div class="convo-line worried"><img class="convo-avatar" src="{man_avatar_uri}" alt="Worried shopper"><p>I spent ₹6,200 last month on groceries... I have no idea where it all went!</p></div>
<div class="convo-line calm"><img class="convo-avatar" src="{woman_avatar_uri}" alt="Calm Mitra"><p>That's exactly why I use Mehengaai Mitra — it shows me the breakdown before I shop.</p></div>
<div class="convo-line calm"><img class="convo-avatar" src="{woman_avatar_uri}" alt="Calm Mitra"><p>Just tell Mitra what you need, your budget, and it helps you choose what makes sense. Simple!</p></div>
</div>
</div>

<img class="corner-duo" src="{corner_duo_uri}" alt="Two people discussing a grocery budget">
</section>""", unsafe_allow_html=True)
st.markdown('<div id="mitra-chat"></div>', unsafe_allow_html=True)
st.markdown('<div class="dashboard-label">Start with a question</div>', unsafe_allow_html=True)
with st.form("landing_prompt", border=False):
    landing_question = st.text_input("Ask Mitra", placeholder="e.g. I need rice, atta, eggs and dal for this month. Help me stay within ₹5,000.", label_visibility="collapsed")
    enter_chat = st.form_submit_button("Open Mitra →")
if enter_chat and landing_question.strip():
    create_chat()
    st.session_state.pending_question = landing_question
    st.session_state.mitra_view = "chat"
    st.rerun()
st.markdown('<div id="price-signals" class="dashboard-label">Your basket dashboard</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Latest grocery basket", f"₹{latest_cost:,.0f}", f"{change_pct:+.1f}% vs last month")
c2.metric("Next-month ML estimate", f"₹{forecast:,.0f}", f"₹{forecast-latest_cost:+,.0f} trend")
c3.metric("Largest price shock", shock_item, f"{shock_pct:+.1f}% MoM")
c4.metric("Budget headroom", f"₹{budget-latest_cost:,.0f}", "Latest basket vs budget")

left, right = st.columns([1.55, 1])
with left:
    st.subheader("📈 Price movement by item")
    selected_items = st.multiselect("Compare items", df.item.unique(), default=list(df.item.unique()))
    chart_df = df[df.item.isin(selected_items)]

    # Prettier chart with better colors and styling - FIXED
    chart = alt.Chart(chart_df).mark_line(
        point=alt.OverlayMarkDef(
            filled=True,
            fill="white",
            size=60,
            strokeWidth=2
        ),
        strokeWidth=3,
        interpolate='monotone'
    ).encode(
        x=alt.X("month:T", title="Month", axis=alt.Axis(labelAngle=0, labelFontSize=12, titleFontSize=14)),
        y=alt.Y("price_inr:Q", title="Price (₹)", axis=alt.Axis(labelFontSize=12, titleFontSize=14)),
        color=alt.Color("item:N", title="Item", 
                       scale=alt.Scale(range=["#ffd700", "#2db464", "#70d6ce", "#d8a3e8", "#f08a9b"]), 
                       legend=alt.Legend(titleFontSize=13, labelFontSize=12))
    ).properties(
        height=380, 
        background="#0a2d1c"
    ).configure_view(
        fill="#0a2d1c",
        stroke=None
    ).configure_axis(
        labelColor="#bcd7d3",
        titleColor="#bcd7d3",
        gridColor="rgba(45,180,100,0.15)",
        domainColor="#2db464",
        grid=True,
        gridOpacity=0.3
    ).configure_legend(
        labelColor="#d0e4e1",
        titleColor="#d0e4e1",
        padding=10,
        cornerRadius=8,
        strokeColor="rgba(45,180,100,0.2)",
        strokeWidth=1,
        fillColor="rgba(4,42,26,0.5)"
    ).interactive()

    st.altair_chart(chart, use_container_width=True)

    with st.expander("📋 Show as a simple table instead"):
        latest_snapshot = df[df.month == df["month"].max()][["item", "price_inr", "unit"]].rename(columns={"item": "Item", "price_inr": "Price (₹)", "unit": "Unit"})
        st.dataframe(latest_snapshot, hide_index=True, use_container_width=True)

with right:
    st.subheader("📊 Where the basket goes")
    breakdown = df[df.month == latest_month]

    # Prettier bar chart with better colors - FIXED
    bar = alt.Chart(breakdown).mark_bar(
        cornerRadiusTopLeft=4,
        cornerRadiusTopRight=4,
        opacity=0.9
    ).encode(
        x=alt.X("monthly_cost:Q", title="Monthly spend (₹)", axis=alt.Axis(labelFontSize=12, titleFontSize=14)),
        y=alt.Y("item:N", sort="-x", title="", axis=alt.Axis(labelFontSize=13)),
        color=alt.Color("item:N", 
                       legend=None, 
                       scale=alt.Scale(range=["#ffd700", "#2db464", "#70d6ce", "#d8a3e8", "#f08a9b"])), 
        tooltip=["item:N", "monthly_cost:Q", "quantity:Q", "unit:N"]
    ).properties(
        height=380, 
        background="#0a2d1c"
    ).configure_view(
        fill="#0a2d1c",
        stroke=None
    ).configure_axis(
        labelColor="#bcd7d3",
        titleColor="#bcd7d3",
        gridColor="rgba(45,180,100,0.15)",
        domainColor="#2db464",
        grid=True,
        gridOpacity=0.3
    )

    st.altair_chart(bar, use_container_width=True)

st.markdown(
    '''<section id="about-mitra" class="about-mitra">
        <div class="about-kicker">✨ YOUR SMART GROCERY COMPANION</div>
        <h3>More than just a budget tracker — Mitra helps you shop smarter.</h3>
        <div class="about-grid">
            <div class="about-card">
                <div class="about-icon">💰</div>
                <h4>Set Your Budget</h4>
                <p>Tell Mitra your monthly grocery budget or income, and it keeps you on track. No more surprises at checkout.</p>
            </div>
            <div class="about-card">
                <div class="about-icon">🛒</div>
                <h4>Smart Shopping Lists</h4>
                <p>Tell Mitra what you want to buy — or what you want to cook — and it builds a complete shopping list that fits your budget.</p>
            </div>
            <div class="about-card">
                <div class="about-icon">🏷️</div>
                <h4>Brand & Store Comparison</h4>
                <p>Not sure which brand to pick? Mitra compares prices across online, supermarkets, and local kirana stores. Choose branded, generic, or loose options.</p>
            </div>
            <div class="about-card">
                <div class="about-icon">❤️</div>
                <h4>Health-Aware Planning</h4>
                <p>Manage diabetes, high blood pressure, kidney conditions, and more. Mitra optimizes your grocery list based on your family's health needs.</p>
            </div>
            <div class="about-card">
                <div class="about-icon">📊</div>
                <h4>Price History & Forecast</h4>
                <p>Upload your grocery bills or use sample data. Mitra tracks price movements and predicts next month's costs using machine learning.</p>
            </div>
            <div class="about-card">
                <div class="about-icon">🌐</div>
                <h4>Real-Time Price Search</h4>
                <p>In shopping mode, Mitra searches current verified prices online — so you know exactly what you're paying before you step out.</p>
            </div>
        </div>
        <div class="about-footer">
            <p><strong>How it works:</strong> Set your household profile → Tell Mitra what you need → Choose your preferences → Get a smart, budget-friendly shopping list. Simple.</p>
            <p style="margin-top: 12px; opacity: 0.7; font-size: 13px;">🍅 Mehengaai Mitra is a companion, not a marketplace. Every decision stays with you.</p>
        </div>
    </section>''',
    unsafe_allow_html=True,
)