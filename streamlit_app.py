import streamlit as st
import math

# ==============================================================================
# ⚽ CONSTANTES E FUNÇÕES AUXILIARES
# ==============================================================================

# Valor de segurança para prevenir divisão por zero (0.001)
EPSILON = 1e-3 

def calcular_lambda_total_from_odds(p_over):
    """Estima o Lambda (Expected Total Goals) a partir da probabilidade P(Over 2.5 Gols)."""
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
# 🎯 FUNÇÃO DO MODELO xG DINÂMICO PRINCIPAL CORRIGIDA
# ==============================================================================

def modelo_xg_dinamico_avancado_estavel(
    xg_home, xg_away,
    minutos_jogados,
    placar_home, placar_away,
    odds_over_mkt, odds_under_mkt,
    # Métricas Estatísticas
    gols_marcados_casa, gols_sofridos_fora, eficacia_conversao_casa,
    gols_marcados_fora, gols_sofridos_casa, eficacia_conversao_fora,
    media_liga_gols_por_jogo,
    # Odds Pré-Jogo
    odds_over_pre, odds_under_pre,
    odds_1, odds_x, odds_2,
    odds_over_1_5_pre, odds_under_1_5_pre,
    duracao=90
):
    
    if minutos_jogados == 0:
        return None, "Erro: Minutos jogados não podem ser zero."

    # --- 1. CÁLCULO DOS FATORES DE FORÇA PRÉ-JOGO (3 TIPOS) ---
    
    liga_baseline = max(media_liga_gols_por_jogo, EPSILON) 
    FATOR_NEUTRO_CONVERSAO = 0.10
    
    fator_conversao_relativo_casa = eficacia_conversao_casa / max(FATOR_NEUTRO_CONVERSAO, EPSILON)
    fator_conversao_relativo_fora = eficacia_conversao_fora / max(FATOR_NEUTRO_CONVERSAO, EPSILON)

    # Aplicação do Fator Base
    fator_ofensivo_casa_base = gols_marcados_casa / liga_baseline
    fator_defensivo_fora_base = liga_baseline / max(gols_sofridos_fora, EPSILON)
    fator_baseline_casa = fator_ofensivo_casa_base * fator_defensivo_fora_base * fator_conversao_relativo_casa
    
    fator_ofensivo_fora_base = gols_marcados_fora / liga_baseline
    fator_defensivo_casa_base = liga_baseline / max(gols_sofridos_casa, EPSILON)
    fator_baseline_fora = fator_ofensivo_fora_base * fator_defensivo_casa_base * fator_conversao_relativo_fora

    # Fatores Direto e Mercado (Lógica Inalterada)
    fator_direto_casa = (gols_marcados_casa / max(gols_sofridos_fora, EPSILON)) * fator_conversao_relativo_casa
    fator_direto_fora = (gols_marcados_fora / max(gols_sofridos_casa, EPSILON)) * fator_conversao_relativo_fora
    
    p_over_pre = calcular_prob_implicita(odds_over_pre)
    p_under_pre = calcular_prob_implicita(odds_under_pre)
    margem = (p_over_pre + p_under_pre) - 1
    p_over_pre_normalizado = p_over_pre / max(1 + margem, EPSILON) 
    lambda_total_pre = calcular_lambda_total_from_odds(p_over_pre_normalizado)
    fator_mercado_total = lambda_total_pre / liga_baseline
    fator_mercado_casa = math.sqrt(fator_mercado_total)
    fator_mercado_fora = math.sqrt(fator_mercado_total)

    
    # --- 2. CÁLCULO DE RITMO E AJUSTES ---
    
    ritmo_home_medio = xg_home / minutos_jogados
    ritmo_away_medio = xg_away / minutos_jogados
    
    # FATORES FIXOS
    momentum_home = 1.0; momentum_away = 1.0
    fator_mando = 1.0 
    
    # AJUSTE DE PLACAR SUAVIZADO
    ajuste_home = 1.0; ajuste_away = 1.0
    if placar_home > placar_away:
        ajuste_home = 0.85 # Menos redução (antes era 0.7)
        ajuste_away = 1.15 # Menos boost (antes era 1.4)
    elif placar_home < placar_away:
        ajuste_home = 1.15
        ajuste_away = 0.85
    
    minutos_restantes = duracao - minutos_jogados
    if minutos_restantes <= 0:
        return None, "Erro: O jogo já acabou."
        
    # --- 3. EXECUÇÃO DAS PROJEÇÕES (3 Cenários) ---
    
    def run_projection(fator_casa, fator_fora, nome_modelo):
        
        # FATOR SORTE (LUCK FACTOR): Gols / xG
        # Aplicamos um LIMITE MÁXIMO de 1.5x (50% acima do que o xG sugere)
        luck_casa = placar_home / max(xg_home, EPSILON) 
        luck_fora = placar_away / max(xg_away, EPSILON)

        fator_sorte_casa = min(luck_casa, 1.5) # Limita a 1.5x
        fator_sorte_fora = min(luck_fora, 1.5) # Limita a 1.5x

        # Ritmo Projetado: xG Médio * Força Pré-Jogo * Mando * Ajuste Placar * FATOR SORTE
        ritmo_proj_home = ritmo_home_medio * fator_casa * fator_mando * ajuste_home * fator_sorte_casa
        ritmo_proj_away = ritmo_away_medio * fator_fora * ajuste_away * fator_sorte_fora
        
        # Lambda e Poisson
        lambda_casa = ritmo_proj_home * minutos_restantes
        lambda_fora = ritmo_proj_away * minutos_restantes
        lambda_xg_total = lambda_casa + lambda_fora
        
        p0 = math.exp(-lambda_xg_total)
        pover = 1 - p0
        
        # Odds e EV
        odds_justa_over = 1 / pover if pover > 0 else float('inf')
        odds_justa_under = 1 / p0 if p0 > 0 else float('inf')
        
        ev_over = (pover * odds_over_mkt) - 1
        ev_under = (p0 * odds_under_mkt) - 1
        
        # CÁLCULO 1X2 (Heurística)
        gols_casa_final = placar_home + lambda_casa
        gols_fora_final = placar_away + lambda_fora
        diff = gols_casa_final - gols_fora_final
        
        if diff > 0.5:
            p_casa_final = 0.6 + (diff * 0.1)
            p_empate_final = 0.2
            p_fora_final = 0.2 - (diff * 0.1)
        elif diff < -0.5:
            p_fora_final = 0.6 + (abs(diff) * 0.1)
            p_empate_final = 0.2
            p_casa_final = 0.2 - (abs(diff) * 0.1)
        else:
            p_casa_final = 0.33; p_empate_final = 0.34; p_fora_final = 0.33
            
        soma_final = p_casa_final + p_empate_final + p_fora_final
        p_casa_final /= max(soma_final, EPSILON)
        p_empate_final /= max(soma_final, EPSILON)
        p_fora_final /= max(soma_final, EPSILON)
        
        
        return {
            "lambda": round(lambda_xg_total, 3),
            # Under/Over
            "P(0 gols)": round(p0, 3),
            "P(>=1 gol)": round(pover, 3),
            "Odd Justa Under": round(odds_justa_under, 2),
            "EV Under (%)": round(ev_under * 100, 1),
            "EV Over (%)": round(ev_over * 100, 1),
            # 1X2 (Resultado Final)
            "P(Casa)": round(p_casa_final, 3),
            "P(Empate)": round(p_empate_final, 3),
            "P(Fora)": round(p_fora_final, 3),
            # Fatores
            "Fator Casa Usado": round(fator_casa, 2),
            "Fator Fora Usado": round(fator_fora, 2),
            "Fator Sorte Casa": round(fator_sorte_casa, 2),
            "Fator Sorte Fora": round(fator_sorte_fora, 2),
            "Nome": nome_modelo
        }

    resultados = {}
    resultados["Modelo Base (Baseline)"] = run_projection(fator_baseline_casa, fator_baseline_fora, "Estatístico (Baseline)")
    resultados["Modelo Direto (Comparação)"] = run_projection(fator_direto_casa, fator_direto_fora, "Estatístico (Direto)")
    resultados["Modelo Mercado"] = run_projection(fator_mercado_casa, fator_mercado_fora, "Expectativa Mercado")
    
    # Fatores Fixo
    resultados["Fatores Dinâmicos"] = {
        "Momentum Home": 1.0, 
        "Momentum Away": 1.0,
        "Fator Mando Fixo": 1.0,
    }

    return resultados, None

# ==============================================================================
# 🏠 INTERFACE STREAMLIT (NÃO PRECISA DE ALTERAÇÕES GRANDES)
# ==============================================================================

# (O resto do código da interface Streamlit permanece inalterado)
# ...
st.set_page_config(
    page_title="Modelo Dinâmico xG (Estável c/ Luck)", 
    layout="wide"
)

st.title("⚽ Modelo Dinâmico xG (Estável c/ Luck)")
st.markdown("Projeta gols restantes com ajuste suavizado por **Placar** e **Fator de Sorte (Luck)** limitado.")

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
        eficacia_conversao_casa = st.number_input(
            "Eficácia de Conversão (Decimal)", 
            min_value=0.01, 
            max_value=0.50, 
            value=0.11, 
            step=0.01, 
            format="%.2f",
            help="Insira a taxa de conversão como decimal (Ex: 0.11 para 11%)."
        )

    # Time Visitante
    with st.expander("Time Visitante"):
        gols_marcados_fora = st.number_input("Gols Marcados/Jogo (Fora)", min_value=0.5, value=1.2, step=0.01, format="%.2f")
        gols_sofridos_fora = st.number_input("Gols Sofridos/Jogo (Fora)", min_value=0.5, value=0.7, step=0.01, format="%.2f")
        eficacia_conversao_fora = st.number_input(
            "Eficácia de Conversão (Decimal)", 
            min_value=0.01, 
            max_value=0.50, 
            value=0.10, 
            step=0.01, 
            format="%.2f",
            help="Insira a taxa de conversão como decimal (Ex: 0.10 para 10%)."
        )


with col3:
    st.header("📈 Odds de Mercado")
    
    st.subheader("Odds Pré-Jogo (Força do Mercado)")
    
    # INPUTS 1X2
    st.markdown("Odds 1X2")
    col3_1, col3_2, col3_3 = st.columns(3)
    with col3_1:
        odds_1 = st.number_input("Odds 1 (Casa)", min_value=1.01, value=2.20, step=0.01, format="%.2f")
    with col3_2:
        odds_x = st.number_input("Odds X (Empate)", min_value=1.01, value=3.40, step=0.01, format="%.2f")
    with col3_3:
        odds_2 = st.number_input("Odds 2 (Fora)", min_value=1.01, value=3.20, step=0.01, format="%.2f")
    
    # INPUTS O/U 1.5
    st.markdown("Odds Over/Under 1.5")
    odds_over_1_5_pre = st.number_input("Odds Over 1.5 (Pré-Jogo)", min_value=1.01, value=1.30, step=0.01, format="%.2f")
    odds_under_1_5_pre = st.number_input("Odds Under 1.5 (Pré-Jogo)", min_value=1.01, value=3.40, step=0.01, format="%.2f")

    # INPUTS O/U 2.5 (Usados para o Lambda)
    st.markdown("Odds Over/Under 2.5 (Usado para o Lambda)")
    odds_over_pre = st.number_input("Odds Over 2.5 (Pré-Jogo)", min_value=1.01, value=1.90, step=0.01, format="%.2f")
    odds_under_pre = st.number_input("Odds Under 2.5 (Pré-Jogo)", min_value=1.01, value=1.90, step=0.01, format="%.2f")


    st.subheader("Odds In-Play (Para EV)")
    st.markdown("Odds Over/Under 0.5 Gols Restantes (Odds atuais)")
    odds_over_mkt = st.number_input("Odds Over 0.5 (In-Play)", min_value=1.01, value=1.60, step=0.01, format="%.2f")
    odds_under_mkt = st.number_input("Odds Under 0.5 (In-Play)", min_value=1.01, value=2.20, step=0.01, format="%.2f")


# --- BOTÃO E EXECUÇÃO ---
if st.button("Calcular Projeção e EV (3 Cenários)", type="primary"):
    
    # Executa o modelo
    resultados, erro = modelo_xg_dinamico_avancado_sem_momentum(
        xg_home=xg_home, xg_away=xg_away,
        minutos_jogados=minutos_jogados,
        placar_home=placar_home, placar_away=placar_away,
        odds_over_mkt=odds_over_mkt, odds_under_mkt=odds_under_mkt,
        gols_marcados_casa=gols_marcados_casa, gols_sofridos_fora=gols_sofridos_fora, eficacia_conversao_casa=eficacia_conversao_casa,
        gols_marcados_fora=gols_marcados_fora, gols_sofridos_casa=gols_sofridos_casa, eficacia_conversao_fora=eficacia_conversao_fora,
        media_liga_gols_por_jogo=media_liga_gols_por_jogo,
        # INPUTS PASSADOS
        odds_over_pre=odds_over_pre, odds_under_pre=odds_under_pre,
        odds_1=odds_1, odds_x=odds_x, odds_2=odds_2,
        odds_over_1_5_pre=odds_over_1_5_pre, odds_under_1_5_pre=odds_under_1_5_pre,
        duracao=duracao
    )

    if erro:
        st.error(erro)
    else:
        st.divider()
        st.header("💡 Resultados da Projeção e Valor Esperado (EV)")
        
        # Colunas de Resultados
        col_fat, col_base, col_dir, col_mkt = st.columns(4)
        fatores = resultados["Fatores Dinâmicos"]

        # 1. Fatores Fixo
        with col_fat:
            st.subheader("Fatores Aplicados")
            st.metric(label="Fator Momentum Casa", value=f"{fatores['Momentum Home']:.2f}", help="Fixo em 1.0 (Neutro)")
            st.metric(label="Fator Momentum Visitante", value=f"{fatores['Momentum Away']:.2f}", help="Fixo em 1.0 (Neutro)")
            st.metric(label="Fator Mando de Campo", value=f"{fatores['Fator Mando Fixo']:.2f}", help="Fixo em 1.0 (Neutro)")

        # Função auxiliar para exibir o EV
        def display_ev_column(col, result_key, title):
            res = resultados[result_key]
            with col:
                st.subheader(title)
                st.caption(f"Fator Casa: **{res['Fator Casa Usado']:.2f}** | Fator Fora: **{res['Fator Fora Usado']:.2f}**")
                st.caption(f"Sorte Casa: **{res['Fator Sorte Casa']:.2f}** | Sorte Fora: **{res['Fator Sorte Fora']:.2f}**") # NOVO

                st.metric(label="xG Esperado (λ)", value=f"{res['lambda']:.3f}")
                
                # EV Over/Under
                st.markdown("**Under/Over 0.5 Gols Restantes**")
                ev_under_valor = res['EV Under (%)']
                ev_over_valor = res['EV Over (%)'] 
                
                # EV Under
                st.metric(
                    label=f"💰 EV Under ({odds_under_mkt:.2f})", 
                    value=f"{ev_under_valor:.1f}%", 
                    delta_color="normal" if ev_under_valor > 0 else "inverse", 
                    delta="Vantagem" if ev_under_valor > 0 else "Desvantagem"
                )
                # EV Over
                st.metric(
                    label=f"💰 EV Over ({odds_over_mkt:.2f})", 
                    value=f"{ev_over_valor:.1f}%", 
                    delta_color="normal" if ev_over_valor > 0 else "inverse", 
                    delta="Vantagem" if ev_over_valor > 0 else "Desvantagem"
                )
                
                st.markdown("---")
                # 1X2
                st.markdown(f"**P(Final 1X2):**")
                st.text(f"Casa: {res['P(Casa)']:.1%}")
                st.text(f"Empate: {res['P(Empate)']:.1%}")
                st.text(f"Fora: {res['P(Fora)']:.1%}")

        # 2. Modelo Estatístico (Baseline)
        display_ev_column(col_base, "Modelo Base (Baseline)", "1. Estatístico (Baseline)")
        
        # 3. Modelo Estatístico (Direto)
        display_ev_column(col_dir, "Modelo Direto (Comparação)", "2. Estatístico (Direto)")
        
        # 4. Modelo Mercado
        display_ev_column(col_mkt, "Modelo Mercado", "3. Expectativa Mercado")
        
        st.divider()
        st.markdown(
            "***Estabilidade Final:*** O **Fator Sorte** (Gols/xG) agora é aplicado, mas limitado a **1.5x** para evitar inflação. O **Ajuste por Placar** também foi suavizado para $0.85/1.15$."
        )
