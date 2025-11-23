import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from datetime import date, timedelta

# --- Configuración de la Página ---
st.set_page_config(page_title="Looping Master - Calculator & Backtest", layout="wide")

st.title("🛡️ Looping Master: Calculadora & Backtesting")

# Usamos Tabs para separar la calculadora estática del backtest temporal
tab_calc, tab_backtest = st.tabs(["🧮 Calculadora de Escenarios", "📉 Backtest Histórico"])

# ==============================================================================
#  PESTAÑA 1: CALCULADORA DE ESCENARIOS (Tu código validado)
# ==============================================================================
with tab_calc:
    st.markdown("### Simulador Estático de Defensa")
    
    # --- Inputs Calculadora ---
    col_input1, col_input2, col_input3 = st.columns(3)
    with col_input1:
        c_asset = st.text_input("Activo", value="WBTC", key="c_asset")
        c_price = st.number_input("Precio Actual ($)", value=100000.0, step=100.0, key="c_price")
        c_target = st.number_input("Precio Objetivo ($)", value=130000.0, step=100.0, key="c_target")
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
    c_target_ratio = c_liq_price / c_price # Ratio a mantener
    
    # Bucle Cascada
    cascade_data = []
    curr_collat = c_collat_amt
    curr_liq = c_liq_price
    cum_cost = 0.0
    
    for i in range(1, c_zones + 1):
        trig_p = curr_liq * (1 + c_threshold)
        drop_pct = (c_price - trig_p) / c_price
        
        # Objetivo: Restaurar ratio
        targ_liq = trig_p * c_target_ratio
        
        # Colateral necesario
        need_col = c_debt_usd / (targ_liq * c_ltv)
        add_col = need_col - curr_collat
        cost = add_col * trig_p
        
        cum_cost += cost
        curr_collat += add_col
        total_inv = c_capital + cum_cost
        
        # ROI al target
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
    
    # Output Calculadora
    st.divider()
    st.dataframe(df_calc.style.format({
        "Precio Activación": "${:,.2f}", "Caída (%)": "{:.2%}", "Inversión Extra ($)": "${:,.0f}",
        "Total Invertido ($)": "${:,.0f}", "Nuevo P. Liq": "${:,.2f}", "Beneficio ($)": "${:,.0f}",
        "ROI (%)": "{:.2f}%", "Ratio": "{:.2f}"
    }), use_container_width=True)
    
    # Informe rápido
    if not df_calc.empty:
        last = df_calc.iloc[-1]
        st.info(f"🛡️ **Resumen:** Para aguantar una caída del **{last['Caída (%)']:.1%}** (Precio: ${last['Precio Activación']:,.0f}), necesitas tener listos **${last['Total Invertido ($)']:,.0f}** en total.")


# ==============================================================================
#  PESTAÑA 2: MOTOR DE BACKTESTING
# ==============================================================================
with tab_backtest:
    st.markdown("### 📉 Validación Histórica (Backtest)")
    st.caption("Comprueba cómo se habría comportado la estrategia en el pasado real.")

    # --- Inputs Backtest ---
    col_bt1, col_bt2, col_bt3 = st.columns(3)
    
    with col_bt1:
        # Ticker compatible con Yahoo Finance (BTC-USD, ETH-USD)
        bt_ticker = st.text_input("Ticker (Yahoo Finance)", value="BTC-USD")
        bt_capital = st.number_input("Capital Inicial ($)", value=10000.0, key="bt_cap")
    
    with col_bt2:
        bt_start_date = st.date_input("Fecha Inicio", value=date.today() - timedelta(days=365*1))
        bt_leverage = st.slider("Apalancamiento Inicial", 1.1, 4.0, 2.0, 0.1, key="bt_lev")
    
    with col_bt3:
        bt_threshold = st.number_input("Umbral Defensa (%)", value=15.0, step=1.0, key="bt_th") / 100.0
        # Checkbox para reinvertir o no (Simplificación: Asumimos NO reinversión, solo defensa)
        run_bt = st.button("🚀 Ejecutar Backtest", type="primary")

    # --- LÓGICA DEL BACKTEST ---
    if run_bt:
        with st.spinner(f"Descargando datos de {bt_ticker} y simulando..."):
            try:
                # 1. Descarga de datos
                df_hist = yf.download(bt_ticker, start=bt_start_date, end=date.today(), progress=False)
                if df_hist.empty:
                    st.error("No se encontraron datos. Revisa el Ticker (ej: BTC-USD).")
                    st.stop()
                
                # Aplanar columnas si es MultiIndex (problema común en nuevas versiones de yfinance)
                if isinstance(df_hist.columns, pd.MultiIndex):
                    df_hist.columns = df_hist.columns.get_level_values(0)

                # 2. Inicialización de Variables de Estado
                # Datos iniciales en T0 (Primer día del df)
                start_price = float(df_hist.iloc[0]['Close']) # Precio de entrada
                
                # Posición
                collateral_usd = bt_capital * bt_leverage
                debt_usd = collateral_usd - bt_capital # Deuda en USD (asumimos estable)
                collateral_amt = collateral_usd / start_price # Cantidad de BTC
                
                # Límites
                # Usamos el mismo LTV definido en la pestaña 1 o uno estándar
                ltv_liq = c_ltv 
                liq_price = debt_usd / (collateral_amt * ltv_liq)
                
                # Ratio Objetivo (El "ADN" de la estrategia: mantener el colchón relativo)
                target_ratio = liq_price / start_price 
                
                # Métricas de seguimiento
                history = []
                total_injected = 0.0
                is_liquidated = False
                liquidated_date = None
                
                # 3. BUCLE DÍA A DÍA
                for date_idx, row in df_hist.iterrows():
                    high = float(row['High'])
                    low = float(row['Low'])
                    close = float(row['Close'])
                    
                    # A. Chequeo de Liquidación (Game Over)
                    # Si el precio baja del Liq Price ANTES de que podamos defender (gap down fuerte)
                    # Asumimos defensa instantánea al tocar el trigger, pero si Low < Liq... riesgo.
                    # Simplificación: Si Low <= Liq Price Y Low < Trigger (obvio), checkeamos.
                    
                    trigger_price = liq_price * (1 + bt_threshold)
                    
                    action = "Hold"
                    cost_today = 0.0
                    
                    # Lógica: Si Low toca el Trigger, ejecutamos defensa.
                    if low <= trigger_price and not is_liquidated:
                        # Calculamos defensa
                        # Objetivo: Nuevo Liq Price que respete el target_ratio respecto al precio de trigger
                        # (Asumimos que defendemos AL PRECIO DEL TRIGGER, orden limitada)
                        defense_price = trigger_price 
                        
                        # Si el gap fue brutal y abrió por debajo del trigger, usamos el Open o Low
                        if float(row['Open']) < trigger_price:
                             defense_price = float(row['Open']) # Peor caso
                        
                        # Check fatal: ¿El precio de defensa ya es liquidación?
                        if defense_price <= liq_price:
                            is_liquidated = True
                            liquidated_date = date_idx
                            action = "LIQUIDATED ☠️"
                        else:
                            # Ejecutar Defensa
                            target_liq_new = defense_price * target_ratio
                            
                            # Colateral necesario para ese target
                            needed_collat_amt = debt_usd / (target_liq_new * ltv_liq)
                            add_collat_amt = needed_collat_amt - collateral_amt
                            
                            if add_collat_amt > 0:
                                cost_today = add_collat_amt * defense_price # Costo en USD
                                
                                # Actualizar Estado
                                collateral_amt += add_collat_amt
                                total_injected += cost_today
                                liq_price = target_liq_new # Nuevo suelo
                                action = "DEFENSA 🛡️"
                    
                    # B. Check Liquidación Post-Defensa (o si no hubo defensa pero bajó mucho)
                    if low <= liq_price and not is_liquidated:
                         is_liquidated = True
                         liquidated_date = date_idx
                         action = "LIQUIDATED ☠️"

                    # C. Valoración Diaria
                    # Valor Posición = (Colateral * Precio Cierre) - Deuda
                    pos_value = (collateral_amt * close) - debt_usd
                    total_invested = bt_capital + total_injected
                    
                    history.append({
                        "Fecha": date_idx,
                        "Precio Cierre": close,
                        "Acción": action,
                        "Liq Price": liq_price if not is_liquidated else 0,
                        "Trigger Price": trigger_price if not is_liquidated else 0,
                        "Colateral Total": collateral_amt,
                        "Inversión Acumulada": total_invested,
                        "Valor Estrategia": pos_value if not is_liquidated else 0,
                        "Valor HODL": (bt_capital / start_price) * close # Simulación simple de HODL
                    })
                    
                    if is_liquidated:
                        break # Salimos del bucle si morimos
                
                # 4. Resultados y Gráficas
                df_res = pd.DataFrame(history)
                df_res.set_index("Fecha", inplace=True)
                
                # --- KPIS ---
                last_row = df_res.iloc[-1]
                final_roi_strat = ((last_row['Valor Estrategia'] - last_row['Inversión Acumulada']) / last_row['Inversión Acumulada']) * 100
                final_roi_hodl = ((last_row['Valor HODL'] - bt_capital) / bt_capital) * 100
                
                kpi1, kpi2, kpi3, kpi4 = st.columns(4)
                kpi1.metric("Estado Final", "LIQUIDADO" if is_liquidated else "VIVO", delta_color="inverse" if is_liquidated else "normal")
                kpi2.metric("Capital Total Inyectado", f"${total_injected:,.0f}", help="Dinero extra añadido para defender")
                kpi3.metric("ROI Estrategia", f"{final_roi_strat:.2f}%", f"${last_row['Valor Estrategia']:,.0f} Valor Final")
                kpi4.metric("ROI HODL (Comparativa)", f"{final_roi_hodl:.2f}%", delta=f"{final_roi_strat - final_roi_hodl:.2f}% vs Strat")

                # --- GRÁFICO ---
                st.markdown("##### 📈 Evolución del Patrimonio vs Inversión")
                fig = go.Figure()
                
                # Área de Valor Estrategia
                fig.add_trace(go.Scatter(x=df_res.index, y=df_res["Valor Estrategia"], 
                                         mode='lines', name='Valor Estrategia (Neto)', line=dict(color='green', width=2), fill='tozeroy', fillcolor='rgba(0, 255, 0, 0.1)'))
                
                # Línea de Inversión Total (Escalera)
                fig.add_trace(go.Scatter(x=df_res.index, y=df_res["Inversión Acumulada"], 
                                         mode='lines', name='Capital Invertido (Tu Bolsillo)', line=dict(color='red', dash='dash')))
                
                # Línea HODL
                fig.add_trace(go.Scatter(x=df_res.index, y=df_res["Valor HODL"], 
                                         mode='lines', name='Valor HODL (Sin Loop)', line=dict(color='gray', width=1)))

                # Marcadores de Defensa
                defense_events = df_res[df_res["Acción"].str.contains("DEFENSA")]
                if not defense_events.empty:
                    fig.add_trace(go.Scatter(x=defense_events.index, y=defense_events["Valor Estrategia"],
                                             mode='markers', name='Inyección Defensa', marker=dict(color='orange', size=10, symbol='shield')))

                st.plotly_chart(fig, use_container_width=True)
                
                # --- TABLA DE EVENTOS ---
                st.markdown("##### 🛡️ Diario de Operaciones (Eventos de Defensa)")
                if not defense_events.empty:
                    st.dataframe(defense_events[["Precio Cierre", "Liq Price", "Colateral Total", "Inversión Acumulada", "Valor Estrategia"]].style.format("${:,.2f}"), use_container_width=True)
                else:
                    st.success("¡Increíble! La estrategia nunca necesitó defensa en este periodo.")

            except Exception as e:
                st.error(f"Error en el Backtest: {e}")
                st.info("Asegúrate de haber añadido 'yfinance' a tu requirements.txt")
