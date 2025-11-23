import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from datetime import date, timedelta
from web3 import Web3
import requests

# ==============================================================================
#  CONFIGURACIÓN DE LA PÁGINA
# ==============================================================================
st.set_page_config(page_title="Looping Master - Final", layout="wide")

st.title("🛡️ Looping Master: Calculadora, Backtest & On-Chain")

# ==============================================================================
#  1. CONFIGURACIÓN DE REDES Y CONTRATOS
# ==============================================================================

# Usamos 'pool_provider' (AddressProvider) para encontrar siempre la dirección correcta del Pool
# Esto evita errores si Aave actualiza sus contratos.
NETWORKS = {
    "Base": {
        "chain_id": 8453,
        "rpcs": [
            "https://base.drpc.org",
            "https://mainnet.base.org",
            "https://base-rpc.publicnode.com"
        ],
        "pool_provider": "0xe20fCBdBfFC4Dd138cE8b2E6FBb6CB49777ad64D"
    },
    "Arbitrum": {
        "chain_id": 42161,
        "rpcs": [
            "https://arb1.arbitrum.io/rpc",
            "https://rpc.ankr.com/arbitrum"
        ],
        "pool_provider": "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"
    },
    "Ethereum": {
        "chain_id": 1,
        "rpcs": [
            "https://eth.llamarpc.com",
            "https://rpc.ankr.com/eth"
        ], 
        "pool_provider": "0x2f39d218133AFaB8F2B819B1066c7E434Ad94E9e"
    },
    "Optimism": {
        "chain_id": 10,
        "rpcs": [
            "https://mainnet.optimism.io",
            "https://rpc.ankr.com/optimism"
        ],
        "pool_provider": "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"
    },
    "Polygon": {
        "chain_id": 137,
        "rpcs": [
            "https://polygon-rpc.com",
            "https://rpc.ankr.com/polygon"
        ],
        "pool_provider": "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"
    },
    "Avalanche": {
        "chain_id": 43114,
        "rpcs": [
            "https://api.avax.network/ext/bc/C/rpc"
        ],
        "pool_provider": "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"
    }
}

# ABI LIGERO (Solo lo necesario para conectar y leer totales)
AAVE_ABI = [
    # Función para preguntar al Provider dónde está el Pool
    {
        "inputs": [],
        "name": "getPool",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    # Función ligera getUserAccountData (Devuelve totales en USD base)
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

# Mapeo de activos para los selectores
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
#  2. FUNCIONES AUXILIARES (CONEXIÓN ROBUSTA)
# ==============================================================================

def get_web3_session(rpc_url):
    """Crea una sesión Web3 disfrazada de navegador Chrome para evitar bloqueos"""
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    # Timeout de 60s es suficiente para llamadas ligeras
    return Web3(Web3.HTTPProvider(rpc_url, session=s, request_kwargs={'timeout': 60}))

def connect_robust(network_name):
    """Intenta conectar rotando RPCs y priorizando Secrets"""
    config = NETWORKS[network_name]
    rpcs = config["rpcs"][:] # Copia de la lista para no modificar la original
    
    secret_key = f"{network_name.upper()}_RPC_URL"
    used_private = False
    
    # Inyectar secreto (Alchemy/Infura) si existe en los Secrets de Streamlit
    if secret_key in st.secrets:
        private_rpc = st.secrets[secret_key].strip().replace('"', '').replace("'", "")
        rpcs.insert(0, private_rpc)
        used_private = True
        
    for rpc in rpcs:
        try:
            w3 = get_web3_session(rpc)
            if w3.is_connected():
                # Verificación extra de Chain ID
                if w3.eth.chain_id == config["chain_id"]:
                    return w3, rpc, used_private
        except: 
            continue
    return None, None, False

# ==============================================================================
#  3. INTERFAZ DE USUARIO (PESTAÑAS)
# ==============================================================================

tab_calc, tab_backtest, tab_onchain = st.tabs(["🧮 Calculadora", "📉 Backtest", "📡 Escáner Real"])

# ------------------------------------------------------------------------------
#  PESTAÑA 1: CALCULADORA ESTÁTICA
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

    # Cálculos base
    c_collat_usd = c_capital * c_leverage
    c_debt_usd = c_collat_usd - c_capital
    c_collat_amt = c_collat_usd / c_price
    
    if c_collat_amt > 0 and c_ltv > 0:
        c_liq_price = c_debt_usd / (c_collat_amt * c_ltv)
        c_target_ratio = c_liq_price / c_price 
        c_cushion_pct = (c_price - c_liq_price) / c_price
    else:
        c_liq_price = 0
        c_target_ratio = 0
        c_cushion_pct = 0
    
    # Generación de tabla en cascada
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
        
        # Cálculos de ROI
        final_val = curr_collat * c_target
        net_prof = (final_val - c_debt_usd) - total_inv
        roi = (net_prof / total_inv) * 100 if total_inv > 0 else 0
        ratio = roi / (drop_pct * 100) if drop_pct > 0 else 0
        
        # Nuevo HF
        if c_debt_usd > 0:
            new_hf = ((curr_collat * trig_p) * c_ltv) / c_debt_usd
        else:
            new_hf = 999
        
        cascade_data.append({
            "Zona": f"#{i}", 
            "Precio Activación": trig_p, 
            "Caída (%)": drop_pct, 
            "Inversión Extra ($)": cost, 
            "Total Invertido ($)": total_inv, 
            "Nuevo P. Liq": targ_liq, 
            "Nuevo HF": new_hf,
            "Beneficio ($)": net_prof, 
            "ROI (%)": roi, 
            "Ratio": ratio
        })
        curr_liq = targ_liq

    df_calc = pd.DataFrame(cascade_data)
    
    st.divider()
    st.dataframe(df_calc.style.format({
        "Precio Activación": "${:,.2f}", 
        "Caída (%)": "{:.2%}", 
        "Inversión Extra ($)": "${:,.0f}", 
        "Total Invertido ($)": "${:,.0f}", 
        "Nuevo P. Liq": "${:,.2f}", 
        "Nuevo HF": "{:.2f}",
        "Beneficio ($)": "${:,.0f}", 
        "ROI (%)": "{:.2f}%", 
        "Ratio": "{:.2f}"
    }), use_container_width=True)
    
    # Informe Ejecutivo
    if not df_calc.empty:
        st.divider()
        last_row = df_calc.iloc[-1]
        st.markdown(f"""
        ### 📝 Informe Ejecutivo
        **Configuración Inicial:** Capital: **\${c_capital:,.0f}** | Apalancamiento: **{c_leverage}x** | Precio Liq. Inicial: **\${c_liq_price:,.2f}**.
        
        **Escenario Extremo:** Si el mercado cae un **{last_row['Caída (%)']:.1%}**, necesitarás haber inyectado un total de **\${last_row['Total Invertido ($)']-c_capital:,.0f}** para sobrevivir. Si tras eso el precio recupera al objetivo, tu ROI sería del **{last_row['ROI (%)']:.2f}%**.
        """)

# ------------------------------------------------------------------------------
#  PESTAÑA 2: MOTOR DE BACKTESTING
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
                
                ltv_liq = c_ltv # Usamos el LTV de la pestaña 1
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
#  PESTAÑA 3: ESCÁNER REAL (MODO ROBUSTO + DUAL CON MEMORIA)
# ------------------------------------------------------------------------------
with tab_onchain:
    st.markdown("### 📡 Escáner Aave V3 (Modo Seguro)")
    st.caption("Conexión ligera verificada. Elige tu modo de análisis abajo.")
    
    col_net1, col_net2 = st.columns([1, 3])
    with col_net1:
        selected_network = st.selectbox("Red", list(NETWORKS.keys()))
    with col_net2:
        user_address = st.text_input("Wallet Address (0x...)", placeholder="0x...")
    
    # --- GESTIÓN DE ESTADO (MEMORIA) ---
    if 'portfolio_data' not in st.session_state:
        st.session_state.portfolio_data = None

    if st.button("🔍 Analizar"):
        if not user_address:
            st.warning("Falta dirección")
        else:
            with st.spinner(f"Conectando a {selected_network}..."):
                w3, rpc_used, is_private = connect_robust(selected_network)
                if not w3:
                    st.error("Error conexión RPC"); st.stop()
                
                try:
                    # 1. Obtener Pool Real
                    prov_addr = w3.to_checksum_address(NETWORKS[selected_network]["pool_provider"])
                    prov_contract = w3.eth.contract(address=prov_addr, abi=AAVE_ABI)
                    pool_addr = prov_contract.functions.getPool().call()
                    
                    # 2. Llamada Ligera (getUserAccountData)
                    pool = w3.eth.contract(address=pool_addr, abi=AAVE_ABI)
                    data = pool.functions.getUserAccountData(w3.to_checksum_address(user_address)).call()
                    
                    # 3. Guardar en Memoria
                    st.session_state.portfolio_data = {
                        "col_usd": data[0] / 10**8,
                        "debt_usd": data[1] / 10**8,
                        "lt_avg": data[3] / 10000,
                        "hf": data[5] / 10**18,
                        "status_msg": f"🔒 Privado" if is_private else f"🌍 Público ({rpc_used[:20]}...)"
                    }
                except Exception as e:
                    st.error(f"Error de lectura: {e}")

    # --- MOSTRAR DATOS DESDE MEMORIA ---
    if st.session_state.portfolio_data:
        d = st.session_state.portfolio_data
        
        st.success(f"✅ Datos recibidos. Conexión: {d['status_msg']}")
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Salud (HF)", f"{d['hf']:.2f}", delta_color="normal" if d['hf']>1.1 else "inverse")
        m2.metric("Colateral Total", f"${d['col_usd']:,.2f}")
        m3.metric("Deuda Total", f"${d['debt_usd']:,.2f}")
        m4.metric("Liq. Threshold (Avg)", f"{d['lt_avg']:.2%}")
        
        if d['debt_usd'] > 0:
            st.divider()
            st.subheader("🛠️ Estrategia de Defensa")
            
            # --- SELECTOR DE MODO DE ESTRATEGIA ---
            mode = st.radio("Tipo de Posición:", 
                            ["🛡️ Activo Único (Detallado con Precios)", 
                             "💼 Multi-Colateral (Porcentajes Globales)"], 
                            horizontal=True)
            
            # MODO A: ACTIVO ÚNICO (Como Pestaña 1)
            if "Activo Único" in mode:
                c_sel, c_par = st.columns(2)
                with c_sel:
                    sim_asset = st.selectbox("¿Cuál es tu colateral principal?", list(ASSET_MAP.keys()), key="oc_asset")
                    ticker = ASSET_MAP[sim_asset] if ASSET_MAP[sim_asset] != "MANUAL" else st.text_input("Ticker", "ETH-USD", key="oc_tick")
                with c_par:
                    def_th = st.number_input("Umbral Defensa (%)", 15.0, step=1.0, key="oc_th") / 100.0
                    zones = st.slider("Zonas", 1, 10, 5, key="oc_z")
                    
                try:
                    curr_p = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
                    st.metric(f"Precio Mercado ({ticker})", f"${curr_p:,.2f}")
                    
                    # Ingeniería inversa: Asumimos que todo el colateral es de este activo
                    implied_amt = d['col_usd'] / curr_p
                    liq_price_real = d['debt_usd'] / (implied_amt * d['lt_avg'])
                    cushion = (curr_p - liq_price_real) / curr_p
                    st.metric("Precio Liquidación Actual", f"${liq_price_real:,.2f}", f"{cushion:.2%} Colchón")
                    
                    ratio_target = liq_price_real / curr_p
                    s_data = []
                    s_curr_c, s_curr_l, s_cum = implied_amt, liq_price_real, 0.0
                    
                    for i in range(1, zones+1):
                        trig = s_curr_l * (1 + def_th)
                        targ = trig * ratio_target
                        
                        # Cantidad necesaria para bajar liquidación al target
                        needed_amt = d['debt_usd'] / (targ * d['lt_avg'])
                        add_amt = max(0, needed_amt - s_curr_c)
                        
                        cost_usd = add_amt * trig # Costo al precio del trigger
                        s_cum += cost_usd
                        s_curr_c += add_amt
                        
                        # Nuevo HF al inyectar
                        new_col_usd = s_curr_c * trig
                        new_hf = (new_col_usd * d['lt_avg']) / d['debt_usd']
                        
                        s_data.append({
                            "Zona": f"#{i}", 
                            "Precio Activación": trig, 
                            "Inyectar (Tokens)": add_amt, 
                            "Costo ($)": cost_usd, 
                            "Acumulado ($)": s_cum, 
                            "Nuevo Liq": targ, 
                            "Nuevo HF": new_hf
                        })
                        s_curr_l = targ
                        
                    st.dataframe(pd.DataFrame(s_data).style.format({
                        "Precio Activación": "${:,.2f}", "Costo ($)": "${:,.0f}", 
                        "Acumulado ($)": "${:,.0f}", "Nuevo Liq": "${:,.2f}", 
                        "Nuevo HF": "{:.2f}", "Inyectar (Tokens)": "{:.4f}"
                    }), use_container_width=True)
                    
                except Exception as ex:
                    st.error(f"Error precio: {ex}")

            # MODO B: MULTI-COLATERAL (Porcentajes)
            else:
                st.info("Cálculo basado en caída porcentual global.")
                if (d['col_usd'] * d['lt_avg']) > 0:
                    max_drop = 1 - (d['debt_usd'] / (d['col_usd'] * d['lt_avg']))
                else:
                    max_drop = 0
                    
                st.metric("Margen Caída Mercado", f"{max_drop:.2%}", delta="Distancia Liq")
                
                target_hf = st.number_input("HF Objetivo tras defensa", 1.05, 2.0, 1.05, key="oc_target_hf")
                sim = []
                start = int(max_drop * 100)
                
                for d_step in range(start+2, start+52, 5):
                    drop = d_step/100.0
                    shock_col = d['col_usd'] * (1 - drop)
                    shock_hf = (shock_col * d['lt_avg']) / d['debt_usd']
                    
                    # Capital necesario (repagar deuda)
                    need = d['debt_usd'] - ((shock_col * d['lt_avg']) / target_hf)
                    if need < 0: need = 0
                    
                    final_hf = (shock_col * d['lt_avg']) / (d['debt_usd'] - need) if (d['debt_usd']-need)>0 else 999
                    
                    sim.append({
                        "Caída Mercado": f"-{d_step}%", 
                        "HF Riesgo": f"{shock_hf:.2f}", 
                        "Inyectar (USDC)": need, 
                        "Nuevo HF": f"{final_hf:.2f}"
                    })
                    
                st.dataframe(pd.DataFrame(sim).style.format({"Inyectar (USDC)": "${:,.2f}"}).background_gradient(subset=["Inyectar (USDC)"], cmap="Reds"), use_container_width=True)
                
        else:
            st.success("Sin deuda activa.")
