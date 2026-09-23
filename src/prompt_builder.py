def build_prompt(prompt_padrao: str, prompt_variacao: str, *, tema="", produto="",
                 observacao_usuario="", prompt_negativo="") -> str:
    parts = [p.strip() for p in [prompt_padrao, prompt_variacao] if p and p.strip()]
    if not parts:
        raise ValueError("Prompt vazio.")
    for label, value in [("Tema", tema), ("Produto", produto),
                         ("Observação do usuário", observacao_usuario), ("Evitar", prompt_negativo)]:
        if value.strip():
            parts.append(f"{label}: {value.strip()}")
    return "\n\n".join(parts)
