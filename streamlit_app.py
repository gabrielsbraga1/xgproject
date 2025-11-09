import streamlit as st

st.set_page_config(page_title="Teste de Conexão Streamlit", layout="centered")

st.title("✅ DEPLOY BEM-SUCEDIDO!")
st.subheader("Sua conexão Streamlit Cloud está funcionando.")

st.markdown("""
Parabéns! Este aplicativo foi implantado com sucesso.

Agora, você pode substituir o conteúdo deste arquivo pelo código do seu modelo xG.
""")

if st.button("Clique Aqui para Confirmar"):
    st.balloons()
