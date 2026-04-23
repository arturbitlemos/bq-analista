from mcp_core.server_factory import build_mcp_app

# Herda as 4 ferramentas base: get_context, consultar_bq, publicar_dashboard, listar_analises
app, main = build_mcp_app(agent_name="mcp-exec-devolucoes")

# Adicione ferramentas específicas do domínio devolucoes aqui, se necessário.

if __name__ == "__main__":
    main()
