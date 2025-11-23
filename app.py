import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from datetime import date, timedelta

# --- Configuración de la Página ---
st.set_page_config(page_title="Looping Master - Calculator & Backtest", layout="wide")

st.title("🛡️ Looping Master: Calculadora & Backtesting")

# --- DICCIONARIO DE ACTIVOS (CONFIGURACIÓN) ---
# Mapea el nombre amigable con el Ticker de Yahoo Finance
ASSET_MAP = {
    "Bitcoin (BTC)": "BTC-USD",
    "Ethereum (ETH)": "ETH-USD",
    "Solana (SOL)": "SOL-USD",
    "Binance Coin (BNB)": "BNB-USD",
    "Hyperliquid (HYPE)": "HYPE-USD", # Puede tener poco histórico
    "XRP (XRP)": "XRP-USD",
    "Dogecoin (DOGE)": "DOGE-USD",
    "Cardano (ADA)": "ADA-USD",
    "Avalanche (AVAX)": "AVAX-USD",
    "Link (LINK)": "LINK-USD",
    "✍️ Otro (Escribir manual)": "MANUAL"
}

# Usamos Tabs para separar la calculadora estática del backtest temporal
tab_calc, tab_backtest = st.tabs(["🧮 Calculadora de Escenarios", "📉 Backtest Histórico"])

# ==============================================================================
#  PESTAÑA 1: CALCULADORA DE ESCENARIOS
# ==============================================================================
with tab_calc:
    st.markdown("### Simulador Estático de Defensa")
    
    # --- Inputs Calculadora ---
    col_input1, col_input2, col_input3 = st.columns(3)
    
    with col_input1:
        # Selector de activo
        selected_asset_calc = st.selectbox("Seleccionar Activo", list(ASSET_MAP.keys()), key="sel_asset_c")
        
        if ASSET_MAP[selected_asset_calc] == "MANUAL":
            c_asset_name = st.text_input("Escribe el Ticker o Nombre", value="PEPE", key="c_asset_man")
        else:
            # Extraemos solo el nombre (ej: BTC) para mostrar en el reporte
            c_asset_name = selected_asset_calc.split("(")[1].replace(")", "")
            
        c_price = st.number_input(f"Precio Actual {c_asset_name} ($)", value=100000.0, step=100.0, key="c_price")
        c_target = st.number_input(f"Precio Objetivo (Take Profit) ($)", value=130000.0, step=100.0, key="c_target")
        
    with col_input2:
        c_capital = st.number_input("Capital Inicial ($)", value=10000.0, step=1000.0, key="c_capital")
        c_leverage = st.slider("Apalancamiento (x)", 1.1, 5.0, 2.0, 0.1, key="c_lev")
        
    with col_input3:
        c_ltv = st.slider("LTV Liquidación (%)", 50, 95, 78, 1, key="c_ltv") / 100.0
        c_threshold = st.number_input("Umbral Defensa (%)", value=15.0, step=1.0, key="c_th") / 100.0
        c_zones = st.slider("Zonas de Defensa", 1, 10, 5, key="c_zones")

    # --- Cálculos Calculadora ---
    c_collat_usd = c_capital * c_leverage
    c_debt_usd = c_collat_usd - c_capital
    c_collat_amt = c_collat_usd / c_price
    
    # Liq Inicial
    c_liq_price = c_debt_usd / (c_collat_amt * c_ltv)
    c_target_ratio = c_liq_price / c_price 
    c_cushion_pct = (c_price - c_liq_price) / c_price
    
    # Bucle Cascada
    cascade_data = []
    curr_collat = c_collat_amt
    curr_liq = c_liq_price
    cum_cost = 0.0
    
    for i in range(1, c_zones + 1):
        trig_p = curr_liq * (1 + c_threshold)
        drop_pct = (c_price - trig_p) / c_price
        
        targ_liq = trig_p * c_target_ratio
        
        need_col = c_debt_usd / (targ_liq * c_ltv)
        add_col = need_col - curr_collat
        cost = add_col * trig_p
        
        cum_cost += cost
        curr_collat += add_col
        total_inv = c_capital + cum_cost
        
        final_val = curr_collat * c_target
        net_prof = (final_val - c_debt_usd) - total_inv
        roi = (net_prof / total_inv) * 100
        ratio = roi / (drop_pct * 100) if drop_pct > 0 else 0
        
        cascade_data.append({
            "Zona": f"#{i}",
            "Precio Activación": trig_p,
            "Caída (%)": drop_pct,
            "Inversión Extra ($)": cost,
            "Total Invertido ($)": total_inv,
            "Nuevo P. Liq": targ_liq,
            "Beneficio ($)": net_prof,
            "ROI (%)": roi,
            "Ratio": ratio
        })
        curr_liq = targ_liq

    df_calc = pd.DataFrame(cascade_data)
    
    # Output Calculadora (Tabla)
    st.divider()
    st.dataframe(df_calc.style.format({
        "Precio Activación": "${:,.2f}", "Caída (%)": "{:.2%}", "Inversión Extra ($)": "${:,.0f}",
        "Total Invertido ($)": "${:,.0f}", "Nuevo P. Liq": "${:,.2f}", "Beneficio ($)": "${:,.0f}",
        "ROI (%)": "{:.2f}%", "Ratio": "{:.2f}"
    }), use_container_width=True)
    
    # --- INFORME EJECUTIVO ---
    st.divider()
    if not df_calc.empty:
        last_row = df_calc.iloc[-1]
        
        total_drop_txt = f"{last_row['Caída (%)']:.1%}"
        trigger_final_txt = f"${last_row['Precio Activación']:,.0f}"
        zones_txt = c_zones
        total_invested_txt = f"${last_row['Total Invertido ($)']:,.0f}"
        new_liq_final_txt = f"${last_row['Nuevo P. Liq']:,.0f}"
        net_profit_txt = f"${last_row['Beneficio ($)']:,.0f}"
        roi_final_txt = f"{last_row['ROI (%)']:.2f}%"
        ratio_txt = f"{last_row['Ratio']:.2f}"
        
        report_markdown = f"""
        ### 📝 Informe Ejecutivo: Estrategia en {c_asset_name}
        
        **1. Configuración de Partida**
        Has iniciado una operación de Looping en **{c_asset_name}** con un capital de **\${c_capital:,.0f}** y un apalancamiento de **{c_leverage}x**.
        Tu posición comenzó con un precio de liquidación de **\${c_liq_price:,.2f}**, lo que te daba un colchón de seguridad inicial del **{c_cushion_pct:.1%}**.
        
        **2. Estrategia de Defensa**
        Actuamos preventivamente cuando el precio se acerca un **{c_threshold:.1%}** a la liquidación, inyectando más **{c_asset_name}** para recuperar el colchón de seguridad inicial.
        
        **3. Escenario Extremo (Zona #{zones_txt})**
        Si el mercado cae un **{total_drop_txt}** (Precio {c_asset_name}: **{trigger_final_txt}**):
        * Inversión total necesaria: **{total_invested_txt}**.
        * Nuevo precio de liquidación blindado: **{new_liq_final_txt}**.
        
        **4. Rentabilidad Esperada**
        Si tras esa caída el precio recupera hasta **\${c_target:,.0f}**:
        * Beneficio Neto: **{net_profit_txt}**.
        * ROI Total: **{roi_final_txt}**.
        * Ratio Eficiencia: **{ratio_txt}**.
        """
        st.markdown(report_markdown)


# ==============================================================================
#  PESTAÑA 2: MOTOR DE BACKTESTING (Con Selector)
# ==============================================================================
with tab_backtest:
    st.markdown("### 📉 Validación Histórica (Backtest)")
    st.caption("Comprueba cómo se habría comportado la estrategia en el pasado real.")

    # --- Inputs Backtest ---
    col_bt1, col_bt2, col_bt3 = st.columns(3)
    
    with col_bt1:
        # SELECTOR DE ACTIVO (MEJORADO)
        selected_asset_bt = st.selectbox("Seleccionar Activo Histórico", list(ASSET_MAP.keys()), key="sel_asset_bt")
        
        # Lógica para determinar el Ticker final
        if ASSET_MAP[selected_asset_bt] == "MANUAL":
            bt_ticker = st.text_input("Escribe el Ticker de Yahoo Finance (ej: DOT-USD)", value="DOT-USD")
        else:
            bt_ticker = ASSET_MAP[selected_asset_bt]
            st.info(f"Ticker seleccionado: `{bt_ticker}`")

        bt_capital = st.number_input("Capital Inicial ($)", value=10000.0, key="bt_cap")
    
    with col_bt2:
        bt_start_date = st.date_input("Fecha Inicio", value=date.today() - timedelta(days=365*2))
        bt_leverage = st.slider("Apalancamiento Inicial", 1.1, 4.0, 2.0, 0.1, key="bt_lev")
    
    with col_bt3:
        bt_threshold = st.number_input("Umbral Defensa (%)", value=15.0, step=1.0, key="bt_th") / 100.0
        run_bt = st.button("🚀 Ejecutar Backtest", type="primary")

    # --- LÓGICA DEL BACKTEST ---
    if run_bt:
        with st.spinner(f"Descargando datos de {bt_ticker} y simulando..."):
            try:
                # 1. Descarga de datos
                df_hist = yf.download(bt_ticker, start=bt_start_date, end=date.today(), progress=False)
                
                if df_hist.empty:
                    st.error(f"⚠️ No se encontraron datos para {bt_ticker}. Puede que el activo sea muy nuevo o el ticker sea incorrecto.")
                    st.stop()
                
                # Aplanar columnas
                if isinstance(df_hist.columns, pd.MultiIndex):
                    df_hist.columns = df_hist.columns.get_level_values(0)

                # 2. Inicialización
                start_price = float(df_hist.iloc[0]['Close']) 
                collateral_usd = bt_capital * bt_leverage
                debt_usd = collateral_usd - bt_capital 
                collateral_amt = collateral_usd / start_price 
                
                ltv_liq = c_ltv 
                liq_price = debt_usd / (collateral_amt * ltv_liq)
                
                target_ratio = liq_price / start_price 
                
                history = []
                total_injected = 0.0
                is_liquidated = False
                liquidated_date = None
                
                # 3. Bucle
                for date_idx, row in df_hist.iterrows():
                    # Manejo seguro de NaN
                    if pd.isna(row['Close']): continue

                    high = float(row['High'])
                    low = float(row['Low'])
                    close = float(row['Close'])
                    
                    trigger_price = liq_price * (1 + bt_threshold)
                    action = "Hold"
                    cost_today = 0.0
                    
                    # A. Lógica de Defensa
                    if low <= trigger_price and not is_liquidated:
                        defense_price = trigger_price 
                        if float(row['Open']) < trigger_price:
                             defense_price = float(row['Open']) 
                        
                        if defense_price <= liq_price:
                            is_liquidated = True
                            liquidated_date = date_idx
                            action = "LIQUIDATED ☠️"
                        else:
                            target_liq_new = defense_price * target_ratio
                            needed_collat_amt = debt_usd / (target_liq_new * ltv_liq)
                            add_collat_amt = needed_collat_amt - collateral_amt
                            
                            if add_collat_amt > 0:
                                cost_today = add_collat_amt * defense_price
                                collateral_amt += add_collat_amt
                                total_injected += cost_today
                                liq_price = target_liq_new 
                                action = "DEFENSA 🛡️"
                    
                    # B. Check Liquidación Post-Defensa
                    if low <= liq_price and not is_liquidated:
                         is_liquidated = True
                         liquidated_date = date_idx
                         action = "LIQUIDATED ☠️"

                    # C. Valoración
                    pos_value = (collateral_amt * close) - debt_usd
                    total_invested = bt_capital + total_injected
                    
                    history.append({
                        "Fecha": date_idx,
                        "Precio Cierre": close,
                        "Acción": action,
                        "Liq Price": liq_price if not is_liquidated else 0,
                        "Inversión Acumulada": total_invested,
                        "Valor Estrategia": pos_value if not is_liquidated else 0,
                        "Valor HODL": (bt_capital / start_price) * close 
                    })
                    
                    if is_liquidated:
                        break
                
                # 4. Resultados
                if not history:
                    st.error("No hay suficientes datos históricos para generar el backtest.")
                    st.stop()

                df_res = pd.DataFrame(history)
                df_res.set_index("Fecha", inplace=True)
                
                last_row = df_res.iloc[-1]
                final_roi_strat = ((last_row['Valor Estrategia'] - last_row['Inversión Acumulada']) / last_row['Inversión Acumulada']) * 100
                final_roi_hodl = ((last_row['Valor HODL'] - bt_capital) / bt_capital) * 100
                
                kpi1, kpi2, kpi3, kpi4 = st.columns(4)
                kpi1.metric("Estado Final", "LIQUIDADO" if is_liquidated else "VIVO", delta_color="inverse" if is_liquidated else "normal")
                kpi2.metric("Capital Inyectado", f"${total_injected:,.0f}")
                kpi3.metric("ROI Estrategia", f"{final_roi_strat:.2f}%", f"${last_row['Valor Estrategia']:,.0f}")
                kpi4.metric("ROI HODL", f"{final_roi_hodl:.2f}%", delta=f"{final_roi_strat - final_roi_hodl:.2f}% vs Strat")

                # --- GRÁFICO ---
                st.markdown(f"##### 📈 Evolución con {bt_ticker}")
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(x=df_res.index, y=df_res["Valor Estrategia"], 
                                         mode='lines', name='Valor Estrategia', line=dict(color='green', width=2), fill='tozeroy', fillcolor='rgba(0, 255, 0, 0.1)'))
                
                fig.add_trace(go.Scatter(x=df_res.index, y=df_res["Inversión Acumulada"], 
                                         mode='lines', name='Total Invertido', line=dict(color='red', dash='dash')))
                
                fig.add_trace(go.Scatter(x=df_res.index, y=df_res["Valor HODL"], 
                                         mode='lines', name='Valor HODL', line=dict(color='gray', width=1)))

                defense_events = df_res[df_res["Acción"].str.contains("DEFENSA")]
                if not defense_events.empty:
                    fig.add_trace(go.Scatter(x=defense_events.index, y=defense_events["Valor Estrategia"],
                                             mode='markers', name='Inyección Defensa', marker=dict(color='orange', size=12, symbol='diamond')))

                st.plotly_chart(fig, use_container_width=True)
                
                if not defense_events.empty:
                    st.markdown("##### 🛡️ Detalle de Defensas")
                    st.dataframe(defense_events[["Precio Cierre", "Liq Price", "Inversión Acumulada", "Valor Estrategia"]].style.format("${:,.2f}"), use_container_width=True)

            except Exception as e:
                st.error(f"Error durante el proceso: {e}")
