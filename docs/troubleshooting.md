# 🛠️ Solução de Problemas & FAQ (Troubleshooting)

Este documento reúne soluções para as dúvidas e erros mais comuns encontrados durante a utilização do Kira.

---

## 1. Problemas de Memória de Vídeo (CUDA Out of Memory)

### Sintoma
```
torch.cuda.OutOfMemoryError: CUDA out of memory. Tried to allocate ...
```

### Causa
Páginas de mangá em resolução muito alta (ex: 4K/8K) podem exceder a memória VRAM da GPU ao tentar processar a página inteira de uma só vez.

### Solução
Utilize a técnica de **processamento por blocos (tiles)** reduzindo o tamanho da janela com o parâmetro `-t` ou `--tile`:
```bash
# Reduzir o tamanho do tile para 200 ou 300 pixels:
kira process -i "./mangas" -o "./saida" --tile 200
```
Você também pode habilitar a flag `--half` (padrão em GPUs NVIDIA) para utilizar precisão FP16 e economizar 50% de VRAM.

---

## 2. Erro ao Extrair Arquivos `.rar` ou `.cbr`

### Sintoma
```
RuntimeError: Failed to extract RAR archive ... Please install unrar or p7zip-full.
```

### Causa
Arquivos `.rar` e `.cbr` utilizam algoritmos proprietários de compressão que exigem bibliotecas externas de descompactação no sistema operacional.

### Solução
Instale os utilitários de descompactação no Linux / WSL2:
```bash
# Debian / Ubuntu / WSL2:
sudo apt update && sudo apt install -y p7zip-full unrar
```

---

## 3. Comportamento em Modo Offline ou com Falha nas APIs

### Sintoma
```
[Kira Warning] Volume mapping lookup skipped for 'Death Note': ...
```

### O que acontece?
O Kira possui **tratamento de falha em três níveis**:
1. Se o AniList estiver fora do ar, ele tenta o Jikan / MyAnimeList automaticamente.
2. Se a sua conexão com a internet cair completamente, o Kira **não aborta**: ele continua o processamento local, utiliza a primeira imagem do arquivo como capa e realiza a conversão normalmente.

---

## 4. O E-book gerado não exibe o título ou autor no Kindle

### Causa
Leitores de e-book utilizam metadados internos incorporados no arquivo `.epub`, e não apenas o nome do arquivo.

### Solução
O Kira gera automaticamente o arquivo comercial `ComicInfo.xml` e passa as flags `--keepcomicinfo` e `--metadatatitle 2` para o conversor KCC. Certifique-se de que está utilizando a versão mais recente do Kira:
```bash
git pull origin develop
pip install -e .
```

---

## 5. Como Executar os Testes Unitários de Verificação

Para auditar e verificar se todos os módulos do seu ambiente local estão funcionando com 100% de integridade:

```bash
# Executar a suíte completa de testes:
python -m pytest tests/ -q
```

Todos os testes devem passar no ambiente configurado. A contagem exibida pelo
Pytest é intencionalmente variável, pois novos casos são adicionados ao longo
do desenvolvimento. O mesmo comando é executado pelo workflow do GitHub
Actions em pushes e pull requests para `main`.
