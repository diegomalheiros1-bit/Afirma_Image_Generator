"""Read-only authentication probe. Never logs provider responses or credentials."""


def check_api_connection(key):
    from openai import OpenAI, APITimeoutError, APIConnectionError

    try:
        # Explicit destination: OPENAI_BASE_URL must not redirect the user's key.
        # No image endpoint, no hidden SDK retries and no model list in UI state.
        with OpenAI(api_key=key, base_url="https://api.openai.com/v1",
                    timeout=10, max_retries=0) as client:
            client.models.list()
        return {"status": "connected", "message": "Autenticação confirmada nesta verificação."}
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        if isinstance(exc, APITimeoutError):
            message = "A verificação demorou além do esperado. Tente novamente."
        elif isinstance(exc, APIConnectionError):
            message = "Não foi possível acessar a OpenAI. Confira sua conexão e tente novamente."
        else:
            message = {
                401: "Autenticação recusada. Confira a chave e as restrições de acesso da sua conta.",
                403: "A conta ou chave não tem permissão para esta verificação. Confira as permissões na OpenAI.",
                429: "A OpenAI limitou a verificação. Confira os limites da conta e tente novamente mais tarde.",
            }.get(status, "A conexão não pôde ser confirmada. Tente novamente em instantes.")
        return {"status": "disconnected", "message": message}
