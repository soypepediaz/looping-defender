import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from datetime import date, timedelta
from web3 import Web3
import requests

# --- Configuración de la Página ---
st.set_page_config(page_title="Looping Master - Portfolio Pro", layout="wide")

st.title("🛡️ Looping Master: Calculadora, Backtest & On-Chain")

# ==============================================================================
#  1. CONFIGURACIÓN DE REDES Y CONTRATOS
# ==============================================================================

# Diccionario de Redes con RPCs robustos y direcciones de contratos Aave V3
NETWORKS = {
    "Base": {
        "chain_id": 8453,
        "rpcs": [
            "https://base.drpc.org",
            "https://mainnet.base.org", 
            "https://base-rpc.publicnode.com"
        ],
        "pool_address_provider": "0xe20fCBdBfFC4Dd138cE8b2E6FBb6CB49777ad64D",
        "ui_pool_data_provider": "0x2d8A3C5677189723C4cB8873CfC9E899d6317760"
    },
    "Arbitrum": {
        "chain_id": 42161,
        "rpcs": ["https://arb1.arbitrum.io/rpc", "https://rpc.ankr.com/arbitrum"],
        "pool_address_provider": "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb",
        "ui_pool_data_provider": "0x145291d4eD5Af6A539112d69D89875634b92e7D2"
    },
    "Ethereum": {
        "chain_id": 1,
        "rpcs": ["https://eth.llamarpc.com", "https://rpc.ankr.com/eth"], 
        "pool_address_provider": "0x2f39d218133AFaB8F2B819B1066c7E434Ad94E9e",
        "ui_pool_data_provider": "0x91c0eA31b49B69Ea18607702c5d9aC360bf3dE7d"
    },
    "Optimism": {
        "chain_id": 10,
        "rpcs": ["https://mainnet.optimism.io", "https://rpc.ankr.com/optimism"],
        "pool_address_provider": "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb",
        "ui_pool_data_provider": "0xbd83DdBE37fc91923d59C8c1E0bDe0CccCa332d5"
    },
    "Polygon": {
        "chain_id": 137,
        "rpcs": ["https://polygon-rpc.com", "https://rpc.ankr.com/polygon"],
        "pool_address_provider": "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb",
        "ui_pool_data_provider": "0xC69728f11E9E6127733751c8410432913123acf1"
    },
    "Avalanche": {
        "chain_id": 43114,
        "rpcs": ["https://api.avax.network/ext/bc/C/rpc"],
        "pool_address_provider": "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb",
        "ui_pool_data_provider": "0xF53837E394524028942E03708334277894963337"
    }
}

# ABI para UiPoolDataProvider (Lectura masiva de datos)
UI_ABI = [
    {
        "inputs": [
            {"internalType": "contract IPoolAddressesProvider", "name": "provider", "type": "address"},
            {"internalType": "address", "name": "user", "type": "address"}
        ],
        "name": "getUserReservesData",
        "outputs": [
            {
                "components": [
                    {"internalType": "address", "name": "underlyingAsset", "type": "address"},
                    {"internalType": "uint256", "name": "scaledATokenBalance", "type": "uint256"},
                    {"internalType": "bool", "name": "usageAsCollateralEnabledOnUser", "type": "bool"},
                    {"internalType": "uint256", "name": "scaledVariableDebt", "type": "uint256"},
                ],
                "internalType": "struct IUiPoolDataProviderV3.UserReserveData[]",
                "name": "",
                "type": "tuple[]"
            },
            {"internalType": "uint8", "name": "", "type": "uint8"} 
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "contract IPoolAddressesProvider", "name": "provider", "type": "address"}],
        "name": "getReservesData",
        "outputs": [
            {
                "components": [
                    {"internalType": "address", "name": "underlyingAsset", "type": "address"},
                    {"internalType": "string", "name": "name", "type": "string"},
                    {"internalType": "string", "name": "symbol", "type": "string"},
                    {"internalType": "uint256", "name": "decimals", "type": "uint256"},
                    {"internalType": "uint256", "name": "baseLTVasCollateral", "type": "uint256"},
                    {"internalType": "uint256", "name": "reserveLiquidationThreshold", "type": "uint256"},
                    {"internalType": "uint256", "name": "reserveLiquidationBonus", "type": "uint256"},
                    {"internalType": "uint256", "name": "priceInMarketReferenceCurrency", "type": "uint256"}
                ],
                "internalType": "struct IUiPoolDataProviderV3.AggregatedReserveData[]",
                "name": "",
                "type": "tuple[]"
            },
            {
                "components": [
                    {"internalType": "uint256", "name": "marketReferenceCurrencyUnit", "type": "uint256"},
                    {"internalType": "int256", "name": "marketReferenceCurrencyPriceInUsd", "type": "int256"},
                    {"internalType": "int256", "name": "networkBaseTokenPriceInUsd", "type": "int256"},
                    {"internalType": "uint8", "name": "networkBaseTokenPriceDecimals", "type": "uint8"}
                ],
                "internalType": "struct IUiPoolDataProviderV3.BaseCurrencyInfo",
                "name": "",
                "type": "tuple"
            }
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

# ==============================================================================
#  2. FUNCIONES AUXILIARES (CONEXIÓN Y LÓGICA)
# ==============================================================================

def get_web3_session(rpc_url):
    """Crea una sesión con User-Agent de navegador para evitar bloqueos."""
    s = requests.Session()
    s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
    return Web3(Web3.HTTPProvider(rpc_url, session=s))

def connect_robust(network_name):
    """Intenta conectar rotando RPCs y usando Secretos si existen."""
    config = NETWORKS[network_name]
    rpcs = config["rpcs"]
    
    # Inyectar secreto (Alchemy/Infura) si existe en la configuración
    secret_key = f"{network_name.upper()}_RPC_URL"
    if secret_key in st.secrets:
        rpcs.insert(0, st.secrets[secret_key])
        
    for rpc in rpcs:
        try:
            w3 = get_web3_session(rpc)
            if w3.is_connected():
                if w3.eth.chain_id == config["chain_id"]:
                    return w3, rpc
        except: continue
    return None, None

def process_user_data(w3, network, user_address):
    """Lógica principal para extraer y procesar el portafolio de Aave."""
    config = NETWORKS[network]
    ui_provider_addr = w3.to_checksum_address(config["ui_pool_data_provider"])
    pool_provider_addr = w3.to_checksum_address(config["pool_address_provider"])
    
    ui_contract = w3.eth.contract(address=ui_provider_addr, abi=UI_ABI)
    
    # 1. Obtener DATOS GLOBALES (Precios, LTVs) - Con GAS MANUAL aumentado
    reserves_data, currency_info = ui_contract.functions.getReservesData(pool_provider_addr).call({'gas': 30000000})
    
    base_currency_unit = currency_info[0]
    base_currency_price_usd = currency_info[1] / (10 ** 8) 
    
    reserves_map = {}
    for r in reserves_data:
        asset = r[0]
        price = (r[7] / base_currency_unit) * base_currency_price_usd 
        reserves_map[asset] = {
            "symbol": r[2], "decimals": r[3],
            "ltv": r[4] / 10000, "lt": r[5] / 10000,
            "price_usd": price
        }

    # 2. Obtener DATOS DEL USUARIO - Con GAS MANUAL aumentado
    user_reserves, _ = ui_contract.functions.getUserReservesData(pool_provider_addr, user_address).call({'gas': 30000000})
    
    portfolio = []
    total_collateral_usd = 0
    total_debt_usd = 0
    weighted_lt_numerator = 0
    
    for u in user_reserves:
        asset = u[0]
        if asset not in reserves_map: continue
        market = reserves_map[asset]
        decimals = market["decimals"]
        
        # Calcular montos (simplificado)
        col_amt = u[1] / (10 ** decimals)
        debt_amt = u[3] / (10 ** decimals)
        
        col_val = col_amt * market["price_usd"]
        debt_val = debt_amt * market["price_usd"]
        
        # Filtro de saldos vacíos o polvo (< $1)
        if col_val > 1 or debt_val > 1:
            portfolio.append({
                "Activo": market["symbol"],
                "Colateral": col_amt,
                "Valor Colateral ($)": col_val,
                "Deuda": debt_amt,
                "Valor Deuda ($)": debt_val,
                "LT (%)": market["lt"],
                "Precio ($)": market["price_usd"]
            })
            
            if u[2] and col_val > 0: # Si está habilitado como colateral
                total_collateral_usd += col_val
                weighted_lt_numerator += col_val * market["lt"]
            total_debt_usd += debt_val

    avg_lt = weighted_lt_numerator / total_collateral_usd if total_collateral_usd > 0 else 0
    hf = (total_collateral_usd * avg_lt) / total_debt_usd if total_debt_usd > 0 else 999.0
        
    return portfolio, total_collateral_usd, total_debt_usd, avg_lt, hf

# ==============================================================================
#  3. INTERFAZ DE USUARIO (TABS)
# ==============================================================================

tab_calc, tab_backtest, tab_onchain = st.tabs(["🧮 Calculadora", "📉 Backtest", "📡 Escáner Portafolio Real"])

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

# ------------------------------------------------------------------------------
#  PESTAÑA 3: ESCÁNER DE PORTAFOLIO (VERSIÓN PRO CON GAS FIX)
# ------------------------------------------------------------------------------
with tab_onchain:
    st.markdown("### 📡 Escáner de Portafolio Aave V3 (Multi-Colateral)")
    st.caption("Detecta automáticamente todos tus activos y simula una caída global del mercado.")

    col_net1, col_net2 = st.columns([1, 3])
    with col_net1:
        selected_network = st.selectbox("Red", list(NETWORKS.keys()))
    with col_net2:
        user_address_input = st.text_input("Wallet Address (0x...)", placeholder="0x...")
        
    if st.button("🔍 Analizar Portafolio"):
        if not user_address_input:
            st.warning("Introduce una dirección")
        else:
            with st.spinner(f"Conectando a {selected_network} y descargando datos masivos..."):
                # Usamos la conexión robusta
                w3, rpc = connect_robust(selected_network)
                if not w3:
                    st.error("⚠️ Todos los nodos públicos gratuitos están saturados.")
                    st.info("Para usar esta función avanzada en Base/Arbitrum, necesitas una clave gratuita de Alchemy en los Secrets de Streamlit.")
                    st.stop()
                
                try:
                    valid_addr = w3.to_checksum_address(user_address_input)
                    portfolio, tot_col, tot_debt, avg_lt, hf = process_user_data(w3, selected_network, valid_addr)
                    
                    st.success(f"✅ Datos cargados vía {rpc[:25]}...")
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Health Factor", f"{hf:.2f}", delta="Riesgo" if hf < 1.1 else "Seguro", delta_color="normal" if hf > 1.1 else "inverse")
                    m2.metric("Colateral Total", f"${tot_col:,.2f}")
                    m3.metric("Deuda Total", f"${tot_debt:,.2f}")
                    m4.metric("Umbral Liq. (Avg)", f"{avg_lt:.2%}", help="Promedio ponderado del Liquidation Threshold")
                    
                    st.divider()
                    
                    st.subheader("💼 Composición del Portafolio")
                    if portfolio:
                        st.dataframe(pd.DataFrame(portfolio).style.format({"Colateral": "{:.4f}", "Valor Colateral ($)": "${:,.2f}", "Deuda": "{:.4f}", "Valor Deuda ($)": "${:,.2f}", "LT (%)": "{:.1%}", "Precio ($)": "${:,.2f}"}), use_container_width=True)
                    else: st.warning("No se encontraron activos.")
                    
                    if tot_debt > 0:
                        st.divider()
                        st.subheader("📉 Simulación: Caída General del Mercado")
                        if (tot_col * avg_lt) > 0: liquidation_drop = 1 - (tot_debt / (tot_col * avg_lt))
                        else: liquidation_drop = 0
                        st.metric("Margen de Caída hasta Liquidación", f"{liquidation_drop:.2%}", delta="Distancia de Seguridad", delta_color="normal")
                        
                        st.markdown("#### 🛡️ Plan de Defensa (Inyección de Capital)")
                        target_hf = st.number_input("Health Factor Objetivo tras defensa", value=1.05, step=0.05, min_value=1.01)
                        sim_data = []
                        start_drop = int(liquidation_drop * 100)
                        for drop_pct in range(start_drop + 5, start_drop + 55, 5):
                            drop = drop_pct / 100.0
                            shocked_col = tot_col * (1 - drop)
                            shocked_hf = (shocked_col * avg_lt) / tot_debt
                            needed_capital = tot_debt - ((shocked_col * avg_lt) / target_hf)
                            if needed_capital < 0: needed_capital = 0
                            new_debt = tot_debt - needed_capital
                            final_hf = (shocked_col * avg_lt) / new_debt if new_debt > 0 else 999.0
                            sim_data.append({"Caída Mercado": f"-{drop_pct}%", "HF (Sin Defensa)": f"{shocked_hf:.2f}", "Capital a Inyectar ($)": needed_capital, "Nuevo HF": f"{final_hf:.2f}"})
                        st.dataframe(pd.DataFrame(sim_data).style.format({"Capital a Inyectar ($)": "${:,.2f}"}).background_gradient(subset=["Capital a Inyectar ($)"], cmap="Reds"), use_container_width=True)

                except Exception as e:
                    st.error(f"Error procesando datos: {e}")
                    st.warning("Si ves un error de 'transact', es posible que el nodo público haya rechazado la consulta por ser muy pesada. Intenta usar una clave de Alchemy.")
