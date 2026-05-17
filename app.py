import streamlit as st
from playwright.sync_api import sync_playwright
import time, re, json, os

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
    if not girdi: return ""
    if len(girdi) <= 3 and girdi.isalpha(): return girdi.upper()
    anahtar = girdi.upper()
    if anahtar in ULKELER: return ULKELER[anahtar]
    for k, v in ULKELER.items():
        if k.startswith(anahtar): return v
    return girdi.upper()

def gtip_cevir(girdi):
    temiz = str(girdi).replace(".", "").replace(" ", "").strip()
    if len(temiz) == 12:
        temiz = temiz[:-1]
    return temiz

def tarih_cevir(girdi):
    girdi = girdi.strip()
    p = re.split(r'[.\-/]', girdi)
    if len(p) == 3:
        return f"{p[0].zfill(2)}-{p[1].zfill(2)}-{p[2]}"
    return girdi

def satirlari_parse_et(ham):
    ham = ham.strip()
    sonuc = []
    tarih_re = re.compile(r'\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}')
    for satir in ham.splitlines():
        satir = satir.strip()
        if not satir: continue
        if "\t" in satir:
            p = [x.strip() for x in satir.split("\t") if x.strip()]
            if len(p) >= 3:
                sonuc.append(p[:3])
        else:
            m = tarih_re.search(satir)
            if m:
                kalan = satir[:m.start()].strip()
                gm = re.match(r'[\d.]+', kalan)
                if gm:
                    sonuc.append([kalan[:gm.end()].strip(), kalan[gm.end():].strip(), m.group()])
    return [{
        "gtip": gtip_cevir(p[0]), "ulke": ulke_cevir(p[1]), "tarih": tarih_cevir(p[2]),
    } for p in sonuc if len(p) >= 3]

def html_temizle(html):
    html = re.sub(r'<meta[^>]*(x-frame-options|content-security-policy)[^>]*>', '', html, flags=re.IGNORECASE)
    ek = ('<base href="https://ec.europa.eu" target="_self">'
          '<style>body{font-size:15px!important;line-height:1.7!important;font-family:Arial,sans-serif!important}'
          'table{font-size:14px!important}td,th{padding:6px 10px!important}</style>')
    return html.replace("<head>", "<head>" + ek, 1) if "<head>" in html else ek + html

FORM_URL = "https://ec.europa.eu/taxation_customs/dds2/taric/taric_consultation.jsp?Lang=en"

@st.cache_resource
def get_browser():
    pw      = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=True,
        executable_path="/usr/bin/chromium",
        args=["--no-sandbox", "--disable-dev-shm-usage"]
    )
    ctx  = browser.new_context()
    page = ctx.new_page()
    page.goto(FORM_URL, wait_until="domcontentloaded")
    page.wait_for_selector("#taricCode", timeout=10000)
    return pw, browser, page

# ─── SAYFA KONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="TARIC Sorgu", page_icon="🛃", layout="wide")
st.markdown("""
<style>
html,body,[data-testid="stAppViewContainer"]{background:#f5f3ef;}
section[data-testid="stSidebar"]{display:none;}
header{display:none!important;}
.block-container{padding:12px 16px!important;max-width:100%!important;}
[data-testid="stTextInput"] input{
    border:1px solid #d4c97a!important;border-radius:4px!important;
    font-family:monospace!important;font-size:13px!important;font-weight:700!important;padding:7px 10px!important;
}
[data-testid="stTextArea"] textarea{
    border:1px solid #9ca3af!important;border-radius:4px!important;
    font-family:monospace!important;font-size:10px!important;padding:8px 10px!important;
    white-space:pre!important;overflow-x:auto!important;tab-size:16!important;
}
.stButton>button{font-weight:700!important;border-radius:4px!important;padding:9px 0!important;width:100%!important;border:none!important;}
.btn-s  .stButton>button{background:#1d4ed8!important;color:white!important;font-size:14px!important;padding:13px 0!important;}
.btn-p  .stButton>button{background:#16a34a!important;color:white!important;}
.btn-p65.stButton>button{background:#0891b2!important;color:white!important;}
.btn-d  .stButton>button{background:#d97706!important;color:white!important;}
.btn-r  .stButton>button{background:#e5e7eb!important;color:#6b7280!important;}
.btn-web .stButton>button{background:#7c3aed!important;color:white!important;font-size:13px!important;}
.kart{background:white;border:1px solid #e5e7eb;border-radius:5px;padding:5px 10px;margin-bottom:3px;font-family:monospace;font-size:11px;}
.aktif{border-color:#1d4ed8!important;background:#eff6ff!important;font-weight:700;color:#1d4ed8!important;}
.tamam{opacity:0.4;}
.prog{background:#e5e7eb;border-radius:8px;height:5px;overflow:hidden;margin:3px 0 10px;}
.prog-bar{background:linear-gradient(90deg,#1d4ed8,#7c3aed);height:100%;}
hr{border-color:#e0ddd5!important;margin:8px 0!important;}

/* Web paneli */
.web-panel-baslik{
    background:#1a1a1a;border-radius:6px 6px 0 0;
    padding:8px 14px;font-family:monospace;font-size:12px;
    color:#c8b560;font-weight:700;display:flex;align-items:center;gap:8px;
}
.web-panel-bar{
    background:#e8e6e1;border-radius:0;
    padding:6px 10px;font-family:monospace;font-size:11px;
    color:#555;border-bottom:1px solid #d0ccc4;
    display:flex;align-items:center;gap:6px;
}
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ─────────────────────────────────────────────────────────────
for k, v in {
    "kuyruk": [], "idx": 0,
    "html": None, "pdf": None, "pdf65": None,
    "pdf_n": 0, "ver": 0, "hata": "", "sure": "",
    "tetik": False, "tgtip": "", "tulke": "", "ttarih": "",
    "sonuc_url": "",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

def av():
    i = st.session_state.idx
    if st.session_state.kuyruk and i < len(st.session_state.kuyruk):
        return st.session_state.kuyruk[i]
    return {"gtip": "", "ulke": "", "tarih": ""}

def temizle():
    st.session_state.html      = None
    st.session_state.pdf       = None
    st.session_state.pdf65     = None
    st.session_state.sonuc_url = ""

# ─── SORGU ────────────────────────────────────────────────────────────────────
if st.session_state.tetik:
    st.session_state.tetik = False
    gtip  = st.session_state.tgtip
    ulke  = st.session_state.tulke
    tarih = st.session_state.ttarih
    durum = st.empty()
    t0    = time.time()

    try:
        try:
            _, _, page = get_browser()
            page.title()
        except Exception:
            get_browser.clear()
            _, _, page = get_browser()

        t1 = time.time()

        durum.info("✏️ Form dolduruluyor...")
        try:
            page.wait_for_selector("#taricCode", timeout=3000)
        except:
            page.goto(FORM_URL, wait_until="domcontentloaded")
            page.wait_for_selector("#taricCode", timeout=10000)

        page.fill("#taricCode", "")
        page.fill("#taricCode", gtip)
        if ulke:
            try: page.select_option("#taricArea", ulke)
            except: pass
        if tarih:
            page.evaluate("(t) => { document.querySelector('#SimDatePic').value = t; }", tarih)

        durum.info("🔍 Sorgulanıyor...")
        page.click("button[value='Retrieve Measures']")
        page.wait_for_selector("h1", timeout=15000)
        t2 = time.time()

        durum.info("📄 PDF alınıyor...")

        # Sonuç URL'sini kaydet
        st.session_state.sonuc_url = page.url

        html  = page.content()
        pdf   = page.pdf(format="A4", print_background=True, scale=1.0)
        pdf65 = page.pdf(format="A4", print_background=True, scale=0.65)
        t3 = time.time()

        st.session_state.html  = html_temizle(html)
        st.session_state.pdf   = pdf
        st.session_state.pdf65 = pdf65
        st.session_state.hata  = ""
        st.session_state.sure  = f"hazırlık:{t1-t0:.1f}s | sorgu:{t2-t1:.1f}s | pdf:{t3-t2:.1f}s | toplam:{t3-t0:.1f}s"
        durum.success(f"✅ {t3-t0:.1f}s")

    except Exception as e:
        st.session_state.hata = str(e)
        durum.error(f"❌ {e}")
        get_browser.clear()

# ─── LAYOUT: 3 KOLON (sol panel | iframe | web sayfası) ───────────────────────
sol, orta, sag = st.columns([0.65, 1.5, 1.5], gap="small")

# ══════════════════════════════════════════════════════
# SOL PANEL
# ══════════════════════════════════════════════════════
with sol:
    st.markdown("<div style='font-size:22px;font-weight:800;padding-bottom:10px;border-bottom:2px solid #c8b560;margin-bottom:12px;'>🛃 TARIC</div>", unsafe_allow_html=True)

    with st.expander("📋 Excel'den kopyala yapıştır", expanded=not st.session_state.kuyruk):
        t = st.text_area("", height=100, key="txt",
            placeholder="72.07.11.14.00.00\tRusya\t1.01.2024",
            label_visibility="collapsed")
        rows = satirlari_parse_et(t) if t.strip() else []
        if rows:
            st.markdown(f"<div style='font-size:11px;color:#166534;font-weight:700;'>✅ {len(rows)} satır</div>", unsafe_allow_html=True)
        if st.button("📥 Kuyruğa Yükle", use_container_width=True, disabled=not rows):
            st.session_state.kuyruk = rows
            st.session_state.idx    = 0
            st.session_state.pdf_n  = 0
            st.session_state.ver   += 1
            temizle()
            st.rerun()

    if st.session_state.kuyruk:
        total = len(st.session_state.kuyruk)
        i     = st.session_state.idx
        pct   = min(int(i/total*100), 100)
        st.markdown(f"<div style='font-size:11px;color:#6b7280;font-family:monospace;'>{min(i,total)}/{total} · {pct}% · 📄{st.session_state.pdf_n}</div><div class='prog'><div class='prog-bar' style='width:{pct}%'></div></div>", unsafe_allow_html=True)

    a = av()
    v = st.session_state.ver
    st.markdown("<div style='font-size:10px;color:#555;font-weight:700;margin-bottom:2px;'>SORGULANACAK VERİ</div>", unsafe_allow_html=True)
    g = st.text_input("GTİP",  value=a["gtip"],  key=f"g_{v}")
    u = st.text_input("Ülke",  value=a["ulke"],  key=f"u_{v}")
    d = st.text_input("Tarih", value=a["tarih"], key=f"d_{v}")

    if st.session_state.hata:
        st.error(f"❌ {st.session_state.hata}")
    if st.session_state.sure:
        st.caption(f"⏱ {st.session_state.sure}")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    st.markdown("<div class='btn-s'>", unsafe_allow_html=True)
    if st.button("🔍  Sorgula", use_container_width=True):
        st.session_state.tetik  = True
        st.session_state.tgtip  = gtip_cevir(g)
        st.session_state.tulke  = ulke_cevir(u)
        st.session_state.ttarih = tarih_cevir(d)
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    i       = st.session_state.idx
    dosya   = f"{i+1}_{g}_{u}.pdf"
    dosya65 = f"{i+1}_{g}_{u}_65.pdf"
    var_p   = bool(st.session_state.pdf)
    var_p65 = bool(st.session_state.pdf65)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("<div class='btn-p'>", unsafe_allow_html=True)
        if st.download_button("📄 PDF", data=st.session_state.pdf or b"",
                file_name=dosya, mime="application/pdf",
                use_container_width=True, disabled=not var_p, key="dp"):
            st.session_state.pdf_n += 1
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='btn-p65'>", unsafe_allow_html=True)
        if st.download_button("📄 PDF%65", data=st.session_state.pdf65 or b"",
                file_name=dosya65, mime="application/pdf",
                use_container_width=True, disabled=not var_p65, key="dp65"):
            st.session_state.pdf_n += 1
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div class='btn-d'>", unsafe_allow_html=True)
        if st.button("⏭️", use_container_width=True, disabled=not var_p):
            st.session_state.idx  += 1
            st.session_state.ver  += 1
            temizle()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.kuyruk:
        total = len(st.session_state.kuyruk)
        i     = st.session_state.idx
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        n1, n2, n3 = st.columns([1, 2, 1])
        with n1:
            if st.button("◀", use_container_width=True, disabled=i==0):
                st.session_state.idx -= 1
                st.session_state.ver += 1
                temizle()
                st.rerun()
        with n2:
            st.markdown(f"<div style='text-align:center;font-size:12px;color:#6b7280;padding:8px 0;font-family:monospace;'>{i+1}/{total}</div>", unsafe_allow_html=True)
        with n3:
            if st.button("▶", use_container_width=True, disabled=i>=total-1):
                st.session_state.idx += 1
                st.session_state.ver += 1
                temizle()
                st.rerun()

        st.markdown("<hr>", unsafe_allow_html=True)
        for j, s in enumerate(st.session_state.kuyruk):
            if j < i:    cls, ikon = "kart tamam", "✅"
            elif j == i: cls, ikon = "kart aktif", "▶"
            else:        cls, ikon = "kart", f"{j+1}."
            st.markdown(f"<div class='{cls}'>{ikon} {s['gtip']} / {s['ulke']}</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:4px'></div><div class='btn-r'>", unsafe_allow_html=True)
        if st.button("↺ Sıfırla", use_container_width=True):
            st.session_state.kuyruk = []
            st.session_state.idx    = 0
            st.session_state.pdf_n  = 0
            st.session_state.ver   += 1
            st.session_state.hata   = ""
            temizle()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# ORTA: İFRAME (Mevcut HTML görünümü)
# ══════════════════════════════════════════════════════
with orta:
    if st.session_state.html:
        st.markdown(
            f"<div class='web-panel-baslik'>🛃 {st.session_state.tgtip} / {st.session_state.tulke} &nbsp;·&nbsp; <span style='color:#aaa;font-weight:400;font-size:11px;'>Önizleme</span></div>",
            unsafe_allow_html=True
        )
        st.components.v1.html(st.session_state.html, height=820, scrolling=True)
    else:
        st.markdown("""
        <div style='display:flex;flex-direction:column;align-items:center;justify-content:center;
                    min-height:75vh;text-align:center;background:white;border-radius:8px;border:1px dashed #d0ccc4;'>
            <div style='font-size:48px;opacity:0.10;'>📋</div>
            <div style='font-size:14px;font-weight:700;color:#bbb;margin-top:16px;'>Önizleme</div>
            <div style='font-size:11px;color:#ccc;margin-top:8px;'>Sorgu sonrası burada görünür</div>
        </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# SAĞ: GERÇEK WEB SAYFASI (popup boyutunda açılır)
# ══════════════════════════════════════════════════════
with sag:
    if st.session_state.sonuc_url:
        url = st.session_state.sonuc_url
        st.markdown(
            f"""
            <div class='web-panel-baslik'>🌐 AB TARIC &nbsp;·&nbsp;
            <span style='color:#aaa;font-weight:400;font-size:11px;'>Tıklanabilir Sayfa</span></div>
            <div style='display:flex;flex-direction:column;align-items:center;justify-content:center;
                        min-height:75vh;background:white;border:1px solid #d0ccc4;border-top:none;
                        border-radius:0 0 8px 8px;text-align:center;padding:32px;'>
                <div style='font-size:52px;margin-bottom:20px;'>🌐</div>
                <div style='font-size:17px;font-weight:800;color:#1a1a1a;margin-bottom:6px;'>
                    {st.session_state.tgtip} / {st.session_state.tulke}
                </div>
                <div style='font-size:11px;color:#999;margin-bottom:32px;font-family:monospace;'>
                    {url[:55]}{'...' if len(url)>55 else ''}
                </div>
                <a href="{url}" target="_blank"
                   style='display:inline-block;background:#1d4ed8;color:white;
                          padding:16px 40px;border-radius:8px;font-size:16px;
                          font-weight:800;text-decoration:none;letter-spacing:0.5px;
                          box-shadow:0 4px 14px rgba(29,78,216,0.35);'>
                    🌐 &nbsp; Sayfayı Aç
                </a>
                <div style='font-size:11px;color:#bbb;margin-top:20px;line-height:1.8;'>
                    ✅ Tüm TARIC kodları tıklanabilir<br>
                    ✅ Toggle / açılır-kapanır çalışır<br>
                    ✅ Tam AB TARIC deneyimi
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown("""
        <div style='display:flex;flex-direction:column;align-items:center;justify-content:center;
                    min-height:75vh;text-align:center;background:white;border-radius:8px;border:1px dashed #d0ccc4;'>
            <div style='font-size:48px;opacity:0.10;'>🌐</div>
            <div style='font-size:14px;font-weight:700;color:#bbb;margin-top:16px;'>Web Sayfası</div>
            <div style='font-size:11px;color:#ccc;margin-top:8px;'>Sorgu sonrası AB sitesi burada açılır</div>
            <div style='font-size:11px;color:#ccc;margin-top:4px;'>Tüm linkler ve toggle'lar çalışır</div>
        </div>""", unsafe_allow_html=True)
