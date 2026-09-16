# ZENDB CLI
_Zen Engine for Databases_

CLI para aplicação de regras de negócio especificadas em formato JSON conforme o [JDM Standard proposto pela plataforma GoRules](https://docs.gorules.io/developers/jdm/standard) sobre bases de dados em diferentes formatos (csv/csv.gz/excel/json).


## Descrição
Esta CLI foi construída para facilitar a aplicação de regras sobre bases de dados, definindo padrões de aplicação simples e intuitivos para projetos que envolvem regras de negócio sobre grandes volumes de dados.

A CLI fornece ferramentas para:
- aplicar uma ou mais regras, considerando uma versão específica do pacote de regras (tag ou branch git)
- listar as regras disponíveis para o usuário
- guardar sources e fluxos reutilizáveis em `zendb.json`

Para projetos de aplicação em massa, é possível configurar opções de aplicação pré-prontas no arquivo `zendb.json`, que auxiliam no fluxo de pipelines de ETL. A CLI também fornece comandos para auxiliar na construção dessas configurações de forma interativa e simples.


### Demo - Comandos
```
zendb config --create
zendb config --create sample
zendb config --edit

zendb apply --s source_one --r is_asps_desp is_mde_desp --i data-raw/exec_desp.xlsx --o data/exec_desp.csv --v 1.2.1
zendb apply --s https://github.com/user/rules_repo --r is_asps_desp --i data-raw/exec_desp.csv

zendb flow financedata

zendb list
zendb list --s source_two --f discount

zendb --help
zendb apply --help
zendb flow --help
```

### Configurações em zendb.json

Ver [configs.md](configs.md). Sources (id, path ou URL GitHub/GitLab, autenticação, versão) e flows (id, rules, input/output opcionais). Flows são chamados com `zendb flow <id>`, não com flags de `apply`.
