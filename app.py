import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from datetime import date, timedelta
from web3 import Web3
import requests # Necesario para el "disfraz"

# --- Configuración de la Página ---
st.set_page_config(page_title="Looping Master - MultiChain", layout="wide")

st.title("🛡️ Looping Master: Calculadora, Backtest & On-Chain")

# --- CONFIGURACIÓN DE REDES ---
NETWORKS = {
    "Base": {
        "chain_id": 8453, # ID de Base Mainnet (Vital para verificar)
        "rpcs": [
            "https://mainnet.base.org",
            "https://base.drpc.org",
            "https://base-rpc.publicnode.com"
        ],
        "pool_address": "0xA238Dd80C259a72e81d7e4664a98015D33062B7f"
    },
    "Arbitrum": {
        "chain_id": 42161,
        "rpcs": ["https://arb1.arbitrum.io/rpc", "https://rpc.ankr.com/arbitrum"],
        "pool_address": "0x794a61358D6845594F94dc1DB02A252b5b4814aD"
    },
    "Ethereum": {
        "chain_id": 1,
        "rpcs": ["https://eth.llamarpc.com", "https://rpc.ankr.com/eth"], 
        "pool_address": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
    },
    "Optimism": {
        "chain_id": 10,
        "rpcs": ["https://mainnet.optimism.io", "https://rpc.ankr.com/optimism"],
        "pool_address": "0x794a61358D6845594F94dc1DB02A252b5b4814aD"
    },
    "Polygon": {
        "chain_id": 137,
        "rpcs": ["https://polygon-rpc.com", "https://rpc.ankr.com/polygon"],
        "pool_address": "0x794a61358D6845594F94dc1DB02A252b5b4814aD"
    },
    "Avalanche": {
        "chain_id": 43114,
        "rpcs": ["https://api.avax.network/ext/bc/C/rpc"],
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

ASSET_MAP = {
    "Bitcoin (WBTC/BTC)": "BTC-USD", "Ethereum (WETH/ETH)": "ETH-USD",
    "Arbitrum (ARB)": "ARB-USD", "Optimism (OP)": "OP-USD",
    "Polygon (MATIC)": "MATIC-USD", "Solana (SOL)": "SOL-USD",
    "Avalanche (AVAX)": "AVAX-USD", "Base (ETH)": "ETH-USD", 
    "Link (LINK)": "LINK-USD", "✍️ Otro (Escribir manual)": "MANUAL"
}

# --- FUNCIÓN DE CONEXIÓN "DISFRAZADA" ---
def get_web3_session(rpc_url):
    """Crea una sesión Web3 disfrazada de navegador Chrome"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    # Conectamos Web3 usando esta sesión personalizada
    w3 = Web3(Web3.HTTPProvider(rpc_url, session=session))
    return w3

def connect_robust(network_name):
    config = NETWORKS[network_name]
    rpcs = config["rpcs"]
    
    # Intentar inyectar secreto si existe
    secret_key = f"{network_name.upper()}_RPC_URL"
    if secret_key in st.secrets:
        rpcs.insert(0, st.secrets[secret_key])
        
    last_error = "No RPCs available"
    
    for rpc in rpcs:
        try:
            w3 = get_web3_session(rpc) # Usamos la sesión con headers
            
            if w3.is_connected():
                # Verificación extra: ¿Estamos en la cadena correcta?
                # A veces un nodo público te redirige mal.
                chain_id = w3.eth.chain_id
                if chain_id == config["chain_id"]:
                    return w3, rpc
                else:
                    last_error = f"Chain ID mismatch: {chain_id} vs {config['chain_id']}"
            else:
                last_error = "Not connected"
        except Exception as e:
            last_error = str(e)
            continue
            
    return None, last_error

# TABS
tab_calc, tab_backtest, tab_onchain = st.tabs(["🧮 Calculadora", "📉 Backtest", "📡 Escáner On-Chain"])

# ... (PESTAÑA 1 y 2 SE MANTIENEN IGUAL QUE ANTES, OMITIDAS POR BREVEDAD, PEGA TU CÓDIGO AQUÍ) ...
# (Para que funcione, asegúrate de mantener el código de las pestañas 1 y 2 que ya tenías)

# ==============================================================================
#  PESTAÑA 1: CALCULADORA (Versión compacta para copiar)
# ==============================================================================
with tab_calc:
    st.markdown("### Simulador Estático de Defensa")
    c1, c2, c3 = st.columns(3)
    with c1:
        sel_a = st.selectbox("Activo", list(ASSET_MAP.keys()))
        t_name = st.text_input("Ticker", "PEPE") if ASSET_MAP[sel_a] == "MANUAL" else sel_a.split("(")[1].replace(")", "")
        c_p = st.number_input(f"Precio {t_name}", 100000.0, step=100.0)
        c_t = st.number_input("Objetivo", 130000.0, step=100.0)
    with c2:
        c_cap = st.number_input("Capital", 10000.0, step=1000.0)
        c_lev = st.slider("Leverage", 1.1, 5.0, 2.0)
    with c3:
        c_ltv = st.slider("LTV Liq %", 50, 95, 78) / 100.0
        c_th = st.number_input("Umbral %", 15.0) / 100.0
        c_z = st.slider("Zonas", 1, 10, 5)

    c_col = c_cap * c_lev
    c_debt = c_col - c_cap
    c_amt = c_col / c_p
    c_liq = c_debt / (c_amt * c_ltv) if c_amt > 0 else 0
    
    st.divider()
    if c_liq > 0:
        data = []
        curr_col, curr_liq, cum_cost = c_amt, c_liq, 0.0
        ratio = c_liq / c_p
        for i in range(1, c_z+1):
            trig = curr_liq * (1 + c_th)
            targ = trig * ratio
            need = c_debt / (targ * c_ltv)
            add = max(0, need - curr_col)
            cost = add * trig
            cum_cost += cost
            curr_col += add
            curr_liq = targ
            data.append({"Zona": i, "Activación": trig, "Costo": cost, "Acumulado": cum_cost, "Nuevo Liq": targ})
        st.dataframe(pd.DataFrame(data))

# ==============================================================================
#  PESTAÑA 2: BACKTEST (Versión compacta)
# ==============================================================================
with tab_backtest:
    st.write("Backtest disponible (copia el código anterior si lo necesitas aquí)")

# ==============================================================================
#  PESTAÑA 3: ON-CHAIN SCANNER (DEBUG MODE)
# ==============================================================================
with tab_onchain:
    st.markdown("### 📡 Escáner Aave V3 (Anti-Bloqueo)")
    
    col_net1, col_net2 = st.columns([1, 3])
    with col_net1:
        selected_network = st.selectbox("Red", list(NETWORKS.keys()))
    with col_net2:
        user_address = st.text_input("Wallet", placeholder="0x...")
    
    if st.button("🔍 Analizar"):
        if not user_address:
            st.warning("Falta dirección.")
        else:
            with st.spinner(f"Conectando a {selected_network} (Modo Navegador)..."):
                w3, rpc_used = connect_robust(selected_network)
            
            if not w3:
                st.error(f"❌ Fallo total de conexión. Revisa si el RPC de {selected_network} está caído.")
                st.stop()
            
            # Debug Info (Para ver si estamos conectados de verdad)
            chain_id = w3.eth.chain_id
            block = w3.eth.block_number
            st.caption(f"✅ Conectado a Chain ID: {chain_id} | Bloque: {block} | Vía: {rpc_used}")

            try:
                valid_addr = w3.to_checksum_address(user_address)
                pool_addr = NETWORKS[selected_network]["pool_address"]
                
                # Checkeo de contrato
                code = w3.eth.get_code(pool_addr)
                if code == b'\x00' or code == b'':
                    st.error(f"⚠️ El nodo dice que no hay contrato Aave en {pool_addr}. Problema de sincronización del nodo.")
                    st.stop()

                contract = w3.eth.contract(address=pool_addr, abi=AAVE_ABI)
                data = contract.functions.getUserAccountData(valid_addr).call()
                
                col_usd = data[0] / 10**8
                debt_usd = data[1] / 10**8
                hf = data[5] / 10**18
                
                m1, m2, m3 = st.columns(3)
                m1.metric("HF", f"{hf:.2f}")
                m2.metric("Colateral", f"${col_usd:,.2f}")
                m3.metric("Deuda", f"${debt_usd:,.2f}")
                
                # ... (Resto de la lógica de simulación) ...
                st.success("Lectura completada con éxito.")

            except Exception as e:
                st.error(f"Error de lectura: {e}")
