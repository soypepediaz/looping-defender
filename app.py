import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from datetime import date, timedelta
from web3 import Web3
import requests
from wallet_connect import wallet_connect

# ==============================================================================
#  CONFIGURACIÓN DE LA PÁGINA Y ESTILOS
# ==============================================================================
st.set_page_config(
    page_title="Looping Master - Campamento DeFi",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS para limpiar la interfaz (Ocultar marcas de Streamlit)
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stDeployButton {display:none;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# ==============================================================================
#  0. CONFIGURACIÓN DE MARKETING Y ACCESO (NFTs + MOOSEND)
# ==============================================================================

# 1. Configuración Moosend
MOOSEND_LIST_ID = "75c61863-63dc-4fd3-9ed8-856aee90d04a"

def add_subscriber_moosend(name, email):
    """Envía el suscriptor a la lista de Moosend vía API"""
    try:
        # Verificar si existe la API Key en los secretos
        if "MOOSEND_API_KEY" not in st.secrets:
            return False, "Falta configuración de API Key en Secrets."
            
        api_key = st.secrets["MOOSEND_API_KEY"]
        
        # Endpoint de suscripción de Moosend
        url = f"https://api.moosend.com/v3/subscribers/{MOOSEND_LIST_ID}/subscribe.json?apikey={api_key}"
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        payload = {
            "Name": name,
            "Email": email,
            "HasExternalDoubleOptIn": False # False para evitar el email de confirmación doble
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            return True, "Success"
        else:
            # Intentar leer el error
            try:
                error_msg = response.json().get("Error", "Unknown Error")
            except:
                error_msg = str(response.status_code)
            return False, error_msg
            
    except Exception as e:
        return False, str(e)

# 2. Configuración NFT Gating (Arbitrum)
ALLOWED_NFT_CONTRACTS = {
    "Membresía": "0xF4820467171695F4d2760614C77503147A9CB1E8",
    "Inconfiscable": "0x8d8731994A082626E2BcFd47F0623e685251e70D"
}
REQUIRED_BALANCE = 1 

# ABI Híbrido para NFT (Soporta activeBalanceOf y balanceOf estándar)
NFT_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "owner", "type": "address"}], 
        "name": "balanceOf", 
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], 
        "stateMutability": "view", "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "user", "type": "address"}], 
        "name": "activeBalanceOf", 
        "outputs": [{"internalType": "uint256", "name": "bal", "type": "uint256"}], 
        "stateMutability": "view", "type": "function"
    }
]

# ==============================================================================
#  1. CONFIGURACIÓN DE REDES (AAVE V3)
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

# ABI Ligero Aave (AddressProvider + UserData)
AAVE_ABI = [
    {
        "inputs": [],
        "name": "getPool",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
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
#  2. FUNCIONES AUXILIARES (WEB3)
# ==============================================================================

def get_web3_session(rpc_url):
    """Crea una sesión Web3 disfrazada de navegador Chrome"""
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    # Timeout extendido a 60s para evitar cortes en redes congestionadas
    return Web3(Web3.HTTPProvider(rpc_url, session=s, request_kwargs={'timeout': 60}))

def connect_robust(network_name):
    """Intenta conectar rotando RPCs y priorizando Secrets"""
    config = NETWORKS[network_name]
    rpcs = config["rpcs"][:] # Hacemos copia para no modificar la original
    
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
                # Verificamos el Chain ID para estar seguros
                if w3.eth.chain_id == config["chain_id"]:
                    return w3, rpc, used_private
        except: 
            continue
            
    return None, None, False

def process_user_data(w3, network, user_address):
    """
    Lógica ligera para obtener datos del usuario.
    Ya no usamos UiPoolDataProvider para evitar timeouts en Base.
    """
    # Placeholder: Esta función se llama directamente dentro de la Pestaña 3 
    # para tener acceso a las variables de sesión y evitar duplicidades.
    pass 

# ==============================================================================
#  3. BARRA LATERAL Y CONTROL DE ACCESO
# ==============================================================================

with st.sidebar:
    # Logo o imagen del Campamento (Placeholder)
    st.image("https://placehold.co/200x80/PNG?text=Campamento+DeFi", use_container_width=True)
    st.markdown("---")
    st.markdown("### 🔐 Acceso Socios")
    
    # Botón de Wallet Connect
    wallet_address = wallet_connect(label="wallet", key="login_btn")
    
    st.markdown("---")
    st.caption("Conecta tu wallet en Arbitrum para verificar tu NFT.")

has_access = False

# Lógica de Verificación de NFT
if wallet_address:
    try:
        # Conectamos a Arbitrum (donde viven tus contratos)
        w3_arb, _, _ = connect_robust("Arbitrum")
        
        if w3_arb:
            valid_contracts = []
            
            # Revisamos cada contrato permitido
            for name, contract_addr in ALLOWED_NFT_CONTRACTS.items():
                try:
                    nft_contract = w3_arb.eth.contract(address=w3_arb.to_checksum_address(contract_addr), abi=NFT_ABI)
                    target = w3_arb.to_checksum_address(wallet_address)
                    
                    # INTENTO 1: Chequear 'activeBalanceOf' (Tiene en cuenta caducidad)
                    try:
                        balance = nft_contract.functions.activeBalanceOf(target).call()
                    except:
                        # INTENTO 2: Fallback a 'balanceOf' estándar si el contrato es antiguo o diferente
                        balance = nft_contract.functions.balanceOf(target).call()
                    
                    if balance >= REQUIRED_BALANCE:
                        valid_contracts.append(name)
                except:
                    continue # Si falla la lectura de un contrato, pasamos al siguiente
            
            if len(valid_contracts) > 0:
                has_access = True
                st.sidebar.success(f"✅ Acceso Verificado\n\n({', '.join(valid_contracts)})")
            else:
                st.sidebar.error("❌ Sin Acceso.")
                st.sidebar.caption("No se detectó ningún NFT activo en esta wallet.")
                
    except Exception as e:
        st.sidebar.warning(f"Error de verificación: {e}")

# ==============================================================================
#  4. ESTRUCTURA DE PESTAÑAS (PÚBLICO VS PRIVADO)
# ==============================================================================

# Definimos las pestañas primero
tab_home, tab_calc, tab_backtest, tab_onchain = st.tabs([
    "🏠 Inicio", 
    "🧮 Calculadora", 
    "📉 Backtest", 
    "📡 Escáner Real"
])

# ------------------------------------------------------------------------------
#  PESTAÑA 0: PORTADA (VISIBLE PARA TODOS)
# ------------------------------------------------------------------------------
with tab_home:
    col_hero_L, col_hero_R = st.columns([2, 1])
    
    with col_hero_L:
        st.title("🛡️ Domina el Looping en DeFi")
        st.markdown("""
        ### Maximiza tus rendimientos sin morir en el intento.
        
        Bienvenido a **Looping Master**, la herramienta definitiva para analizar, proyectar y 
        defender tus posiciones apalancadas en Aave y otros protocolos.
        
        **¿Qué puedes hacer aquí?**
        * 🧮 **Calculadora:** Proyecta rentabilidades y puntos de liquidación.
        * 📉 **Backtest:** Valida tu estrategia con datos históricos reales.
        * 📡 **Escáner:** Audita tu cartera real en Blockchain y simula "Crash Tests".
        """)
        
        if has_access:
            st.success("✅ Tienes acceso completo. Navega por las pestañas superiores.")
        else:
            st.info("🔒 **Contenido Bloqueado:** Conecta tu wallet con el NFT del Campamento para acceder.")

    with col_hero_R:
        st.markdown("### ⛺ Campamento DeFi")
        st.markdown("Tu comunidad de Estrategias On-Chain.")
        st.metric("Nivel de Riesgo", "Gestionado", delta="Alto Rendimiento")

    st.divider()

    # Sección de Captación (Lead Magnet)
    st.markdown("### 🚀 ¿Quieres recibir más estrategias como esta?")
    
    c_form_1, c_form_2 = st.columns([3, 2])
    
    with c_form_1:
        st.markdown("""
        Esta herramienta es solo la punta del iceberg. En el **Campamento DeFi** compartimos:
        - Estrategias de Yield Farming avanzadas.
        - Alertas de seguridad y gestión de riesgo.
        - Herramientas exclusivas para miembros.
        
        **Únete gratis a nuestra Newsletter y recibe el "Manual de Supervivencia DeFi".**
        """)
        
        # Gráfico Demo (Solo visual)
        demo_df = pd.DataFrame({
            "Caída": ["-10%", "-20%", "-30%", "-35% (LIQ)", "-40%"],
            "Salud": [1.45, 1.30, 1.15, 1.00, 0.90]
        })
        st.line_chart(demo_df.set_index("Caída"))
        
    with c_form_2:
        with st.form("lead_magnet_form"):
            st.write("**Suscríbete al Campamento:**")
            name_input = st.text_input("Nombre", placeholder="Tu nombre")
            email_input = st.text_input("Tu mejor Email", placeholder="tu@email.com")
            
            submitted = st.form_submit_button("📩 Unirme y Recibir Manual", type="primary")
            
            if submitted:
                if email_input and "@" in email_input:
                    with st.spinner("Enviando a la base central..."):
                        success, msg = add_subscriber_moosend(name_input, email_input)
                        
                    if success:
                        st.success(f"¡Bienvenido al Campamento, {name_input}! Revisa tu bandeja de entrada.")
                        st.balloons()
                    else:
                        st.error(f"Hubo un error al suscribirte: {msg}")
                else:
                    st.error("Por favor, introduce un email válido.")

    st.divider()
    st.caption("Desarrollado con ❤️ por el equipo de Campamento DeFi. DYOR.")

# ------------------------------------------------------------------------------
#  BLOQUEO DE SEGURIDAD (STOP)
# ------------------------------------------------------------------------------
if not has_access:
    # Si no tiene acceso, mostramos mensajes de bloqueo en las otras pestañas y paramos
    for tab in [tab_calc, tab_backtest, tab_onchain]:
        with tab:
            st.warning("🔒 **Contenido Bloqueado**")
            st.markdown("Esta herramienta es exclusiva para miembros del Campamento DeFi.")
            st.markdown("Por favor, conecta tu wallet en la barra lateral para verificar tu NFT.")
    
    st.stop() # DETIENE LA EJECUCIÓN DEL SCRIPT AQUÍ PARA NO SOCIOS

# ==============================================================================
#  A PARTIR DE AQUÍ: SOLO SOCIOS VERIFICADOS (CÓDIGO COMPLETO)
# ==============================================================================

# ------------------------------------------------------------------------------
#  PESTAÑA 1: CALCULADORA ESTÁTICA
# ------------------------------------------------------------------------------
with tab_calc:
    st.markdown("### 🧮 Simulador Estático de Defensa")
    
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
        
        # Métricas financieras
        total_inv = c_capital + cum_cost
        final_val = curr_collat * c_target
        net_prof = (final_val - c_debt_usd) - total_inv
        
        if total_inv > 0:
            roi = (net_prof / total_inv) * 100
        else:
            roi = 0
            
        if drop_pct > 0:
            ratio = roi / (drop_pct * 100)
        else:
            ratio = 0
        
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
    st.dataframe(
        df_calc.style.format({
            "Precio Activación": "${:,.2f}", 
            "Caída (%)": "{:.2%}", 
            "Inversión Extra ($)": "${:,.0f}", 
            "Total Invertido ($)": "${:,.0f}", 
            "Nuevo P. Liq": "${:,.2f}", 
            "Nuevo HF": "{:.2f}",
            "Beneficio ($)": "${:,.0f}", 
            "ROI (%)": "{:.2f}%", 
            "Ratio": "{:.2f}"
        }), 
        use_container_width=True
    )
    
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
                
                # Variables iniciales
                collateral_usd = bt_capital * bt_leverage
                debt_usd = collateral_usd - bt_capital 
                collateral_amt = collateral_usd / start_price 
                
                ltv_liq = c_ltv # Heredado de Tab 1 para coherencia
                liq_price = debt_usd / (collateral_amt * ltv_liq)
                target_ratio = liq_price / start_price 
                
                history = []
                total_injected = 0.0
                is_liquidated = False
                
                for date_idx, row in df_hist.iterrows():
                    if pd.isna(row['Close']): continue
                    
                    low_val = float(row['Low'])
                    close_val = float(row['Close'])
                    open_val = float(row['Open'])
                    
                    trigger_price = liq_price * (1 + bt_threshold)
                    action = "Hold"
                    
                    if low_val <= trigger_price and not is_liquidated:
                        defense_price = min(open_val, trigger_price) 
                        
                        if defense_price <= liq_price:
                            is_liquidated = True
                            action = "LIQUIDATED ☠️"
                        else:
                            # Defensa
                            target_liq_new = defense_price * (liq_price / start_price)
                            needed_collat_amt = debt_usd / (target_liq_new * ltv_liq)
                            add_collat_amt = needed_collat_amt - collateral_amt
                            
                            if add_collat_amt > 0:
                                total_injected += add_collat_amt * defense_price
                                collateral_amt += add_collat_amt
                                liq_price = target_liq_new 
                                action = "DEFENSA 🛡️"
                    
                    if low_val <= liq_price and not is_liquidated:
                        is_liquidated = True
                        
                    if not is_liquidated:
                        pos_value = (collateral_amt * close_val) - debt_usd
                    else:
                        pos_value = 0
                        
                    history.append({
                        "Fecha": date_idx, 
                        "Acción": action, 
                        "Liq Price": liq_price if not is_liquidated else 0,
                        "Inversión Acumulada": bt_capital + total_injected, 
                        "Valor Estrategia": pos_value if not is_liquidated else 0, 
                        "Valor HODL": (bt_capital / start_price) * close_val 
                    })
                    
                    if is_liquidated: break
                
                df_res = pd.DataFrame(history).set_index("Fecha")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Resultado", "LIQUIDADO" if is_liquidated else "VIVO")
                c2.metric("Inyectado Total", f"${total_injected:,.0f}")
                if not df_res.empty:
                    c3.metric("Valor Final", f"${df_res.iloc[-1]['Valor Estrategia']:,.0f}")
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_res.index, y=df_res["Valor Estrategia"], name='Estrategia', fill='tozeroy', line=dict(color='green')))
                fig.add_trace(go.Scatter(x=df_res.index, y=df_res["Inversión Acumulada"], name='Inversión', line=dict(color='red', dash='dash')))
                
                # Marcadores de defensa
                events = df_res[df_res["Acción"].str.contains("DEFENSA", na=False)]
                if not events.empty:
                    fig.add_trace(go.Scatter(x=events.index, y=events["Valor Estrategia"], mode='markers', name='Defensa', marker=dict(color='orange', size=10, symbol='diamond')))
                
                st.plotly_chart(fig, use_container_width=True)
                
                st.divider()
                st.subheader("🏁 Datos de Entrada")
                st.write(f"Inicio: {start_date_actual} | Precio Entrada: ${start_price:,.2f} | Deuda Inicial: ${debt_usd:,.0f}")

            except Exception as e:
                st.error(f"Error: {e}")

# ------------------------------------------------------------------------------
#  PESTAÑA 3: ESCÁNER REAL (MODO ROBUSTO + DUAL + MEMORIA)
# ------------------------------------------------------------------------------
with tab_onchain:
    st.markdown("### 📡 Escáner Aave V3 (Modo Seguro)")
    st.caption("Conexión ligera verificada. Elige tu modo de análisis abajo.")
    
    col_net1, col_net2 = st.columns([1, 3])
    with col_net1:
        net = st.selectbox("Red", list(NETWORKS.keys()))
    with col_net2:
        addr = st.text_input("Wallet Address (0x...)", placeholder="0x...")
    
    # --- GESTIÓN DE ESTADO (MEMORIA DE SESIÓN) ---
    if 'portfolio_data' not in st.session_state:
        st.session_state.portfolio_data = None

    if st.button("🔍 Analizar"):
        if not addr:
            st.warning("Falta dirección")
        else:
            with st.spinner(f"Conectando a {net}..."):
                w3, rpc_used, is_private = connect_robust(net)
                if not w3:
                    st.error("Error conexión RPC. Revisa tus Secrets."); st.stop()
                
                try:
                    # 1. Obtener Pool Real
                    prov_addr = w3.to_checksum_address(NETWORKS[net]["pool_provider"])
                    prov_contract = w3.eth.contract(address=prov_addr, abi=AAVE_ABI)
                    pool_addr = prov_contract.functions.getPool().call()
                    
                    # 2. Llamada Ligera (getUserAccountData)
                    pool = w3.eth.contract(address=pool_addr, abi=AAVE_ABI)
                    data = pool.functions.getUserAccountData(w3.to_checksum_address(addr)).call()
                    
                    # 3. Guardar en Memoria Session State
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
            
            # SELECTOR DE MODO
            mode = st.radio("Tipo de Posición:", 
                            ["🛡️ Activo Único (Detallado con Precios)", 
                             "💼 Multi-Colateral (Plan Preventivo por Salud)"], 
                            horizontal=True)
            
            # ==================================================================
            # MODO A: ACTIVO ÚNICO
            # ==================================================================
            if "Activo Único" in mode:
                c_sel, c_par = st.columns(2)
                with c_sel:
                    sim_asset = st.selectbox("¿Cuál es tu colateral principal?", list(ASSET_MAP.keys()), key="oc_asset")
                    ticker = ASSET_MAP[sim_asset] if ASSET_MAP[sim_asset] != "MANUAL" else st.text_input("Ticker", "ETH-USD", key="oc_tick")
                with c_par:
                    # Umbral mínimo bajado al 5%
                    def_th = st.number_input("Umbral Defensa (%)", 5.0, step=1.0, key="oc_th") / 100.0
                    zones = st.slider("Zonas", 1, 10, 5, key="oc_z")
                    
                try:
                    curr_p = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
                    st.metric(f"Precio Mercado ({ticker})", f"${curr_p:,.2f}")
                    
                    # Ingeniería inversa
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
                        
                        # Cantidad necesaria
                        needed_amt = d['debt_usd'] / (targ * d['lt_avg'])
                        add_amt = max(0, needed_amt - s_curr_c)
                        
                        cost_usd = add_amt * trig
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

            # ==================================================================
            # MODO B: MULTI-COLATERAL (LÓGICA PREVENTIVA DE SALUD)
            # ==================================================================
            else:
                st.info("Planificación preventiva basada en caída de Salud (Health Factor).")
                
                col_opts, col_ref = st.columns(2)
                with col_opts:
                    num_defenses = st.slider("Número de Defensas", 1, 10, 5, key="mc_zones")
                with col_ref:
                    witness_asset = st.selectbox("Activo Testigo (Referencia Visual)", list(ASSET_MAP.keys()), key="mc_witness")
                    w_ticker = ASSET_MAP[witness_asset] if ASSET_MAP[witness_asset] != "MANUAL" else "ETH-USD"
                
                try:
                    w_price = yf.Ticker(w_ticker).history(period="1d")['Close'].iloc[-1]
                except: w_price = 0

                current_hf = d['hf']
                
                if current_hf <= 1.0:
                    st.error("La posición ya está en rango de liquidación (HF < 1.0)")
                else:
                    # Step para bajar desde HF actual hasta 1.0
                    hf_gap = current_hf - 1.0
                    hf_step = hf_gap / num_defenses
                    
                    mc_data = []
                    
                    for i in range(1, num_defenses + 1):
                        # 1. Trigger HF
                        trigger_hf = current_hf - (hf_step * i)
                        if trigger_hf <= 1.001: trigger_hf = 1.001
                        
                        # 2. Caída necesaria para llegar ahí
                        drop_pct = 1 - (trigger_hf / current_hf)
                        
                        # 3. Capital para RESTAURAR al HF Original
                        shocked_col = d['col_usd'] * (1 - drop_pct)
                        shocked_lt_val = (d['col_usd'] * d['lt_avg']) * (1 - drop_pct)
                        
                        # Inyeccion = Deuda - (Shocked_Val / Target_HF_Original)
                        needed_capital = d['debt_usd'] - (shocked_lt_val / current_hf)
                        if needed_capital < 0: needed_capital = 0
                        
                        # Precio testigo
                        w_price_shock = w_price * (1 - drop_pct)
                        
                        # Nuevo HF real tras inyección
                        final_debt = d['debt_usd'] - needed_capital
                        if final_debt > 0:
                            final_hf = (shocked_col * d['lt_avg']) / final_debt
                        else:
                            final_hf = 999.0
                        
                        mc_data.append({
                            "Trigger HF": f"{trigger_hf:.2f}",
                            "Caída Mercado": f"-{drop_pct:.2%}",
                            f"Precio {w_ticker}": w_price_shock,
                            "Capital a Restaurar ($)": needed_capital,
                            "Nuevo HF": f"{final_hf:.2f}"
                        })
                    
                    st.dataframe(
                        pd.DataFrame(mc_data).style.format({
                            "Capital a Restaurar ($)": "${:,.2f}",
                            f"Precio {w_ticker}": "${:,.2f}"
                        }).background_gradient(subset=["Capital a Restaurar ($)"], cmap="Reds"), 
                        use_container_width=True
                    )
        else:
            st.success("Sin deuda activa.")
