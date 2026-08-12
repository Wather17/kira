# 🌸 Kira: Manga Upscale & Kindle Adaptation Pipeline

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Wather17/kira/blob/main/Kira_Manga_Pipeline.ipynb)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Kira** é um pipeline automatizado desenvolvido para amantes de mangás que desejam a melhor experiência de leitura no **Amazon Kindle**.

O Kira resolve dois problemas comuns em mangás digitais:
1. **Baixa resolução de páginas baixadas/scans**: melhora drasticamente a nitidez e as traços do mangá usando **Real-ESRGAN** (modelo `RealESRGAN_x4plus_anime_6B` especializado em traços de anime e retículas de mangá).
2. **Formatação incorreta no Kindle**: adapta as dimensões, contraste, gamma e ordem de leitura (Direita para Esquerda / RTL) para o modelo exato do seu e-reader Kindle usando a tecnologia do **KCC (Kindle Comic Converter)**.

---

## 🛠️ Arquitetura do Pipeline

```
┌───────────────────────────┐
│ Google Drive / Local      │ (Arquivos .cbz, .zip, .cbr, .rar ou pastas de imagens)
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│  Manga Extractor          │ (Extração e ordenação natural numérica das páginas)
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│ Real-ESRGAN Upscaler      │ (Upscale 4x com IA treinada para mangás em GPU Colab)
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│  Kindle Converter (KCC)   │ (Ajuste de margens, gamma, resolução de tela e RTL)
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│ Arquivo Final (.epub/.mobi│ (Salvo no Google Drive em MyDrive/Kindle_Outputs)
└───────────────────────────┘
```

---

## 🚀 Como Usar no Google Colab (Recomendado)

O Google Colab oferece **GPUs gratuitas (T4 / P100)** que tornam o upscale por Inteligência Artificial extremamente rápido.

1. Abra o notebook [Kira_Manga_Pipeline.ipynb](Kira_Manga_Pipeline.ipynb) no Google Colab clicando no botão **Open in Colab** no topo deste README.
2. Ative a GPU no Colab: `Ambiente de execução` -> `Alterar tipo de ambiente de execução` -> Selecione **GPU T4**.
3. Crie uma pasta no seu Google Drive (ex: `Manga_Inputs`) e coloque os arquivos `.cbz` do seu mangá lá.
4. Execute as células do Notebook:
   - **Passo 1**: Conectar seu Google Drive (`drive.mount('/content/drive')`).
   - **Passo 2**: Instalar dependências automáticas.
   - **Passo 3**: Definir suas preferências no formulário interativo e clicar em **Executar**.

Os arquivos convertidos prontos para ler no Kindle serão salvos automaticamente na pasta `Kindle_Outputs` do seu Google Drive!

---

## 💻 Como Usar Localmente (CLI)

### Instalação

```bash
# Clonar o repositório
git clone https://github.com/Wather17/kira.git
cd kira

# Instalar o pacote Kira em modo editável
pip install -e .
```

### Comandos Principais

#### 1. Processar Mangás (Upscale + Conversão Kindle)
```bash
kira process -i ~/Downloads/meus_mangas -o ~/Documentos/Kindle_Prontos --profile KPW5 --format EPUB
```

#### 2. Opções e Parâmetros da CLI
- `-i, --input`: Arquivo `.cbz` individual ou pasta contendo múltiplos arquivos/pastas.
- `-o, --output`: Pasta onde os arquivos finais para Kindle serão salvos.
- `-m, --model`: Modelo Real-ESRGAN (`RealESRGAN_x4plus_anime_6B` [padrão], `realesr-animevideov3`, `RealESRGAN_x4plus`).
- `-p, --profile`: Perfil do modelo do Kindle:
  - `KPW5`: Kindle Paperwhite 5 (11ª Geração, 6.8") [Padrão]
  - `KPW3`: Kindle Paperwhite 3/4 (6")
  - `KO`: Kindle Oasis (1/2/3)
  - `KS`: Kindle Scribe (10.2")
  - `K11`: Kindle Basic (11ª Geração - 2022)
  - `KV`: Kindle Voyage
- `-f, --format`: Formato de saída (`EPUB` [Recomendado para Send-to-Kindle], `MOBI`, `AZW3`, `CBZ`).
- `--gamma`: Ajuste de contraste para telas e-ink (padrão `1.0`, use `1.2` para escurecer traços).
- `--tile`: Tamanho do tile GPU para economizar VRAM (padrão `400`).

#### 3. Verificar Status do Ambiente
```bash
kira info
```

---

## 🧪 Testes

Para rodar os testes automatizados da biblioteca:

```bash
python3 -m unittest discover -s tests
```

---

## 📄 Licença

Este projeto está licenciado sob a licença [MIT](LICENSE).
