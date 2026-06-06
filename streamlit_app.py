import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import io
import base64

st.set_page_config(page_title="Portefeuille BNC", layout="wide")
st.title("📈 Mon Portefeuille BNC en Direct")

# Insérez le lien modifié ici
#URL_ONEDRIVE = "https://onedrive.live.com/:x:/g/personal/f3dc5429b587ae35/IQAm87v8ehTnQrt_lz2sW1Q5AUk-6g4cno5k6CgDX9V0qtU?download=1"
LIEN_ONEDRIVE = "https://1drv.ms/x/c/f3dc5429b587ae35/IQAm87v8ehTnQrt_lz2sW1Q5AUk-6g4cno5k6CgDX9V0qtU?e=T6VP12"

def creer_lien_direct_onedrive(lien):
    """Convertit automatiquement un lien de partage en lien de téléchargement API"""
    lien_b64 = base64.b64encode(lien.encode('utf-8')).decode('utf-8')
    lien_b64 = lien_b64.replace('/', '_').replace('+', '-').rstrip('=')
    return f"https://api.onedrive.com/v1.0/shares/u!{lien_b64}/root/content"

@st.cache_data(ttl=300)  # Rafraîchit les données toutes les 5 minutes maximum
def charger_donnees_base():
    # On génère le lien direct automatiquement
    lien_telechargement = creer_lien_direct_onedrive(LIEN_ONEDRIVE)
    reponse = requests.get(lien_telechargement)
    reponse.raise_for_status() 
    return pd.read_excel(io.BytesIO(reponse.content), sheet_name='Portefeuille BNC', engine='openpyxl')

def mise_a_jour_prix(df):
    for index, row in df.iterrows():
        symbole = row.get('Symbole')
        if pd.notna(symbole):
            try:
                # Requête rapide à Yahoo Finance
                ticker = yf.Ticker(str(symbole).strip())
                infos = ticker.history(period="1d")
                if not infos.empty:
                    prix_actuel = infos['Close'].iloc[-1]
                    
                    # Mise à jour des données de la ligne
                    df.at[index, 'Prix $'] = prix_actuel
                    achat = row['Achat $']
                    qte = row['Qtée']
                    
                    # Recalculs mathématiques en direct
                    df.at[index, 'Gain %'] = (prix_actuel - achat) / achat
                    df.at[index, 'Gain $'] = (prix_actuel - achat) * qte
            except Exception:
                pass
    return df

try:
    with st.spinner("Connexion à OneDrive et Yahoo Finance..."):
        df_base = charger_donnees_base()
        df_live = mise_a_jour_prix(df_base)
    
    # Affichage du tableau final avec les mêmes formats
    st.dataframe(
        df_live,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Pré G %": st.column_config.NumberColumn(format="%.2f %%"),
            "Prix $": st.column_config.NumberColumn(format="$ %.2f"),
            "Achat $": st.column_config.NumberColumn(format="$ %.2f"),
            "Gain %": st.column_config.NumberColumn(format="%.2f %%"),
            "Gain $": st.column_config.NumberColumn(format="$ %.2f"),
            "Date Achat": st.column_config.DatetimeColumn(format="YYYY-MM-DD")
        }
    )
    
    st.success("Données synchronisées avec succès !")

except Exception as e:
    st.error(f"Erreur lors du chargement : {e}")
