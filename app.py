import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from datetime import date, timedelta
from web3 import Web3
import requests 

# --- Configuración de la Página ---
st.set_page_config(page_title="Looping Master - MultiChain", layout="wide")

st.title("🛡️ Looping Master: Calculadora, Backtest & On-Chain")

# --- CONFIGURACIÓN DE REDES (ADDRESS PROVIDERS) ---
# En lugar de apuntar al Pool, apuntamos al "AddressesProvider" que es inmutable.
NETWORKS = {
    "Base": {
        "chain_id": 8453,
        "rpcs": ["https://mainnet.base.org", "https://base.drpc.org"],
        "provider_address": "0xe20fCBdBfFC4Dd138cE8b2E6FBb6CB49777ad64D"
    },
    "Arbitrum": {
        "chain_id": 42161,
        "rpcs": ["https://arb1.arbitrum.io/rpc", "https://rpc.ankr.com/arbitrum"],
        "provider_address": "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"
    },
    "Ethereum": {
        "chain_id": 1,
        "rpcs": ["https://eth.llamarpc.com", "https://rpc.ankr.com/eth"], 
        "provider_address": "0x2f39d218133AFaB8F2B819B1066c7E434Ad94E9e"
    },
    "Optimism": {
        "chain_id": 10,
        "rpcs": ["https://mainnet.optimism.io", "https://rpc.ankr.com/optimism"],
        "provider_address": "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"
    },
    "Polygon": {
        "chain_id": 137,
        "rpcs": ["https://polygon-rpc.com", "https://rpc.ankr.com/polygon"],
        "provider_address": "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"
    },
    "Avalanche": {
        "chain_id": 43114,
        "rpcs": ["https://api.avax.network/ext/bc/C/rpc"],
        "provider_address": "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"
    }
}

# ABI COMBINADO (Provider + Pool)
AAVE_ABI = [
    # Función para preguntar al Provider dónde está el Pool
    {
        "inputs": [],
        "name": "getPool",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    # Función para preguntar al Pool los datos del usuario
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
    "Bitcoin (WBTC/BTC)": "BTC-USD", "Ethereum (WETH/ETH)": "ETH-USD",
    "Arbitrum (ARB)": "ARB-USD", "Optimism (OP)": "OP-USD",
    "Polygon (MATIC)": "MATIC-USD", "Solana (SOL)": "SOL-USD",
    "Avalanche (AVAX)": "AVAX-USD", "Base (ETH)": "ETH-USD", 
    "Link (LINK)": "LINK-USD", "✍️ Otro (Escribir manual)": "MANUAL"
}

# --- FUNCIÓN DE CONEXIÓN ROBUSTA ---
def get_web3_session(rpc_url):
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    return Web3(Web3.HTTPProvider(rpc_url, session=session))

def connect_robust(network_name):
    config = NETWORKS[network_name]
    rpcs = config["rpcs"]
    
    # Inyectar secreto si existe
    secret_key = f"{network_name.upper()}_RPC_URL"
    if secret_key in st.secrets:
        rpcs.insert(0, st.secrets[secret_key])
        
    last_error = "No RPCs"
    
    for rpc in rpcs:
        try:
            w3 = get_web3_session(rpc)
            if w3.is_connected():
                if w3.eth.chain_id == config["chain_id"]:
                    return w3, rpc
        except Exception as e:
            last_error = str(e)
            continue
    return None, last_error

# TABS
tab_calc, tab_backtest, tab_onchain = st.tabs(["🧮 Calculadora", "📉 Backtest", "📡 Escáner On-Chain"])

# ==============================================================================
#  PESTAÑA 1: CALCULADORA (Restaurada)
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
#  PESTAÑA 2: MOTOR DE BACKTESTING (Restaurado)
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
#  PESTAÑA 3: ON-CHAIN SCANNER (MODO ADDRESS PROVIDER)
# ==============================================================================
with tab_onchain:
    st.markdown("### 📡 Escáner Aave V3 (Oficial - Provider Mode)")
    st.caption("Conecta directamente al registro oficial de Aave para encontrar tu posición.")
    
    col_net1, col_net2 = st.columns([1, 3])
    with col_net1:
        selected_network = st.selectbox("Red", list(NETWORKS.keys()))
    with col_net2:
        user_address = st.text_input("Wallet", placeholder="0x...")
    
    if st.button("🔍 Analizar"):
        if not user_address:
            st.warning("Falta dirección.")
        else:
            with st.spinner(f"Conectando a {selected_network}..."):
                w3, rpc_used = connect_robust(selected_network)
            
            if not w3:
                st.error(f"❌ Fallo total de conexión. Revisa si el RPC de {selected_network} está caído.")
                st.stop()
            
            try:
                # 1. Preparar dirección de Usuario
                valid_addr = w3.to_checksum_address(user_address)
                
                # 2. Conectar al PROVIDER (El Jefe)
                provider_addr_raw = NETWORKS[selected_network]["provider_address"]
                provider_addr = w3.to_checksum_address(provider_addr_raw)
                provider_contract = w3.eth.contract(address=provider_addr, abi=AAVE_ABI)
                
                with st.spinner("Preguntando al Provider dónde está el Pool..."):
                    # 3. Preguntar al Jefe: "¿Dónde está el Pool?"
                    actual_pool_address = provider_contract.functions.getPool().call()
                
                # 4. Conectar al POOL real
                pool_contract = w3.eth.contract(address=actual_pool_address, abi=AAVE_ABI)
                
                with st.spinner(f"Leyendo datos del Pool en {actual_pool_address[:10]}..."):
                    # 5. Obtener datos del usuario
                    data = pool_contract.functions.getUserAccountData(valid_addr).call()
                
                # Procesar
                col_usd = data[0] / 10**8
                debt_usd = data[1] / 10**8
                current_liq_threshold = data[3] / 10000 
                hf = data[5] / 10**18
                
                st.success(f"✅ Conectado a Chain ID: {w3.eth.chain_id} | RPC: {rpc_used[:30]}...")
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("HF", f"{hf:.2f}", delta="OK" if hf>1.1 else "Risk", delta_color="normal" if hf>1.1 else "inverse")
                m2.metric("Colateral", f"${col_usd:,.2f}")
                m3.metric("Deuda", f"${debt_usd:,.2f}")
                m4.metric("LT (Avg)", f"{current_liq_threshold:.2%}")
                
                # --- SIMULACIÓN DE DEFENSA ---
                st.divider()
                st.subheader("🛠️ Simular Estrategia de Defensa")
                
                c_s1, c_s2, c_s3 = st.columns(3)
                with c_s1:
                    sim_asset = st.selectbox("Activo Ref", list(ASSET_MAP.keys()))
                    s_tick = ASSET_MAP[sim_asset] if ASSET_MAP[sim_asset] != "MANUAL" else st.text_input("Ticker", "ETH-USD")
                with c_s2:
                    s_th = st.number_input("Umbral Defensa %", 15.0) / 100.0
                
                # Precio actual
                try:
                    curr_p = yf.Ticker(s_tick).history(period="1d")['Close'].iloc[-1]
                except:
                    curr_p = 0
                
                with c_s3:
                    st.metric(f"Precio {s_tick}", f"${curr_p:,.2f}")

                if curr_p > 0 and debt_usd > 0:
                    sim_col_amt = col_usd / curr_p
                    sim_liq = debt_usd / (sim_col_amt * current_liq_threshold)
                    # Colchón en %
                    cushion = (curr_p - sim_liq) / curr_p
                    
                    st.metric("Liquidación Estimada", f"${sim_liq:,.2f}", f"{cushion:.2%} Colchón")
                    
                    # Tabla cascada
                    s_targ_rat = sim_liq / curr_p
                    s_data = []
                    s_curr_c, s_curr_l, s_cum = sim_col_amt, sim_liq, 0.0
                    
                    for i in range(1, 6):
                        trig = s_curr_l * (1 + s_th)
                        targ = trig * s_targ_rat
                        need = debt_usd / (targ * current_liq_threshold)
                        add = max(0, need - s_curr_c)
                        cost = add * trig
                        s_cum += cost
                        s_curr_c += add
                        s_data.append({"Zona": i, "Activación": trig, "Añadir Colateral": add, "Costo $": cost, "Acumulado $": s_cum, "Nuevo Liq": targ})
                        s_curr_l = targ
                    
                    st.dataframe(pd.DataFrame(s_data).style.format({"Activación": "${:,.2f}", "Costo $": "${:,.0f}", "Acumulado $": "${:,.0f}", "Nuevo Liq": "${:,.2f}"}), use_container_width=True)

                elif debt_usd == 0:
                    st.success("Sin deuda activa.")

            except Exception as e:
                st.error(f"Error técnico: {e}")
