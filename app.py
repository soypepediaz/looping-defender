import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- Configuración de la Página ---
st.set_page_config(page_title="Looping Defense - Cascade V2", layout="wide")

st.title("🛡️ Estrategia de Defensa en Cascada (Looping)")
st.markdown("""
Esta herramienta simula una defensa secuencial. Cuando el precio se acerca a la liquidación, 
se inyecta colateral para **restaurar el colchón de seguridad original**.
""")

# --- Barra Lateral: Parámetros ---
st.sidebar.header("1. Posición Inicial")
asset_name = st.sidebar.text_input("Activo", value="WBTC")
initial_price = st.sidebar.number_input(f"Precio Inicial {asset_name} ($)", value=100000.0, step=100.0)
initial_capital = st.sidebar.number_input("Capital Inicial ($)", value=10000.0, step=1000.0)

st.sidebar.header("2. Protocolo & Riesgo")
leverage = st.sidebar.slider("Apalancamiento (x)", 1.1, 5.0, 2.0, 0.1)
ltv_liq = st.sidebar.slider("LTV de Liquidación (%)", 50, 95, 78, 1) / 100.0

st.sidebar.header("3. Estrategia de Defensa")
defense_threshold_pct = st.sidebar.number_input("Umbral de Protección (%)", value=15.0, step=1.0, help="Porcentaje por encima del precio de liquidación donde actúas.") / 100.0
num_zones = st.sidebar.slider("Número de Zonas de Defensa", 1, 15, 7) # Ampliado a 15 para probar

# --- CÁLCULOS INICIALES ---
initial_collateral_usd = initial_capital * leverage
initial_debt_usd = initial_collateral_usd - initial_capital
initial_collateral_amt = initial_collateral_usd / initial_price

# Precio Liquidación Inicial
# P_liq = Debt / (Colateral_Amt * LT)
liq_price_start = initial_debt_usd / (initial_collateral_amt * ltv_liq)

# Colchón Inicial (Target Ratio)
# Este es el ratio que intentaremos mantener en cada defensa.
target_ratio = liq_price_start / initial_price
initial_cushion_pct = (initial_price - liq_price_start) / initial_price

# --- VISUALIZACIÓN ESTADO 0 ---
st.divider()
st.subheader("Estado Inicial")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Colateral Inicial", f"{initial_collateral_amt:.4f} {asset_name}")
c2.metric("Deuda Total", f"${initial_debt_usd:,.0f}")
c3.metric("Precio Liq. Inicial", f"${liq_price_start:,.2f}", delta=f"-{(initial_price - liq_price_start):,.0f}$ hasta liq.", delta_color="inverse")
c4.metric("Colchón Objetivo", f"{initial_cushion_pct:.2%}", help=f"Intentaremos restaurar este margen de seguridad en cada caída.")

# --- MOTOR DE CÁLCULO EN CASCADA ---
cascade_data = []

# Variables que irán mutando en el bucle
current_collateral_amt = initial_collateral_amt
current_liq_price = liq_price_start
cumulative_cost_usd = 0.0

for i in range(1, num_zones + 1):
    # 1. ¿A qué precio salta la alarma? (Precio Trigger)
    trigger_price = current_liq_price * (1 + defense_threshold_pct)
    
    # --- NUEVO CÁLCULO: Caída desde el precio original ---
    # Si el precio inicial es 100k y el trigger es 70k, la caída es (100-70)/100 = 30%
    drop_from_start_pct = (initial_price - trigger_price) / initial_price
    
    # 2. ¿Cuál es nuestro objetivo de Nuevo Precio de Liquidación?
    # Queremos restaurar el colchón original RELATIVO al precio del trigger.
    target_liq_price = trigger_price * target_ratio
    
    # 3. ¿Cuánto colateral EXTRA necesitamos para bajar el Liq Price a ese target?
    # Fórmula derivada: Col_Total_Needed = Debt / (Target_Liq * LT)
    needed_total_collateral = initial_debt_usd / (target_liq_price * ltv_liq)
    collateral_to_add = needed_total_collateral - current_collateral_amt
    
    # Costo de esa inyección (al precio de mercado del momento, que es el Trigger Price)
    cost_injection = collateral_to_add * trigger_price
    
    # Actualizar acumulados
    cumulative_cost_usd += cost_injection
    current_collateral_amt += collateral_to_add # El nuevo total de colateral
    
    # Guardar datos de esta zona
    cascade_data.append({
        "Zona": f"Defensa #{i:02d}", # Formato con 0 delante para ordenar bien
        "Precio Activación ($)": trigger_price,
        "Caída Total (%)": drop_from_start_pct, # <--- NUEVA COLUMNA
        f"Colateral a Añadir ({asset_name})": collateral_to_add,
        "Costo Inyección ($)": cost_injection,
        "Nuevo Precio Liq. ($)": target_liq_price,
        "Total Acumulado ($)": cumulative_cost_usd
    })
    
    # El nuevo precio de liquidación se convierte en el actual para la siguiente iteración
    current_liq_price = target_liq_price

# Crear DataFrame
df_cascade = pd.DataFrame(cascade_data)

# --- RESULTADOS VISUALES (LAYOUT VERTICAL) ---
st.divider()
st.subheader("📍 Plan de Defensa Escalonado (Detalle)")

# 1. Tabla formateada (OCUPA TODO EL ANCHO)
st.dataframe(df_cascade.style.format({
    "Precio Activación ($)": "${:,.2f}",
    "Caída Total (%)": "{:.1%}", # Formato de porcentaje
    f"Colateral a Añadir ({asset_name})": "{:.4f}",
    "Costo Inyección ($)": "${:,.2f}",
    "Nuevo Precio Liq. ($)": "${:,.2f}",
    "Total Acumulado ($)": "${:,.2f}"
}), hide_index=True, use_container_width=True)

# 2. Resumen Estratégico (Debajo de la tabla)
total_needed = df_cascade["Total Acumulado ($)"].iloc[-1]
last_liq_price = df_cascade["Nuevo Precio Liq. ($)"].iloc[-1]
last_trigger_price = df_cascade["Precio Activación ($)"].iloc[-1]
total_drop = df_cascade["Caída Total (%)"].iloc[-1]

st.info(f"""
**Resumen de la Estrategia:**
Para soportar una caída del mercado del **{total_drop:.1%}** (Precio {asset_name} en **${last_trigger_price:,.0f}**), 
necesitas una reserva de liquidez total de **${total_needed:,.0f}**.
Esto representa un **{(total_needed/initial_capital)*100:.1f}%** de tu capital inicial.
Tu precio de liquidación final quedaría en **${last_liq_price:,.0f}**.
""")

# 3. Gráfico Visual (Al final de la página, opcional)
st.divider()
with st.expander("Ver Gráfico de Evolución Visual", expanded=False):
    st.markdown("##### Evolución del Precio de Liquidación vs Mercado")
    
    fig = go.Figure()
    
    # Línea de Precio de Mercado (Trigger)
    fig.add_trace(go.Scatter(
        x=df_cascade["Zona"], 
        y=df_cascade["Precio Activación ($)"],
        mode='lines+markers',
        name='Precio de Mercado (Trigger)',
        line=dict(color='orange', dash='dash')
    ))
    
    # Línea de Precio de Liquidación (que vamos empujando hacia abajo)
    fig.add_trace(go.Scatter(
        x=df_cascade["Zona"], 
        y=df_cascade["Nuevo Precio Liq. ($)"],
        mode='lines+markers',
        name='Nuevo Precio Liquidación',
        line=dict(color='green', width=3),
        fill='tonexty', # Relleno para visualizar el "Colchón"
        fillcolor='rgba(0, 255, 0, 0.1)'
    ))

    fig.update_layout(
        yaxis_title="Precio del Activo ($)",
        hovermode="x unified",
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)
