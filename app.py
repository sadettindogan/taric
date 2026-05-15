import streamlit as st
from playwright.sync_api import sync_playwright
import json, os, time, re

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

def tarih_to_simdate(tarih):
    p = tarih.strip().split('-')
    if len(p) == 3:
        return p[2] + p[1] + p[0]
    return tarih

def tarih_cevir(girdi):
    girdi = girdi.strip()
    parcalar = re.split(r'[.\-/]', girdi)
    if len(parcalar) == 3:
        g, m, y = parcalar
        return f"{g.zfill(2)}-{m.zfill(2)}-{y}"
    return girdi

def satirlari_parse_et(ham):
    ham = ham.strip()
    satirlar = []
    tarih_re = re.compile(r'\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}')
    for satir in ham.splitlines():
        satir = satir.strip()
        if not satir: continue
        if "\t" in satir:
            p = [x.strip() for x in satir.split("\t") if x.strip()]
            if len(p) >= 3:
                satirlar.append(p[:3])
            elif len(p) == 2:
                m = tarih_re.search(p[1])
                if m:
                    satirlar.append([p[0], p[1][:m.start()].strip(), m.group()])
        else:
            m = tarih_re.search(satir)
            if m:
                tarih_str = m.group()
                kalan = satir[:m.start()].strip()
                gtip_m = re.match(r'[\d.]+', kalan)
                if gtip_m:
                    satirlar.append([kalan[:gtip_m.end()].strip(), kalan[gtip_m.end():].strip(), tarih_str])
    sonuc = []
    for p in satirlar:
        if len(p) >= 3:
            sonuc.append({
                "gtip_ham": p[0], "ulke_ham": p[1], "tarih_ham": p[2],
                "gtip": gtip_cevir(p[0]), "ulke": ulke_cevir(p[1]), "tarih": tarih_cevir(p[2]),
            })
    return sonuc

# ─── PLAYWRIGHT: Tek tarayıcı, açık kalır ─────────────────────────────────────
@st.cache_resource
def get_browser():
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=True,
        executable_path="/usr/bin/chromium",
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
              "--disable-extensions", "--blink-settings=imagesEnabled=false"]
    )
    return pw, browser

# Tek sayfa — açık kalır, her sorguda yeni URL'ye gider
_sayfa = {}

def taric_sorgula(gtip, ulke, tarih):
    """Direkt measures URL — form yok, çok hızlı"""
    try:
        _, browser = get_browser()
        simdate = tarih_to_simdate(tarih)
        url = (
            f"https://ec.europa.eu/taxation_customs/dds2/taric/measures.jsp"
            f"?Lang=en&SimDate={simdate}&Area={ulke.strip()}"
            f"&MeasType=&StartPub=&EndPub=&MeasText=&GoodsText=&op="
            f"&Taric={gtip.strip()}&AdditionalCode=&search_text=goods"
            f"&textSearch=&LangDescr=en&OrderDir=DESC&show="
        )
        page = _sayfa.get("page")
        if not page:
            ctx  = browser.new_context(viewport={"width": 1400, "height": 900})
            page = ctx.new_page()
            _sayfa["page"] = page

        t0 = time.time()
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        # Sadece içerik tablosunu bekle
        try:
            page.wait_for_selector(".measures, table, #content", timeout=5000)
        except:
            pass
        t1 = time.time()

        html_content    = page.content()
        pdf_bytes       = page.pdf(format="A4", print_background=True, scale=1.0)
        pdf_bytes_kucuk = page.pdf(format="A4", print_background=True, scale=0.65)
        t2 = time.time()

        # Zamanlama bilgisini HTML'e göm
        zaman = f"goto:{t1-t0:.1f}s | pdf:{t2-t1:.1f}s | toplam:{t2-t0:.1f}s"
        html_content = html_content.replace("</body>",
            f"<div style='position:fixed;bottom:0;left:0;background:#111;color:#c8b560;"
            f"font:11px monospace;padding:3px 8px;z-index:9999;'>⏱ {zaman}</div></body>")

        return html_content, pdf_bytes, pdf_bytes_kucuk, None
    except Exception as e:
        _sayfa["page"] = None
        return None, None, None, str(e)

def taric_url_ac(url):
    """GTİP linkine tıklanınca çağrılır"""
    try:
        _, browser = get_browser()
        page = _sayfa.get("page")
        if not page:
            ctx  = browser.new_context(viewport={"width": 1400, "height": 900})
            page = ctx.new_page()
            _sayfa["page"] = page

        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        try:
            page.wait_for_selector("table", timeout=5000)
        except:
            pass
        html_content    = page.content()
        pdf_bytes       = page.pdf(format="A4", print_background=True, scale=1.0)
        pdf_bytes_kucuk = page.pdf(format="A4", print_background=True, scale=0.65)
        return html_content, pdf_bytes, pdf_bytes_kucuk, None
    except Exception as e:
        _sayfa["page"] = None
        return None, None, None, str(e)

def linkleri_cıkar(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    seen, sonuc = set(), []
    for a in soup.find_all("a", href=True):
        href  = a["href"]
        metin = a.get_text(strip=True)
        if not metin or not href: continue
        if "Taric=" not in href and "taric=" not in href: continue
        if not re.match(r'^[\d\s]+$', metin): continue
        if len(metin.strip()) < 4: continue
        if href.startswith("/"): href = "https://ec.europa.eu" + href
        if not href.startswith("http") or href in seen: continue
        seen.add(href)
        sonuc.append({"metin": metin.strip(), "url": href})
    return sonuc

def html_temizle(html, base_url="https://ec.europa.eu"):
    html = re.sub(r'<meta[^>]*(x-frame-options|content-security-policy)[^>]*>', '', html, flags=re.IGNORECASE)
    ek = f'<base href="{base_url}" target="_self"><style>body{{font-size:15px!important;line-height:1.7!important;font-family:Arial,sans-serif!important}}table{{font-size:14px!important}}td,th{{padding:6px 10px!important}}a[href]{{cursor:pointer!important}}</style>'
    return html.replace("<head>", "<head>" + ek, 1) if "<head>" in html else ek + html

# ─── SAYFA AYARI ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="TARIC Sorgu", page_icon="🛃",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Syne:wght@400;700;800&display=swap');
html,body,[data-testid="stAppViewContainer"]{background:#f5f3ef;font-family:'Syne',sans-serif;color:#1a1a1a;}
section[data-testid="stSidebar"]{display:none;}
header{display:none!important;}
.block-container{padding:12px 16px!important;max-width:100%!important;}
[data-testid="stTextArea"] textarea{
    background:#fff!important;border:1px solid #9ca3af!important;border-radius:4px!important;
    color:#111827!important;font-family:'JetBrains Mono',monospace!important;
    font-size:10px!important;line-height:1.8!important;padding:8px 10px!important;
    white-space:pre!important;overflow-x:auto!important;tab-size:16!important;
}
[data-testid="stTextInput"] input{
    background:white!important;border:1px solid #d4c97a!important;border-radius:4px!important;
    color:#1a1a1a!important;font-family:'JetBrains Mono',monospace!important;
    font-size:13px!important;font-weight:700!important;padding:7px 10px!important;
}
[data-testid="stTextArea"] label,[data-testid="stTextInput"] label{
    color:#888!important;font-size:10px!important;font-weight:700!important;
    letter-spacing:1.5px!important;text-transform:uppercase!important;
}
.stButton>button{
    font-family:'Syne',sans-serif!important;font-weight:700!important;font-size:11px!important;
    border-radius:4px!important;padding:8px 0!important;width:100%!important;border:none!important;
}
.btn-sorgula .stButton>button{background:#1d4ed8!important;color:white!important;font-size:13px!important;padding:12px 0!important;}
.btn-pdf     .stButton>button{background:#16a34a!important;color:white!important;}
.btn-pdf65   .stButton>button{background:#0891b2!important;color:white!important;}
.btn-devam   .stButton>button{background:#d97706!important;color:white!important;}
.btn-reset   .stButton>button{background:#e5e7eb!important;color:#6b7280!important;}
.satir-kart{background:white;border:1px solid #e5e7eb;border-radius:5px;padding:5px 10px;
            margin-bottom:3px;font-family:'JetBrains Mono',monospace;font-size:11px;color:#374151;}
.satir-aktif{border-color:#1d4ed8!important;background:#eff6ff!important;font-weight:700;color:#1d4ed8!important;}
.satir-tamam{opacity:0.4;}
.prog{background:#e5e7eb;border-radius:8px;height:5px;overflow:hidden;margin:3px 0 10px;}
.prog-bar{background:linear-gradient(90deg,#1d4ed8,#7c3aed);height:100%;border-radius:8px;}
hr{border-color:#e0ddd5!important;margin:8px 0!important;}
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ─────────────────────────────────────────────────────────────
for k, v in {
    "kuyruk": [], "aktif_idx": 0,
    "page_html": None, "pdf_bytes": None, "pdf_bytes_kucuk": None,
    "sorgulandı": False, "pdf_sayisi": 0, "input_ver": 0,
    "navigate_url": "", "linkler": [],
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

def aktif_veri():
    idx = st.session_state.aktif_idx
    if st.session_state.kuyruk and idx < len(st.session_state.kuyruk):
        return st.session_state.kuyruk[idx]
    return {"gtip": "", "ulke": "", "tarih": ""}

def sonraki_satira_gec():
    st.session_state.aktif_idx  += 1
    st.session_state.sorgulandı  = False
    st.session_state.page_html   = None
    st.session_state.pdf_bytes   = None
    st.session_state.pdf_bytes_kucuk = None
    st.session_state.input_ver  += 1

# ─── LAYOUT ───────────────────────────────────────────────────────────────────
sol, sag = st.columns([0.75, 2.25], gap="medium")

with sol:
    st.markdown("""
    <div style='padding-bottom:10px;border-bottom:2px solid #c8b560;margin-bottom:12px;'>
        <div style='font-size:20px;font-weight:800;'>🛃 TARIC</div>
        <div style='font-size:10px;color:#999;letter-spacing:2px;'>GÜMRÜK TARİFE SORGULAMA</div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📋 Excel'den GTİP, Ülke, Tarih kopyala — bu alana yapıştır",
                     expanded=len(st.session_state.kuyruk)==0):
        yapistir = st.text_area("",
            placeholder="72.07.11.14.00.00\tRusya\t1.01.2024\n72.07.12.10.00.00\tPakistan\t11.12.2024",
            height=100, key="yapistir_kutu", label_visibility="collapsed")
        satirlar = []
        if yapistir.strip():
            satirlar = satirlari_parse_et(yapistir)
            if satirlar:
                st.markdown(f"<div style='font-size:11px;color:#166534;font-weight:700;'>✅ {len(satirlar)} satır algılandı</div>", unsafe_allow_html=True)
        if st.button("📥  Kuyruğa Yükle", use_container_width=True, disabled=len(satirlar)==0):
            st.session_state.kuyruk      = satirlar
            st.session_state.aktif_idx   = 0
            st.session_state.sorgulandı  = False
            st.session_state.page_html   = None
            st.session_state.pdf_bytes   = None
            st.session_state.pdf_bytes_kucuk = None
            st.session_state.pdf_sayisi  = 0
            st.session_state.input_ver  += 1
            st.rerun()

    if st.session_state.kuyruk:
        toplam = len(st.session_state.kuyruk)
        idx    = st.session_state.aktif_idx
        pct    = min(int((idx / toplam) * 100), 100)
        st.markdown(f"""
        <div style='font-size:11px;color:#6b7280;font-family:JetBrains Mono,monospace;'>
            {min(idx,toplam)}/{toplam} · {pct}% · 📄{st.session_state.pdf_sayisi} PDF
        </div>
        <div class='prog'><div class='prog-bar' style='width:{pct}%'></div></div>
        """, unsafe_allow_html=True)

    av  = aktif_veri()
    ver = st.session_state.input_ver
    st.markdown("<div style='font-size:10px;color:#555;letter-spacing:1.5px;font-weight:700;margin-bottom:2px;'>SORGULANACAK VERİ</div>", unsafe_allow_html=True)
    akt_gtip  = st.text_input("GTİP",  value=av["gtip"],  key=f"inp_gtip_{ver}")
    akt_ulke  = st.text_input("Ülke",  value=av["ulke"],  key=f"inp_ulke_{ver}")
    akt_tarih = st.text_input("Tarih", value=av["tarih"], key=f"inp_tarih_{ver}")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    idx_no      = st.session_state.aktif_idx
    dosya       = f"{idx_no+1}_{akt_gtip}_{akt_ulke}.pdf"
    dosya_kucuk = f"{idx_no+1}_{akt_gtip}_{akt_ulke}_65.pdf"
    var_pdf     = bool(st.session_state.pdf_bytes)
    var_pdf65   = bool(st.session_state.pdf_bytes_kucuk)

    st.markdown("<div class='btn-sorgula'>", unsafe_allow_html=True)
    sorgula = st.button("🔍  Sorgula", use_container_width=True,
                        disabled=not bool(akt_gtip.strip()))
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("<div class='btn-pdf'>", unsafe_allow_html=True)
        if st.download_button("📄 PDF", data=st.session_state.pdf_bytes or b"",
            file_name=dosya, mime="application/pdf",
            use_container_width=True, disabled=not var_pdf, key="dl_pdf"):
            st.session_state.pdf_sayisi += 1
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='btn-pdf65'>", unsafe_allow_html=True)
        if st.download_button("📄 PDF%65", data=st.session_state.pdf_bytes_kucuk or b"",
            file_name=dosya_kucuk, mime="application/pdf",
            use_container_width=True, disabled=not var_pdf65, key="dl_pdf65"):
            st.session_state.pdf_sayisi += 1
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div class='btn-devam'>", unsafe_allow_html=True)
        if st.button("⏭️", use_container_width=True,
                     help="PDF almadan sonraki", disabled=not var_pdf):
            sonraki_satira_gec()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.kuyruk:
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        idx    = st.session_state.aktif_idx
        toplam = len(st.session_state.kuyruk)
        cn1, cn2, cn3 = st.columns([1, 2, 1])
        with cn1:
            if st.button("◀", use_container_width=True, disabled=idx==0):
                st.session_state.aktif_idx -= 1
                st.session_state.sorgulandı = False
                st.session_state.page_html  = None
                st.session_state.pdf_bytes  = None
                st.session_state.pdf_bytes_kucuk = None
                st.session_state.input_ver += 1
                st.rerun()
        with cn2:
            st.markdown(f"<div style='text-align:center;font-size:12px;color:#6b7280;padding:8px 0;font-family:JetBrains Mono,monospace;'>{idx+1} / {toplam}</div>", unsafe_allow_html=True)
        with cn3:
            if st.button("▶", use_container_width=True, disabled=idx>=toplam-1):
                st.session_state.aktif_idx += 1
                st.session_state.sorgulandı = False
                st.session_state.page_html  = None
                st.session_state.pdf_bytes  = None
                st.session_state.pdf_bytes_kucuk = None
                st.session_state.input_ver += 1
                st.rerun()

    if st.session_state.get("linkler"):
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:10px;color:#1d4ed8;font-weight:700;margin-bottom:4px;'>🔵 GTİP LİNKLERİ</div>", unsafe_allow_html=True)
        for i, link in enumerate(st.session_state.linkler):
            if st.button(link["metin"], key=f"link_{i}_{ver}", use_container_width=True):
                with sag:
                    with st.spinner(f"⏳ {link['metin']} açılıyor..."):
                        h, pdf, pdf_k, hata = taric_url_ac(link["url"])
                    if not hata:
                        st.session_state.page_html       = html_temizle(h)
                        st.session_state.pdf_bytes       = pdf
                        st.session_state.pdf_bytes_kucuk = pdf_k
                        st.session_state.linkler = linkleri_cıkar(h)
                    else:
                        st.error(f"❌ {hata}")
                st.rerun()

    if st.session_state.kuyruk:
        st.markdown("<hr>", unsafe_allow_html=True)
        idx = st.session_state.aktif_idx
        for i, s in enumerate(st.session_state.kuyruk):
            if i < idx:    cls, ikon = "satir-kart satir-tamam", "✅"
            elif i == idx: cls, ikon = "satir-kart satir-aktif", "▶"
            else:          cls, ikon = "satir-kart", f"{i+1}."
            st.markdown(f"<div class='{cls}'>{ikon} {s['gtip']} / {s['ulke']}</div>", unsafe_allow_html=True)
        st.markdown("<div style='height:4px'></div><div class='btn-reset'>", unsafe_allow_html=True)
        if st.button("↺ Sıfırla", use_container_width=True):
            for k in ["kuyruk","aktif_idx","page_html","pdf_bytes","pdf_bytes_kucuk",
                      "sorgulandı","pdf_sayisi","linkler"]:
                st.session_state[k] = [] if k in ["kuyruk","linkler"] else (
                    0 if k in ["aktif_idx","pdf_sayisi"] else (
                    False if k=="sorgulandı" else None))
            st.session_state.input_ver += 1
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# ─── SORGU ────────────────────────────────────────────────────────────────────
if sorgula:
    with sag:
        with st.spinner(f"⏳ {akt_gtip.strip()} / {akt_ulke.strip()} sorgulanıyor..."):
            html_content, pdf_bytes, pdf_bytes_kucuk, hata = taric_sorgula(
                akt_gtip.strip(), akt_ulke.strip(), akt_tarih.strip())
        if hata:
            st.error(f"❌ {hata}")
        else:
            st.session_state.page_html       = html_temizle(html_content)
            st.session_state.pdf_bytes       = pdf_bytes
            st.session_state.pdf_bytes_kucuk = pdf_bytes_kucuk
            st.session_state.sorgulandı      = True
            st.session_state.linkler         = linkleri_cıkar(html_content)
    st.rerun()

# ─── SAĞ PANEL ────────────────────────────────────────────────────────────────
with sag:
    if st.session_state.page_html:
        st.markdown(f"""
        <div style='display:flex;align-items:center;justify-content:space-between;
                    padding:10px 16px;background:#1a1a1a;border-radius:6px;margin-bottom:4px;'>
            <div style='font-family:JetBrains Mono,monospace;font-size:12px;color:#c8b560;font-weight:700;'>
                🛃 {akt_gtip} / {akt_ulke}
            </div>
            <div style='font-size:11px;color:#555;'>Sol paneldeki GTİP linklerine tıklayabilirsiniz</div>
        </div>
        """, unsafe_allow_html=True)
        st.components.v1.html(st.session_state.page_html, height=820, scrolling=True)
    else:
        st.markdown("""
        <div style='display:flex;flex-direction:column;align-items:center;justify-content:center;
                    min-height:75vh;text-align:center;background:white;
                    border-radius:8px;border:1px dashed #d0ccc4;'>
            <div style='font-size:56px;opacity:0.10;margin-bottom:16px;'>🛃</div>
            <div style='font-size:16px;font-weight:700;color:#bbb;margin-bottom:6px;'>Sorgu Bekleniyor</div>
            <div style='font-size:12px;color:#ccc;line-height:1.8;'>
                Sol panelden veri girin veya Excel'den yapıştırın<br>
                Sorgula'ya basın — sonuç burada görünür
            </div>
        </div>
        """, unsafe_allow_html=True)
