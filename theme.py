import streamlit as st

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@600;700;800&family=Poppins:wght@400;500;600;700;800&display=swap');

:root {
    --brutal-black: #2A140D;
    --brutal-coral: #FF9288;
    --brutal-peach: #FFB89C;
    --brutal-apricot: #FFD6A0;
    --brutal-cream: #FFF0BE;
    --brutal-dark: #4A2318;
    --brutal-dark-2: #5C2E1F;
}

.stApp {
    background: linear-gradient(135deg, #FF9288 0%, #FFB89C 35%, #FFD6A0 68%, #FFF0BE 100%);
}

header[data-testid="stHeader"] {
    background: transparent;
}

html, body, [class*="css"] {
    font-family: 'Poppins', sans-serif;
}

/* ===== JUDUL (coklat tua solid, tanpa perlu putih - kontras terverifikasi >=6:1 di semua pastel) ===== */
.brutal-title {
    font-family: 'Baloo 2', sans-serif;
    font-weight: 800;
    font-size: 2.4rem;
    line-height: 1.05;
    color: var(--brutal-dark);
    text-shadow: 3px 3px 0px rgba(42,20,13,0.25);
    margin-bottom: 0.3rem;
}
.brutal-title .accent {
    display: inline-block;
    background: var(--brutal-dark);
    color: var(--brutal-cream);
    padding: 2px 12px;
    border-radius: 8px;
    text-shadow: none;
}
.brutal-subtitle {
    font-family: 'Baloo 2', sans-serif;
    font-weight: 700;
    font-size: 1.3rem;
    color: var(--brutal-cream);
    line-height: 1.15;
}
.brutal-subtitle .accent {
    color: var(--brutal-coral);
}

.brutal-badge {
    display: inline-block;
    background: var(--brutal-dark);
    border: 3px solid var(--brutal-black);
    border-radius: 10px;
    padding: 5px 14px;
    font-family: 'Poppins', sans-serif;
    font-weight: 700;
    font-size: 0.8rem;
    color: var(--brutal-cream);
    box-shadow: 4px 4px 0 var(--brutal-black);
    margin: 0.3rem 0 1rem 0;
}

/* ===== KARTU FORM (APRICOT, BORDER TEBAL, TEKSTUR DOT) ===== */
div[data-testid="stForm"] {
    background-color: var(--brutal-apricot);
    background-image: radial-gradient(rgba(42,20,13,0.12) 1.5px, transparent 1.5px);
    background-size: 14px 14px;
    border: 4px solid var(--brutal-black);
    border-radius: 20px;
    padding: 1.6rem 1.6rem 1.2rem 1.6rem;
    box-shadow: 10px 10px 0px var(--brutal-black);
}
div[data-testid="stForm"] label p {
    font-family: 'Poppins', sans-serif;
    font-weight: 700;
    color: var(--brutal-dark);
    font-size: 0.85rem;
}

/* ===== SELECTBOX GAYA PIL COKLAT TUA ===== */
div[data-baseweb="select"] > div {
    background-color: var(--brutal-dark) !important;
    border: 2px solid var(--brutal-black) !important;
    border-radius: 10px !important;
    color: var(--brutal-cream) !important;
}
div[data-baseweb="select"] span, div[data-baseweb="select"] div {
    color: var(--brutal-cream) !important;
    font-weight: 600;
}

/* ===== RADIO GAYA PIL ===== */
div[data-testid="stRadio"] > div[role="radiogroup"] {
    gap: 10px;
}
div[data-testid="stRadio"] label {
    background: var(--brutal-cream);
    border: 2.5px solid var(--brutal-black);
    border-radius: 999px;
    padding: 6px 18px 6px 10px !important;
    box-shadow: 3px 3px 0 var(--brutal-black);
    margin-bottom: 4px;
}
div[data-testid="stRadio"] label p {
    font-family: 'Poppins', sans-serif;
    font-weight: 700;
    color: var(--brutal-dark);
    font-size: 0.9rem;
}

/* ===== TOMBOL UTAMA (COKLAT TUA, PIL) ===== */
div[data-testid="stFormSubmitButton"] button,
div[data-testid="stButton"] button,
div[data-testid="stDownloadButton"] button {
    background-color: var(--brutal-dark) !important;
    color: var(--brutal-cream) !important;
    border: 3px solid var(--brutal-black) !important;
    border-radius: 999px !important;
    font-family: 'Poppins', sans-serif;
    font-weight: 800 !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    box-shadow: 5px 5px 0px var(--brutal-black) !important;
    padding: 0.6rem 1.4rem !important;
    transition: transform 0.05s ease, box-shadow 0.05s ease;
}
div[data-testid="stFormSubmitButton"] button:hover,
div[data-testid="stButton"] button:hover,
div[data-testid="stDownloadButton"] button:hover {
    transform: translate(2px, 2px);
    box-shadow: 3px 3px 0px var(--brutal-black) !important;
    color: var(--brutal-cream) !important;
}

/* ===== METRIC CARD ===== */
div[data-testid="stMetric"] {
    background: var(--brutal-cream);
    border: 3px solid var(--brutal-black);
    border-radius: 16px;
    padding: 0.8rem 1rem;
    box-shadow: 6px 6px 0px var(--brutal-black);
}
div[data-testid="stMetricLabel"] p {
    font-weight: 700 !important;
    color: var(--brutal-dark) !important;
}
div[data-testid="stMetricValue"] {
    color: var(--brutal-black) !important;
}

/* ===== DATAFRAME / TABEL ===== */
div[data-testid="stDataFrame"] {
    border: 3px solid var(--brutal-black);
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 6px 6px 0px var(--brutal-black);
}

/* ===== SIDEBAR ===== */
section[data-testid="stSidebar"] {
    background: var(--brutal-dark);
    border-right: 4px solid var(--brutal-black);
}
section[data-testid="stSidebar"] * {
    color: var(--brutal-cream) !important;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label {
    background: var(--brutal-dark-2);
    border: 2px solid var(--brutal-black);
    border-radius: 12px;
    padding: 8px 12px !important;
    margin-bottom: 6px;
    box-shadow: 3px 3px 0 var(--brutal-black);
}

/* ===== INPUT LAIN (text/number/date/textarea) ===== */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stDateInput"] input,
div[data-testid="stTextArea"] textarea {
    background-color: var(--brutal-dark) !important;
    color: var(--brutal-cream) !important;
    border: 2px solid var(--brutal-black) !important;
    border-radius: 10px !important;
    font-weight: 600;
}

/* ===== EXPANDER ===== */
div[data-testid="stExpander"] {
    border: 3px solid var(--brutal-black) !important;
    border-radius: 14px !important;
    background: rgba(255,240,190,0.92) !important;
}

/* ===== TABS ===== */
button[data-baseweb="tab"] p {
    font-family: 'Poppins', sans-serif;
    font-weight: 700 !important;
    color: var(--brutal-cream) !important;
}
div[data-baseweb="tab-list"] {
    gap: 6px;
}
button[data-baseweb="tab"] {
    background: var(--brutal-dark);
    border: 2px solid var(--brutal-black);
    border-radius: 10px 10px 0 0 !important;
}
button[aria-selected="true"][data-baseweb="tab"] {
    background: var(--brutal-apricot) !important;
}
button[aria-selected="true"][data-baseweb="tab"] p {
    color: var(--brutal-dark) !important;
}

/* ===== DIVIDER PUTUS-PUTUS ===== */
.brutal-divider {
    border: none;
    border-top: 3px dashed rgba(42,20,13,0.5);
    margin: 1.4rem 0;
}

/* ===== INFO/CAPTION BOX ===== */
.brutal-infobox {
    background: var(--brutal-dark);
    border: 3px solid var(--brutal-black);
    border-radius: 14px;
    padding: 0.8rem 1rem;
    color: var(--brutal-cream);
    font-weight: 500;
}

/* Alert bawaan Streamlit (info/success/warning/error) dibuat senada */
div[data-testid="stAlert"] {
    border: 3px solid var(--brutal-black) !important;
    border-radius: 14px !important;
    box-shadow: 5px 5px 0px var(--brutal-black) !important;
}

/* ===================================================================
   FIX KONTRAS TEKS
   Beberapa elemen (label metric, teks expander, subheader) sebelumnya
   ikut warna teks default tema (terang) sehingga nyaris tak terbaca di
   atas kartu krem/peach atau gradient. Di sini warnanya dipaksa gelap,
   plus efek outline krem tipis untuk teks yang duduk langsung di atas
   gradient (bukan di dalam kartu solid).
   =================================================================== */

/* Warna teks default di area utama (di luar sidebar) -> coklat tua */
.stApp {
    color: var(--brutal-dark);
}

/* Semua heading (title, subheader, header bawaan Streamlit) */
h1, h2, h3, h4, h5, h6 {
    color: var(--brutal-dark) !important;
    text-shadow:
        -1px -1px 0 var(--brutal-cream),
         1px -1px 0 var(--brutal-cream),
        -1px  1px 0 var(--brutal-cream),
         1px  1px 0 var(--brutal-cream);
}

/* Label & angka pada kartu metric (mis. "Saldo Kas Umum") */
div[data-testid="stMetric"],
div[data-testid="stMetric"] * {
    color: var(--brutal-dark) !important;
}
div[data-testid="stMetricValue"],
div[data-testid="stMetricValue"] * {
    color: var(--brutal-black) !important;
    font-weight: 800 !important;
}

/* Judul expander (mis. "Lihat rincian pemasukan & pengeluaran per kas") */
div[data-testid="stExpander"] summary,
div[data-testid="stExpander"] summary * {
    color: var(--brutal-dark) !important;
    font-weight: 700 !important;
}

/* Caption & teks bantu (st.caption) di area utama */
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] * {
    color: var(--brutal-dark-2) !important;
}

/* Teks label widget umum (radio/selectbox/dsb di luar sidebar) */
.stApp [data-testid="stWidgetLabel"] p {
    color: var(--brutal-dark) !important;
    font-weight: 600;
}
</style>
"""


def inject():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_title(main_text: str, accent_text: str = None):
    html = f'<div class="brutal-title">{main_text}'
    if accent_text:
        html += f' <span class="accent">{accent_text}</span>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_sidebar_title(main_text: str, accent_text: str, badge_text: str = None):
    html = f'<div class="brutal-subtitle">{main_text}<br><span class="accent">{accent_text}</span></div>'
    st.markdown(html, unsafe_allow_html=True)
    if badge_text:
        st.markdown(f'<div class="brutal-badge">{badge_text}</div>', unsafe_allow_html=True)


def divider():
    st.markdown('<hr class="brutal-divider">', unsafe_allow_html=True)


def infobox(text: str):
    st.markdown(f'<div class="brutal-infobox">{text}</div>', unsafe_allow_html=True)
