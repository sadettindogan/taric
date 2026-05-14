import streamlit as st
from playwright.sync_api import sync_playwright
import json, os, time, traceback

# ─── YARDIMCI FONKSİYONLAR ───────────────────────────────────────────────────
@st.cache_data
def ulke_listesi_yukle():
    json_yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ulkeler.json")
    if os.path.exists(json_yol):
        with open(json_yol, encoding="utf-8") as f:
            return json.load(f)
    return {}

ULKELER = ulke_listesi_yukle()

def ulke_cevir(girdi):
    girdi = girdi.strip()
    if not girdi:
        return ""

    if len(girdi) <= 3 and girdi.isalpha():
        return girdi.upper()

    anahtar = girdi.upper()

    if anahtar in ULKELER:
        return ULKELER[anahtar]

    for k, v in ULKELER.items():
        if k.startswith(anahtar):
            return v

    return girdi.upper()

def gtip_cevir(girdi):
    temiz = str(girdi).replace(".", "").replace(" ", "").strip()

    if len(temiz) == 12:
        temiz = temiz[:-1]

    return temiz

def parse_yapistir(ham):
    ham = ham.strip()

    if "\t" in ham:
        return [p.strip() for p in ham.split("\t") if p.strip()]
    else:
        return [p.strip() for p in ham.splitlines() if p.strip()]

# ─── TARIC SORGUSU ────────────────────────────────────────────────────────────
def taric_sorgula(gtip, ulke, tarih):

    try:
        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )

            context = browser.new_context(
                viewport={"width": 1400, "height": 900}
            )

            page = context.new_page()

            url = "https://ec.europa.eu/taxation_customs/dds2/taric/taric_consultation.jsp?Lang=en"

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            # inputlar yüklenene kadar bekle
            page.wait_for_selector("#taricCode", timeout=30000)

            # GTIP
            page.fill("#taricCode", gtip.strip())

            # ÜLKE
            if ulke.strip():
                try:
                    page.select_option("#taricArea", ulke.strip())
                except:
                    pass

            # TARİH
            if tarih.strip():
                try:
                    page.evaluate(
                        """
                        (t) => {
                            let el = document.querySelector('#SimDatePic');
                            if(el){
                                el.value = t;
                            }
                        }
                        """,
                        tarih.strip()
                    )
                except:
                    pass

            # buton
            try:
                page.locator("text=Search").click(timeout=10000)
            except:
                page.get_by_role("button").click(timeout=10000)

            # sonuç bekle
            page.wait_for_load_state("domcontentloaded", timeout=30000)

            time.sleep(3)

            html_content = page.content()

            pdf_bytes = page.pdf(
                format="A4",
                print_background=True
            )

            browser.close()

            return html_content, pdf_bytes, None

    except Exception:
        return None, None, traceback.format_exc()

# ─── HTML TEMİZLE ─────────────────────────────────────────────────────────────
def html_temizle(html):

    ek = """
    <base href="https://ec.europa.eu" target="_blank">

    <style>
    body{
        font-size:15px!important;
        line-height:1.7!important;
        font-family:Arial,sans-serif!important;
    }

    table{
        font-size:14px!important;
    }

    td,th{
        padding:6px 10px!important;
    }
    </style>
    """

    if "<head>" in html:
        return html.replace("<head>", "<head>" + ek, 1)

    return ek + html

# ─── SAYFA AYARI ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TARIC Sorgu",
    page_icon="🛃",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>

html,body,[data-testid="stAppViewContainer"]{
    background:#f5f3ef;
    font-family:Arial,sans-serif;
}

.block-container{
    padding:12px 16px!important;
    max-width:100%!important;
}

.stButton>button{
    border-radius:6px!important;
    font-weight:700!important;
}

</style>
""", unsafe_allow_html=True)

# ─── SESSION ──────────────────────────────────────────────────────────────────
defaults = {
    "page_html": None,
    "pdf_bytes": None,
    "durum": "",
    "sorgulandı": False,
    "gtip_son": "",
    "ulke_son": "",
    "tarih_son": "",
    "gtip_kirp": ""
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── LAYOUT ───────────────────────────────────────────────────────────────────
sol, sag = st.columns([0.5, 2.5], gap="medium")

with sol:

    st.title("🛃 TARIC")

    yapistir = st.text_area(
        "Excel'den Yapıştır",
        placeholder="72.07.11.14.00.00\tRUSYA\t01.01.2024",
        height=120
    )

    gtip_hazir = ""
    ulke_hazir = ""
    tarih_hazir = ""

    if yapistir.strip():

        parcalar = parse_yapistir(yapistir)

        if len(parcalar) >= 3:

            gtip_ham = parcalar[0]
            ulke_ham = parcalar[1]
            tarih_ham = parcalar[2]

            gtip_hazir = (
                st.session_state.gtip_kirp
                if st.session_state.gtip_kirp
                else gtip_cevir(gtip_ham)
            )

            ulke_hazir = ulke_cevir(ulke_ham)

            tarih_hazir = (
                tarih_ham
                .replace(".", "-")
                .replace("/", "-")
            )

            st.success(
                f"{gtip_hazir} / {ulke_hazir} / {tarih_hazir}"
            )

        else:
            st.warning("GTIP + Ülke + Tarih girin")

    sorgula = st.button(
        "🔍 SORGULA",
        use_container_width=True
    )

    if st.session_state.pdf_bytes:

        st.download_button(
            "📄 PDF İndir",
            st.session_state.pdf_bytes,
            file_name=f"TARIC_{st.session_state.gtip_son}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    if st.session_state.sorgulandı:

        kirp = st.button(
            "✂️ Sondan 1 Rakam Sil",
            use_container_width=True
        )
    else:
        kirp = False

    temizle = st.button(
        "✕ Temizle",
        use_container_width=True
    )

# ─── SORGULA ─────────────────────────────────────────────────────────────────
if sorgula:

    if not gtip_hazir:
        st.error("Önce veri girin")

    else:

        with sag:

            with st.spinner("Sorgulanıyor..."):

                html_content, pdf_bytes, hata = taric_sorgula(
                    gtip_hazir,
                    ulke_hazir,
                    tarih_hazir
                )

            if hata:

                st.code(hata)

            else:

                st.session_state.page_html = html_temizle(html_content)
                st.session_state.pdf_bytes = pdf_bytes
                st.session_state.sorgulandı = True
                st.session_state.gtip_son = gtip_hazir
                st.session_state.ulke_son = ulke_hazir
                st.session_state.tarih_son = tarih_hazir
                st.session_state.gtip_kirp = ""
                st.session_state.durum = f"✅ {gtip_hazir}"

                st.rerun()

# ─── KIRP ─────────────────────────────────────────────────────────────────────
if kirp:

    mevcut = st.session_state.gtip_son

    if len(mevcut) > 4:

        yeni = mevcut[:-1]

        st.session_state.gtip_kirp = yeni

        with sag:

            with st.spinner("Tekrar sorgulanıyor..."):

                html_content, pdf_bytes, hata = taric_sorgula(
                    yeni,
                    st.session_state.ulke_son,
                    st.session_state.tarih_son
                )

            if hata:
                st.code(hata)

            else:

                st.session_state.page_html = html_temizle(html_content)
                st.session_state.pdf_bytes = pdf_bytes
                st.session_state.gtip_son = yeni
                st.session_state.durum = f"✅ {yeni}"

        st.rerun()

# ─── TEMİZLE ──────────────────────────────────────────────────────────────────
if temizle:

    for k in defaults.keys():

        if k == "sorgulandı":
            st.session_state[k] = False

        elif k in ["page_html", "pdf_bytes"]:
            st.session_state[k] = None

        else:
            st.session_state[k] = ""

    st.rerun()

# ─── SAĞ PANEL ────────────────────────────────────────────────────────────────
with sag:

    if st.session_state.page_html:

        st.markdown(f"""
        <div style='
            background:#111;
            color:#c8b560;
            padding:10px 14px;
            border-radius:8px 8px 0 0;
            font-weight:700;
        '>
            🛃 {st.session_state.gtip_son} / {st.session_state.ulke_son}
        </div>
        """, unsafe_allow_html=True)

        st.components.v1.html(
            st.session_state.page_html,
            height=850,
            scrolling=True
        )

    else:

        st.info(
            "GTIP / Ülke / Tarih girip sorgulama yapın."
        )
