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
    if "\t" in ham:
        for satir in ham.splitlines():
            satir = satir.strip()
            if not satir: continue
            p = [x.strip() for x in satir.split("\t") if x.strip()]
            if len(p) >= 3:
                satirlar.append(p[:3])
    else:
        tum = [s.strip() for s in ham.splitlines() if s.strip()]
        i = 0
        while i < len(tum):
            if i + 2 < len(tum):
                satirlar.append([tum[i], tum[i+1], tum[i+2]])
                i += 3
            elif i + 1 < len(tum):
                sonraki = tum[i+1]
                m = re.search(r'(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})', sonraki)
                if m:
                    satirlar.append([tum[i], sonraki[:m.start()].strip(), m.group(1)])
                i += 2
            else:
                break
    sonuc = []
    for p in satirlar:
        sonuc.append({
            "gtip_ham": p[0], "ulke_ham": p[1], "tarih_ham": p[2],
            "gtip": gtip_cevir(p[0]), "ulke": ulke_cevir(p[1]), "tarih": tarih_cevir(p[2]),
        })
    return sonuc

def taric_sorgula(gtip, ulke, tarih):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path="/usr/bin/chromium",
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
            context = browser.new_context(viewport={"width": 1400, "height": 900})
            page = context.new_page()
            page.goto("https://ec.europa.eu/taxation_customs/dds2/taric/taric_consultation.jsp?Lang=en",
                      wait_until="networkidle", timeout=30000)
            page.wait_for_selector("#taricCode", timeout=10000)
            page.fill("#taricCode", gtip.strip())
            if ulke.strip():
                try: page.select_option("#taricArea", ulke.strip())
                except: pass
            if tarih.strip():
                page.evaluate("(t) => { document.querySelector('#SimDatePic').value = t; }", tarih.strip())
            try: page.get_by_text("Retrieve Measures", exact=True).click()
            except:
                try: page.locator("button", has_text="Retrieve Measures").click()
                except: page.keyboard.press("Enter")
            page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(2)
            html_content    = page.content()
            pdf_bytes       = page.pdf(format="A4", print_background=True, scale=1.0)
            pdf_bytes_kucuk = page.pdf(format="A4", print_background=True, scale=0.65)
            browser.close()
            return html_content, pdf_bytes, pdf_bytes_kucuk, None
    except Exception as e:
        return None, None, None, str(e)

def linkleri_cıkar(html):
    """
    TARIC sayfasındaki MAVİ GTİP linklerini çıkarır.
    Kriter: href'te 'Taric=' parametresi olan VE metni sadece rakam+boşluk olan linkler.
    """
    from bs4 import BeautifulSoup
    import re as _re
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    sonuc = []
    for a in soup.find_all("a", href=True):
        href  = a["href"]
        metin = a.get_text(strip=True)
        if not metin or not href: continue
        # Sadece TARIC GTİP linkleri — href'te Taric= var
        if "Taric=" not in href and "taric=" not in href: continue
        # Metin sadece rakam ve boşluktan oluşmalı (GTİP kodu)
        if not _re.match(r'^[\d\s]+$', metin): continue
        if len(metin.strip()) < 4: continue
        # Absolute URL yap
        if href.startswith("/"):
            href = "https://ec.europa.eu" + href
        if not href.startswith("http"): continue
        if href in seen: continue
        seen.add(href)
        # GTİP kodunu düzenli göster: "7207 12 10" → "7207 12 10"
        sonuc.append({"metin": metin.strip(), "url": href})
    return sonuc

def taric_url_ac(url):
    """Verilen TARIC URL'sini Playwright ile açar, HTML ve PDF döner"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path="/usr/bin/chromium",
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
            context = browser.new_context(viewport={"width": 1400, "height": 900})
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(1.5)
            html_content = page.content()
            pdf_bytes       = page.pdf(format="A4", print_background=True, scale=1.0)
            pdf_bytes_kucuk = page.pdf(format="A4", print_background=True, scale=0.65)
            browser.close()
            return html_content, pdf_bytes, pdf_bytes_kucuk, None
    except Exception as e:
        return None, None, None, str(e)

def html_temizle(html, base_url="https://ec.europa.eu"):
    import re as _re

    # 1. X-Frame-Options ve CSP meta tag'larını kaldır
    html = _re.sub(r'<meta[^>]*(x-frame-options|content-security-policy)[^>]*>', '', html, flags=_re.IGNORECASE)

    # 2. Harici script/link tag'larını kaldır (CSP engellemez)
    # 3. Linklere tıklanınca Streamlit input'a URL yaz
    link_script = """
<script>
(function() {
    function patchLinks() {
        document.querySelectorAll('a[href]').forEach(function(a) {
            if (a.dataset.patched) return;
            a.dataset.patched = '1';
            a.addEventListener('click', function(e) {
                var href = a.getAttribute('href');
                if (!href || href === '#' || href.startsWith('javascript')) return;
                e.preventDefault();
                e.stopPropagation();
                if (href.startsWith('/')) href = 'https://ec.europa.eu' + href;
                if (!href.startsWith('http')) return;
                // Streamlit parent'a mesaj gönder
                try { window.parent.postMessage({type:'taric_nav', url: href}, '*'); } catch(ex) {}
                // Ayrıca hidden input'a yaz
                try {
                    var inputs = window.parent.document.querySelectorAll('input[type=text]');
                    inputs.forEach(function(inp) {
                        if (inp.placeholder === '__taric_nav__') {
                            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            nativeInputValueSetter.call(inp, href);
                            inp.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                    });
                } catch(ex2) {}
            });
        });
    }
    document.addEventListener('DOMContentLoaded', patchLinks);
    // Dinamik içerik için MutationObserver
    var obs = new MutationObserver(function() { patchLinks(); });
    document.addEventListener('DOMContentLoaded', function() {
        obs.observe(document.body, {childList: true, subtree: true});
    });
})();
</script>
"""
    stil = """<style>
body{font-size:15px!important;line-height:1.7!important;font-family:Arial,sans-serif!important}
table{font-size:14px!important}
td,th{padding:6px 10px!important}
a[href]{cursor:pointer!important;text-decoration:underline!important;}
a[href]:hover{opacity:0.75!important;}
</style>"""
    ek = f'<base href="{base_url}" target="_self">{stil}{link_script}'
    return html.replace("<head>", "<head>" + ek, 1) if "<head>" in html else ek + html

# ─── SAYFA AYARI ─────────────────────────────────────────────────────────────
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
    background:white!important;border:1px solid #d4c97a!important;border-radius:4px!important;
    color:#1a1a1a!important;font-family:'JetBrains Mono',monospace!important;font-size:12px!important;padding:8px 10px!important;
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
    letter-spacing:0.5px!important;text-transform:uppercase!important;border-radius:4px!important;
    padding:8px 0!important;width:100%!important;transition:all 0.15s!important;border:none!important;
}
.btn-sorgula .stButton>button{background:#1d4ed8!important;color:white!important;font-size:13px!important;padding:12px 0!important;}
.btn-pdf     .stButton>button{background:#16a34a!important;color:white!important;padding:9px 0!important;}
.btn-devam   .stButton>button{background:#d97706!important;color:white!important;padding:9px 0!important;}
.btn-pdf65   .stButton>button{background:#0891b2!important;color:white!important;padding:9px 0!important;}
.btn-pdf65   .stButton>button:hover{background:#0e7490!important;}
.btn-reset   .stButton>button{background:#e5e7eb!important;color:#6b7280!important;}
.btn-link    .stButton>button{background:#eff6ff!important;color:#1d4ed8!important;
             border:1px solid #bfdbfe!important;font-family:'JetBrains Mono',monospace!important;
             font-size:12px!important;text-align:left!important;padding:6px 10px!important;}
.btn-link    .stButton>button:hover{background:#dbeafe!important;}
.satir-kart{background:white;border:1px solid #e5e7eb;border-radius:5px;padding:5px 10px;
            margin-bottom:3px;font-family:'JetBrains Mono',monospace;font-size:11px;color:#374151;}
.satir-aktif{border-color:#1d4ed8!important;background:#eff6ff!important;font-weight:700;color:#1d4ed8!important;}
.satir-tamam{opacity:0.4;}
.prog{background:#e5e7eb;border-radius:8px;height:5px;overflow:hidden;margin:3px 0 10px;}
.prog-bar{background:linear-gradient(90deg,#1d4ed8,#7c3aed);height:100%;border-radius:8px;}
hr{border-color:#e0ddd5!important;margin:8px 0!important;}
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ────────────────────────────────────────────────────────────
for k, v in {
    "kuyruk": [], "aktif_idx": 0,
    "page_html": None, "pdf_bytes": None,
    "sorgulandı": False, "pdf_sayisi": 0,
    "input_ver": 0,
    "navigate_url": "",
    "url_gecmisi": [],
    "linkler": [],
    "pdf_bytes_kucuk": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

def aktif_veri():
    idx = st.session_state.aktif_idx
    if st.session_state.kuyruk and idx < len(st.session_state.kuyruk):
        return st.session_state.kuyruk[idx]
    return {"gtip": "", "ulke": "", "tarih": ""}

def sonraki_satira_gec():
    st.session_state.aktif_idx += 1
    st.session_state.sorgulandı = False
    st.session_state.page_html  = None
    st.session_state.pdf_bytes  = None
    st.session_state.input_ver += 1  # input'ları yenile

# ─── LAYOUT ──────────────────────────────────────────────────────────────────
sol, sag = st.columns([0.5, 2.5], gap="medium")

with sol:
    st.markdown("""
    <div style='padding-bottom:10px;border-bottom:2px solid #c8b560;margin-bottom:12px;'>
        <div style='font-size:20px;font-weight:800;'>🛃 TARIC</div>
        <div style='font-size:10px;color:#999;letter-spacing:2px;'>GÜMRÜK TARİFE SORGULAMA</div>
    </div>
    """, unsafe_allow_html=True)

    # ── TOPLU VERİ ───────────────────────────────────────────────────────────
    with st.expander("📋 Excel'den Toplu Yapıştır", expanded=len(st.session_state.kuyruk)==0):
        yapistir = st.text_area("GTİP · Ülke · Tarih (her satır bir kayıt)",
            placeholder="72.07.11.14.00.00\tRusya\t1.01.2024\n72.07.12.10.00.00\tPakistan\t11.12.2024",
            height=100, key="yapistir_kutu")
        satirlar = []
        if yapistir.strip():
            satirlar = satirlari_parse_et(yapistir)
            if satirlar:
                st.markdown(f"<div style='font-size:11px;color:#166534;font-weight:700;'>✅ {len(satirlar)} satır</div>", unsafe_allow_html=True)
        if st.button("📥  Kuyruğa Yükle", use_container_width=True, disabled=len(satirlar)==0):
            st.session_state.kuyruk     = satirlar
            st.session_state.aktif_idx  = 0
            st.session_state.sorgulandı = False
            st.session_state.page_html  = None
            st.session_state.pdf_bytes  = None
            st.session_state.pdf_sayisi = 0
            st.session_state.input_ver += 1
            st.rerun()

    # ── İLERLEME ─────────────────────────────────────────────────────────────
    if st.session_state.kuyruk:
        toplam = len(st.session_state.kuyruk)
        idx    = st.session_state.aktif_idx
        pct    = min(int((idx / toplam) * 100), 100)
        st.markdown(f"""
        <div style='font-size:11px;color:#6b7280;font-family:JetBrains Mono,monospace;'>
            {min(idx,toplam)}/{toplam} · {pct}% · 📄 {st.session_state.pdf_sayisi} PDF
        </div>
        <div class='prog'><div class='prog-bar' style='width:{pct}%'></div></div>
        """, unsafe_allow_html=True)

    # ── SORGULANACAK VERİ (kuyruktaki aktif satırdan dolu gelir) ─────────────
    av = aktif_veri()
    ver = st.session_state.input_ver  # widget key versiyonu

    st.markdown("<div style='font-size:10px;color:#555;letter-spacing:1.5px;font-weight:700;margin-bottom:2px;'>SORGULANACAK VERİ</div>", unsafe_allow_html=True)

    # key'e versiyon ekleyerek Streamlit'i yeni value kabul etmeye zorla
    akt_gtip  = st.text_input("GTİP",  value=av["gtip"],  key=f"inp_gtip_{ver}")
    akt_ulke  = st.text_input("Ülke",  value=av["ulke"],  key=f"inp_ulke_{ver}")
    akt_tarih = st.text_input("Tarih", value=av["tarih"], key=f"inp_tarih_{ver}")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ── SORGULA + PDF BUTONLARI (her zaman görünür) ───────────────────────────
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
        if st.download_button(
            "📄 PDF", 
            data=st.session_state.pdf_bytes or b"",
            file_name=dosya, mime="application/pdf",
            use_container_width=True, disabled=not var_pdf
        ):
            st.session_state.pdf_sayisi += 1
            sonraki_satira_gec()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='btn-pdf65'>", unsafe_allow_html=True)
        if st.download_button(
            "📄 %65",
            data=st.session_state.pdf_bytes_kucuk or b"",
            file_name=dosya_kucuk, mime="application/pdf",
            use_container_width=True, disabled=not var_pdf65,
            help="Kağıt tasarruflu — %65 ölçek"
        ):
            st.session_state.pdf_sayisi += 1
            sonraki_satira_gec()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div class='btn-devam'>", unsafe_allow_html=True)
        if st.button("⏭️", use_container_width=True,
                     help="PDF almadan devam", disabled=not var_pdf):
            sonraki_satira_gec()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # ── NAVİGASYON < > ───────────────────────────────────────────────────────
    if st.session_state.kuyruk:
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        idx    = st.session_state.aktif_idx
        toplam = len(st.session_state.kuyruk)
        cn1, cn2, cn3 = st.columns([1, 2, 1])
        with cn1:
            if st.button("◀", use_container_width=True, disabled=idx == 0):
                st.session_state.aktif_idx -= 1
                st.session_state.sorgulandı = False
                st.session_state.page_html  = None
                st.session_state.pdf_bytes  = None
                st.session_state.input_ver += 1
                st.rerun()
        with cn2:
            st.markdown(f"<div style='text-align:center;font-family:JetBrains Mono,monospace;"
                        f"font-size:12px;color:#6b7280;padding:8px 0;'>"
                        f"{idx+1} / {toplam}</div>", unsafe_allow_html=True)
        with cn3:
            if st.button("▶", use_container_width=True, disabled=idx >= toplam - 1):
                st.session_state.aktif_idx += 1
                st.session_state.sorgulandı = False
                st.session_state.page_html  = None
                st.session_state.pdf_bytes  = None
                st.session_state.input_ver += 1
                st.rerun()

    # ── MAVİ GTİP LİNKLERİ ───────────────────────────────────────────────────
    if st.session_state.get("linkler"):
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("""
        <div style='font-size:10px;color:#1d4ed8;letter-spacing:1px;font-weight:700;margin-bottom:6px;'>
            🔵 GTİP LİNKLERİ — tıkla, aç
        </div>""", unsafe_allow_html=True)
        for i, link in enumerate(st.session_state.linkler):
            # GTİP kodunu formatla: "7207121000" → "7207 12 10 00"
            metin = link["metin"]
            if st.button(
                f"{metin}",
                key=f"link_{i}_{st.session_state.input_ver}",
                use_container_width=True
            ):
                with sag:
                    with st.spinner(f"⏳ {metin} açılıyor..."):
                        h, pdf, pdf_k, hata = taric_url_ac(link["url"])
                    if not hata:
                        st.session_state.url_gecmisi.append(st.session_state.navigate_url or "")
                        st.session_state.navigate_url     = link["url"]
                        st.session_state.page_html        = html_temizle(h)
                        st.session_state.pdf_bytes        = pdf
                        st.session_state.pdf_bytes_kucuk  = pdf_k
                        try:
                            st.session_state.linkler = linkleri_cıkar(h)
                        except:
                            st.session_state.linkler = []
                    else:
                        st.error(f"❌ {hata}")
                st.rerun()

    # ── KUYRUK LİSTESİ ───────────────────────────────────────────────────────
    if st.session_state.kuyruk:
        st.markdown("<hr>", unsafe_allow_html=True)
        idx = st.session_state.aktif_idx
        for i, s in enumerate(st.session_state.kuyruk):
            if i < idx:
                cls, ikon = "satir-kart satir-tamam", "✅"
            elif i == idx:
                cls, ikon = "satir-kart satir-aktif", "▶"
            else:
                cls, ikon = "satir-kart", f"{i+1}."
            st.markdown(f"<div class='{cls}'>{ikon} {s['gtip']} / {s['ulke']}</div>",
                        unsafe_allow_html=True)
        st.markdown("<div style='height:4px'></div><div class='btn-reset'>", unsafe_allow_html=True)
        if st.button("↺ Sıfırla", use_container_width=True):
            st.session_state.kuyruk     = []
            st.session_state.aktif_idx  = 0
            st.session_state.sorgulandı = False
            st.session_state.page_html  = None
            st.session_state.pdf_bytes  = None
            st.session_state.pdf_sayisi = 0
            st.session_state.input_ver += 1
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# ─── SORGU İŞLEMİ ────────────────────────────────────────────────────────────
if sorgula:
    gtip  = akt_gtip.strip()
    ulke  = akt_ulke.strip()
    tarih = akt_tarih.strip()
    with sag:
        with st.spinner(f"⏳ {gtip} / {ulke} sorgulanıyor..."):
            html_content, pdf_bytes, pdf_bytes_kucuk, hata = taric_sorgula(gtip, ulke, tarih)
        if hata:
            st.error(f"❌ {hata}")
        else:
            st.session_state.page_html      = html_temizle(html_content)
            st.session_state.pdf_bytes      = pdf_bytes
            st.session_state.pdf_bytes_kucuk = pdf_bytes_kucuk
            st.session_state.sorgulandı     = True
            try:
                st.session_state.linkler = linkleri_cıkar(html_content)
            except:
                st.session_state.linkler = []
    st.rerun()

# ─── SAĞ PANEL ───────────────────────────────────────────────────────────────
with sag:
    if st.session_state.page_html:
        # Geri butonu
        geri_col, baslik_col = st.columns([1, 5])
        with geri_col:
            if st.button("◀ Geri", use_container_width=True,
                         disabled=len(st.session_state.url_gecmisi) == 0):
                onceki_url = st.session_state.url_gecmisi.pop()
                with st.spinner("Yükleniyor..."):
                    h, pdf, pdf_k, hata = taric_url_ac(onceki_url)
                if not hata:
                    st.session_state.page_html       = html_temizle(h)
                    st.session_state.pdf_bytes       = pdf
                    st.session_state.pdf_bytes_kucuk = pdf_k
                st.rerun()
        with baslik_col:
            st.markdown(f"""
            <div style='display:flex;align-items:center;justify-content:space-between;
                        padding:10px 16px;background:#1a1a1a;border-radius:6px;'>
                <div style='font-family:JetBrains Mono,monospace;font-size:12px;color:#c8b560;font-weight:700;'>
                    🛃 {akt_gtip} / {akt_ulke}
                </div>
                <div style='font-size:11px;color:#555;'>Mavi linklere tıklayabilirsiniz</div>
            </div>
            """, unsafe_allow_html=True)

        # Canlı HTML render — st.components.v1.html iframe içinde çalışır
        # postMessage dinleyici — linke tıklanınca URL'yi yakala
        # Linklere tıklanınca URL'yi Streamlit'e ilet
        link_nav_script = """
<script>
(function() {
    // Sayfa yüklenince tüm linkleri yakala
    function patchLinks() {
        document.querySelectorAll('a[href]').forEach(function(a) {
            if (a._patched) return;
            a._patched = true;
            a.addEventListener('click', function(e) {
                var href = a.getAttribute('href');
                if (!href || href === '#' || href.startsWith('javascript')) return;
                e.preventDefault();
                if (href.startsWith('/')) href = 'https://ec.europa.eu' + href;
                if (!href.startsWith('http')) return;
                // Streamlit'e gönder
                window.parent.postMessage({type: 'taric_nav', url: href}, '*');
            });
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', patchLinks);
    } else {
        patchLinks();
    }
    new MutationObserver(patchLinks).observe(document.documentElement, {childList:true, subtree:true});
})();
</script>
"""
        st.components.v1.html(
            link_nav_script + st.session_state.page_html,
            height=820,
            scrolling=True,
        )

        # Streamlit'ten gelen URL mesajını dinle
        nav_js = """
<script>
window.addEventListener('message', function(e) {
    if (e.data && e.data.type === 'taric_nav') {
        // Streamlit'in query string'ine yaz
        var url = new URL(window.location.href);
        url.searchParams.set('taric_url', e.data.url);
        window.history.replaceState({}, '', url.toString());
    }
});
</script>
"""
        st.components.v1.html(nav_js, height=0)
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
