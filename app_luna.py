
import os
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from groq import Groq

# Carrega variáveis locais se existirem (.env)
load_dotenv()

# CONFIGURAÇÃO DO BANCO DE DADOS 
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./luna.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# MODELOS DE DADOS 
class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    senha = Column(String, nullable=False)
    vendas = relationship("Venda", back_populates="usuario")

class Venda(Base):
    __tablename__ = "vendas"
    id = Column(Integer, primary_key=True, index=True)
    produto = Column(String, nullable=False)
    quantidade = Column(Integer, nullable=False)
    valor = Column(Float, nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    usuario = relationship("Usuario", back_populates="vendas")

Base.metadata.create_all(bind=engine)

# CÉREBRO DA IA (LUNA) 
def consultar_luna(pergunta_usuario: str, usuario_id: int, db):
    vendas = db.query(Venda).filter(Venda.usuario_id == usuario_id).all()
    
    if vendas:
        # Transforma em DataFrame para agrupar dados duplicados
        dados_lista = [{"Produto": v.produto.strip().title(), "Quantidade": v.quantidade, "Valor": v.valor} for v in vendas]
        df_ia = pd.DataFrame(dados_lista)
        
        # Agrupa por produto somando as quantidades e os valores
        df_ia_agrupado = df_ia.groupby("Produto").agg({"Quantidade": "sum", "Valor": "sum"}).reset_index()
        
        dados_vendas = "Histórico de Vendas Consolidado e Atualizado do Cliente:\n"
        for _, linha in df_ia_agrupado.iterrows():
            dados_vendas += f"- Produto: {linha['Produto']} | Qtd Total Vendida: {linha['Quantidade']} | Faturamento Total do Item: R$ {linha['Valor']:.2f}\n"
    else:
        dados_vendas = "O usuário ainda não possui vendas cadastradas.\n"

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "⚠️ Erro: A chave 'GROQ_API_KEY' não foi configurada."
        
    client = Groq(api_key=api_key)
    
    prompt_sistema = (
        "Você é a Luna, uma consultora de negócios e analista de inteligência comercial altamente estratégica. "
        "Seu objetivo é analisar os dados de vendas fornecidos e responder à pergunta do usuário trazendo "
        "insights valiosos, padrões ocultos, ideias de combos, estratégias de marketing e planos de ação práticos. "
        "Seja profissional, empática, motivadora e direta.\n"
        "REGRAS CRÍTICAS DE TEXTO: Escreva em parágrafos limpos e bem espaçados. "
        "Nunca repita a mesma informação. Sempre use o formato de moeda brasileiro correto (ex: R$ 10.500,00) "
        "e certifique-se de colocar um espaço entre o 'R$' e o número. Evite caracteres matemáticos estranhos.\n\n"
        f"{dados_vendas}"
    )
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": pergunta_usuario}
            ],
            temperature=0.6, 
            max_tokens=1024
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"Desculpe, a Luna encontrou um problema: {str(e)}"

# INTERFACE STREAMLIT 
st.set_page_config(page_title="Luna AI - Mercado Luamar", page_icon="📊", layout="centered")

def cadastrar_usuario(nome, email, senha):
    db = SessionLocal()
    existe = db.query(Usuario).filter(Usuario.email == email).first()
    if existe:
        db.close()
        return False
    novo_usuario = Usuario(nome=nome, email=email, senha=senha)
    db.add(novo_usuario)
    db.commit()
    db.close()
    return True

def fazer_login(email, senha):
    db = SessionLocal()
    usuario = db.query(Usuario).filter(Usuario.email == email, Usuario.senha == senha).first()
    db.close()
    return usuario

def salvar_venda(produto, quantidade, valor, usuario_id):
    db = SessionLocal()
    # Força o nome do produto a ficar padronizado em minúsculo e limpo
    nome_limpo = str(produto).strip().lower()
    nova_venda = Venda(produto=nome_limpo, quantidade=int(quantidade), valor=float(valor), usuario_id=usuario_id)
    db.add(nova_venda)
    db.commit()
    db.close()

def buscar_vendas(usuario_id):
    db = SessionLocal()
    vendas = db.query(Venda).filter(Venda.usuario_id == usuario_id).all()
    db.close()
    return vendas

if "usuario" not in st.session_state:
    st.session_state.usuario = None

# TELA DE ACESSO 
if st.session_state.usuario is None:
    st.title("🌙 Luna Business AI")
    st.subheader("Faça login ou crie sua conta corporativa")
    
    aba_login, aba_cadastro = st.tabs(["🔑 Login", "📝 Cadastrar Empresa"])
    
    with aba_login:
        email_log = st.text_input("E-mail", key="email_log")
        senha_log = st.text_input("Senha", type="password", key="senha_log")
        if st.button("Entrar", key="btn_login"):
            user = fazer_login(email_log, senha_log)
            if user:
                st.session_state.usuario = {"id": user.id, "nome": user.nome}
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos.")
                
    with aba_cadastro:
        nome_cad = st.text_input("Nome da Empresa/Usuário", key="nome_cad")
        email_cad = st.text_input("E-mail de Acesso", key="email_cad")
        senha_cad = st.text_input("Senha de Segurança", type="password", key="senha_cad")
        if st.button("Criar Conta", key="btn_cad"):
            if nome_cad and email_cad and senha_cad:
                sucesso = cadastrar_usuario(nome_cad, email_cad, senha_cad)
                if sucesso:
                    st.success("Conta criada! Faça login ao lado.")
                else:
                    st.error("Este e-mail já está cadastrado.")

# PAINEL PRINCIPAL LOGADO 
else:
    st.title(f"📊 Painel Estratégico - {st.session_state.usuario['nome']}")
    
    if st.sidebar.button("🚪 Sair do Sistema"):
        st.session_state.usuario = None
        st.rerun()
        
    aba_vendas, aba_chat = st.tabs(["🛒 Gerenciamento de Vendas", "🌙 Converse com Luna AI"])
    
    with aba_vendas:
        st.subheader("Cadastrar Nova Venda")
        col_man, col_plan = st.columns(2)
        
        with col_man:
            st.markdown("### ✍️ Lançar Manualmente")
            with st.form("form_venda", clear_on_submit=True):
                prod = st.text_input("Nome do Produto")
                qtd = st.number_input("Quantidade", min_value=1, step=1)
                val = st.number_input("Preço Unitário (R$)", min_value=0.01, step=0.01)
                if st.form_submit_button("Salvar Venda"):
                    if prod:
                        # Multiplica a quantidade pelo valor unitário digitado
                        faturamento_manual = int(qtd) * float(val)
                        
                        salvar_venda(prod, qtd, faturamento_manual, st.session_state.usuario["id"])
                        st.success(f"Venda de '{prod}' salva com sucesso!")
                        st.rerun()
                    else:
                        st.error("Digite o nome do produto.")
                        
        with col_plan:
            st.markdown("### 📁 Importar Vendas por Planilha (Inteligente)")
            # AGORA ACEITA CSV E EXCEL (.xlsx)
            arquivo_upload = st.file_uploader("Arraste seu arquivo CSV ou Excel de vendas aqui", type=["csv", "xlsx"])
            
            if arquivo_upload is not None:
                try:
                    # Identifica se o usuário subiu Excel ou CSV e lê do jeito certo
                    if arquivo_upload.name.endswith('.xlsx'):
                        df_upload = pd.read_excel(arquivo_upload)
                    else:
                        df_upload = pd.read_csv(arquivo_upload)
                        
                    colunas_do_arquivo = list(df_upload.columns)
                    
                    st.warning("⚠️ Identifique as colunas da sua planilha para o sistema entender:")
                    
                    # Cria caixinhas de seleção para o usuário dizer quem é quem
                    col_prod = st.selectbox("Qual coluna representa o Produto?", colunas_do_arquivo, 
                                            index=colunas_do_arquivo.index("Produto") if "Produto" in colunas_do_arquivo else 0)
                    
                    col_qtd = st.selectbox("Qual coluna representa a Quantidade?", colunas_do_arquivo,
                                           index=colunas_do_arquivo.index("Quantidade") if "Quantidade" in colunas_do_arquivo else 0)
                    
                    col_val = st.selectbox("Qual coluna representa o Valor/Preço?", colunas_do_arquivo,
                                           index=colunas_do_arquivo.index("Valor") if "Valor" in colunas_do_arquivo else 0)
                    
                    if st.button("🚀 Confirmar Carga no Banco"):
                        for _, linha in df_upload.iterrows():
                            quantidade_item = int(linha[col_qtd])
                            valor_unitario = float(linha[col_val])
                            faturamento_calculado = quantidade_item * valor_unitario
                                
                            salvar_venda(
                                produto=str(linha[col_prod]),
                                quantidade=quantidade_item,
                                valor=faturamento_calculado,
                                usuario_id=st.session_state.usuario["id"]
                            )
                        st.success("Planilha importada com sucesso!")
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Erro ao ler arquivo: {str(e)}")

        # PROCESSAMENTO DOS METRICS E GRÁFICOS 
        lista_vendas = buscar_vendas(st.session_state.usuario["id"])
        
        if lista_vendas:
            # PADRONIZAÇÃO: Garante que os nomes vão todos em minúsculo para agrupar 100% certo
            dados = [{"Produto": str(v.produto).strip().lower(), "Quantidade": v.quantidade, "Faturamento": v.valor} for v in lista_vendas]
            df = pd.DataFrame(dados)
            
            # Garante tipos corretos
            df["Faturamento"] = pd.to_numeric(df["Faturamento"], errors='coerce')
            df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors='coerce')
            
            # Consolida dados por produto (Soma tudo sem duplicar nomes)
            df_agrupado = df.groupby("Produto").agg({"Faturamento": "sum", "Quantidade": "sum"}).reset_index()
            
            # Ordena do menor para o maior faturamento
            df_agrupado = df_agrupado.sort_values(by="Faturamento", ascending=True)
            
            # Cálculos dos blocos de destaque (KPIs)
            faturamento_total = df_agrupado["Faturamento"].sum()
            idx_mais_vendido = df_agrupado["Quantidade"].idxmax()
            produto_mais_vendido = df_agrupado.loc[idx_mais_vendido, "Produto"]
            
            # Exibição dos cards de destaque formatados bonitos em R$
            col_kpi1, col_kpi2 = st.columns(2)
            faturamento_formatado = f"R$ {faturamento_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            col_kpi1.metric("Faturamento Total", faturamento_formatado)
            col_kpi2.metric("Produto Mais Vendido (Qtd)", str(produto_mais_vendido).title())
            
            st.divider()
            st.subheader("📊 Análise de Desempenho por Produto")
            
            # Desenha o Gráfico Horizontal Ajustado
            fig, ax = plt.subplots(figsize=(8, 4.5))
            
            # Deixa os nomes dos produtos mais bonitos no eixo vertical do gráfico (Primeira letra maiúscula)
            nomes_grafico = [p.title() for p in df_agrupado["Produto"]]
            ax.barh(nomes_grafico, df_agrupado["Faturamento"], color="#6C5CE7")
            
            ax.set_xticklabels([])
            ax.set_xticks([])
            
            ax.set_ylabel("Produto")
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_visible(False) 
            
            # Dá um respiro excelente na esquerda para os nomes não sumirem
            plt.tight_layout()
            st.pyplot(fig)
            
            # Formata também os valores da tabela inferior para ficarem limpos e organizados
            df_visual = df.copy()
            df_visual["Faturamento"] = df_visual["Faturamento"].map(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            df_visual["Produto"] = df_visual["Produto"].str.title()
            
            st.dataframe(df_visual, use_container_width=True)
        else:
            st.info("Nenhum dado encontrado. Faça um lançamento ou importe um CSV!")

    with aba_chat:
        st.subheader("🌙 Converse com a Luna AI")
        st.caption("Peça análises sobre suas vendas, ideias de promoções ou estratégias de crescimento.")
        
        # Cria o histórico de chat se ele ainda não existir
        if "historico_chat" not in st.session_state:
            st.session_state.historico_chat = []
            
        # Cria um container exclusivo para as mensagens para o Streamlit não se perder
        container_mensagens = st.container()
        
        with container_mensagens:
            for msg in st.session_state.historico_chat:
                with st.chat_message(msg["role"]):
                    st.write(msg["text"])
                    
        pergunta = st.chat_input("Como podemos melhorar as vendas Luna?", key="input_chat_luna")
        
        if pergunta:
            # Salva a pergunta do usuário
            st.session_state.historico_chat.append({"role": "user", "text": pergunta})
            st.rerun()

# ESSA PARTE PROCESSA A RESPOSTA DA LUNA FORA DAS ABAS 
if st.session_state.usuario is not None and "historico_chat" in st.session_state and st.session_state.historico_chat:
    if st.session_state.historico_chat[-1]["role"] == "user":
        pergunta_atual = st.session_state.historico_chat[-1]["text"]
        
        # Exibe o carregamento simulado na tela
        st.toast("Luna está lendo o banco de dados...", icon="🌙")
        
        db = SessionLocal()
        resposta_luna = consultar_luna(
            pergunta_usuario=pergunta_atual,
            usuario_id=st.session_state.usuario["id"],
            db=db
        )
        db.close()
        
        # Adiciona a resposta da Luna e recarrega a página para atualizar o chat
        st.session_state.historico_chat.append({"role": "assistant", "text": resposta_luna})
        st.rerun()