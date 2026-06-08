import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import io
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(page_title="Portefeuille BNC", layout="wide")

# --- ASTUCE CSS : Forcer les proportions exactes sur mobile (Version Ultra-Robuste) ---
st.markdown("""
    <style>
        /* Désactive le retour à la ligne forcé par Streamlit sur téléphone */
        div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 10px !important;
        }
        /* Première boîte (Sélecteur) : Forcée à 35% de l'écran */
        div[data-testid="stHorizontalBlock"] > div:nth-child(1) {
            width: 35% !important;
            min-width: 35% !important;
            flex: none !important;
        }
        /* Deuxième boîte (Bouton) : Forcée à 65% de l'écran */
        div[data-testid="stHorizontalBlock"] > div:nth-child(2) {
            width: 65% !important;
            min-width: 65% !important;
            flex: none !important;
        }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def heure_mise_a_jour():
    return datetime.now(ZoneInfo("America/Toronto")).strftime("%H:%M")

st.title("📈 BNC")

heure_actuelle = heure_mise_a_jour()

col_tri, col_btn = st.columns([1, 2.5])

with col_tri:
    colonne_tri = st.selectbox("Tri", ["Pré G %", "Gain %"], label_visibility="collapsed")
    
with col_btn:
    if st.button(f"🔄 Rafraîchir ({heure_actuelle})", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

URL_ONEDRIVE = "https://onedrive.live.com/:x:/g/personal/f3dc5429b587ae35/IQAm87v8ehTnQrt_lz2sW1Q5AUk-6g4cno5k6CgDX9V0qtU?download=1"

@st.cache_data(ttl=300)
def charger_donnees_base():
    entetes = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    reponse = requests.get(URL_ONEDRIVE, headers=entetes, allow_redirects=True)
    reponse.raise_for_status() 
    return pd.read_excel(io.BytesIO(reponse.content), sheet_name='Portefeuille BNC', engine='openpyxl')

def mise_a_jour_prix(df):
    for index, row in df.iterrows():
        symbole = row.get('Symbole')
        if pd.notna(symbole):
            try:
                ticker = yf.Ticker(str(symbole).strip())
                
                # On demande 5 jours d'historique pour être sûr d'avoir le prix de la veille
                infos = ticker.history(period="5d")
                
                # On s'assure d'avoir au moins 2 jours de données (aujourd'hui et la veille)
                if not infos.empty and len(infos) >= 2:
                    prix_actuel = infos['Close'].iloc[-1]
                    prix_veille = infos['Close'].iloc[-2]
                    
                    df.at[index, 'Prix $'] = prix_actuel
                    
                    # --- NOUVEAU : Calcul de la variation du jour (Var %) ---
                    df.at[index, 'Var %'] = (prix_actuel - prix_veille) / prix_veille
                    
                    achat = row['Achat $']
                    qte = row['Qtée']
                    df.at[index, 'Gain %'] = (prix_actuel - achat) / achat
                    df.at[index, 'Gain $'] = (prix_actuel - achat) * qte
                
                infos_generales = ticker.info
                prevision_1an = infos_generales.get('targetMeanPrice')
                if prevision_1an is not None:
                    df.at[index, 'Pré 1an $'] = prevision_1an
                    
            except Exception:
                pass
    return df

try:
    with st.spinner("Connexion à OneDrive et Yahoo Finance..."):
        df_base = charger_donnees_base()

        # --- NOUVEAU : Filtrage des lignes ---
        # On conserve uniquement les lignes où la colonne "No." n'est pas égale à 0
        if 'No.' in df_base.columns:
            df_base = df_base[df_base['No.'] != 0].reset_index(drop=True)

        df_live = mise_a_jour_prix(df_base)

        colonnes_pourcentage = ["Pré G %", "Gain %", "Var %"]
        for col in colonnes_pourcentage:
            if col in df_live.columns:
                df_live[col] = df_live[col] * 100

        if colonne_tri == "Pré G %":
            df_live = df_live.sort_values(by="Pré G %", ascending=True) 
        elif colonne_tri == "Gain %":
            df_live = df_live.sort_values(by="Gain %", ascending=False) 

    valeur_totale = (df_live['Prix $'] * df_live['Qtée']).sum()
    gain_total = df_live['Gain $'].sum()

    gain_formate = f"{gain_total:,.2f} $".replace(',', ' ')
    valeur_formate = f"{valeur_totale:,.2f} $".replace(',', ' ')

    st.markdown(f"""
        <div style="display: flex; justify-content: space-between; margin-bottom: 20px;">
            <div style="text-align: left;">
                <p style="margin: 0px; font-size: 14px; color: gray;">Gain total</p>
                <p style="margin: 0px; font-size: 22px; font-weight: bold;">{gain_formate}</p>
            </div>
            <div style="text-align: right;">
                <p style="margin: 0px; font-size: 14px; color: gray;">Valeur totale</p>
                <p style="margin: 0px; font-size: 22px; font-weight: bold;">{valeur_formate}</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    def couleur_alerte_vente(valeur):
        if pd.isna(valeur):
            return ''
        if valeur <= 5:
            return 'background-color: rgba(255, 0, 0, 0.3)'
        elif valeur < 15:
            return 'background-color: rgba(255, 255, 0, 0.3)'
        else:
            return 'background-color: rgba(0, 255, 0, 0.3)'

    df_stylise = df_live.style.map(couleur_alerte_vente, subset=['Pré G %'])

    st.dataframe(
        df_stylise,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Pré G %": st.column_config.NumberColumn(format="%.0f %%"),
            "Prix $": st.column_config.NumberColumn(format="$ %.2f"),
            "Pré 1an $": st.column_config.NumberColumn(format="$ %.2f"),
            "Achat $": st.column_config.NumberColumn(format="$ %.2f"),
            "Gain %": st.column_config.NumberColumn(format="%.0f %%"),
            "Var %": st.column_config.NumberColumn(format="%.0f %%"),
            "Gain $": st.column_config.NumberColumn(format="$ %.2f"),
            "Date Achat": st.column_config.DatetimeColumn(format="YYYY-MM-DD")
        }
    )
    
except Exception as e:
    st.error(f"Erreur lors du chargement : {e}")
