# app.py — versão usando apenas Google Sheets (sem e-mail)
import pandas as pd
import streamlit as st
from datetime import datetime

# ==== Google Sheets ====
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Validação de CIDs — Notas Clínicas", layout="wide")

@st.cache_resource
def load_data(pickle_path: str):
    df = pd.read_pickle(pickle_path)
    if "NotaIndex" in df.columns:
        df["NotaIndex"] = df["NotaIndex"].astype(int)
    model_cols = [c for c in df.columns if c not in ["NotaIndex", "Nota Clínica"]]
    for col in model_cols:
        df[col] = df[col].apply(lambda x: x if isinstance(x, list) else ([] if pd.isna(x) or x == "" else [str(x)]))
    return df

def truncate(text: str, n=200):
    s = str(text)
    return s if len(s) <= n else s[:n] + "…"

def filter_checked(items, show_ok=True, show_nok=True):
    if show_ok and show_nok:
        return items
    if show_ok and not show_nok:
        return [x for x in items if str(x).strip().startswith("✅")]
    if show_nok and not show_ok:
        return [x for x in items if str(x).strip().startswith("❌")]
    return []

@st.cache_resource
def open_sheet():
    gsa = st.secrets.get("gcp_service_account", None)
    gsheet_id = st.secrets.get("GSHEET_ID", None)
    gsheet_tab = st.secrets.get("GSHEET_TAB", "Analises")
    if not gsa or not gsheet_id:
        raise RuntimeError("Config Google Sheets ausente em st.secrets (gcp_service_account / GSHEET_ID).")
    creds = Credentials.from_service_account_info(
        gsa,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    client = gspread.authorize(creds)
    sh = client.open_by_key(gsheet_id)
    try:
        ws = sh.worksheet(gsheet_tab)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=gsheet_tab, rows=2000, cols=12)
        ws.append_row(["timestamp", "nota_index", "analista", "nota_preview", "analise", "modelos", "itens_mostrados_json"])
    return ws

# -------- Sidebar --------
st.sidebar.title("Configurações")
pickle_file = st.sidebar.text_input("Caminho do pickle", value="tabela_full.pkl")
df = load_data(pickle_file)
model_cols = [c for c in df.columns if c not in ["NotaIndex", "Nota Clínica"]]

st.sidebar.markdown("### Filtros")
q = st.sidebar.text_input("Buscar no texto da nota (case-insensitive)", value="")
sel_models = st.sidebar.multiselect("Filtrar por modelos (colunas)", options=model_cols, default=model_cols)
show_ok = st.sidebar.checkbox("Mostrar CIDs validados (✅)", value=True)
show_nok = st.sidebar.checkbox("Mostrar CIDs não validados (❌)", value=True)

# -------- Filtros --------
df_filtered = df.copy()
if q.strip():
    df_filtered = df_filtered[df_filtered["Nota Clínica"].str.contains(q, case=False, na=False)]

cols_to_show = ["NotaIndex", "Nota Clínica"] + list(sel_models)
df_filtered = df_filtered[cols_to_show]

for c in sel_models:
    df_filtered[c] = df_filtered[c].apply(lambda items: filter_checked(items, show_ok, show_nok))

# -------- Preview --------
st.title("Notas Clínicas — Ouro e Modelos (✅ validados / ❌ não validados)")

preview = df_filtered.copy()
preview["Nota Clínica (preview)"] = preview["Nota Clínica"].apply(lambda s: truncate(s, 200))
ordered_cols = ["NotaIndex", "Nota Clínica (preview)"] + sel_models
st.subheader("Visão geral")
st.dataframe(preview[ordered_cols], use_container_width=True, height=420)

# -------- Detalhe --------
st.subheader("Detalhar NotaIndex")
idx_list = df_filtered["NotaIndex"].tolist()
default_idx = idx_list[0] if len(idx_list) > 0 else 0
nota_idx = st.number_input(
    "Digite um NotaIndex",
    min_value=0,
    max_value=int(df["NotaIndex"].max()),
    value=int(default_idx) if len(idx_list) > 0 else 0,
    step=1
)

linha = df_filtered[df_filtered["NotaIndex"] == int(nota_idx)]
if linha.empty:
    st.info("NotaIndex não encontrado no filtro atual.")
else:
    row = linha.iloc[0]
    with st.container(border=True):
        st.markdown(f"### NotaIndex: `{int(nota_idx)}`")
        st.markdown("**Nota Clínica (texto completo):**")
        st.write(row["Nota Clínica"])

    st.markdown("### Modelos")
    cols = st.columns(3) if len(sel_models) >= 3 else st.columns(max(1, len(sel_models)))
    for i, mcol in enumerate(sel_models):
        box = cols[i % len(cols)].container(border=True)
        title = "🟨 Ouro" if mcol.lower().strip() == "ouro" else f"🔧 {mcol}"
        box.markdown(f"**{title}**")
        items = row[mcol]
        if not items:
            box.write("—")
        else:
            for it in items:
                box.write(f"- {it}")

    # -------- Análise + Sheets --------
    st.markdown("---")
    st.header("Análise do avaliador")

    with st.form("form_analise", clear_on_submit=True):
        analista = st.text_input("Seu nome (opcional)", value="")
        analise_txt = st.text_area("Escreva sua análise aqui:", height=220, placeholder="Descreva a avaliação clínica, justificativas, observações sobre CIDs, etc.")
        submitted = st.form_submit_button("Salvar em Google Sheets")

    if submitted:
        try:
            ws = open_sheet()
            timestamp = datetime.now().isoformat(timespec="seconds")
            nota_preview = truncate(row["Nota Clínica"], 240)
            modelos_list = ", ".join(sel_models)
            # serialização simples dos itens mostrados
            itens_mostrados = {m: row[m] for m in sel_models}

            ws.append_row([
                timestamp,
                int(nota_idx),
                analista,
                nota_preview,
                analise_txt,
                modelos_list,
                str(itens_mostrados),
            ])
            st.success("Registro salvo no Google Sheets ✅")
        except Exception as e:
            st.error(f"Falha ao salvar no Google Sheets: {e}")
