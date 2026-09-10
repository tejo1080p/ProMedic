import streamlit as st

APP_NAME = "ProMedic+"
TAGLINE = "An AI-Powered Health Companion for Medication Adherence, Prescription Decoding, and Nutritional Guidance"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

def init_ui_state() -> None:
    if "theme" not in st.session_state:
        st.session_state["theme"] = "Light"
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "user" not in st.session_state:
        st.session_state["user"] = None
    if "nav" not in st.session_state:
        st.session_state["nav"] = "Home"


def apply_theme_styles(theme: str) -> None:
    if theme == "Dark":
        colors = {
            "bg": "#0e1117",
            "text": "#e6edf3",
            "card": "#161b22",
            "accent": "#4f9cff",
            "accent_soft": "#8abaff",
            "muted": "#9aa4b2",
            "border": "#232a36",
            "shadow": "rgba(0, 0, 0, 0.25)",
            "input_bg": "#0f141c",
        }
    else:
        colors = {
            "bg": "#ffffff",
            "text": "#111827",
            "card": "#f9fafb",
            "accent": "#1f6feb",
            "accent_soft": "#7ca8ff",
            "muted": "#6b7280",
            "border": "#e5e7eb",
            "shadow": "rgba(15, 23, 42, 0.08)",
            "input_bg": "#ffffff",
        }

    st.markdown(
        f"""
        <style>
            :root {{
                --bg: {colors['bg']};
                --text: {colors['text']};
                --card: {colors['card']};
                --accent: {colors['accent']};
                --accent-soft: {colors['accent_soft']};
                --muted: {colors['muted']};
                --border: {colors['border']};
                --shadow: {colors['shadow']};
                --input-bg: {colors['input_bg']};
            }}

            .stApp {{
                background: var(--bg);
                color: var(--text);
            }}

            .header {{
                text-align: center;
                font-size: clamp(36px, 6vw, 50px);
                font-weight: 800;
                letter-spacing: 0.7px;
                margin: 10px 0 6px 0;
                background: linear-gradient(90deg, var(--accent), var(--accent-soft));
                -webkit-background-clip: text;
                color: transparent;
            }}

            .subheader {{
                text-align: center;
                font-size: clamp(16px, 3.2vw, 21px);
                color: var(--muted);
                margin-bottom: 24px;
            }}

            .section {{
                min-height: 185px;
                padding: 20px;
                border-radius: 14px;
                border: 1px solid var(--border);
                background: var(--card);
                box-shadow: 0 8px 22px var(--shadow);
                transition: transform 0.2s ease, box-shadow 0.2s ease;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            }}

            .section:hover {{
                transform: translateY(-3px);
                box-shadow: 0 12px 28px var(--shadow);
            }}

            .section h3 {{
                font-size: 21px;
                margin: 0 0 8px 0;
                letter-spacing: 0.4px;
                color: var(--text);
            }}

            .section p {{
                margin: 0;
                color: var(--muted);
                font-size: 16px;
                line-height: 1.5;
            }}

            .login-wrap {{
                display: flex;
                justify-content: center;
                padding: 5vh 12px;
            }}

            .login-card {{
                width: min(480px, 96%);
                background: var(--card);
                border: 1px solid var(--border);
                border-radius: 14px;
                box-shadow: 0 10px 26px var(--shadow);
                padding: 22px;
                text-align: center;
            }}

            .login-title {{
                font-size: 28px;
                font-weight: 700;
                letter-spacing: 0.4px;
                margin-bottom: 4px;
                color: var(--text);
            }}

            .login-sub {{
                color: var(--muted);
                margin-bottom: 12px;
            }}

            .centered {{
                text-align: center;
                padding: 8vh 16px;
            }}

            .centered h2 {{
                font-size: clamp(24px, 4.5vw, 30px);
                letter-spacing: 0.4px;
                margin-bottom: 8px;
                color: var(--text);
            }}

            .centered p {{
                color: var(--muted);
                font-size: 17px;
            }}

            .stButton > button {{
                border: 1px solid transparent;
                border-radius: 12px;
                padding: 10px 14px;
                font-weight: 600;
                transition: transform 0.2s ease, box-shadow 0.2s ease;
            }}

            .stButton > button:hover {{
                transform: translateY(-3px);
                box-shadow: 0 10px 22px var(--shadow);
            }}

            [data-testid="stChatMessage"] {{
                background: var(--card);
                border: 1px solid var(--border);
                border-radius: 14px;
                padding: 10px 14px;
                margin-bottom: 10px;
            }}

            [data-testid="stTextInput"] input,
            [data-testid="stTextArea"] textarea,
            [data-testid="stChatInput"] textarea,
            [data-testid="stNumberInput"] input,
            [data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
                background: var(--input-bg) !important;
                color: var(--text) !important;
                border: 1px solid var(--border) !important;
                border-radius: 12px !important;
            }}

            .stMarkdown, .stCaption, .stText, label, p, span, h1, h2, h3, h4 {{
                color: var(--text);
            }}

            .stSidebar {{
                background: var(--bg);
            }}

            @media (max-width: 900px) {{
                .section {{
                    min-height: 165px;
                }}
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_feature_card(title: str, description: str, button_label: str, button_key: str, target: str | None = None) -> None:
    st.markdown('<div class="section">', unsafe_allow_html=True)
    st.markdown(f"<h3>{title}</h3><p>{description}</p>", unsafe_allow_html=True)
    if st.button(button_label, key=button_key, use_container_width=True):
        if target:
            st.session_state["nav"] = target
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def show_login_page() -> None:
    st.markdown('<div class="login-wrap"><div class="login-card">', unsafe_allow_html=True)
    st.image("logo.jpg", width=120)
    st.markdown('<div class="login-title">Welcome to ProMedic+</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-sub">Sign in to continue</div>', unsafe_allow_html=True)

    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    col1, col2 = st.columns(2, gap="small")
    with col1:
        if st.button("Sign In", key="signin_btn", use_container_width=True):
            if username == "admin" and password == "admin":
                st.session_state["authenticated"] = True
                st.session_state["user"] = username
                st.success("Signed in successfully.")
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with col2:
        if st.button("Create Account", key="create_account_btn", use_container_width=True):
            st.success("Account creation UI is ready. This demo does not store credentials.")

    st.markdown("</div></div>", unsafe_allow_html=True)

def render_home() -> None:
    st.image("logo.jpg", width=200)
    st.markdown('<p class="header">Welcome to ProMedic+</p>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="subheader">{TAGLINE}</p>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2, gap="large")
    with col1:
        render_feature_card(
            "Prescription OCR",
            "Scan and process prescriptions in English.",
            "Open",
            "card_ocr",
            target="Prescription OCR",
        )
        render_feature_card(
            "Document Assistant",
            "Upload documents and ask questions about them in English.",
            "Open",
            "card_docs",
            target="Document Assistant",
        )

    with col2:
        render_feature_card(
            "Health Chat",
            "Ask health questions and get responses in English only.",
            "Open",
            "card_chat",
            target="Health Chat",
        )
        render_feature_card(
            "Nutrition Assistant",
            "Personalized dietary guidance and nutritional insights based on patient data.",
            "Coming Soon",
            "card_nutrition",
            target="Nutrition Assistant",
        )

    st.markdown(
        """
        <footer style="text-align:center; margin-top: 48px; color: var(--muted);">
            <p>&copy; 2026 ProMedic+</p>
        </footer>
        """,
        unsafe_allow_html=True,
    )


def render_nutrition_placeholder() -> None:
    st.image("logo.jpg", width=170)
    st.markdown(
        """
        <div class="centered">
            <h2>🚧 Nutrition Assistant is an upcoming feature.</h2>
            <p>This module will provide personalized diet and nutrition recommendations.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    init_ui_state()

    theme = st.sidebar.radio("Theme", ["Light", "Dark"], key="theme", horizontal=True)
    apply_theme_styles(theme)

    if not st.session_state["authenticated"]:
        show_login_page()
        st.stop()

    st.sidebar.image("logo.jpg", width=120)
    st.sidebar.title(APP_NAME)
    st.sidebar.caption(TAGLINE)
    st.sidebar.markdown(f"👤 {st.session_state['user']}")

    if st.sidebar.button("Logout"):
        st.session_state["authenticated"] = False
        st.session_state["user"] = None
        st.rerun()

    selected = st.sidebar.radio(
        "Navigation",
        ["Home", "Prescription OCR", "Health Chat", "Document Assistant", "Nutrition Assistant"],
        key="nav",
    )

    if selected == "Home":
        render_home()
    elif selected == "Prescription OCR":
        try:
            from ocr import run_ocr
            run_ocr()
        except Exception as exc:
            st.error(f"Unable to load Prescription OCR: {exc}")
    elif selected == "Health Chat":
        try:
            from app_chainlit import run_chat
            run_chat()
        except Exception as exc:
            st.error(f"Unable to load Health Chat: {exc}")
    elif selected == "Document Assistant":
        try:
            from app_streamlit import run_documents
            run_documents()
        except Exception as exc:
            st.error(f"Unable to load Document Assistant: {exc}")
    elif selected == "Nutrition Assistant":
        render_nutrition_placeholder()


if __name__ == "__main__":
    main()

