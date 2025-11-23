import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- Configuración de la Página ---
st.set_page_config(page_title="Looping Defense - Risk/Reward", layout="wide")

st.title("🛡️ Calculadora Looping: Defensa & Rentabilidad")
st.markdown("""
Esta herramienta simula la defensa en cascada y proyecta la **rentabilidad potencial** si el mercado rebota desde la zona de defensa hasta tu Precio Objetivo.
""")

# --- Barra Lateral: Parámetros ---
st.sidebar.header("1. Posición Inicial & Objetivo")
asset_name = st.sidebar.text_input("Activo", value="WBTC")
initial_price = st.sidebar.number_input(f"Precio Entrada {asset_name} ($)", value=100000.0, step=100.0)
target_price = st.sidebar.number_input(f"Precio Objetivo (Take Profit) ($)", value=130000.0, step=100.0)
initial_capital = st.sidebar.number_input("Capital Inicial ($)", value=10000.0, step=1000.0)

st.sidebar.header("2. Protocolo & Riesgo")
leverage = st.sidebar.slider("Apalancamiento (x)", 1.1, 5.0, 2.0, 0.1)
ltv_liq = st.sidebar.slider("LTV de Liquidación (%)", 50, 95, 78, 1) / 100.0

st.sidebar.header("3. Estrategia de Defensa")
defense_threshold_pct = st.sidebar.number_input("Umbral de Protección (%)", value=15.0, step=1.0, help="% por encima del precio de liq. para actuar.") / 100.0
num_zones = st.sidebar.slider("Número de Zonas de Defensa", 1, 10, 5)

# --- CÁLCULOS INICIALES ---
initial_collateral_usd = initial_capital * leverage
initial_debt_usd = initial_collateral_usd - initial_capital
initial_collateral_amt = initial_collateral_usd / initial_price

# P_liq Inicial
liq_price_start = initial_debt_usd / (initial_collateral_amt * ltv_liq)

# Ratio Objetivo (Colchón) para mantener constante
target_ratio = liq_price_start / initial_price
initial_cushion_pct = (initial_price - liq_price_start) / initial_price

# --- VISUALIZACIÓN ESTADO 0 ---
st.divider()
st.subheader("Estado Inicial")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Colateral Inicial", f"{initial_collateral_amt:.4f} {asset_name}")
c2.metric("Deuda Total", f"${initial_debt_usd:,.0f}")
c3.metric("Precio Liq. Inicial", f"${liq_price_start:,.2f}")
# Cálculo de ganancia si va directo al target sin caer
profit_clean_start = (initial_collateral_amt * target_price) - initial_debt_usd - initial_capital
roi_start = (profit_clean_start / initial_capital) * 100
c4.metric("Potencial Directo (ROI)", f"{roi_start:.2f}%", f"${profit_clean_start:,.0f}")
c5.metric("Colchón Seguridad", f"{initial_cushion_pct:.2%}")

# --- MOTOR DE CÁLCULO EN CASCADA ---
cascade_data = []

current_collateral_amt = initial_collateral_amt
current_liq_price = liq_price_start
cumulative_cost_usd = 0.0

for i in range(1, num_zones + 1):
    # 1. Trigger
    trigger_price = current_liq_price * (1 + defense_threshold_pct)
    
    # 2. Caída desde inicio
    drop_from_start_pct = (initial_price - trigger_price) / initial_price
    
    # 3. Objetivo nuevo Liq
    target_liq_price = trigger_price * target_ratio
    
    # 4. Cálculo Colateral necesario
    needed_total_collateral = initial_debt_usd / (target_liq_price * ltv_liq)
    collateral_to_add = needed_total_collateral - current_collateral_amt
    
    # 5. Costos
    cost_injection = collateral_to_add * trigger_price
    cumulative_cost_usd += cost_injection
    current_collateral_amt += collateral_to_add
    
    total_invested_so_far = initial_capital + cumulative_cost_usd
    
    # --- NUEVO: CÁLCULOS DE RENTABILIDAD (SI REBOTA AL TARGET) ---
    # Valor de mi posición (colateral total) si el precio sube a Target Price
    final_position_value = current_collateral_amt * target_price
    
    # Patrimonio Neto = Valor Posición - Deuda
    net_equity = final_position_value - initial_debt_usd
    
    # Beneficio Neto = Patrimonio Neto - Total Dinero Puesto (Inicial + Inyecciones)
    net_profit = net_equity - total_invested_so_far
    
    # ROI %
    roi_pct = (net_profit / total_invested_so_far) * 100
    
    # RATIO: Beneficio % / Caída %
    # Ejemplo: Gano un 80% tras aguantar una caída del 40%. Ratio = 2.0
    if drop_from_start_pct > 0:
        risk_reward_ratio = roi_pct / (drop_from_start_pct * 100)
    else:
        risk_reward_ratio = 0

    # Guardar datos
    cascade_data.append({
        "Zona": f"Defensa #{i:02d}",
        "Precio Activación ($)": trigger_price,
        "Caída Max (%)": drop_from_start_pct, 
        "Inversión Extra ($)": cost_injection,
        "Total Invertido ($)": total_invested_so_far,
        "Nuevo P. Liq ($)": target_liq_price,
        # Nuevas Columnas
        "Beneficio al Objetivo ($)": net_profit,
        "ROI (%)": roi_pct,
        "Ratio (Ganancia/Caída)": risk_reward_ratio
    })
    
    # Preparar siguiente iteración
    current_liq_price = target_liq_price

df_cascade = pd.DataFrame(cascade_data)

# --- RESULTADOS ---
st.divider()
st.subheader(f"📍 Análisis de Escenarios: Rebote hasta ${target_price:,.0f}")

# Estilo de la tabla
st.dataframe(df_cascade.style.format({
    "Precio Activación ($)": "${:,.2f}",
    "Caída Max (%)": "{:.2%}",
    "Inversión Extra ($)": "${:,.0f}",
    "Total Invertido ($)": "${:,.0f}",
    "Nuevo P. Liq ($)": "${:,.2f}",
    "Beneficio al Objetivo ($)": "${:,.0f}", # Sin decimales para limpieza
    "ROI (%)": "{:.2f}%",
    "Ratio (Ganancia/Caída)": "{:.2f}"
}).background_gradient(subset=["Ratio (Ganancia/Caída)"], cmap="RdYlGn"), 
hide_index=True, use_container_width=True)

# Resumen Final
last_row = df_cascade.iloc[-1]
st.info(f"""
**Interpretación de la última zona:** Si el precio cae un **{last_row['Caída Max (%)']:.1%}** (hasta ${last_row['Precio Activación ($)']:,.0f}) y tú defiendes la posición:
tendrás un total de **${last_row['Total Invertido ($)']:,.0f}** invertidos. 
Si luego el precio recupera hasta **${target_price:,.0f}**, ganarás **${last_row['Beneficio al Objetivo ($)']:,.0f}** ({last_row['ROI (%)']:.2f}% ROI).
""")

# Gráfico Opcional
st.divider()
with st.expander("Ver Gráfico de Niveles", expanded=False):
    fig = go.Figure()
    # Mercado
    fig.add_trace(go.Scatter(x=df_cascade["Zona"], y=df_cascade["Precio Activación ($)"],
                             name='Precio Mercado (Caída)', line=dict(color='orange', dash='dash')))
    # Liquidación
    fig.add_trace(go.Scatter(x=df_cascade["Zona"], y=df_cascade["Nuevo P. Liq ($)"],
                             name='Nuevo Precio Liq', line=dict(color='red')))
    # Target (Línea recta arriba)
    fig.add_trace(go.Scatter(x=df_cascade["Zona"], y=[target_price]*len(df_cascade),
                             name='Precio Objetivo', line=dict(color='green', width=4)))

    fig.update_layout(title="Mapa de Precios: Caída vs Liquidación vs Objetivo", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
