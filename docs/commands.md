# COMMANDS


## CONFIG

### Objetivo e Funcionamento
Escrever ou editar o arquivo de configurações "zendb.json".
O arquivo não é estritamente necessário para o funcionamento dos demais comandos, mas auxilia na construção de pipelines e processos em massa.

...

### Especificações
To be written.

## LIST

### Objetivo e Funcionamento
Listar o nome de todas as regras disponíveis para uso de acordo com a(s) fonte(s) disponível(is).

Exemplo de uso:
`zendb list --s https://github.com/user/rules_repo --l asps`


### Especificações

**- "--source" ou "--s":**
- Informa onde a(s) regra(s) a ser(em) listada(s) está(ão) localizada(s).
- Argumento opcional.
    - Se informado: a especificação pode ser o **id** de uma source em `zendb.json`, um **caminho local** (absoluto ou relativo à raiz do projeto) ou o **link** de um repositório GitHub ou GitLab (pasta das regras).
    - Se omitido: lê `zendb.json` na raiz do projeto e busca as regras a partir das sources configuradas.
    - Se `zendb.json` não existir, estiver inválido, ou a source não puder ser resolvida: o comando falha com erro.
- Repositório git: deve ser fornecido o link para a **pasta das regras** (não o link para a raiz do repo, a não ser que as regras estejam na raiz).
- O comando considera os arquivos `.json` da pasta que sejam regras JDM.


**- "--authentication" ou "--a":**
- No caso de repositórios git privados, informa o nome da variável que guarda o token de autenticação para acesso ao repositório.
- Argumento opcional.
    - Default: none.
    - Especificação: nome da variável de ambiente (listada em `.env`) que contém o token. Não é o token em si.


**- "--find" ou "--f":**
- Informa uma string para identificar a existência de uma ou mais regras relacionadas dentre o conjunto fornecido.
- Argumento opcional.
    - Default: none [busca todas as regras para a source especificada].
    - Especificação: string [busca a string fornecida dentre os nomes das regras disponíveis, retornando uma lista com todos os matches]


**- "--version" ou "--v":**
- Informa a ref git (tag **ou** nome de branch) do conjunto de regras a listar.
- Argumento válido apenas para repositórios git.
- Argumento opcional.
    - Default: tag mais recente do repositório. Se não houver tags, usa a branch padrão (`main` / `master`).


## APPLY

### Objetivo e Funcionamento

Aplicar uma ou mais regras especificadas sobre uma base de dados.

Exemplo de uso:
`zendb apply --s https://github.com/user/rules_repo --r is_asps_desp is_mde_desp --i data-raw/exec_desp.xlsx --o data/exec_desp.csv --v 1.2.1`

Identifica uma fonte de regras (um ou mais arquivos json escritos no formato JDM Standard do GoRules) e busca nessa fonte a(s) regra(s) especificada(s) no comando (`--r`). No caso de as regras constarem em um repositório git, é possível especificar a versão das regras que se deseja aplicar utilizando-se o argumento version (`--v`), que aceita o nome de uma **tag** ou de uma **branch**.

Encontradas as regras, o comando lê os dados de input (`--i`) — arquivo (caminho completo ou relativo à raiz do projeto) ou stdin — nos formatos csv, csv.gz, excel e json, e os transforma para o formato esperado (dict) para aplicação das regras.

Em seguida, aplica a [Zen Engine](https://docs.gorules.io/developers/overview/bre-vs-brms#zen-engine) (via [Python SDK](https://docs.gorules.io/developers/sdks/python)) sobre os dados considerando as regras requeridas e devolve as saídas. A saída, por padrão, não é salva como arquivo físico (vai para stdout); é possível especificar `--output` (`--o`) para definir um caminho de salvamento.


### Especificações


**- "--source" ou "--s":**

- Informa onde a(s) regra(s) a ser(em) aplicada(s) está(ão) localizada(s).
- Argumento opcional.
    - Se informado: a especificação pode ser:
        1. o **id** de uma source em `zendb.json`
        2. um **caminho local** (absoluto ou relativo à raiz do projeto)
        3. o **link** de um repositório GitHub ou GitLab (pasta das regras)
    - Se omitido: lê `zendb.json` na raiz do projeto e busca as regras a partir das sources configuradas.
    - Se `zendb.json` não existir, estiver inválido, ou a source não puder ser resolvida: o comando falha com erro.
- Repositório git: deve ser fornecido o link para a **pasta das regras** (não o link para a raiz do repo, a não ser que as regras estejam na raiz).
- O comando lerá os arquivos `.json` JDM da pasta; os nomes (stem do arquivo) são os valores válidos de `--rules`.
- Hosts aceitos quando a source é remota: **GitHub** e **GitLab**.


**- "--authentication" ou "--a":**
- No caso de repositórios git privados, informa o nome da variável que guarda o token de autenticação para acesso ao repositório.
- Argumento opcional.
    - Default: none.
    - Especificação: nome da variável de ambiente (listada em `.env`) que contém o token. Não é o token em si.


**- "--rules" ou "--r":**

- Informa as regras a serem aplicadas (uma ou mais).
- Argumento obrigatório.


**- "--input" ou "--i":**

- Informa o arquivo de entrada, ou lê dados já gerados no terminal (pipelining).
- Argumento opcional.
    - Default: stdin (csv ou json). Útil para `... | zendb apply --r ...`.
    - Se omitido e o stdin for um terminal interativo (não há pipe), o comando falha com erro — não fica aguardando digitação no teclado.
    - Em arquivo: csv, csv.gz, excel ou json. Excel não é aceito via stdin.


**- "--output" ou "--o":**

- Informa o path de saída, especificando também o nome e formato do arquivo.
- Argumento não obrigatório.
    - Default: não salva arquivo; escreve csv em stdout (permite encadear com outro comando).
    - Especificação: salva o arquivo no caminho e formato indicados.
        - Formatos aceitos: csv, csv.gz, excel ou json


**- "--version" ou "--v":**

- Informa a ref git do conjunto de regras a ser utilizada para aplicação: nome de **tag** ou nome de **branch**.
- Argumento válido apenas para repositórios git (erro se usado com source local).
- Argumento não obrigatório.
    - Default: tag mais recente do repositório. Se o repositório não tiver tags, usa a branch padrão (`main` / `master`).
    - Exemplo de tag: `--v 1.2.1`. Exemplo de branch: `--v main`.


## FLOW

### Objetivo e Funcionamento

Utilizar fluxos (completos ou parte) pré-configurados em zendb.json. Permite personalização de pipelines, unindo facilmente a aplicação de regras a outros fluxos no terminal, de forma automatizada.

Exemplo de uso:
`zendb flow financedata`

O comando `flow` é independente de `apply`. Ele não recebe `--rules`, `--source`, `--input` etc.: compacta esses argumentos num único **id** definido em `zendb.json`. Para aplicar regras de forma explícita, use `zendb apply`.

### Especificações

O comando `zendb flow` recebe como único parâmetro o **id** do fluxo.
O id deve ser um valor válido (string) e **único** descrito em zendb.json.
A descrição do fluxo deve conter todos os requisitos especificados em configs.md.

Regras do fluxo são buscadas nas sources configuradas em `zendb.json` (não há source dentro do próprio flow). Se `zendb.json` não existir ou o id não for encontrado, o comando falha com erro.


## HELP

Ajuda padrão gerada pelo Typer. Sem tópicos extras (regra ou flow).

Exemplos:
`zendb --help` ou `zendb -h`: ajuda da CLI e comandos disponíveis.
`zendb apply --help` ou `zendb apply -h`: ajuda do comando `apply`.
`zendb flow --help` ou `zendb list --help`: ajuda de cada comando.
