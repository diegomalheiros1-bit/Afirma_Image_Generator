def build_prompt(prompt_padrao: str, prompt_variacao: str) -> str:
    parts = [p.strip() for p in [prompt_padrao, prompt_variacao] if p and p.strip()]
    if not parts:
        raise ValueError("Prompt vazio.")
    return "\n\n".join(parts)
