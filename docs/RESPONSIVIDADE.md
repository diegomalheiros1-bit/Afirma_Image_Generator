# Layout fluido — versão 1.0.11

O contêiner principal deixou de limitar a Home a 1.400 px. Cabeçalho, ferramentas,
avisos, painéis e histórico usam a mesma largura disponível, com margens laterais
fluidas: aproximadamente 32 px em 1.920 px, até 48 px em telas maiores e 10–12 px
em janelas pequenas. A mudança não altera zoom, fontes ou regras de geração.

Os painéis de campanha mantêm a proporção 1,12:1. Até 1.100 px de área útil,
passam para uma coluna. O painel de acompanhamento mantém o alinhamento com o
esquerdo no modo de duas colunas; a linha do tempo continua com rolagem própria.
O estado vazio ocupa o espaço disponível com sua mensagem centralizada.

Configurações preservam o limite de 1.040 px e ficam alinhadas à margem inicial
do workspace. Textos de apresentação e explicação mantêm limites de leitura.
Campos acompanham a largura dos painéis, enquanto botões conservam tamanho
adequado ao conteúdo. Os temas, tooltips, foco e confirmações permanecem ativos.

O diagnóstico nativo usa uma instância WebView2 isolada, credenciais fictícias,
API real bloqueada e uma linha do tempo fictícia de 53 itens. A matriz verifica
larguras externas de 520, 768, 1.024, 1.366, 1.920 e 2.560 px, nos dois temas,
além de maximizar/restaurar e zoom do WebView2 de 125% e 150%.
O relatório registra a largura útil real, que exclui bordas e barras da janela.
As capturas `fluid-*.png` mostram Home, configurações e linha do tempo.

As verificações conferem ausência de rolagem horizontal da página ou controles
cortados, alinhamento das bordas, leitura dos formulários e rolagem interna da
linha do tempo. Os diálogos e fluxos existentes continuam na suíte nativa.
Zoom do WebView2 é usado apenas na validação; a escala de DPI do Windows do
usuário não é alterada.

Entrega local para revisão, sem publicar, substituir instalação, fechar a
instância do usuário ou realizar chamadas reais de API.
