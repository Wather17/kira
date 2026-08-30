# 📱 Guia de Leitura & Otimização para Kindle

O **Kira** foi projetado para produzir a melhor experiência visual possível em leitores de livros digitais com telas **e-Ink** (tinta eletrônica).

---

## 1. Tabela de Perfis de Dispositivos Suportados

Ao executar o Kira, selecione a flag `-p` correspondente ao seu modelo de Kindle para que as imagens sejam redimensionadas e otimizadas pixel a pixel:

| Perfil (`-p`) | Modelo de Kindle | Tamanho da Tela | Resolução Ideal | Densidade |
| :--- | :--- | :--- | :--- | :--- |
| **`K11`** *(Padrão)* | Kindle Básico 11ª Geração (2022+) | 6.0 polegadas | **1072 × 1448** | 300 PPI |
| **`KPW34`** | Kindle Paperwhite 3 e 4 (2015/2018) | 6.0 polegadas | **1072 × 1448** | 300 PPI |
| **`KV`** | Kindle Voyage (2014) | 6.0 polegadas | **1072 × 1448** | 300 PPI |
| **`KPW`** | Kindle Paperwhite 1 e 2 (2012/2013) | 6.0 polegadas | **758 × 1024** | 212 PPI |
| **`K34` / `K57`** | Kindle 3/4/5/7 e Touch | 6.0 polegadas | **600 × 800** | 212 PPI |
| **`OTHER`** | Outros e-readers / Tablets genéricos | Customizável | Proporcional | — |

> Obs.: `KPW3` e `K345` são aliases aceitos pela CLI (com aviso de depreciação), traduzidos para `KPW34` e `K34`, respectivamente.

---

## 2. Como Enviar os Mangás para o seu Kindle

### Método 1: Send to Kindle Web (Recomendado ⭐)
O formato padrão gerado pelo Kira é o **`.epub`**. A Amazon descontinuou o formato `.mobi` e agora utiliza o `.epub` como formato padrão do serviço *Send to Kindle*.

1. Acesse o site oficial: [amazon.com/sendtokindle](https://www.amazon.com/sendtokindle).
2. Faça login com sua conta da Amazon vinculada ao seu dispositivo Kindle.
3. Arraste e solte o arquivo `.epub` gerado pelo Kira na tela.
4. Clique em **Send**.
5. **Vantagens**:
   - O mangá é sincronizado pela nuvem em todos os seus Kindles e no app Kindle do celular.
   - O Whispersync sincroniza a página exata onde você parou de ler.
   - A capa oficial em alta resolução é exibida automaticamente na sua biblioteca.

---

### Método 2: Transferência via Cabo USB (Sem Internet)
Se você preferir transferir arquivos offline sem usar a nuvem da Amazon:

1. Conecte o Kindle ao seu computador usando o cabo USB.
2. Ao rodar o Kira, escolha o formato `.azw3` ou `.mobi`:
   ```bash
   kira process -i "./meu_manga.cbz" -o "./saida" -p KPW5 -f AZW3
   ```
3. Abra a unidade de disco do Kindle e copie o arquivo `.azw3` diretamente para a pasta **`documents/`**.
4. Ejete o Kindle com segurança.

---

## 3. Como Ativar a Capa do Mangá na Tela de Bloqueio

Os arquivos gerados pelo Kira incluem capas comerciais em alta resolução preparadas para a tela de bloqueio do Kindle:

1. No seu Kindle, vá em **Configurações** (ícone de engrenagem) ➔ **Todas as configurações**.
2. Toque em **Opções do dispositivo**.
3. Ative a chave **Mostrar capa** (*Display Cover*).
4. Ao desligar a tela do seu Kindle, a capa oficial do volume do mangá que você está lendo aparecerá na tela inteira!

---

## 4. Recursos Especiais de Leitura

- **Leitura Oriental (Right-to-Left)**: Todos os volumes gerados pelo Kira abrem nativamente no sentido oriental de leitura de mangás (passar a página para a esquerda avança a história).
- **Tratamento de Páginas Duplas**: Páginas duplas de ação (*double spreads*) são automaticamente detectadas e adaptadas para exibição nítida na orientação paisagem ou divididas perfeitamente para leitura contínua.
- **Ajuste de Gama (Contraste e-Ink)**: Telas de tinta eletrônica podem clarear traços sutis de nanquim. Você pode usar a flag `--gamma 1.1` para escurecer traços finos e acentuar sombras.
