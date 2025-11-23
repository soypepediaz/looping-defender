import streamlit as st
import pandas as pd

# --- Configuración de la Página ---
st.set_page_config(page_title="Looping Defense - Final Report", layout="wide")

st.title("🛡️ Calculadora Looping: Defensa & Rentabilidad")
st.markdown("""
Esta herramienta simula una estrategia de defensa en cascada y genera un informe ejecutivo 
sobre las necesidades de capital y el potencial de retorno (Risk/Reward).
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
    
    # --- CÁLCULOS DE RENTABILIDAD ---
    # Valor de mi posición (colateral total) si el precio sube a Target Price
    final_position_value = current_collateral_amt * target_price
    
    # Patrimonio Neto = Valor Posición - Deuda
    net_equity = final_position_value - initial_debt_usd
    
    # Beneficio Neto = Patrimonio Neto - Total Dinero Puesto (Inicial + Inyecciones)
    net_profit = net_equity - total_invested_so_far
    
    # ROI %
    roi_pct = (net_profit / total_invested_so_far) * 100
    
    # RATIO: Beneficio % / Caída %
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
        "Beneficio al Objetivo ($)": net_profit,
        "ROI (%)": roi_pct,
        "Ratio (Ganancia/Caída)": risk_reward_ratio
    })
    
    # Preparar siguiente iteración
    current_liq_price = target_liq_price

df_cascade = pd.DataFrame(cascade_data)

# --- TABLA DE RESULTADOS ---
st.divider()
st.subheader(f"📍 Análisis de Escenarios: Rebote hasta ${target_price:,.0f}")

# Tabla limpia y expandida
st.dataframe(df_cascade.style.format({
    "Precio Activación ($)": "${:,.2f}",
    "Caída Max (%)": "{:.2%}",
    "Inversión Extra ($)": "${:,.0f}",
    "Total Invertido ($)": "${:,.0f}",
    "Nuevo P. Liq ($)": "${:,.2f}",
    "Beneficio al Objetivo ($)": "${:,.0f}", 
    "ROI (%)": "{:.2f}%",
    "Ratio (Ganancia/Caída)": "{:.2f}"
}), hide_index=True, use_container_width=True)


# --- INFORME EJECUTIVO (Plantilla) ---
st.divider()

if not df_cascade.empty:
    last_row = df_cascade.iloc[-1]
    
    # Variables para el texto
    total_drop_txt = f"{last_row['Caída Max (%)']:.1%}"
    trigger_final_txt = f"${last_row['Precio Activación ($)']:,.0f}"
    zones_txt = num_zones
    total_invested_txt = f"${last_row['Total Invertido ($)']:,.0f}"
    new_liq_final_txt = f"${last_row['Nuevo P. Liq ($)']:,.0f}"
    net_profit_txt = f"${last_row['Beneficio al Objetivo ($)']:,.0f}"
    roi_final_txt = f"{last_row['ROI (%)']:.2f}%"
    ratio_txt = f"{last_row['Ratio (Ganancia/Caída)']:.2f}"
    
    # Plantilla Markdown
    report_markdown = f"""
    ### 📝 Informe Ejecutivo de Estrategia: Looping con Defensa Activa
    
    **1. Configuración de Partida** Has iniciado una operación de Looping en **{asset_name}** con un capital de **\${initial_capital:,.0f}** y un apalancamiento de **{leverage}x**.  
    Tu posición comenzó con un precio de liquidación de **\${liq_price_start:,.2f}**, lo que te daba un colchón de seguridad inicial del **{initial_cushion_pct:.1%}**.
    
    **2. Lógica de Defensa (Tu Seguro)** Para evitar la liquidación, hemos establecido una estrategia de "Muro de Contención".
    * **¿Cuándo actuamos?** Actuamos preventivamente cuando el precio se acerca (sube) un **{defense_threshold_pct:.1%}** sobre tu nivel de liquidación.
    * **¿Qué hacemos?** Inyectamos más **{asset_name}** (colateral) a la posición.
    * **¿El objetivo?** Restaurar la tranquilidad. Cada inyección empuja el precio de liquidación hacia abajo lo suficiente para recuperar el mismo margen de seguridad (**{initial_cushion_pct:.1%}**) que tenías al principio.
    
    **3. Análisis de Escenario Extremo (Zona #{zones_txt})** En el peor escenario simulado, donde el mercado sufre una caída acumulada del **{total_drop_txt}** (llevando el precio de {asset_name} a **{trigger_final_txt}**):
    * Habrás tenido que defender la posición **{zones_txt}** veces.
    * Tu inversión total (Capital Inicial + Defensas) habrá ascendido a **{total_invested_txt}**.
    * Tu nuevo precio de liquidación estaría blindado en **{new_liq_final_txt}**.
    
    **4. Proyección de Rentabilidad (Risk/Reward)** Si logras aguantar esta caída extrema y el mercado eventualmente rebota hasta tu objetivo de **\${target_price:,.0f}**:
    * El valor de tu posición se disparará debido a la gran cantidad de colateral acumulado a precios bajos.
    * Tu beneficio neto sería de **{net_profit_txt}**.
    * Esto supone un retorno del **{roi_final_txt}** sobre todo el dinero invertido.
    * **Ratio de Eficiencia:** Por cada 1% que el mercado cayó, tú recuperaste un **{ratio_txt}%** de beneficio en la subida.
    """
    
    st.markdown(report_markdown)

else:
    st.warning("Ajusta los parámetros para generar escenarios de defensa.")
