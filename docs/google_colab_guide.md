# ⚡ Guia Completo do Google Colab & MCP Server

O **Google Colab** oferece acesso gratuito a aceleradores gráficos de alta performance (**NVIDIA T4, L4 e A100**), permitindo que você processe centenas de páginas de mangá em minutos sem consumir bateria ou aquecer sua máquina local.

O Kira suporta **três formas flexíveis** de utilização com o Google Colab:

---

## Modo 1: Execução Automatizada via Terminal (`kira colab-run`)

Esta é a forma mais prática e rápida. Você não precisa abrir nenhum navegador:

```bash
kira colab-run -i "Manga_Inputs" -o "Kindle_Outputs" --gpu T4
```

### O que acontece nos bastidores:
1. O Kira provisiona uma sessão remota no Google Colab com a GPU selecionada.
2. Monta o seu Google Drive em `/content/drive/MyDrive`.
3. Dispara o processamento dos mangás encontrados em `Manga_Inputs`.
4. Transmite o log de upscale e conversão em tempo real no seu terminal local.
5. Salva os e-books prontos na sua pasta `Kindle_Outputs` do Google Drive.
6. **Desliga a GPU do Colab automaticamente** para economizar seus créditos!

---

## Modo 2: Execução Interativa no Navegador ([`Kira_Manga_Pipeline.ipynb`](file:///home/henrique/projetos/kira/Kira_Manga_Pipeline.ipynb))

Se você preferir uma interface visual em células interativas:

1. Abra o arquivo [`Kira_Manga_Pipeline.ipynb`](file:///home/henrique/projetos/kira/Kira_Manga_Pipeline.ipynb) no [Google Colab Web](https://colab.research.google.com).
2. Selecione o ambiente de execução com GPU:
   - Menu: **Ambiente de Execução** ➔ **Alterar tipo de ambiente de execução** ➔ **T4 GPU**.
3. Execute as células sequencialmente:
   - **Célula 1**: Montagem do Google Drive (`drive.mount('/content/drive')`).
   - **Célula 2**: Instalação automática do Kira e do Real-ESRGAN.
   - **Célula 3**: Execução do pipeline em lote apontando para suas pastas.

---

## Modo 3: Servidor MCP do Google Colab no Antigravity IDE

O Kira possui integração nativa com o protocolo MCP (*Model Context Protocol*) através do servidor `googlecolab/colab-mcp`.

### Configuração do MCP
O arquivo de configuração do MCP já está preparado no repositório em [`.agents/mcp_config.json`](file:///home/henrique/projetos/kira/.agents/mcp_config.json):

```json
{
  "mcpServers": {
    "colab-mcp": {
      "command": "/home/henrique/.local/bin/colab-mcp-runner",
      "args": []
    }
  }
}
```

O script utilitário `colab-mcp-runner` gerencia os sinais de encerramento (`SIGTERM`) e garante que a comunicação entre o assistente de IA e suas instâncias de nuvem permaneça estável.

---

## 📂 Estrutura de Pastas Recomendada no Google Drive

Para máxima organização, crie as seguintes pastas na raiz do seu Google Drive:

```
Meu Drive/
├── Manga_Inputs/            <- Coloque seus mangás aqui (.cbz, .zip, .rar ou pastas)
│   ├── Attack_on_Titan/
│   ├── Death_Note_Ch_01.cbz
│   └── Monster_Vol_01.zip
│
└── Kindle_Outputs/          <- O Kira salvará os e-books finais aqui (.epub prontos)
    ├── Attack_on_Titan_Vol_01.epub
    ├── Death_Note_Vol_01.epub
    └── Monster_Vol_01.epub
```

---

## 💰 Dicas para Economia de Recursos
- Sempre utilize a flag padrão `--auto-stop` no `kira colab-run` para garantir que a VM seja desligada assim que o último volume for convertido.
- Se estiver processando uma coleção muito grande (+1.000 páginas), a GPU **L4** ou **A100** oferece até 3x mais velocidade na passagem dos modelos neurais.
