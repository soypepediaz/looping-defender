import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from datetime import date, timedelta
from web3 import Web3
import requests

# --- Configuración de la Página ---
st.set_page_config(page_title="Looping Master - Final", layout="wide")

st.title("🛡️ Looping Master: Calculadora, Backtest & On-Chain")

# ==============================================================================
#  1. CONFIGURACIÓN DE REDES Y CONTRATOS
# ==============================================================================

# Usamos 'pool_provider' (AddressProvider) para encontrar siempre la dirección correcta del Pool
NETWORKS = {
    "Base": {
        "chain_id": 8453,
        "rpcs": ["https://base.drpc.org", "https://mainnet.base.org"],
        "pool_provider": "0xe20fCBdBfFC4Dd138cE8b2E6FBb6CB49777ad64D"
    },
    "Arbitrum": {
        "chain_id": 42161,
        "rpcs": ["https://arb1.arbitrum.io/rpc", "https://rpc.ankr.com/arbitrum"],
        "pool_provider": "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"
    },
    "Ethereum": {
        "chain_id": 1,
        "rpcs": ["https://eth.llamarpc.com", "https://rpc.ankr.com/eth"], 
        "pool_provider": "0x2f39d218133AFaB8F2B819B1066c7E434Ad94E9e"
    },
    "Optimism": {
        "chain_id": 10,
        "rpcs": ["https://mainnet.optimism.io", "https://rpc.ankr.com/optimism"],
        "pool_provider": "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"
    },
    "Polygon": {
        "chain_id": 137,
        "rpcs": ["https://polygon-rpc.com", "https://rpc.ankr.com/polygon"],
        "pool_provider": "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"
    },
    "Avalanche": {
        "chain_id": 43114,
        "rpcs": ["https://api.avax.network/ext/bc/C/rpc"],
        "pool_provider": "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"
    }
}

# ABI MIXTO (Ligero)
AAVE_ABI = [
    # Función para preguntar al Provider dónde está el Pool
    {
        "inputs": [],
        "name": "getPool",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    # Función ligera getUserAccountData (Funciona siempre)
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

ASSET_MAP = {
    "Bitcoin (WBTC/BTC)": "BTC-USD", 
    "Ethereum (WETH/ETH)": "ETH-USD", 
    "Arbitrum (ARB)": "ARB-USD", 
    "Base (ETH)": "ETH-USD", 
    "Solana (SOL)": "SOL-USD", 
    "Link (LINK)": "LINK-USD", 
    "✍️ Otro": "MANUAL"
}

# ==============================================================================
#  2. FUNCIONES AUXILIARES
# ==============================================================================

def get_web3_session(rpc_url):
    """Sesión Web3 con Headers de navegador y Timeout seguro"""
    s = requests.Session()
    s.headers.update({'User-Agent': 'Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36'})
    return Web3(Web3.HTTPProvider(rpc_url, session=s, request_kwargs={'timeout': 30}))

def connect_robust(network_name):
    """Conexión inteligente: Secrets > Lista Pública"""
    config = NETWORKS[network_name]
    rpcs = config["rpcs"][:] # Copia
    
    secret_key = f"{network_name.upper()}_RPC_URL"
    used_private = False
    
    # Inyección de Secreto
    if secret_key in st.secrets:
        private_rpc = st.secrets[secret_key].strip().replace('"', '').replace("'", "")
        rpcs.insert(0, private_rpc)
        used_private = True
        
    for rpc in rpcs:
        try:
            w3 = get_web3_session(rpc)
            if w3.is_connected():
                if w3.eth.chain_id == config["chain_id"]:
                    return w3, rpc, used_private
        except: continue
    return None, None, False

# ==============================================================================
#  3. INTERFAZ DE USUARIO (TABS)
# ==============================================================================

tab_calc, tab_backtest, tab_onchain = st.tabs(["🧮 Calculadora", "📉 Backtest", "📡 Escáner Real (Modo Seguro)"])

# ------------------------------------------------------------------------------
#  PESTAÑA 1: CALCULADORA (CÓDIGO ORIGINAL COMPLETO)
# ------------------------------------------------------------------------------
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
    
    if c_collat_amt > 0 and c_ltv > 0:
        c_liq_price = c_debt_usd / (c_collat_amt * c_ltv)
        c_target_ratio = c_liq_price / c_price 
        c_cushion_pct = (c_price - c_liq_price) / c_price
    else:
        c_liq_price = 0; c_target_ratio = 0; c_cushion_pct = 0
    
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
    
    if not df_calc.empty:
        st.divider()
        last_row = df_calc.iloc[-1]
        st.markdown(f"""
        ### 📝 Informe Ejecutivo
        **Configuración Inicial:** Capital: **\${c_capital:,.0f}** | Apalancamiento: **{c_leverage}x** | Precio Liq. Inicial: **\${c_liq_price:,.2f}**.
        
        **Escenario Extremo:** Si el mercado cae un **{last_row['Caída (%)']:.1%}**, necesitarás haber inyectado un total de **\${last_row['Total Invertido ($)']-c_capital:,.0f}** para sobrevivir. Si tras eso el precio recupera al objetivo, tu ROI sería del **{last_row['ROI (%)']:.2f}%**.
        """)

# ------------------------------------------------------------------------------
#  PESTAÑA 2: BACKTEST (CÓDIGO ORIGINAL COMPLETO)
# ------------------------------------------------------------------------------
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
                
                ltv_liq = c_ltv # Heredado de la pestaña 1 por coherencia
                liq_price = debt_usd / (collateral_amt * ltv_liq)
                target_ratio = liq_price / start_price 
                
                history = []
                total_injected = 0.0
                is_liquidated = False
                
                for date_idx, row in df_hist.iterrows():
                    if pd.isna(row['Close']): continue
                    low, close = float(row['Low']), float(row['Close'])
                    
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
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Resultado", "LIQUIDADO" if is_liquidated else "VIVO")
                c2.metric("Inyectado Total", f"${total_injected:,.0f}")
                c3.metric("Valor Final", f"${df_res.iloc[-1]['Valor Estrategia']:,.0f}")
                
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

# ------------------------------------------------------------------------------
#  PESTAÑA 3: ESCÁNER REAL (MODO ROBUSTO / LIGERO)
# ------------------------------------------------------------------------------
with tab_onchain:
    st.markdown("### 📡 Escáner Aave V3 (Modo Seguro)")
    st.caption("Utiliza una conexión ligera verificada para evitar bloqueos en Base/L2s. Compatible con Multi-Colateral.")
    
    col_net1, col_net2 = st.columns([1, 3])
    with col_net1:
        selected_network = st.selectbox("Red", list(NETWORKS.keys()))
    with col_net2:
        user_address = st.text_input("Wallet Address (0x...)", placeholder="0x...")
    
    if st.button("🔍 Analizar"):
        if not user_address:
            st.warning("Falta dirección")
        else:
            with st.spinner(f"Conectando a {selected_network}..."):
                w3, rpc_used, is_private = connect_robust(selected_network)
                if not w3:
                    st.error("Error de conexión RPC. Revisa tus Secrets.")
                    st.stop()
                
                try:
                    # 1. Obtener Pool Real (Preguntando al Jefe)
                    provider_addr = w3.to_checksum_address(NETWORKS[selected_network]["pool_provider"])
                    provider_contract = w3.eth.contract(address=provider_addr, abi=AAVE_ABI)
                    pool_addr = provider_contract.functions.getPool().call()
                    
                    # 2. Llamada Ligera (getUserAccountData) - ESTA NO FALLA
                    pool_contract = w3.eth.contract(address=pool_addr, abi=AAVE_ABI)
                    valid_addr = w3.to_checksum_address(user_address)
                    data = pool_contract.functions.getUserAccountData(valid_addr).call()
                    
                    # 3. Procesar Datos
                    col_usd = data[0] / 10**8
                    debt_usd = data[1] / 10**8
                    lt_avg = data[3] / 10000 # Umbral de liquidación promedio ponderado
                    hf = data[5] / 10**18
                    
                    # Estado de conexión
                    status_msg = f"🔒 Privado (Alchemy)" if is_private else f"🌍 Público ({rpc_used[:20]}...)"
                    st.success(f"✅ Datos recibidos. Conexión: {status_msg}")
                    
                    # Métricas
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Salud (HF)", f"{hf:.2f}", delta_color="normal" if hf>1.1 else "inverse")
                    m2.metric("Colateral Total", f"${col_usd:,.2f}")
                    m3.metric("Deuda Total", f"${debt_usd:,.2f}")
                    m4.metric("Liq. Threshold (Avg)", f"{lt_avg:.2%}", help="Media ponderada de tus activos")
                    
                    # Lógica de Defensa Multi-Colateral
                    if debt_usd > 0:
                        st.divider()
                        st.subheader("📉 Simulación de Estrés (Portafolio Global)")
                        st.info("Calculamos cuánto capital necesitas si **todo tu portafolio** pierde valor simultáneamente.")
                        
                        # Cálculo de caída máxima
                        # Col * (1-drop) * LT = Deuda  ->  1-drop = Deuda/(Col*LT)
                        if (col_usd * lt_avg) > 0:
                            max_drop = 1 - (debt_usd / (col_usd * lt_avg))
                        else:
                            max_drop = 0
                            
                        st.metric("Margen Caída Mercado", f"{max_drop:.2%}", delta="Distancia a Liquidación")
                        
                        # Tabla de Defensa
                        st.markdown("#### 🛡️ Tabla de Defensa (Inyección en USD)")
                        target_hf = st.number_input("HF Objetivo tras defensa", 1.05, 2.0, 1.05)
                        
                        sim_data = []
                        start_drop = int(max_drop * 100)
                        # Escenarios desde la liquidación + 5% hasta + 55%
                        for d in range(start_drop + 5, start_drop + 55, 5):
                            drop = d / 100.0
                            
                            # Escenario de Crash
                            shock_col = col_usd * (1 - drop)
                            shock_hf = (shock_col * lt_avg) / debt_usd
                            
                            # Capital necesario
                            # (ShockCol * LT) / (Deuda - Cap) = TargetHF
                            needed = debt_usd - ((shock_col * lt_avg) / target_hf)
                            if needed < 0: needed = 0
                            
                            # Nuevo HF real
                            new_debt = debt_usd - needed
                            final_hf = (shock_col * lt_avg) / new_debt if new_debt > 0 else 999.0
                            
                            sim_data.append({
                                "Caída Mercado": f"-{d}%",
                                "HF (Riesgo)": f"{shock_hf:.2f}",
                                "Inyectar (USDC)": needed,
                                "Nuevo HF": f"{final_hf:.2f}"
                            })
                            
                        st.dataframe(
                            pd.DataFrame(sim_data).style.format({"Inyectar (USDC)": "${:,.2f}"})
                            .background_gradient(subset=["Inyectar (USDC)"], cmap="Reds"),
                            use_container_width=True
                        )
                    else:
                        st.success("Posición sin deuda. Estás 100% seguro.")
                        
                except Exception as e:
                    st.error(f"Error técnico: {e}")
                    if "transact" in str(e):
                        st.warning("El nodo rechazó la llamada. Intenta recargar.")
