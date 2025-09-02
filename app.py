import ast
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Validação de CIDs — Notas Clínicas", layout="wide")

@st.cache_resource
def load_data(pickle_path: str):
    df = pd.read_pickle(pickle_path)
    # Garante tipos
    if "NotaIndex" in df.columns:
        df["NotaIndex"] = df["NotaIndex"].astype(int)
    # Normaliza: algumas colunas (modelos) podem ter listas/strings
    model_cols = [c for c in df.columns if c not in ["NotaIndex", "Nota Clínica"]]
    for col in model_cols:
        df[col] = df[col].apply(lambda x: x if isinstance(x, list) else ([] if pd.isna(x) or x == "" else [str(x)]))
    return df

def truncate(text: str, n=200):
    s = str(text)
    return s if len(s) <= n else s[:n] + "…"

def filter_checked(items, show_ok=True, show_nok=True):
    """Filtra lista com prefixos ✅/❌ conforme toggles."""
    if show_ok and show_nok:
        return items
    if show_ok and not show_nok:
        return [x for x in items if str(x).strip().startswith("✅")]
    if show_nok and not show_ok:
        return [x for x in items if str(x).strip().startswith("❌")]
    return []  # nenhum

# === Sidebar ===
st.sidebar.title("Configurações")

pickle_file = st.sidebar.text_input("Caminho do pickle", value="tabela_full.pkl")
df = load_data(pickle_file)

model_cols = [c for c in df.columns if c not in ["NotaIndex", "Nota Clínica"]]

st.sidebar.markdown("### Filtros")
q = st.sidebar.text_input("Buscar no texto da nota (case-insensitive)", value="")
sel_models = st.sidebar.multiselect("Filtrar por modelos (colunas)", options=model_cols, default=model_cols)
show_ok = st.sidebar.checkbox("Mostrar CIDs validados (✅)", value=True)
show_nok = st.sidebar.checkbox("Mostrar CIDs não validados (❌)", value=True)

# Filtro por texto
df_filtered = df.copy()
if q.strip():
    df_filtered = df_filtered[df_filtered["Nota Clínica"].str.contains(q, case=False, na=False)]

# Filtra colunas de modelos conforme selecionadas
cols_to_show = ["NotaIndex", "Nota Clínica"] + list(sel_models)
df_filtered = df_filtered[cols_to_show]

# Aplica filtros ✅/❌ no conteúdo das listas
for c in sel_models:
    df_filtered[c] = df_filtered[c].apply(lambda items: filter_checked(items, show_ok, show_nok))

# --- Preview (tabela compacta) ---
st.title("Notas Clínicas — Ouro e Modelos (✅ validados / ❌ não validados)")

preview = df_filtered.copy()
preview["Nota Clínica (preview)"] = preview["Nota Clínica"].apply(lambda s: truncate(s, 200))
ordered_cols = ["NotaIndex", "Nota Clínica (preview)"] + sel_models
st.subheader("Visão geral")
st.dataframe(preview[ordered_cols], use_container_width=True, height=420)

# --- Detalhe por NotaIndex ---
st.subheader("Detalhar NotaIndex")
idx_list = df_filtered["NotaIndex"].tolist()
default_idx = idx_list[0] if len(idx_list) > 0 else 0
nota_idx = st.number_input("Digite um NotaIndex", min_value=0, max_value=int(df["NotaIndex"].max()), value=int(default_idx) if len(idx_list) > 0 else 0, step=1)

linha = df_filtered[df_filtered["NotaIndex"] == int(nota_idx)]
if linha.empty:
    st.info("NotaIndex não encontrado no filtro atual.")
else:
    row = linha.iloc[0]
    with st.container(border=True):
        st.markdown(f"### NotaIndex: `{int(nota_idx)}`")
        st.markdown("**Nota Clínica (texto completo):**")
        st.write(row["Nota Clínica"])

    # Grid de modelos
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

# --- Download do recorte filtrado ---
st.download_button(
    "Baixar recorte filtrado (CSV)",
    data=df_filtered.to_csv(index=False).encode("utf-8"),
    file_name="tabela_full_filtrada.csv",
    mime="text/csv"
)
