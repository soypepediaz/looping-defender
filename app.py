import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from datetime import date, timedelta
from web3 import Web3
from web3.middleware import geth_poa_middleware # <--- IMPORTANTE

# --- Configuración de la Página ---
st.set_page_config(page_title="Looping Master - MultiChain", layout="wide")

st.title("🛡️ Looping Master: Calculadora, Backtest & On-Chain")

# --- CONFIGURACIÓN MULTI-CADENA (AAVE V3) ---
# Usamos Ankr Protocol por estabilidad + Middleware PoA
NETWORKS = {
    "Arbitrum": {
        "rpc": "https://rpc.ankr.com/arbitrum",
        "pool_address": "0x794a61358D6845594F94dc1DB02A252b5b4814aD"
    },
    "Ethereum Mainnet": {
        "rpc": "https://rpc.ankr.com/eth", 
        "pool_address": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
    },
    "Optimism": {
        "rpc": "https://rpc.ankr.com/optimism",
        "pool_address": "0x794a61358D6845594F94dc1DB02A252b5b4814aD"
    },
    "Polygon (Matic)": {
        "rpc": "https://rpc.ankr.com/polygon",
        "pool_address": "0x794a61358D6845594F94dc1DB02A252b5b4814aD"
    },
    "Base": {
        "rpc": "https://rpc.ankr.com/base", 
        "pool_address": "0xA238Dd80C259a72e81d7e4664a98015D33062B7f"
    },
    "Avalanche": {
        "rpc": "https://rpc.ankr.com/avalanche",
        "pool_address": "0x794a61358D6845594F94dc1DB02A252b5b4814aD"
    }
}

# ABI Mínimo
AAVE_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
        "name": "getUserAccountData",
        "outputs": [
            {"internalType": "uint256", "name": "totalCollateralBase", "type": "uint256"},
            {"internalType": "uint256", "name": "totalDebtBase", "type": "uint256"},
            {"internalType": "uint256", "name": "availableBorrowsBase", "type": "uint256"},
            {"internalType": "uint256", "name": "currentLiquidationThreshold", "type": "uint256"},
            {"internalType": "uint256", "name": "ltv", "type": "uint256"},
            {"internalType": "uint256", "name": "healthFactor", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

# --- DICCIONARIO DE ACTIVOS ---
ASSET_MAP = {
    "Bitcoin (WBTC/BTC)": "BTC-USD",
    "Ethereum (WETH/ETH)": "ETH-USD",
    "Arbitrum (ARB)": "ARB-USD",
    "Optimism (OP)": "OP-USD",
    "Polygon (MATIC)": "MATIC-USD",
    "Solana (SOL)": "SOL-USD",
    "Avalanche (AVAX)": "AVAX-USD",
    "Base (ETH)": "ETH-USD", 
    "Link (LINK)": "LINK-USD",
    "✍️ Otro (Escribir manual)": "MANUAL"
}

# TABS
tab_calc, tab_backtest, tab_onchain = st.tabs(["🧮 Calculadora", "📉 Backtest", "📡 Escáner On-Chain"])

# ==============================================================================
#  PESTAÑA 1: CALCULADORA
# ==============================================================================
with tab_calc:
    st.markdown("### Simulador Estático de Defensa")
    
    col_input1, col_input2, col_input3 = st.columns(3)
    
    with col_input1:
        selected_asset_calc = st.selectbox("Seleccionar Activo", list(ASSET_MAP.keys()), key="sel_asset_c")
        if ASSET_MAP[selected_asset_calc] == "MANUAL":
            c_asset_name = st.text_input("Ticker", value="PEPE", key="c_asset_man")
        else:
            c_asset_name = selected_asset_calc.split("(")[1].replace(")", "")
            
        c_price = st.number_input(f"Precio Actual {c_asset_name} ($)", value=100000.0, step=100.0, key="c_price")
        c_target = st.number_input(f"Precio Objetivo ($)", value=130000.0, step=100.0, key="c_target")
        
    with col_input2:
        c_capital = st.number_input("Capital Inicial ($)", value=10000.0, step=1000.0, key="c_capital")
        c_leverage = st.slider("Apalancamiento (x)", 1.1, 5.0, 2.0, 0.1, key="c_lev")
        
    with col_input3:
        c_ltv = st.slider("LTV Liquidación (%)", 50, 95, 78, 1, key="c_ltv") / 100.0
        c_threshold = st.number_input("Umbral Defensa (%)", value=15.0, step=1.0, key="c_th") / 100.0
        c_zones = st.slider("Zonas de Defensa", 1, 10, 5, key="c_zones")

    # Cálculos
    c_collat_usd = c_capital * c_leverage
    c_debt_usd = c_collat_usd - c_capital
    c_collat_amt = c_collat_usd / c_price
    
    # Liq Inicial
    if c_collat_amt > 0 and c_ltv > 0:
        c_liq_price = c_debt_usd / (c_collat_amt * c_ltv)
        c_target_ratio = c_liq_price / c_price 
        c_cushion_pct = (c_price - c_liq_price) / c_price
    else:
        c_liq_price = 0
        c_target_ratio = 0
        c_cushion_pct = 0
    
    # Bucle Cascada
    cascade_data = []
    curr_collat = c_collat_amt
    curr_liq = c_liq_price
    cum_cost = 0.0
    
    for i in range(1, c_zones + 1):
        trig_p = curr_liq * (1 + c_threshold)
        drop_pct = (c_price - trig_p) / c_price
        targ_liq = trig_p * c_target_ratio
        
        if targ_liq > 0:
            need_col = c_debt_usd / (targ_liq * c_ltv)
            add_col = need_col - curr_collat
        else:
            add_col = 0
            
        cost = add_col * trig_p
        cum_cost += cost
        curr_collat += add_col
        total_inv = c_capital + cum_cost
        
        final_val = curr_collat * c_target
        net_prof = (final_val - c_debt_usd) - total_inv
        
        roi = (net_prof / total_inv) * 100 if total_inv > 0 else 0
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
    
    st.divider()
    st.dataframe(df_calc.style.format({
        "Precio Activación": "${:,.2f}", "Caída (%)": "{:.2%}", "Inversión Extra ($)": "${:,.0f}",
        "Total Invertido ($)": "${:,.0f}", "Nuevo P. Liq": "${:,.2f}", "Beneficio ($)": "${:,.0f}",
        "ROI (%)": "{:.2f}%", "Ratio": "{:.2f}"
    }), use_container_width=True)


# ==============================================================================
#  PESTAÑA 2: MOTOR DE BACKTESTING
# ==============================================================================
with tab_backtest:
    st.markdown("### 📉 Validación Histórica")
    
    col_bt1, col_bt2, col_bt3 = st.columns(3)
    with col_bt1:
        selected_asset_bt = st.selectbox("Seleccionar Activo Histórico", list(ASSET_MAP.keys()), key="sel_asset_bt")
        if ASSET_MAP[selected_asset_bt] == "MANUAL":
            bt_ticker = st.text_input("Ticker Yahoo", value="DOT-USD")
        else:
            bt_ticker = ASSET_MAP[selected_asset_bt]
        bt_capital = st.number_input("Capital Inicial ($)", value=10000.0, key="bt_cap")
    
    with col_bt2:
        bt_start_date = st.date_input("Fecha Inicio", value=date.today() - timedelta(days=365*2))
        bt_leverage = st.slider("Apalancamiento Inicial", 1.1, 4.0, 2.0, 0.1, key="bt_lev")
    
    with col_bt3:
        bt_threshold = st.number_input("Umbral Defensa (%)", value=15.0, step=1.0, key="bt_th") / 100.0
        run_bt = st.button("🚀 Ejecutar Backtest", type="primary")

    if run_bt:
        with st.spinner(f"Simulando {bt_ticker}..."):
            try:
                df_hist = yf.download(bt_ticker, start=bt_start_date, end=date.today(), progress=False)
                if df_hist.empty:
                    st.error("Sin datos.")
                    st.stop()
                
                if isinstance(df_hist.columns, pd.MultiIndex):
                    df_hist.columns = df_hist.columns.get_level_values(0)

                start_date_actual = df_hist.index[0].date()
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
                
                for date_idx, row in df_hist.iterrows():
                    if pd.isna(row['Close']): continue
                    high, low, close = float(row['High']), float(row['Low']), float(row['Close'])
                    
                    trigger_price = liq_price * (1 + bt_threshold)
                    action, cost_today = "Hold", 0.0
                    
                    if low <= trigger_price and not is_liquidated:
                        defense_price = min(float(row['Open']), trigger_price) 
                        
                        if defense_price <= liq_price:
                            is_liquidated = True
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
                    
                    if low <= liq_price and not is_liquidated: is_liquidated = True

                    pos_value = (collateral_amt * close) - debt_usd
                    history.append({
                        "Fecha": date_idx,
                        "Acción": action,
                        "Liq Price": liq_price if not is_liquidated else 0,
                        "Inversión Acumulada": bt_capital + total_injected,
                        "Valor Estrategia": pos_value if not is_liquidated else 0,
                        "Valor HODL": (bt_capital / start_price) * close 
                    })
                    if is_liquidated: break
                
                df_res = pd.DataFrame(history).set_index("Fecha")
                last_row = df_res.iloc[-1]
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Resultado", "LIQUIDADO" if is_liquidated else "VIVO")
                c2.metric("Inyectado Total", f"${total_injected:,.0f}")
                c3.metric("Valor Final Estrategia", f"${last_row['Valor Estrategia']:,.0f}")
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_res.index, y=df_res["Valor Estrategia"], name='Estrategia', fill='tozeroy', line=dict(color='green')))
                fig.add_trace(go.Scatter(x=df_res.index, y=df_res["Inversión Acumulada"], name='Inversión', line=dict(color='red', dash='dash')))
                
                events = df_res[df_res["Acción"].str.contains("DEFENSA")]
                if not events.empty:
                    fig.add_trace(go.Scatter(x=events.index, y=events["Valor Estrategia"], mode='markers', name='Defensa', marker=dict(color='orange', size=10, symbol='diamond')))
                
                st.plotly_chart(fig, use_container_width=True)
                
                st.divider()
                st.subheader("🏁 Datos de Entrada")
                st.write(f"Inicio: {start_date_actual} | Precio Entrada: ${start_price:,.2f} | Deuda Inicial: ${debt_usd:,.0f}")

            except Exception as e:
                st.error(f"Error: {e}")

# ==============================================================================
#  PESTAÑA 3: ON-CHAIN SCANNER (MULTI-CHAIN)
# ==============================================================================
with tab_onchain:
    st.markdown("### 📡 Escáner de Posiciones Aave V3 (Multi-Chain)")
    st.caption("Analiza tu salud, deuda y calcula defensas en cualquier red EVM soportada.")

    # 1. SELECTOR DE RED
    col_net1, col_net2 = st.columns([1, 3])
    with col_net1:
        selected_network = st.selectbox("Selecciona la Red", list(NETWORKS.keys()))
        rpc_url = NETWORKS[selected_network]["rpc"]
        pool_address = NETWORKS[selected_network]["pool_address"]
    
    with col_net2:
        user_address = st.text_input("Dirección de Wallet (0x...)", placeholder="0x...")
    
    # Botón de análisis
    if st.button("🔍 Analizar Posición On-Chain"):
        if not user_address:
            st.warning("Por favor, introduce una dirección.")
        else:
            try:
                # 1. Conexión Web3 dinámica
                w3 = Web3(Web3.HTTPProvider(rpc_url))
                
                # --- CORRECCIÓN CRÍTICA: MIDDLEWARE PARA L2s (Base, Matic, Optimism) ---
                w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                
                if not w3.is_connected():
                    st.error(f"No se pudo conectar al nodo de {selected_network}. La red puede estar congestionada.")
                    st.stop()
                
                try:
                    valid_address = w3.to_checksum_address(user_address)
                    valid_pool = w3.to_checksum_address(pool_address)
                except:
                    st.error("Dirección inválida.")
                    st.stop()

                # 2. Llamada al contrato
                aave_contract = w3.eth.contract(address=valid_pool, abi=AAVE_ABI)
                
                with st.spinner(f"Leyendo Aave V3 en {selected_network}..."):
                    user_data = aave_contract.functions.getUserAccountData(valid_address).call()
                
                # 3. Procesar Datos (Aave V3 devuelve 8 decimales en modo base USD)
                total_collateral_usd = user_data[0] / 10**8
                total_debt_usd = user_data[1] / 10**8
                current_liq_threshold = user_data[3] / 10000 
                health_factor = user_data[5] / 10**18
                
                # --- MOSTRAR RESULTADOS ---
                st.success(f"✅ Datos obtenidos correctamente de {selected_network}")
                
                met1, met2, met3, met4 = st.columns(4)
                met1.metric("Health Factor", f"{health_factor:.2f}", 
                            delta="Peligro" if health_factor < 1.1 else "Seguro", 
                            delta_color="normal" if health_factor > 1.1 else "inverse")
                met2.metric("Colateral Total", f"${total_collateral_usd:,.2f}")
                met3.metric("Deuda Total", f"${total_debt_usd:,.2f}")
                met4.metric("Umbral Liq. (Avg)", f"{current_liq_threshold:.2%}")
                
                st.divider()
                
                # --- CONECTAR CON SIMULADOR ---
                st.subheader("🛠️ Simular Estrategia de Defensa")
                
                col_sim1, col_sim2, col_sim3 = st.columns(3)
                
                with col_sim1:
                    sim_asset = st.selectbox("Activo de Referencia", list(ASSET_MAP.keys()), key="sim_asset")
                    if ASSET_MAP[sim_asset] == "MANUAL":
                        sim_ticker = st.text_input("Ticker Manual", "ETH-USD")
                    else:
                        sim_ticker = ASSET_MAP[sim_asset]
                
                with col_sim2:
                    # Input para modificar el umbral de defensa
                    sim_threshold_input = st.number_input("Umbral de Defensa (%)", value=15.0, step=1.0, min_value=1.0, max_value=50.0) / 100.0

                # Obtener precio y calcular
                try:
                    ticker_data = yf.Ticker(sim_ticker)
                    current_market_price = ticker_data.history(period="1d")['Close'].iloc[-1]
                except:
                    current_market_price = 0
                
                with col_sim3:
                    st.metric(f"Precio Mercado ({sim_ticker})", f"${current_market_price:,.2f}")

                # --- CÁLCULO DE LIQUIDACIÓN Y TABLA ---
                if current_market_price > 0 and total_debt_usd > 0:
                    
                    # 1. Calcular Precio de Liquidación Actual (Estimado)
                    sim_collat_amt = total_collateral_usd / current_market_price
                    sim_liq_price = total_debt_usd / (sim_collat_amt * current_liq_threshold)
                    
                    # --- CAMBIO APLICADO: Mostrar Colchón en % ---
                    cushion_pct = (current_market_price - sim_liq_price) / current_market_price
                    
                    st.metric("Precio Liquidación Actual (Est.)", f"${sim_liq_price:,.2f}", 
                              delta=f"{cushion_pct:.2%} Colchón de Liquidación", delta_color="normal")
                    
                    st.markdown("#### 🛡️ Plan de Defensa Generado")
                    
                    sim_target_ratio = sim_liq_price / current_market_price
                    
                    sim_cascade = []
                    sim_curr_collat = sim_collat_amt
                    sim_curr_liq = sim_liq_price
                    sim_cum_cost = 0.0
                    
                    for i in range(1, 6): 
                        trig = sim_curr_liq * (1 + sim_threshold_input)
                        targ = trig * sim_target_ratio
                        
                        need_c = total_debt_usd / (targ * current_liq_threshold)
                        add_c = need_c - sim_curr_collat 
                        
                        if add_c < 0: add_c = 0
                            
                        cost = add_c * trig 
                        
                        sim_cum_cost += cost
                        sim_curr_collat += add_c
                        
                        sim_cascade.append({
                            "Zona": f"Defensa #{i}",
                            "Precio Activación": trig,
                            "Colateral a Añadir": add_c,
                            "Costo ($)": cost,
                            "Total Acumulado ($)": sim_cum_cost,
                            "Nuevo P. Liq": targ
                        })
                        sim_curr_liq = targ
                        
                    df_sim = pd.DataFrame(sim_cascade)
                    st.dataframe(df_sim.style.format({
                        "Precio Activación": "${:,.2f}", "Colateral a Añadir": "{:.4f}",
                        "Costo ($)": "${:,.0f}", "Total Acumulado ($)": "${:,.0f}",
                        "Nuevo P. Liq": "${:,.2f}"
                    }), use_container_width=True)
                    
                elif total_debt_usd == 0:
                    st.success("Esta billetera no tiene deuda activa. ¡Estás a salvo!")
                else:
                    st.warning("No se pudo obtener el precio del activo de referencia.")

            except Exception as e:
                st.error(f"Error conectando a {selected_network}: {e}")
                st.info("Inténtalo de nuevo. Los nodos públicos a veces se saturan.")
