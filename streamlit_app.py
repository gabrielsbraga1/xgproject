import streamlit as st
import math

# ==============================================================================
# ⚽ FUNÇÃO DO MODELO xG DINÂMICO
# ==============================================================================

def modelo_xg_dinamico(
    xg_home, xg_away,
    minutos_jogados,
    placar_home, placar_away,
    odds_over, odds_under,
    xg_home_pregame=1.6, xg_away_pregame=1.4,
    fator_mando=1.1,  # boost de 10% para o mandante
    momentum_home=1.0, momentum_away=1.0,  # >1 se estiver pressionando
    duracao=90
):
    """
    Modelo dinâmico de previsão de gols baseado em xG e contexto de jogo.
    """
    
    # Prevenção de divisão por zero
    if minutos_jogados == 0:
        return None, "Erro: Minutos jogados não podem ser zero."

    # === 1. Cálculo do ritmo de xG até agora ===
    ritmo_home = (xg_home / minutos_jogados)
    ritmo_away = (xg_away / minutos_jogados)

    # === 2. Ajuste de ritmo pelo contexto do placar ===
    ajuste_home = 1.0
    ajuste_away = 1.0

    if placar_home > placar_away:  # mandante vencendo
        ajuste_home = 0.7
        ajuste_away = 1.4
    elif placar_home < placar_away:  # mandante perdendo
        ajuste_home = 1.4
        ajuste_away = 0.7

    # === 3. Ajuste por força pré-jogo e mando de campo ===
    # Multiplicamos pelo fator de pré-jogo e contexto do placar/mando/momentum.
    
    ritmo_proj_home = ritmo_home * (xg_home_pregame / 1.5) * fator_mando * ajuste_home * momentum_home
    ritmo_proj_away = ritmo_away * (xg_away_pregame / 1.5) * ajuste_away * momentum_away


    # === 4. Cálculo de tempo restante e xG projetado ===
    minutos_restantes = duracao - minutos_jogados
    xg_restante = (ritmo_proj_home + ritmo_proj_away) * minutos_restantes
    
    # Variável lambda (λ) para Poisson
    lambda_xg_restante = xg_restante  

    if minutos_restantes <= 0:
        return None, "Erro: O jogo já acabou (ou o tempo inserido é maior que a duração total)."

    # === 5. Probabilidades via Poisson ===
    p0 = math.exp(-lambda_xg_restante)
    p1 = lambda_xg_restante * math.exp(-lambda_xg_restante)
    p2plus = 1 - (p0 + p1)
    pover = 1 - p0  # probabilidade de sair ao menos 1 gol

    # === 6. Odds justas ===
    odds = lambda p: 1 / p if p > 0 else float("inf")

    odd_justa_over = odds(pover)
    odd_justa_under = odds(p0)

    # === 7. Probabilidades implícitas do mercado e EV ===
    
    # 8. Valor esperado (EV%) ===
    ev_over = (pover * odds_over) - 1
    ev_under = (p0 * odds_under) - 1

    return {
        "Lambda (xG esperado até fim)": round(lambda_xg_restante, 3),
        "P(0 gols) - Probabilidade de *nenhum* gol": round(p0, 3),
        "P(>=1 gol) - Probabilidade de *ao menos um* gol": round(pover, 3),
        "Odd Justa Over (>=1 gol)": round(odd_justa_over, 2),
        "Odd Justa Under (0 gols)": round(odd_justa_under, 2),
        "EV Over (baseado em P(>=1)) (%)": round(ev_over * 100, 1),
        "EV Under (baseado em P(0)) (%)": round(ev_under * 100, 1),
        "Prob. Implícita Over Mercado": round(1 / odds_over, 3),
        "Prob. Implícita Under Mercado": round(1 / odds_under, 3)
    }, None

# ==============================================================================
# 🏠 INTERFACE STREAMLIT
# ==============================================================================

st.set_page_config(
    page_title="Modelo Dinâmico xG (Probabilidade de Gols)", 
    layout="wide"
)

st.title("⚽ Modelo Dinâmico xG para Previsão de Gols")
st.markdown("Insira os dados em tempo real do jogo para obter a projeção de gols restantes e o Valor Esperado (EV).")

st.divider()

# --- INPUTS DO JOGO (COLUNA 1) ---
col1, col2, col3 = st.columns(3)

with col1:
    st.header("⏱️ Contexto do Jogo")
    minutos_jogados = st.slider("Minutos Jogados", 1, 90, 70)
    placar_home = st.number_input("Placar Time da Casa", min_value=0, value=1, step=1)
    placar_away = st.number_input("Placar Time Visitante", min_value=0, value=0, step=1)
    duracao = st.number_input("Duração Total do Jogo (min)", min_value=60, max_value=120, value=90, step=5)

with col2:
    st.header("📊 xG Acumulado")
    xg_home = st.number_input("xG Time da Casa", min_value=0.0, value=1.31, step=0.01, format="%.2f")
    xg_away = st.number_input("xG Time Visitante", min_value=0.0, value=0.57, step=0.01, format="%.2f")

    st.header("✨ Fatores de Ajuste")
    fator_mando = st.slider("Fator Mando de Campo", 0.5, 2.0, 1.1, 0.05, help="Multiplicador de xG para o time da casa. 1.1 = 10% de boost.")
    momentum_home = st.slider("Momentum Casa", 0.5, 2.0, 0.9, 0.05, help="Multiplicador de xG. >1 se estiver pressionando/jogando melhor.")
    momentum_away = st.slider("Momentum Visitante", 0.5, 2.0, 1.2, 0.05, help="Multiplicador de xG. >1 se estiver pressionando/jogando melhor.")

with col3:
    st.header("📈 Odds de Mercado")
    st.markdown("Para fins de EV, use as odds para Over/Under 1.5 ou 0.5 conforme o mercado (o modelo usa P(>=1) e P(0)).")
    odds_over = st.number_input("Odds Over (Ex: Over 0.5 gols)", min_value=1.01, value=1.60, step=0.01, format="%.2f")
    odds_under = st.number_input("Odds Under (Ex: Under 0.5 gols)", min_value=1.01, value=2.20, step=0.01, format="%.2f")
    
    st.header("⭐ Força Pré-Jogo (xG esperado)")
    xg_home_pregame = st.number_input("xG Esperado Casa (Pré-jogo)", min_value=0.5, value=1.7, step=0.01, format="%.2f", help="Força ofensiva esperada antes do jogo.")
    xg_away_pregame = st.number_input("xG Esperado Visitante (Pré-jogo)", min_value=0.5, value=1.5, step=0.01, format="%.2f", help="Força ofensiva esperada antes do jogo.")


# --- BOTÃO E EXECUÇÃO ---
if st.button("Calcular Projeção e EV", type="primary"):
    
    # Executa o modelo
    resultado, erro = modelo_xg_dinamico(
        xg_home=xg_home, xg_away=xg_away,
        minutos_jogados=minutos_jogados,
        placar_home=placar_home, placar_away=placar_away,
        odds_over=odds_over, odds_under=odds_under,
        xg_home_pregame=xg_home_pregame, xg_away_pregame=xg_away_pregame,
        fator_mando=fator_mando, momentum_home=momentum_home, momentum_away=momentum_away,
        duracao=duracao
    )

    if erro:
        st.error(erro)
    else:
        st.divider()
        st.header("💡 Resultados da Projeção e Valor Esperado (EV)")
        
        col_res1, col_res2 = st.columns(2)
        
        with col_res1:
            st.subheader("Projeção do Modelo (xG Remanescente e Poisson)")
            st.metric(
                label="xG Total Esperado até o Final (λ)", 
                value=f"{resultado['Lambda (xG esperado até fim)']:.3f}", 
                help="Parâmetro λ da distribuição de Poisson. É a soma do xG projetado (casa + fora) até o fim do jogo."
            )
            st.metric(
                label="Prob. de 0 Gols (P0)", 
                value=f"{resultado['P(0 gols) - Probabilidade de *nenhum* gol']:.1%}",
                help="Probabilidade de NÃO sair mais NENHUM gol no jogo, baseada na distribuição de Poisson."
            )
            st.metric(
                label="Prob. de ≥1 Gol (Pover)", 
                value=f"{resultado['P(>=1 gol) - Probabilidade de *ao menos um* gol']:.1%}",
                help="Probabilidade de sair ao menos UM gol no jogo, baseada na distribuição de Poisson."
            )

        with col_res2:
            st.subheader("Odds Justas e Valor Esperado (EV)")
            
            # Formatação condicional para EV
            ev_over_valor = resultado['EV Over (baseado em P(>=1)) (%)']
            ev_under_valor = resultado['EV Under (baseado em P(0)) (%)']
            
            # EV Over
            st.metric(
                label=f"💰 EV Over ({odds_over:.2f})", 
                value=f"{ev_over_valor:.1f}%", 
                delta_color="normal" if ev_over_valor > 0 else "inverse", 
                delta="Vantagem" if ev_over_valor > 0 else ("Desvantagem" if ev_over_valor < 0 else "Neutro")
            )

            # EV Under
            st.metric(
                label=f"💰 EV Under ({odds_under:.2f})", 
                value=f"{ev_under_valor:.1f}%", 
                delta_color="normal" if ev_under_valor > 0 else "inverse", 
                delta="Vantagem" if ev_under_valor > 0 else ("Desvantagem" if ev_under_valor < 0 else "Neutro")
            )
            
            st.metric(
                label="Odd Justa Over (Modelo)", 
                value=f"{resultado['Odd Justa Over (>=1 gol)']:.2f}",
                help="Odds calculada pelo seu modelo para P(>=1 gol)."
            )
            st.metric(
                label="Odd Justa Under (Modelo)", 
                value=f"{resultado['Odd Justa Under (0 gols)']:.2f}",
                help="Odds calculada pelo seu modelo para P(0 gols)."
            )

        st.divider()
        st.markdown(
            """
            ⚠️ **Atenção:** Seu cálculo de EV usa as probabilidades de **P(0 gols)** e **P(>=1 gol)**. 
            O Valor Esperado (EV) mostra a sua vantagem (ou desvantagem) ao apostar em 0 gols ou no mínimo 1 gol.
            """
        )
