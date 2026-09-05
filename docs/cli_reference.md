# 📖 Manual da Linha de Comando (CLI Reference)

O **Kira** oferece uma interface de terminal rica, colorida e totalmente interativa através do comando `kira`.

```
Usage: kira [OPTIONS] COMMAND [ARGS]...

  Kira - AI Manga Upscaling & Kindle Converter Pipeline.

Commands:
  process        Run end-to-end upscale & Kindle conversion pipeline.
  colab-run      Provision a remote Google Colab GPU instance and run...
  merge-volumes  Merge individual chapter CBZ files or folders into...
  colab-setup    Display environment verification & Google Drive mount...
  info           Display system info, CUDA status, and available models.
```

---

## 1. `kira process`
Executa o pipeline completo: extração, upscale com IA, divisão/metadados e conversão para Kindle.

### Sintaxe
```bash
kira process [OPÇÕES]
```

### Opções e Flags

| Flag / Parâmetro | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `-i, --input` **(Obrigatório)** | `TEXT` | — | Arquivo de entrada (`.cbz`, `.zip`, `.rar`) ou pasta contendo volumes/capítulos. |
| `-o, --output` **(Obrigatório)** | `TEXT` | — | Pasta de destino para os e-books gerados. |
| `-m, --model` | `CHOICE` | `RealESRGAN_x4plus_anime_6B` | Modelo de IA (`RealESRGAN_x4plus_anime_6B`, `realesr-animevideov3`, `RealESRGAN_x4plus`). |
| `-s, --scale` | `INT` | `4` | Fator de ampliação de escala do upscaler (2, 3 ou 4). |
| `-t, --tile` | `INT` | `400` | Tamanho do bloco para processamento por mosaicos (evita estouro de VRAM). `0` desativa. |
| `-p, --profile` | `CHOICE` | `K11` | Perfil do leitor Kindle (`K11` padrão, `KPW5`, `KO`, `KS`, `KV`, `KPW34`, `KPW`, `K34`, `K57`, `OTHER`). |
| `-f, --format` | `CHOICE` | `EPUB` | Formato do arquivo final (`EPUB`, `CBZ`, `KFX`). `AZW3`/`MOBI` são mapeados para EPUB com aviso (requisito do Send to Kindle). |
| `--half / --no-half` | `FLAG` | Auto | Forçar ou desativar inferência em FP16 (Half-Precision). |
| `--grayscale / --no-grayscale` | `FLAG` | `False` | Converter páginas para escala de cinza pura antes do upscale. |
| `--manga-style / --webtoon` | `FLAG` | `--manga-style` | Leitura da direita para a esquerda (Mangá) ou rolagem contínua (Webtoon). |
| `--gamma` | `FLOAT` | `1.0` | Correção gama de contraste para telas e-Ink (ex: 1.1 para tons mais escuros). |
| `--cropping` | `INT` | `0` | Modo de corte automático do KCC (`0` desabilitado — preserva a página original, `1` margens, `2` margens + número de página). |
| `--keep-extracted` | `FLAG` | `False` | Manter a pasta de imagens descompactadas após o término. |
| `--keep-cbz / --no-keep-cbz`| `FLAG` | `--keep-cbz` | Salvar uma cópia das imagens ampliadas em `.cbz` na pasta de saída. |

### Exemplos de Uso
```bash
# Processar volume único para Kindle Paperwhite 5
kira process -i "./mangas/Monster_Vol_01.cbz" -o "./kindle" -p KPW5 -f EPUB

# Processar pasta com vários volumes para Kindle Scribe em alta definição
kira process -i "./Manga_Inputs" -o "./Kindle_Outputs" -p KS -m RealESRGAN_x4plus_anime_6B --gamma 1.05
```

---

## 2. `kira colab-run`
Aloca uma máquina virtual com GPU NVIDIA no Google Colab remotamente, monta o Google Drive, executa o pipeline e desliga a VM automaticamente ao terminar.

### Sintaxe
```bash
kira colab-run [OPÇÕES]
```

### Opções e Flags

| Flag / Parâmetro | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `-i, --input` **(Obrigatório)** | `TEXT` | — | Pasta/Arquivo de entrada no Google Drive (ex: `Manga_Inputs`). |
| `-o, --output` **(Obrigatório)** | `TEXT` | — | Pasta de saída no Google Drive (ex: `Kindle_Outputs`). |
| `--gpu` | `CHOICE` | `T4` | Tipo de acelerador GPU no Colab (`T4`, `L4`, `A100`). |
| `-m, --model` | `CHOICE` | `RealESRGAN_x4plus_anime_6B` | Modelo Real-ESRGAN a ser utilizado. |
| `-p, --profile` | `CHOICE` | `K11` | Perfil do Kindle. |
| `-f, --format` | `CHOICE` | `EPUB` | Formato de saída. |
| `--session-name` | `TEXT` | `kira-gpu-worker` | Nome da sessão no Colab CLI. |
| `--auto-stop / --no-stop` | `FLAG` | `--auto-stop` | Liberar a VM e parar a GPU imediatamente ao finalizar o lote. |

### Exemplos de Uso
```bash
# Rodar na nuvem do Google Colab usando GPU T4 gratuita
kira colab-run -i "Manga_Inputs" -o "Kindle_Outputs" --gpu T4

# Rodar em GPU A100 de alta performance
kira colab-run -i "Manga_Inputs/Vinland_Saga" -o "Kindle_Outputs" --gpu A100 -p KS
```

---

## 3. `kira merge-volumes`
Identifica capítulos avulsos, busca a divisão oficial nas editoras japonesas, baixa as capas oficiais em alta definição e gera os arquivos `.cbz` com metadados comerciais `ComicInfo.xml`.

### Sintaxe
```bash
kira merge-volumes [OPÇÕES]
```

### Opções e Flags

| Flag / Parâmetro | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `-i, --input` **(Obrigatório)** | `TEXT` | — | Pasta contendo os capítulos soltos (`.cbz`, `.zip` ou pastas). |
| `-o, --output` **(Obrigatório)** | `TEXT` | — | Pasta para salvar os volumes oficiais gerados. |
| `-t, --title` | `TEXT` | `None` | *(Opcional)* Título da obra. Se omitido, o Kira detecta automaticamente! |
| `-m, --mapping` | `TEXT` | `None` | *(Opcional)* Caminho para arquivo YAML/JSON com divisão customizada. |

### Exemplos de Uso
```bash
# Detecção 100% automática do título e divisão oficial
kira merge-volumes -i "./meus_capitulos_soltos" -o "./volumes_comerciais"

# Forçando um título específico
kira merge-volumes -i "./capitulos" -o "./volumes" -t "Death Note"
```

---

## 4. `kira info`
Exibe o status do hardware local, disponibilidade de CUDA, versões instaladas e tabela de modelos.

```bash
kira info
```

---

## 5. `kira colab-setup`
Instala as dependências em um notebook Google Colab: pacotes Python, o KCC oficial via `pip install git+https://github.com/ciromattia/kcc.git` e utilitários de sistema. Valida o exit code de cada passo e a versão do KCC ao final — falha com mensagem clara em vez de concluir silenciosamente.

```bash
kira colab-setup
```
