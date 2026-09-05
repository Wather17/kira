# 🚀 Guia de Início Rápido (Getting Started)

Este guia orienta o passo a passo completo para configurar o **Kira Manga Pipeline** no seu ambiente local (Linux, WSL2, macOS ou Windows).

---

## 1. Pré-requisitos do Sistema

Antes de instalar o Kira, certifique-se de que sua máquina possui:
- **Python**: Versão 3.10 ou superior (`python3 --version`).
- **Git**: Para clonar o repositório (`git --version`).
- **Placa de Vídeo (Opcional)**: GPU NVIDIA com suporte a CUDA para aceleração local por IA (se você não tiver GPU NVIDIA local, poderá usar o comando `kira colab-run` para processar gratuitamente na nuvem do Google Colab).
- **Descompactadores de Sistema (Opcional, para arquivos `.rar` / `.cbr`)**:
  ```bash
  # No Debian / Ubuntu / WSL2:
  sudo apt update && sudo apt install -y p7zip-full unrar
  ```

---

## 2. Instalação Passo a Passo

### Passo 1: Clonar o Repositório
```bash
git clone https://github.com/Wather17/kira.git
cd kira
```

### Passo 2: Criar e Ativar o Ambiente Virtual
Recomendamos utilizar um ambiente virtual isolado para não misturar dependências do sistema:
```bash
# Criar ambiente virtual
python3 -m venv venv

# Ativar ambiente virtual no Linux / macOS / WSL2:
source venv/bin/activate

# Ativar no Windows (PowerShell):
# .\venv\Scripts\Activate.ps1
```

### Passo 3: Instalar Dependências e o Kira CLI
```bash
# Instalação com suporte completo a comandos CLI
pip install --upgrade pip
pip install -e .
```

Para executar a suíte local sem instalar ferramentas opcionais:
```bash
python -m pip install --no-deps -e .
python -m pip install pytest numpy Pillow opencv-python-headless natsort requests PyYAML click rich tqdm rarfile
python -m pytest tests/ -q
```

### Passo 4: Verificar a Instalação
Execute o comando de ajuda para confirmar que o executável `kira` está ativo:
```bash
kira --help
```
Você verá a tela de boas-vindas com todos os subcomandos disponíveis (`process`, `colab-run`, `merge-volumes`, `colab-setup`, `info`).

---

## 3. Primeiro Teste Local: Processando um Mangá

### Cenário A: Processar um Volume Completo (`.cbz`, `.zip` ou pasta)
Crie as pastas padrão ou aponte diretamente para os seus arquivos:
```bash
# Processar um arquivo único para Kindle Paperwhite 5 em EPUB
kira process -i "./meu_manga_vol_01.cbz" -o "./saida_kindle" -p KPW5 -f EPUB
```

### Cenário B: Processar uma Pasta Inteira em Lote
```bash
kira process -i "./Manga_Inputs" -o "./Kindle_Outputs" -p KPW5 -f EPUB
```

### Cenário C: Unir Capítulos Avulsos em Volumes Oficiais
Se você tiver 100 capítulos soltos (`Ch_01.cbz`, `Ch_02.cbz`...), o Kira detecta o nome da obra, busca as divisões oficiais e baixa as capas em alta resolução automaticamente:
```bash
kira merge-volumes -i "./capitulos_soltos" -o "./volumes_oficiais"
```

---

## 4. Próximos Passos
- Para entender todos os parâmetros da CLI, consulte o [Manual da Linha de Comando](file:///home/henrique/projetos/kira/docs/cli_reference.md).
- Para rodar em GPUs gratuitas na nuvem, consulte o [Guia do Google Colab](file:///home/henrique/projetos/kira/docs/google_colab_guide.md).
- Para otimizar a experiência de leitura no e-reader, veja o [Guia de Otimização Kindle](file:///home/henrique/projetos/kira/docs/kindle_guide.md).
