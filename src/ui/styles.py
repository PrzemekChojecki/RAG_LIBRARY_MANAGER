import streamlit as st

def apply_custom_styles():
    """Applies custom CSS to the Streamlit app for a premium UI/UX look."""
    
    st.markdown("""
        <style>
        /* Import Inter Font */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        :root {
            --primary-color: #7C3AED;
            --primary-hover: #6D28D9;
            --bg-color: #0F172A;
            --secondary-bg: #1E293B;
            --text-color: #F8FAFC;
            --text-muted: #94A3B8;
            --glass-bg: rgba(30, 41, 59, 0.7);
            --glass-border: rgba(255, 255, 255, 0.1);
        }

        html, body, .stMarkdown, .stText, .stButton, .stTextInput, .stSelectbox, .stNumberInput, .stTabs, .stExpanderBody {
            font-family: 'Inter', sans-serif !important;
        }

        /* Prevent Inter from breaking icons */
        .st-emotion-cache-1vt458o, .st-ae, .st-af, [data-testid="stIcon"] {
            font-family: inherit !important;
        }

        /* Header & Decoration Styling */
        [data-testid="stHeader"], .stDecoration {
            background: transparent !important;
            height: 0px !important;
        }

        /* Glassmorphism Containers */
        .stApp {
            background-color: var(--bg-color);
            background-image: 
                radial-gradient(at 0% 0%, rgba(124, 58, 237, 0.15) 0, transparent 50%), 
                radial-gradient(at 50% 0%, rgba(14, 165, 233, 0.1) 0, transparent 50%);
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: var(--secondary-bg);
            border-right: 1px solid var(--glass-border);
        }

        /* Card-like containers (e.g. Expanders, Tabs) */
        .stExpander {
            background: var(--glass-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border) !important;
            border-radius: 12px !important;
            overflow: hidden;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }

        .stExpander > details > summary {
            padding: 10px 15px !important;
            border-radius: 12px !important;
            transition: background 0.3s ease;
        }

        .stExpander > details > summary:hover {
            background: rgba(255, 255, 255, 0.05);
        }

        .stTabs {
            background: var(--glass-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border);
            border-radius: 12px !important;
            padding: 10px;
            margin-bottom: 20px;
        }

        /* Tab labels */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            padding: 10px;
        }

        .stTabs [data-baseweb="tab"] {
            background-color: transparent;
            border-radius: 8px;
            padding: 12px 24px;
            color: var(--text-muted);
            transition: all 0.3s ease;
            font-size: 1.5rem !important; /* Increased font size */
            font-weight: 600 !important;
        }

        .stTabs [data-baseweb="tab"]:hover {
            background-color: rgba(255, 255, 255, 0.05);
            color: var(--text-color);
        }

        .stTabs [aria-selected="true"] {
            background-color: var(--primary-color) !important;
            color: white !important;
        }

        /* Buttons */
        .stButton > button {
            border-radius: 8px !important;
            font-weight: 500 !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            border: 1px solid var(--glass-border) !important;
            text-transform: none !important;
        }

        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            background-color: var(--primary-color) !important;
            color: white !important;
            border-color: var(--primary-color) !important;
        }

        /* Chat Message Styling */
        .stChatMessage {
            background: transparent !important;
            margin-bottom: 1.5rem !important;
        }

        .stChatMessage [data-testid="stChatMessageContent"] {
            background: var(--glass-bg) !important;
            backdrop-filter: blur(8px) !important;
            border: 1px solid var(--glass-border) !important;
            border-radius: 16px !important;
            padding: 1rem 1.25rem !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
        }

        /* Specific style for user messages */
        [data-testid="stChatMessage"][data-test-role="user"] [data-testid="stChatMessageContent"] {
            border-left: 4px solid var(--primary-color) !important;
        }

        /* Specific style for assistant messages */
        [data-testid="stChatMessage"][data-test-role="assistant"] [data-testid="stChatMessageContent"] {
            border-left: 4px solid #10B981 !important; /* Green for assistant */
        }

        /* Source expander styling */
        .stChatMessage .stExpander {
            margin-top: 10px;
            background: rgba(0, 0, 0, 0.2) !important;
            border: none !important;
        }

        /* Progress bars */
        .stProgress > div > div > div {
            background-image: linear-gradient(90deg, #7C3AED, #3B82F6) !important;
        }

        /* Input fields */
        .stTextInput input, .stSelectbox select, .stNumberInput input {
            background-color: rgba(0, 0, 0, 0.2) !important;
            border: 1px solid var(--glass-border) !important;
            border-radius: 8px !important;
            color: var(--text-color) !important;
        }

        /* Tooltips/Select labels */
        label {
            color: var(--text-muted) !important;
            font-size: 0.875rem !important;
            font-weight: 500 !important;
        }
    </style>
    """, unsafe_allow_html=True)

def render_styled_sources(sources):
    """Renders sources using a cleaner, more visual layout."""
    if not sources:
        return
    
    with st.expander("🔍 View Sources", expanded=False):
        for i, s in enumerate(sources):
            score_val = s.get('score', 0)
            st.markdown(f"""
                <div style="
                    background: rgba(255, 255, 255, 0.03);
                    border-left: 3px solid var(--primary-color);
                    padding: 12px;
                    border-radius: 8px;
                    margin-bottom: 12px;
                ">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span style="font-weight: 600; color: #F8FAFC;"># {i+1} | {s['doc_name']}</span>
                        <span style="font-size: 0.8rem; background: rgba(124, 58, 237, 0.2); color: #C084FC; padding: 2px 8px; border-radius: 12px;">Score: {score_val:.4f}</span>
                    </div>
                    {f'<div style="font-style: italic; font-size: 0.9rem; color: #94A3B8; margin-bottom: 8px;">{s["summary"]}</div>' if s.get('summary') else ''}
                </div>
            """, unsafe_allow_html=True)
            with st.container():
                st.code(s['text'], language="markdown")
