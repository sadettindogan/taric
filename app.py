import streamlit as st
import requests
import time, re, json, os
from urllib.parse import urlencode

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
    while len(temiz) > 10:
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

def sonuc_url_olustur(gtip, ulke, tarih):
    base = "https://ec.europa.eu/taxation_customs/dds2/taric/taric_consultation.jsp"
    params = {"Lang": "en", "taricCode": gtip, "Area": ulke, "SimDate": tarih, "Expand": "true"}
    return f"{base}?{urlencode(params)}"

def html_getir(gtip, ulke, tarih):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://ec.europa.eu/taxation_customs/dds2/taric/taric_consultation.jsp?Lang=en",
    })
    session.get("https://ec.europa.eu/taxation_customs/dds2/taric/taric_consultation.jsp?Lang=en", timeout=15)
    tarih_temiz = tarih.replace("-", "").replace(".", "").replace("/", "")
    data = {
        "Lang": "en",
        "taricCode": gtip,
        "Area": ulke,
        "SimDate": tarih_temiz,
        "action": "retrieve",
        "Expand": "true",
    }
    resp = session.post(
        "https://ec.europa.eu/taxation_customs/dds2/taric/taric_consultation.jsp",
        data=data,
        timeout=20
    )
    resp.encoding = "utf-8"
    return resp.text

def html_temizle(html):
    BASE = "https://ec.europa.eu"
    BASE_TARIC = "https://ec.europa.eu/taxation_customs/dds2/taric"

    # Güvenlik headerlarını kaldır
    html = re.sub(r'<meta[^>]*(x-frame-options|content-security-policy)[^>]*>', '', html, flags=re.IGNORECASE)

    # Tüm relative linkleri absolute yap
    html = re.sub(r'href="(/[^"]*)"', lambda m: f'href="{BASE}{m.group(1)}"', html)
    html = re.sub(r'src="(/[^"]*)"', lambda m: f'src="{BASE}{m.group(1)}"', html)
    html = re.sub(r'action="(/[^"]*)"', lambda m: f'action="{BASE}{m.group(1)}"', html)

    # javascript: linkleri yeni sekmede aç
    html = re.sub(
        r'href="(https?://[^"]*)"',
        r'href="\1" target="_blank"',
        html
    )

    ek = f"""
<base href="{BASE_TARIC}/">
<style>
  body {{
    font-size:14px !important;
    line-height:1.6 !important;
    font-family: Arial, sans-serif !important;
    background: #fff !important;
  }}
  table {{ font-size:13px !important; }}
  td, th {{ padding: 5px 8px !important; }}
  a {{ color: #1d4ed8 !important; cursor: pointer !important; }}
  a:hover {{ text-decoration: underline !important; }}
  /* Gereksiz header/footer gizle */
  .ecl-site-header, .ecl-footer, #header, #footer,
  .ecl-page-header, nav {{ display:none !important; }}
  /* Ana içeriği öne çıkar */
  #content, .ecl-container, main {{
    padding: 8px !important;
    margin: 0 !important;
    max-width: 100% !important;
  }}
</style>
"""
    return html.replace("<head>", "<head>" + ek, 1) if "<head>" in html else ek + html

# ─── SAYFA KONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="TARIC Sorgu", page_icon="🛃", layout="wide")
st.markdown("""
<style>
html,body,[data-testid="stAppViewContainer"]{background:#f5f3ef;}
section[data-testid="stSidebar"]{display:none;}
header{display:none!important;}
.block-container{padding:12px 16px!important;max-width:100%!important;}
[data-testid="column"]:first-child{
    min-width:260px!important;
    max-width:300px!important;
    flex:0 0 20%!important;
}
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
.btn-s .stButton>button{background:#1d4ed8!important;color:white!important;font-size:14px!important;padding:13px 0!important;}
.btn-r .stButton>button{background:#e5e7eb!important;color:#6b7280!important;}
.kart{background:white;border:1px solid #e5e7eb;border-radius:5px;padding:5px 10px;margin-bottom:3px;font-family:monospace;font-size:11px;}
.aktif{border-color:#1d4ed8!important;background:#eff6ff!important;font-weight:700;color:#1d4ed8!important;}
.tamam{opacity:0.4;}
.prog{background:#e5e7eb;border-radius:8px;height:5px;overflow:hidden;margin:3px 0 10px;}
.prog-bar{background:linear-gradient(90deg,#1d4ed8,#7c3aed);height:100%;}
hr{border-color:#e0ddd5!important;margin:8px 0!important;}
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ─────────────────────────────────────────────────────────────
for k, v in {
    "kuyruk": [], "idx": 0,
    "html": None,
    "ver": 0, "hata": "", "sure": "",
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
        durum.info("🔍 Sorgulanıyor...")
        html = html_getir(gtip, ulke, tarih)
        t1   = time.time()
        st.session_state.html      = html_temizle(html)
        st.session_state.sonuc_url = sonuc_url_olustur(gtip, ulke, tarih)
        st.session_state.hata      = ""
        st.session_state.sure      = f"sorgu:{t1-t0:.1f}s"
        durum.success(f"✅ {t1-t0:.1f}s")
    except Exception as e:
        st.session_state.hata = str(e)
        durum.error(f"❌ {e}")

# ─── LAYOUT ───────────────────────────────────────────────────────────────────
sol, sag = st.columns([1, 4], gap="medium")

with sol:
    st.markdown("""
    <div style='display:flex;align-items:center;justify-content:space-between;
                padding-bottom:10px;border-bottom:2px solid #c8b560;margin-bottom:12px;'>
        <div style='font-size:22px;font-weight:800;'>🛃 TARIC</div>
    </div>
    """, unsafe_allow_html=True)

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
            st.session_state.ver   += 1
            temizle()
            st.rerun()

    if st.session_state.kuyruk:
        total = len(st.session_state.kuyruk)
        i     = st.session_state.idx
        pct   = min(int(i/total*100), 100)
        st.markdown(f"<div style='font-size:11px;color:#6b7280;font-family:monospace;'>{min(i,total)}/{total} · {pct}%</div><div class='prog'><div class='prog-bar' style='width:{pct}%'></div></div>", unsafe_allow_html=True)

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

    if st.session_state.kuyruk:
        total = len(st.session_state.kuyruk)
        i     = st.session_state.idx
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
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
            st.session_state.ver   += 1
            st.session_state.hata   = ""
            temizle()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# ─── SAĞ PANEL ────────────────────────────────────────────────────────────────
with sag:
    if st.session_state.html:
        if st.session_state.sonuc_url:
            st.markdown(
                f"<div style='font-size:11px;color:#6b7280;font-family:monospace;padding:0 0 6px;'>"
                f"🔗 <a href='{st.session_state.sonuc_url}' target='_blank' style='color:#1d4ed8;'>AB sitesinde aç ↗</a>"
                f"</div>",
                unsafe_allow_html=True
            )
        st.components.v1.html(st.session_state.html, height=850, scrolling=True)
