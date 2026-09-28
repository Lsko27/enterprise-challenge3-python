# Estruturas de Dados, Ordenação e Análise de Complexidade do GovAtende

## 1. Objetivo

O GovAtende processa solicitações urbanas registradas pelos cidadãos para identificar padrões históricos, organizar a fila de atendimento e gerar previsões de demanda por bairro, categoria e subserviço.

Para realizar esse processamento de forma eficiente, o sistema utiliza diferentes estruturas de dados e algoritmos nos serviços Java e Python:

- listas para armazenamento e processamento sequencial;
- agrupamentos para relacionar solicitações semelhantes;
- ordenação para priorizar previsões;
- fila de prioridade baseada em heap binária;
- pilha para consulta reversa do histórico;
- mapas para contagem e agregação de valores.

A escolha de cada estrutura considera a regra de negócio e a complexidade computacional envolvida.

---

## 2. Agrupamento dos dados históricos

No serviço Python, a função `gerar_previsoes_demanda` recebe uma lista de solicitações históricas e transforma os registros em um `DataFrame` do Pandas.

Os dados são agrupados pelas seguintes chaves:

```python
colunas_agrupamento = [
    "bairro",
    "categoriaId",
    "categoriaNome",
    "subservicoId",
    "subservicoNome",
]
```

O agrupamento é realizado com:

```python
grupos = dataframe.groupby(
    colunas_agrupamento,
    dropna=False,
    sort=False,
)
```

Cada grupo representa um conjunto de solicitações relacionadas ao mesmo bairro, categoria e subserviço.

Por exemplo:

```text
Centro
└── Infraestrutura urbana
    └── Buracos na via
```

O parâmetro `sort=False` evita que o Pandas ordene previamente as chaves do agrupamento. Essa ordenação seria desnecessária porque o resultado final é posteriormente ordenado pela quantidade prevista.

Essa alteração reduz processamento redundante, principalmente quando o volume histórico aumenta.

---

## 3. Lista de previsões

As previsões calculadas são armazenadas em uma lista:

```python
previsoes: list[PrevisaoDemandaItem] = []
```

Cada item é inserido com:

```python
previsoes.append(
    PrevisaoDemandaItem(
        bairro=str(bairro),
        categoriaId=int(categoria_id),
        categoriaNome=str(categoria_nome),
        subservicoId=int(subservico_id),
        subservicoNome=str(subservico_nome),
        ocorrenciasHistoricas=total_ocorrencias,
        quantidadePrevista=quantidade_prevista,
        tendencia=tendencia,
        nivelDemanda=nivel_demanda,
        confianca=confianca,
        justificativa=justificativa,
        nomeModelo="GovAtende Previsão de Demandas",
        versaoModelo="1.0.0",
    )
)
```

A lista foi escolhida porque:

- permite inserção ao final em tempo amortizado `O(1)`;
- mantém todas as previsões geradas;
- pode ser percorrida sequencialmente;
- pode ser ordenada antes da resposta da API;
- é compatível com a serialização realizada pelo FastAPI.

---

## 4. Ordenação das previsões

Depois do processamento dos grupos, as previsões são ordenadas pela quantidade prevista:

```python
previsoes.sort(
    key=lambda previsao: (
        previsao.quantidadePrevista
    ),
    reverse=True,
)
```

O parâmetro `reverse=True` faz com que os maiores valores apareçam primeiro.

Essa ordenação é necessária porque a API precisa entregar inicialmente os bairros e serviços que possuem maior demanda prevista. A mesma ordem é utilizada pelo front-end para apresentar a tabela e o gráfico de maiores demandas.

O método `list.sort()` do Python utiliza o algoritmo Timsort, que combina características de Merge Sort e Insertion Sort.

Sua complexidade é:

- melhor caso: `O(g)`, quando os dados já estão ordenados;
- caso médio: `O(g log g)`;
- pior caso: `O(g log g)`.

A variável `g` representa a quantidade de grupos formados por bairro, categoria e subserviço.

---

## 5. Fluxo do algoritmo de previsão

O processamento pode ser resumido da seguinte forma:

```text
Receber n solicitações históricas
-> Normalizar bairros e datas
-> Remover registros com datas inválidas
-> Filtrar o período histórico
-> Agrupar solicitações relacionadas
-> Calcular tendência, confiança e demanda de cada grupo
-> Inserir os resultados na lista de previsões
-> Ordenar a lista pela quantidade prevista
-> Retornar as previsões pela API
```

---

## 6. Análise de complexidade Big O

Considere:

- `n`: quantidade de solicitações históricas recebidas;
- `g`: quantidade de grupos gerados;
- `g <= n`.

| Operação | Complexidade de tempo | Complexidade de espaço |
|---|---:|---:|
| Normalização dos registros | `O(n)` | `O(n)` |
| Criação do DataFrame | `O(n)` | `O(n)` |
| Conversão e validação das datas | `O(n)` | `O(n)` |
| Filtro do período histórico | `O(n)` | `O(n)` |
| Agrupamento com `sort=False` | `O(n)` em média | `O(g)` |
| Processamento dos grupos | `O(n)` no total | `O(g)` |
| Inserção das previsões | `O(1)` amortizado por item | `O(g)` |
| Ordenação das previsões | `O(g log g)` | `O(g)` |
| Construção da resposta | `O(g)` | `O(g)` |

A complexidade total esperada é:

```text
O(n + g log g)
```

Como `g` não pode ser maior que `n`, no pior cenário a complexidade pode ser representada como:

```text
O(n log n)
```

O consumo de memória adicional é:

```text
O(n + g)
```

Esse custo ocorre porque o sistema mantém os registros históricos processados e a lista final de previsões.

---

## 7. Justificativa da solução

A ordenação completa é adequada porque a API retorna todas as previsões, não apenas os primeiros resultados.

Uma estrutura heap poderia encontrar apenas os `k` maiores elementos em aproximadamente `O(n log k)`. Entretanto, como toda a lista precisa ser devolvida em ordem para a tabela, para o gráfico e para o relatório, seria necessário ordenar os demais elementos posteriormente.

Por isso, o uso de `list.sort()` é mais simples e apropriado para a necessidade atual.

Uma árvore binária criada manualmente também não apresentaria benefício nessa etapa, pois adicionaria complexidade de implementação sem reduzir o custo necessário para devolver todos os registros ordenados.

---

## 8. Heap binária e árvore implícita na fila de triagem

O backend Java utiliza uma `PriorityQueue` para organizar as solicitações pendentes:

```java
Queue<Solicitacao> fila =
        new PriorityQueue<>(
                COMPARADOR_DA_FILA
        );
```

A `PriorityQueue` é implementada internamente como uma heap binária armazenada em um array. Essa estrutura pode ser interpretada como uma árvore implícita, pois os relacionamentos entre pai e filhos são calculados pelos índices:

```text
Pai:            (i - 1) / 2
Filho esquerdo: 2 * i + 1
Filho direito:  2 * i + 2
```

O comparador organiza as solicitações considerando:

1. maior nível de urgência;
2. data de abertura mais antiga;
3. menor identificador em caso de empate.

Código utilizado:

```java
private static final Comparator<Solicitacao>
        COMPARADOR_DA_FILA = Comparator
        .comparingInt(
                (Solicitacao solicitacao) ->
                        solicitacao
                                .getUrgencia()
                                .getPrioridade()
        )
        .reversed()
        .thenComparing(
                Solicitacao::getDataAbertura
        )
        .thenComparing(
                Solicitacao::getId
        );
```

As principais operações possuem as seguintes complexidades:

| Operação da fila | Complexidade |
|---|---:|
| Consultar o elemento prioritário | `O(1)` |
| Inserir uma solicitação | `O(log n)` |
| Remover a próxima solicitação | `O(log n)` |
| Consumir toda a fila | `O(n log n)` |
| Espaço ocupado | `O(n)` |

A heap permite que a solicitação mais prioritária permaneça na raiz da estrutura sem exigir uma nova ordenação completa a cada retirada.

---

## 9. Pilha para histórico reverso

O backend Java também utiliza `ArrayDeque` como pilha para apresentar o histórico de uma solicitação do evento mais recente para o mais antigo:

```java
Deque<HistoricoSolicitacaoResponse> pilha =
        new ArrayDeque<>();
```

Os registros cronológicos são inseridos com:

```java
pilha.push(item);
```

Depois são removidos com:

```java
pilha.pop();
```

Essa estrutura segue a política LIFO:

```text
Last In, First Out
```

As operações `push` e `pop` possuem complexidade `O(1)` amortizada. Para inverter um histórico com `h` registros, a complexidade total é `O(h)`.

---

## 10. Mapas para agregação estatística

Os relatórios estatísticos utilizam `HashMap` para relacionar chaves e valores, como:

- quantidade de solicitações por data;
- frequência dos valores diários;
- identificação da moda;
- preenchimento de dias sem solicitações.

Em condições normais, inserções, buscas e atualizações em um `HashMap` possuem complexidade média de:

```text
O(1)
```

O processamento completo de `n` elementos possui complexidade média:

```text
O(n)
```

Esse uso evita realizar buscas lineares repetidas em listas durante os cálculos estatísticos.

---

## 11. Validação automatizada

O arquivo:

```text
tests/test_previsao_demanda.py
```

valida que:

- todos os registros válidos são analisados;
- os grupos são formados corretamente;
- a quantidade esperada de previsões é produzida;
- as previsões são retornadas em ordem decrescente;
- o grupo com maior demanda aparece na primeira posição.

O teste pode ser executado com:

```powershell
python -m unittest discover -s tests -v
```

O uso de teste automatizado reduz o risco de uma alteração futura quebrar a ordenação esperada pela API e pelo front-end.

---

## 12. Conclusão

O GovAtende utiliza estruturas de dados de acordo com necessidades reais do sistema:

- listas armazenam previsões e respostas;
- agrupamentos relacionam solicitações equivalentes;
- Timsort ordena a demanda prevista;
- heap binária organiza a fila prioritária;
- pilha inverte o histórico;
- mapas realizam agregações estatísticas.

A previsão apresenta complexidade esperada de `O(n + g log g)`, enquanto a fila de triagem mantém inserções e remoções prioritárias em `O(log n)`.

A solução evita estruturas artificiais e utiliza algoritmos adequados aos fluxos de atendimento, análise histórica e tomada de decisão do GovAtende.