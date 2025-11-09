import streamlit as st
import math

# ==============================================================================
# ⚽ CONSTANTES E FUNÇÕES AUXILIARES
# ==============================================================================

def calcular_lambda_total_from_odds(p_over):
    """
    Estima o Lambda (Expected Total Goals) a partir da probabilidade P(Over 2.5 Gols),
    usando um método de aproximação.
    """
    # A curva de probabilidade vs Lambda não é linear. Estes são pontos de referência.
    if p_over >= 0.7: return 3.2 
    if p_over >= 0.6: return 2.8
    if p_over >= 0.5: return 2.4
    if p_over >= 0.4: return 2.0
    if p_over >= 0.3: return 1.6
    return 1.2

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
    # Métricas Estatísticas
    gols_marcados_casa, gols_sofridos_fora, eficacia_conversao_casa, # NOVO: eficacia_conversao_casa
    gols_marcados_fora, gols_sofridos_casa, eficacia_conversao_fora, # NOVO: eficacia_conversao_fora
    media_liga_gols_por_jogo,
    # Odds Pré-Jogo
    odds_over_pre, odds_under_pre,
    duracao=90
):
    
    if minutos_jogados == 0:
        return None, "Erro: Minutos jogados não podem ser zero."

    # --- 1. CÁLCULO DOS FATORES DE FORÇA PRÉ-JOGO (3 TIPOS) ---
    
    # Prevenção de divisão por zero
    liga_baseline = media_liga_gols_por_jogo if media_liga_gols_por_jogo > 0 else 2.5

    # 1.1. Fatores Estatísticos (BASELINE - Padrão)
    
    # NOVO CÁLCULO DE FORÇA: Usamos a conversão para modular a força ofensiva.
    # Ex: (Gols Marcados / Média Liga) * (Média Liga / Gols Sofridos) * Fator Conversão
    
    # Definindo um FATOR NEUTRO DE CONVERSÃO para a liga (ex: 10% ou 0.10)
    FATOR_NEUTRO_CONVERSAO = 0.10 # 10% é uma média razoável para ligas de alto nível.

    # O fator de conversão é a força relativa: (Conversão Time / Conversão Média Liga)
    fator_conversao_relativo_casa = eficacia_conversao_casa / FATOR_NEUTRO_CONVERSAO if FATOR_NEUTRO_CONVERSAO > 0 else 1.0
    fator_conversao_relativo_fora = eficacia_conversao_fora / FATOR_NEUTRO_CONVERSAO if FATOR_NEUTRO_CONVERSAO > 0 else 1.0

    # Aplicação do Fator Base
    fator_ofensivo_casa_base = gols_marcados_casa / liga_baseline
    fator_defensivo_fora_base = liga_baseline / gols_sofridos_fora if gols_sofridos_fora > 0 else 2.0
    fator_baseline_casa = fator_ofensivo_casa_base * fator_defensivo_fora_base * fator_conversao_relativo_casa
    
    fator_ofensivo_fora_base = gols_marcados_fora / liga_baseline
    fator_defensivo_casa_base = liga_baseline / gols_sofridos_casa if gols_sofridos_casa > 0 else 2.0
    fator_baseline_fora = fator_ofensivo_fora_base * fator_defensivo_casa_base * fator_conversao_relativo_fora


    # 1.2. Fatores Estatísticos (COMPARAÇÃO DIRETA - Sem Baseline)
    
    fator_direto_casa = (gols_marcados_casa / gols_sofridos_fora) * fator_conversao_relativo_casa if gols_sofridos_fora > 0 else 2.0
    fator_direto_fora = (gols_marcados_fora / gols_sofridos_casa) * fator_conversao_relativo_fora if gols_sofridos_casa > 0 else 2.0


    # 1.3. Fatores do Mercado (Market-Driven)
    
    p_over_pre = calcular_prob_implicita(odds_over_pre)
    p_under_pre = calcular_prob_implicita(odds_under_pre)
    p_over_pre_normalizado = p_over_pre / (p_over_pre + p_under_pre)
    
    lambda_total_pre = calcular_lambda_total_from_odds(p_over_pre_normalizado)
    
    fator_mercado_total = lambda_total_pre / liga_baseline
    fator_mercado_casa = math.sqrt(fator_mercado_total)
    fator_mercado_fora = math.sqrt(fator_mercado_total)

    
    # --- 2. CÁLCULO MOMENTUM E AJUSTE DE PLACAR ---
    
    # Ritmo Médio (xG/min) e Momentum (Lógica inalterada)
    ritmo_home_medio = xg_home / minutos_jogados
    ritmo_away_medio = xg_away / minutos_jogados
    
    periodo_momentum = 10
    periodo_analise = min(minutos_jogados, periodo_momentum)
        
    ritmo_home_recente = xg_home / periodo_analise if periodo_analise > 0 else 0
    ritmo_away_recente = xg_away / periodo_analise if periodo_analise > 0 else 0

    momentum_home = (ritmo_home_recente / ritmo_home_medio) if ritmo_home_medio > 0 else 1.0
    momentum_away = (ritmo_away_recente / ritmo_away_medio) if ritmo_away_medio > 0 else 1.0
    
    # Ajuste por Placar
    ajuste_home = 1.0
    ajuste_away = 1.0
    if placar_home > placar_away:
        ajuste_home = 0.7; ajuste_away = 1.4
    elif placar_home < placar_away:
        ajuste_home = 1.4; ajuste_away = 0.7

    # Fator Mando de Campo
    fator_mando = 1.1 
    minutos_restantes = duracao - minutos_jogados
    
    if minutos_restantes <= 0:
        return None, "Erro: O jogo já acabou."
        
    # --- 3. EXECUÇÃO DAS PROJEÇÕES (3 Cenários) ---
    
    def run_projection(fator_casa, fator_fora, nome_modelo):
        
        # Ritmo Projetado
        ritmo_proj_home = ritmo_home_medio * fator_casa * fator_mando * ajuste_home * momentum_home
        ritmo_proj_away = ritmo_away_medio * fator_fora * ajuste_away * momentum_away
        
        # Lambda e Poisson
        lambda_xg = (ritmo_proj_home + ritmo_proj_away) * minutos_restantes
        p0 = math.exp(-lambda_xg)
        pover = 1 - p0
        
        # Odds e EV
        odds_justa_over = 1 / pover
        odds_justa_under = 1 / p0
        ev_over = (pover * odds_over_mkt) - 1
        ev_under = (p0 * odds_under_mkt) - 1
        
        return {
            "lambda": round(lambda_xg, 3),
            "P(0 gols)": round(p0, 3),
            "P(>=1 gol)": round(pover, 3),
            "Odd Justa Under": round(odds_justa_under, 2),
            "EV Under (%)": round(ev_under * 100, 1),
            "Fator Casa Usado": round(fator_casa, 2),
            "Fator Fora Usado": round(fator_fora, 2),
            "Nome": nome_modelo
        }

    resultados = {}
    resultados["Modelo Base (Baseline)"] = run_projection(fator_baseline_casa, fator_baseline_fora, "Estatístico (Baseline)")
    resultados["Modelo Direto (Comparação)"] = run_projection(fator_direto_casa, fator_direto_fora, "Estatístico (Direto)")
    resultados["Modelo Mercado"] = run_projection(fator_mercado_casa, fator_mercado_fora, "Expectativa Mercado")
    
    # Fatores Dinâmicos
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

st.title("⚽ Modelo Dinâmico xG Avançado (3 Cenários)")
st.markdown("Analisa a projeção de gols restantes usando *momentum* e três fontes de força pré-jogo: **Estatística (Baseline)**, **Estatística (Direta)** e **Mercado**.")

st.divider()

# --- INPUTS DO JOGO (COLUNA 1) ---
col1, col2, col3 = st.columns(3)

with col1:
    st.header("⏱️ Contexto & xG")
    minutos_jogados = st.number_input("Minutos Jogados", min_value=1, max_value=90, value=70, step=1)
    placar_home = st.number_input("Placar Time da Casa", min_value=0, value=1, step=1)
    placar_away = st.number_input("Placar Time Visitante", min_value=0, value=0, step=1)
    duracao = st.number_input("Duração Total do Jogo (min)", min_value=60, max_value=120, value=90, step=5)
    
    st.markdown("---")
    xg_home = st.number_input("xG Time da Casa (Total)", min_value=0.0, value=1.31, step=0.01, format="%.2f")
    xg_away = st.number_input("xG Time Visitante (Total)", min_value=0.0, value=0.57, step=0.01, format="%.2f")


with col2:
    st.header("⭐ Força Estatística (Pré-Jogo)")
    
    media_liga_gols_por_jogo = st.number_input(
        "Média de Gols/Jogo da Liga (Baseline)", 
        min_value=0.1, 
        value=2.5, 
        step=0.05, 
        format="%.2f",
        help="A média de gols por jogo na liga."
    )
    st.caption("Fator Neutro de Conversão da Liga: 10% (0.10)")

    # Time da Casa
    with st.expander("Time da Casa"):
        gols_marcados_casa = st.number_input("Gols Marcados/Jogo (Casa)", min_value=0.5, value=1.4, step=0.01, format="%.2f")
        gols_sofridos_casa = st.number_input("Gols Sofridos/Jogo (Casa)", min_value=0.5, value=1.2, step=0.01, format="%.2f")
        # NOVO INPUT: Taxa Bruta em Decimal
        eficacia_conversao_casa = st.number_input(
            "Eficácia de Conversão (Decimal)", 
            min_value=0.01, # Mínimo de 1%
            max_value=0.50, # Máximo de 50%
            value=0.11, # 11% como no seu exemplo
            step=0.01, 
            format="%.2f",
            help="Insira a taxa de conversão como decimal (Ex: 0.11 para 11%)."
        )

    # Time Visitante
    with st.expander("Time Visitante"):
        gols_marcados_fora = st.number_input("Gols Marcados/Jogo (Fora)", min_value=0.5, value=1.2, step=0.01, format="%.2f")
        gols_sofridos_fora = st.number_input("Gols Sofridos/Jogo (Fora)", min_value=0.5, value=0.7, step=0.01, format="%.2f")
        # NOVO INPUT: Taxa Bruta em Decimal
        eficacia_conversao_fora = st.number_input(
            "Eficácia de Conversão (Decimal)", 
            min_value=0.01, 
            max_value=0.50, 
            value=0.10, # 10% como no seu exemplo
            step=0.01, 
            format="%.2f",
            help="Insira a taxa de conversão como decimal (Ex: 0.10 para 10%)."
        )


with col3:
    st.header("📈 Odds de Mercado")
    
    st.subheader("Odds Pré-Jogo (Força do Mercado)")
    st.markdown("Odds Over/Under 2.5")
    odds_over_pre = st.number_input("Odds Over 2.5 (Pré-Jogo)", min_value=1.01, value=1.90, step=0.01, format="%.2f")
    odds_under_pre = st.number_input("Odds Under 2.5 (Pré-Jogo)", min_value=1.01, value=1.90, step=0.01, format="%.2f")

    st.subheader("Odds In-Play (Para EV)")
    st.markdown("Odds Over/Under 0.5 Gols Restantes (Odds atuais)")
    odds_over_mkt = st.number_input("Odds Over 0.5 (In-Play)", min_value=1.01, value=1.60, step=0.01, format="%.2f")
    odds_under_mkt = st.number_input("Odds Under 0.5 (In-Play)", min_value=1.01, value=2.20, step=0.01, format="%.2f")


# --- BOTÃO E EXECUÇÃO ---
if st.button("Calcular Projeção e EV (3 Cenários)", type="primary"):
    
    # Executa o modelo
    resultados, erro = modelo_xg_dinamico_avancado(
        xg_home=xg_home, xg_away=xg_away,
        minutos_jogados=minutos_jogados,
        placar_home=placar_home, placar_away=placar_away,
        odds_over_mkt=odds_over_mkt, odds_under_mkt=odds_under_mkt,
        gols_marcados_casa=gols_marcados_casa, gols_sofridos_fora=gols_sofridos_fora, eficacia_conversao_casa=eficacia_conversao_casa,
        gols_marcados_fora=gols_marcados_fora, gols_sofridos_casa=gols_sofridos_casa, eficacia_conversao_fora=eficacia_conversao_fora,
        media_liga_gols_por_jogo=media_liga_gols_por_jogo,
        odds_over_pre=odds_over_pre, odds_under_pre=odds_under_pre
    )

    if erro:
        st.error(erro)
    else:
        st.divider()
        st.header("💡 Resultados da Projeção e Valor Esperado (EV)")
        
        # Colunas de Resultados
        col_fat, col_base, col_dir, col_mkt = st.columns(4)
        fatores = resultados["Fatores Dinâmicos"]

        # 1. Fatores Dinâmicos
        with col_fat:
            st.subheader("Fatores de Ajuste")
            st.metric(label="Fator Momentum Casa", value=f"{fatores['Momentum Home']:.2f}")
            st.metric(label="Fator Momentum Visitante", value=f"{fatores['Momentum Away']:.2f}")
            st.metric(label="Fator Mando de Campo", value=f"{fatores['Fator Mando Fixo']:.2f}")

        # Função auxiliar para exibir o EV
        def display_ev_column(col, result_key, title):
            res = resultados[result_key]
            with col:
                st.subheader(title)
                st.caption(f"Fator Casa: **{res['Fator Casa Usado']:.2f}** | Fator Fora: **{res['Fator Fora Usado']:.2f}**")
                
                st.metric(label="xG Esperado (λ)", value=f"{res['lambda']:.3f}")
                st.metric(label="P(0 Gols)", value=f"{res['P(0 gols)']:.1%}")
                st.metric(label="Odds Justa Under", value=f"{res['Odd Justa Under']:.2f}")
                
                ev_under_valor = res['EV Under (%)']
                st.metric(
                    label=f"💰 EV Under ({odds_under_mkt:.2f})", 
                    value=f"{ev_under_valor:.1f}%", 
                    delta_color="normal" if ev_under_valor > 0 else "inverse", 
                    delta="Vantagem" if ev_under_valor > 0 else "Desvantagem"
                )

        # 2. Modelo Estatístico (Baseline)
        display_ev_column(col_base, "Modelo Base (Baseline)", "1. Estatístico (Baseline)")
        
        # 3. Modelo Estatístico (Direto)
        display_ev_column(col_dir, "Modelo Direto (Comparação)", "2. Estatístico (Direto)")
        
        # 4. Modelo Mercado
        display_ev_column(col_mkt, "Modelo Mercado", "3. Expectativa Mercado")
        
        st.divider()
        st.markdown(
            "***Análise dos Fatores:*** A conversão de **10% (0.10)** foi usada como o fator *neutro* da liga para calibrar a força relativa."
        )
