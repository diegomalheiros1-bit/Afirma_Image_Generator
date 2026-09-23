# Prompt para iniciar no Codex

Quero que você continue o desenvolvimento deste projeto Python já criado.

## Contexto do negócio

O usuário atende clientes que solicitam lotes de 10, 20, 50 ou 100 imagens com o mesmo tema visual.

Existe:
- um prompt técnico padrão;
- uma variação por imagem;
- uma imagem de referência local;
- um nome de saída;
- controle de status.

Exemplo:
- tema: Dia das Mães;
- produtos: perfumes/cosméticos;
- prompt padrão: câmera, lente, luz, desfoque, crop, direção fotográfica etc.;
- variação: modelo negra, loira, mãe e filha, posição lateral etc.;
- referência: foto do produto a ser inserido na composição.

## Objetivo técnico

Criar um sistema simples e confiável em Python que leia `input/fila.xlsx`, processe as linhas pendentes e futuramente chame uma API de geração/edição de imagens.

## Estado atual

O MVP local já deve:
1. ler a planilha;
2. validar as colunas;
3. processar somente `PENDENTE`;
4. marcar `PROCESSANDO`;
5. validar se a referência existe;
6. combinar `Prompt_Padrao + Prompt_Variacao`;
7. registrar logs;
8. marcar `CONCLUIDO` na simulação;
9. marcar `ERRO` em caso de falha;
10. continuar a fila mesmo com erros.

## Requisitos de arquitetura

- Código modular.
- Evitar complexidade desnecessária.
- Fácil manutenção.
- Preparado para futura integração com API.
- Nunca armazenar chave real no código ou Excel.
- Não sobrescrever imagens silenciosamente.
- Reexecução deve ignorar `CONCLUIDO`.
- Erro em uma linha não deve parar a fila toda.

## Primeira tarefa no Codex

1. Revise o código existente.
2. Corrija problemas de arquitetura ou persistência da planilha.
3. Adicione testes unitários básicos para:
   - montagem de prompt;
   - validação de referência;
   - filtro de status;
   - tratamento de erro.
4. Garanta que a aba `Configuracao` da planilha não seja perdida ao salvar.
5. Não implemente API ainda.
6. Documente como executar os testes.
7. Faça alterações diretamente no projeto.

Depois disso, aguarde as imagens e a planilha real do cliente antes de implementar a geração de imagens.
