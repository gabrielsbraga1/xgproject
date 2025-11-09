import streamlit as st
import math

# ==============================================================================
# ⚽ CONSTANTES E FUNÇÕES AUXILIARES
# ==============================================================================

# Média de Gols da Liga (baseline para calcular fatores de força)
MEDIA_LIGA_GOLS_POR_JOGO = 2.5 

def calcular_lambda_total_from_odds(p_over):
    """
    Estima o Lambda (Expected Total Goals) a partir da probabilidade P(Over 2.5 Gols),
    usando um método de aproximação (Iteração).
    """
    # Aproximação de Lambda baseada em P(Over 2.5) assumindo Poisson simples.
    # Esta é uma função não linear complexa de inverter, usamos um valor aproximado.
    if p_over >= 0.7: return 3.2 
    if p_over >= 0.6: return 2.8
    if p_over >= 0.5: return 2.4
    if p_over >= 0.4: return 2.0
    if p_over >= 0.3: return 1.6
    return 1.2 # Default para over baixo

def calcular_prob_implicita(odds):
    """Calcula a probabilidade implícita (sem margem) de uma odd."""
    return (1 / odds) if odds > 0 else 0


# ==============================================================================
# 🎯 FUNÇÃO DO MODELO xG DINÂMICO PRINCIPAL
# ==============================================================================

def modelo_xg_dinamico_avancado(
    xg_home, xg_away,
    minutos_jogados,
    placar_home, placar_away,
    odds_over_mkt, odds_under_mkt,
    # Métricas para Força Estatística
    gols_marcados_casa, gols_sofridos_fora, conversao_casa,
    gols_marcados_fora, gols_sofridos_casa, conversao_fora,
    # Odds Pré-Jogo (para Força do Mercado)
    odds_over_pre, odds_under_pre,
    duracao=90
):
    
    if minutos_jogados == 0:
        return None, "Erro: Minutos jogados não podem ser zero."

    # --- 1. CÁLCULO DOS FATORES DE FORÇA PRÉ-JOGO ---

    # Cenário 1: Força Estatística (Model-Driven)
    # Fator é a média geométrica dos ritmos relativos, ajustado pela eficácia.
    fator_ofensivo_casa = gols_marcados_casa / MEDIA_LIGA_GOLS_POR_JOGO
    fator_defensivo_fora = MEDIA_LIGA_GOLS_POR_JOGO / gols_sofridos_fora
    
    fator_estatistico_casa = fator_ofensivo_casa * fator_defensivo_fora * conversao_casa
    
    fator_ofensivo_fora = gols_marcados_fora / MEDIA_LIGA_GOLS_POR_JOGO
    fator_defensivo_casa = MEDIA_LIGA_GOLS_POR_JOGO / gols_sofridos_casa
    
    fator_estatistico_fora = fator_ofensivo_fora * fator_defensivo_casa * conversao_fora
    
    # Mando de Campo: Usamos uma média fixa de 10% de boost no ritmo total do mandante.
    fator_mando = 1.1 

    # Cenário 2: Força do Mercado (Market-Driven)
    
    # Calcula a probabilidade implícita do mercado Over/Under 2.5 Pré-Jogo
    p_over_pre = calcular_prob_implicita(odds_over_pre)
    p_under_pre = calcular_prob_implicita(odds_under_pre)
    
    # Normaliza a probabilidade para Over (removendo margem)
    p_over_pre_normalizado = p_over_pre / (p_over_pre + p_under_pre)
    
    # Inferir o Lambda Total (xG esperado total) a partir do P(Over 2.5) normalizado
    lambda_total_pre = calcular_lambda_total_from_odds(p_over_pre_normalizado)
    
    # Assumimos que a divisão do Lambda (xG) entre casa/fora segue a proporção do xG/gols histórico
    # Para simplificar, usaremos o fator de mercado como o Lambda Total / MEDIA_LIGA_GOLS_POR_JOGO
    # O modelo do mercado é usado para criar um FATOR TOTAL.
    fator_mercado_total = lambda_total_pre / MEDIA_LIGA_GOLS_POR_JOGO

    # Aplicamos este fator de forma simétrica a Casa e Fora para simplificar a integração
    fator_mercado_casa = math.sqrt(fator_mercado_total) # Raiz quadrada para distribuir o fator
    fator_mercado_fora = math.sqrt(fator_mercado_total)

    # --- 2. CÁLCULO MOMENTUM (REUTILIZADO) ---
    
    # (Lógica do Momentum, Placar, e Ritmo Médio permanecem a mesma)
    
    # Ritmo Médio (xG/min) do time na partida:
    ritmo_home_medio = xg_home / minutos_jogados
    ritmo_away_medio = xg_away / minutos_jogados
    
    # Ritmo recente (considera o período de 10 min, mantendo a variável de input para facilitar)
    periodo_momentum = 10 # Fixo, mas poderia ser um input
    
    if minutos_jogados < periodo_momentum:
        periodo_analise = minutos_jogados
    else:
        periodo_analise = periodo_momentum
        
    if periodo_analise > 0:
        ritmo_home_recente = xg_home / periodo_analise # Usando xG total se for o único disponível
        ritmo_away_recente = xg_away / periodo_analise
    else:
        ritmo_home_recente = 0
        ritmo_away_recente = 0

    # Fatores Momentum (Momentum Home/Away, 1.0 se ritmos forem zero)
    momentum_home = (ritmo_home_recente / ritmo_home_medio) if ritmo_home_medio > 0 else 1.0
    momentum_away = (ritmo_away_recente / ritmo_away_medio) if ritmo_away_medio > 0 else 1.0
    
    # Ajuste por Placar
    ajuste_home = 1.0
    ajuste_away = 1.0

    if placar_home > placar_away:
        ajuste_home = 0.7
        ajuste_away = 1.4
    elif placar_home < placar_away:
        ajuste_home = 1.4
        ajuste_away = 0.7

    # --- 3. EXECUÇÃO DA PROJEÇÃO (DUAS VEZES) ---
    
    resultados = {}

    # Cenário 1: PROJEÇÃO BASEADA NA FORÇA ESTATÍSTICA
    
    ritmo_proj_home_est = ritmo_home_medio * fator_estatistico_casa * fator_mando * ajuste_home * momentum_home
    ritmo_proj_away_est = ritmo_away_medio * fator_estatistico_fora * ajuste_away * momentum_away
    
    minutos_restantes = duracao - minutos_jogados
    lambda_est = (ritmo_proj_home_est + ritmo_proj_away_est) * minutos_restantes

    if minutos_restantes <= 0:
        return None, "Erro: O jogo já acabou."
        
    # Cálculo Poisson
    p0_est = math.exp(-lambda_est)
    pover_est = 1 - p0_est
    odds_justa_over_est = 1 / pover_est
    odds_justa_under_est = 1 / p0_est
    ev_over_est = (pover_est * odds_over_mkt) - 1
    ev_under_est = (p0_est * odds_under_mkt) - 1
    
    resultados["Modelo Estatístico"] = {
        "lambda": round(lambda_est, 3),
        "P(0 gols)": round(p0_est, 3),
        "P(>=1 gol)": round(pover_est, 3),
        "Odd Justa Over": round(odds_justa_over_est, 2),
        "Odd Justa Under": round(odds_justa_under_est, 2),
        "EV Over (%)": round(ev_over_est * 100, 1),
        "EV Under (%)": round(ev_under_est * 100, 1),
        "Fator Casa Usado": round(fator_estatistico_casa, 2),
        "Fator Fora Usado": round(fator_estatistico_fora, 2),
    }

    # Cenário 2: PROJEÇÃO BASEADA NA EXPECTATIVA DO MERCADO

    ritmo_proj_home_mkt = ritmo_home_medio * fator_mercado_casa * fator_mando * ajuste_home * momentum_home
    ritmo_proj_away_mkt = ritmo_away_medio * fator_mercado_fora * ajuste_away * momentum_away

    lambda_mkt = (ritmo_proj_home_mkt + ritmo_proj_away_mkt) * minutos_restantes

    # Cálculo Poisson
    p0_mkt = math.exp(-lambda_mkt)
    pover_mkt = 1 - p0_mkt
    odds_justa_over_mkt = 1 / pover_mkt
    odds_justa_under_mkt = 1 / p0_mkt
    ev_over_mkt = (pover_mkt * odds_over_mkt) - 1
    ev_under_mkt = (p0_mkt * odds_under_mkt) - 1
    
    resultados["Expectativa do Mercado"] = {
        "lambda": round(lambda_mkt, 3),
        "P(0 gols)": round(p0_mkt, 3),
        "P(>=1 gol)": round(pover_mkt, 3),
        "Odd Justa Over": round(odds_justa_over_mkt, 2),
        "Odd Justa Under": round(odds_justa_under_mkt, 2),
        "EV Over (%)": round(ev_over_mkt * 100, 1),
        "EV Under (%)": round(ev_under_mkt * 100, 1),
        "Fator Casa Usado": round(fator_mercado_casa, 2),
        "Fator Fora Usado": round(fator_mercado_fora, 2),
    }

    # Resultados dinâmicos (momentum)
    resultados["Fatores Dinâmicos"] = {
        "Momentum Home": round(momentum_home, 2), 
        "Momentum Away": round(momentum_away, 2),
        "Fator Mando Fixo": fator_mando,
    }

    return resultados, None

# ==============================================================================
# 🏠 INTERFACE STREAMLIT
# ==============================================================================

st.set_page_config(
    page_title="Modelo Dinâmico xG Avançado", 
    layout="wide"
)

st.title("⚽ Modelo Dinâmico xG Avançado")
st.markdown("Analisa a projeção de gols restantes usando *momentum* e duas fontes de força pré-jogo: **Estatística** e **Mercado**.")

st.divider()

# --- INPUTS DO JOGO (COLUNA 1) ---
col1, col2, col3 = st.columns(3)

with col1:
    st.header("⏱️ Contexto da Partida")
    # Alterado para number_input
    minutos_jogados = st.number_input("Minutos Jogados", min_value=1, max_value=90, value=70, step=1)
    placar_home = st.number_input("Placar Time da Casa", min_value=0, value=1, step=1)
    placar_away = st.number_input("Placar Time Visitante", min_value=0, value=0, step=1)
    duracao = st.number_input("Duração Total do Jogo (min)", min_value=60, max_value=120, value=90, step=5)
    
    st.header("📊 xG Acumulado")
    xg_home = st.number_input("xG Time da Casa (Total)", min_value=0.0, value=1.31, step=0.01, format="%.2f")
    xg_away = st.number_input("xG Time Visitante (Total)", min_value=0.0, value=0.57, step=0.01, format="%.2f")


with col2:
    st.header("⭐ Força Estatística (Pré-Jogo)")
    st.markdown(f"*(Baseline da Liga assumida: {MEDIA_LIGA_GOLS_POR_JOGO} Gols)*")
    
    # Time da Casa
    with st.expander("Time da Casa"):
        gols_marcados_casa = st.number_input("Gols Marcados/Jogo (Casa)", min_value=0.5, value=1.7, step=0.01, format="%.2f", help="Média histórica de gols marcados pelo time da casa.")
        gols_sofridos_casa = st.number_input("Gols Sofridos/Jogo (Casa)", min_value=0.5, value=1.2, step=0.01, format="%.2f", help="Média histórica de gols sofridos pelo time da casa.")
        conversao_casa = st.number_input("Eficácia de Conversão (Fator)", min_value=0.5, max_value=2.0, value=1.05, step=0.01, format="%.2f", help="Ajuste fino na força: 1.05 = 5% acima da média.")

    # Time Visitante
    with st.expander("Time Visitante"):
        gols_marcados_fora = st.number_input("Gols Marcados/Jogo (Fora)", min_value=0.5, value=1.1, step=0.01, format="%.2f", help="Média histórica de gols marcados pelo time visitante.")
        gols_sofridos_fora = st.number_input("Gols Sofridos/Jogo (Fora)", min_value=0.5, value=1.5, step=0.01, format="%.2f", help="Média histórica de gols sofridos pelo time visitante.")
        conversao_fora = st.number_input("Eficácia de Conversão (Fator)", min_value=0.5, max_value=2.0, value=0.95, step=0.01, format="%.2f", help="Ajuste fino na força: 0.95 = 5% abaixo da média.")


with col3:
    st.header("📈 Odds de Mercado")
    
    st.subheader("Odds Pré-Jogo (Para Força do Mercado)")
    st.markdown("Odds Over/Under 2.5 (Ex: 1.70 / 2.10)")
    odds_over_pre = st.number_input("Odds Over 2.5 (Pré-Jogo)", min_value=1.01, value=1.90, step=0.01, format="%.2f")
    odds_under_pre = st.number_input("Odds Under 2.5 (Pré-Jogo)", min_value=1.01, value=1.90, step=0.01, format="%.2f")

    st.subheader("Odds In-Play (Para Cálculo do EV)")
    st.markdown("Odds Over/Under 0.5 Gols Restantes")
    odds_over_mkt = st.number_input("Odds Over 0.5 (In-Play)", min_value=1.01, value=1.60, step=0.01, format="%.2f")
    odds_under_mkt = st.number_input("Odds Under 0.5 (In-Play)", min_value=1.01, value=2.20, step=0.01, format="%.2f")


# --- BOTÃO E EXECUÇÃO ---
if st.button("Calcular Projeção e EV (2 Cenários)", type="primary"):
    
    # Executa o modelo
    resultados, erro = modelo_xg_dinamico_avancado(
        xg_home=xg_home, xg_away=xg_away,
        minutos_jogados=minutos_jogados,
        placar_home=placar_home, placar_away=placar_away,
        odds_over_mkt=odds_over_mkt, odds_under_mkt=odds_under_mkt,
        gols_marcados_casa=gols_marcados_casa, gols_sofridos_fora=gols_sofridos_fora, conversao_casa=conversao_casa,
        gols_marcados_fora=gols_marcados_fora, gols_sofridos_casa=gols_sofridos_casa, conversao_fora=conversao_fora,
        odds_over_pre=odds_over_pre, odds_under_pre=odds_under_pre,
        duracao=duracao
    )

    if erro:
        st.error(erro)
    else:
        st.divider()
        st.header("💡 Resultados da Projeção e Valor Esperado (EV)")
        
        col_fat, col_est, col_mkt = st.columns(3)
        fatores = resultados["Fatores Dinâmicos"]

        with col_fat:
            st.subheader("Fatores Dinâmicos Aplicados")
            st.metric(
                label="Fator Momentum Casa", 
                value=f"{fatores['Momentum Home']:.2f}", 
                help="Ritmo Recente / Ritmo Médio (aplicado a ambos cenários)."
            )
            st.metric(
                label="Fator Momentum Visitante", 
                value=f"{fatores['Momentum Away']:.2f}",
                help="Ritmo Recente / Ritmo Médio (aplicado a ambos cenários)."
            )
            st.metric(
                label="Fator Mando de Campo", 
                value=f"{fatores['Fator Mando Fixo']:.2f}",
                help="Fator fixo aplicado ao ritmo do mandante."
            )

        # --- Cenário 1: Modelo Estatístico ---
        est = resultados["Modelo Estatístico"]
        with col_est:
            st.subheader("1. Projeção: Modelo Estatístico (Off/Def)")
            st.caption(f"Fator Casa: **{est['Fator Casa Usado']:.2f}** | Fator Fora: **{est['Fator Fora Usado']:.2f}**")
            
            st.metric(
                label="xG Esperado (λ)", 
                value=f"{est['lambda']:.3f}"
            )
            st.metric(
                label="P(0 Gols)", 
                value=f"{est['P(0 gols)']:.1%}"
            )
            st.metric(
                label="Odds Justa Under", 
                value=f"{est['Odd Justa Under']:.2f}"
            )
            st.metric(
                label="EV Under (%)", 
                value=f"{est['EV Under (%)']:.1f}%", 
                delta_color="normal" if est['EV Under (%)'] > 0 else "inverse", 
                delta="Vantagem" if est['EV Under (%)'] > 0 else "Desvantagem"
            )

        # --- Cenário 2: Expectativa do Mercado ---
        mkt = resultados["Expectativa do Mercado"]
        with col_mkt:
            st.subheader("2. Projeção: Expectativa do Mercado (Odds Pré-Jogo)")
            st.caption(f"Fator Casa: **{mkt['Fator Casa Usado']:.2f}** | Fator Fora: **{mkt['Fator Fora Usado']:.2f}**")

            st.metric(
                label="xG Esperado (λ)", 
                value=f"{mkt['lambda']:.3f}"
            )
            st.metric(
                label="P(0 Gols)", 
                value=f"{mkt['P(0 gols)']:.1%}"
            )
            st.metric(
                label="Odds Justa Under", 
                value=f"{mkt['Odd Justa Under']:.2f}"
            )
            st.metric(
                label="EV Under (%)", 
                value=f"{mkt['EV Under (%)']:.1f}%", 
                delta_color="normal" if mkt['EV Under (%)'] > 0 else "inverse", 
                delta="Vantagem" if mkt['EV Under (%)'] > 0 else "Desvantagem"
            )
            
        st.divider()
        st.markdown(
            "***Diferença de Valor:*** Compare o **EV (%)** dos dois cenários. Se o EV for positivo em um modelo e negativo no outro, isso aponta para uma divergência clara entre a sua análise estatística e o preço do mercado."
        )
