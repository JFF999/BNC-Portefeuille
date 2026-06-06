import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Portefeuille BNC", layout="wide")
st.title("📈 Mon Portefeuille BNC en Direct")

# Insérez le lien modifié ici
URL_ONEDRIVE = "https://1drv.ms/x/c/f3dc5429b587ae35/IQQm87v8ehTnQrt_lz2sW1Q5AfP8HhO2zdEv7dsLHkUOoA4?download=1"

@st.cache_data(ttl=300)  # Rafraîchit les données toutes les 5 minutes maximum
def charger_donnees_base():
    # Télécharge et lit l'onglet spécifique du fichier Excel
    return pd.read_excel(URL_ONEDRIVE, sheet_name='Portefeuille BNC')

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