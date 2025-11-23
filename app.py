import streamlit as st
import pandas as pd
import plotly.express as px

# --- Configuración de la Página ---
st.set_page_config(page_title="DeFi Looping - Collateral Defense", layout="wide")

st.title("🛡️ Calculadora Looping: Defensa con Colateral")
st.markdown("""
Esta herramienta simula una estrategia de **Looping Long** donde la defensa ante caídas
se realiza **añadiendo más del mismo activo** (ej. añadir más WBTC al depósito).
""")

# --- Barra Lateral: Parámetros ---
st.sidebar.header("1. Configuración de la Posición")

asset_name = st.sidebar.text_input("Activo (Ticker)", value="WBTC")
current_price = st.sidebar.number_input(f"Precio Actual {asset_name} ($)", value=65000.0, step=100.0)
initial_capital = st.sidebar.number_input("Capital Inicial ($)", value=10000.0, step=1000.0)

st.sidebar.header("2. Parámetros del Protocolo")
leverage = st.sidebar.slider("Apalancamiento (x)", min_value=1.1, max_value=5.0, value=3.0, step=0.1)
liq_threshold = st.sidebar.slider("Umbral de Liquidación (LT %)", min_value=60, max_value=95, value=82, step=1) / 100

# --- CÁLCULOS BASE ---
# Colateral Total = Capital * Leverage
total_collateral_usd = initial_capital * leverage
# Deuda = Colateral Total - Capital Inicial
total_debt_usd = total_collateral_usd - initial_capital

# Cantidad de tokens (ej. BTC) en la posición inicial
amount_asset_initial = total_collateral_usd / current_price

# Precio de Liquidación Inicial
# P_liq = Deuda / (Cantidad_Activo * LT)
if amount_asset_initial > 0:
    liq_price_initial = total_debt_usd / (amount_asset_initial * liq_threshold)
else:
    liq_price_initial = 0

# HF Actual
if total_debt_usd > 0:
    hf_initial = (total_collateral_usd * liq_threshold) / total_debt_usd
else:
    hf_initial = 0

# --- VISUALIZACIÓN SUPERIOR ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Posición Total (USD)", f"${total_collateral_usd:,.0f}", f"{amount_asset_initial:.4f} {asset_name}")
col2.metric("Deuda Total (USD)", f"${total_debt_usd:,.0f}")
col3.metric("Precio Liquidación", f"${liq_price_initial:,.2f}", delta_color="inverse",
            delta=f"{(current_price - liq_price_initial)/current_price:.1%} distancia")
col4.metric("Health Factor", f"{hf_initial:.2f}", 
            delta="Riesgo" if hf_initial < 1.1 else "Ok", delta_color="normal" if hf_initial >= 1.1 else "inverse")

st.divider()

# --- LÓGICA DE DEFENSA (AÑADIR COLATERAL) ---
st.subheader(f"🛡️ Estrategia: Defender añadiendo {asset_name}")
st.info(f"Al añadir {asset_name} como colateral, el cálculo tiene en cuenta que tu 'escudo' vale menos cuando el precio baja.")

defense_data = []
niveles = range(15, 80, 5) # De 15% a 75% de distancia

for dist_pct in niveles:
    # 1. Definimos el Precio Objetivo de Liquidación (Target Price)
    # "Quiero que mi nuevo precio de liquidación esté un X% abajo del precio ACTUAL"
    target_liq_price = current_price * (1 - (dist_pct / 100))
    
    # 2. La Matemática
    # Fórmula Liq: P_target = Deuda / ( (Tokens_Iniciales + Tokens_Extra) * LT )
    # Despejamos Tokens_Extra:
    # Tokens_Extra = ( Deuda / (P_target * LT) ) - Tokens_Iniciales
    
    if target_liq_price > 0:
        required_total_tokens = total_debt_usd / (target_liq_price * liq_threshold)
        tokens_to_add = required_total_tokens - amount_asset_initial
    else:
        tokens_to_add = 0
        
    # Si sale negativo, significa que ya estamos cubiertos para ese nivel
    if tokens_to_add < 0:
        tokens_to_add = 0

    # Costo en USD hoy (lo que te cuesta comprar esos tokens AHORA para depositarlos)
    cost_now_usd = tokens_to_add * current_price
    
    # Nuevo HF AHORA (si añades el colateral hoy al precio actual)
    new_collateral_usd = (amount_asset_initial + tokens_to_add) * current_price
    new_hf_now = (new_collateral_usd * liq_threshold) / total_debt_usd

    defense_data.append({
        "Distancia Deseada": f"{dist_pct}%",
        "Nuevo Precio Liq.": target_liq_price,
        f"Añadir {asset_name}": tokens_to_add,
        "Costo Hoy ($)": cost_now_usd,
        "% vs Capital Inicial": (cost_now_usd / initial_capital) * 100,
        "Nuevo HF (Hoy)": new_hf_now
    })

df = pd.DataFrame(defense_data)

# --- MOSTRAR TABLA Y GRÁFICO ---
c_table, c_chart = st.columns([4, 5])

with c_table:
    st.markdown("#### Tabla de Necesidades")
    st.dataframe(df.style.format({
        "Nuevo Precio Liq.": "${:,.2f}",
        f"Añadir {asset_name}": "{:.4f}",
        "Costo Hoy ($)": "${:,.0f}",
        "% vs Capital Inicial": "{:.1f}%",
        "Nuevo HF (Hoy)": "{:.2f}"
    }), hide_index=True, use_container_width=True)

with c_chart:
    st.markdown(f"#### Costo de Defensa ({asset_name})")
    if not df.empty and df["Costo Hoy ($)"].sum() > 0:
        fig = px.line(df, x="Distancia Deseada", y="Costo Hoy ($)", 
                      markers=True, title=f"Capital ($) necesario para defender {asset_name}",
                      labels={"Distancia Deseada": "Distancia de Seguridad (%)", "Costo Hoy ($)": "Inversión Necesaria ($)"})
        fig.update_layout(yaxis_tickformat="$,.0f")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.success("Tu posición actual ya es segura para estos niveles.")