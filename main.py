from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(
    title="GovAtende IA",
    description=(
        "Serviço de classificação, priorização e previsão "
        "de demandas urbanas."
    ),
    version="2.0.0",
)


NivelUrgencia = Literal[
    "BAIXA",
    "MEDIA",
    "ALTA",
    "CRITICA",
]

NivelPrioridade = Literal[
    "BAIXA",
    "MEDIA",
    "ALTA",
    "CRITICA",
]

TendenciaDemanda = Literal[
    "CRESCENTE",
    "ESTAVEL",
    "DECRESCENTE",
]

NivelDemanda = Literal[
    "BAIXA",
    "MEDIA",
    "ALTA",
    "CRITICA",
]


# =========================================================
# MODELOS DE ENTRADA E SAÍDA
# =========================================================


class CategoriaIaItem(BaseModel):
    id: int
    nome: str


class SubservicoIaItem(BaseModel):
    id: int
    categoriaId: int
    nome: str


class AnaliseIaRequest(BaseModel):
    solicitacaoId: int

    titulo: str = Field(
        min_length=1,
        max_length=200,
    )

    descricao: str = Field(
        min_length=1,
        max_length=4000,
    )

    categorias: list[CategoriaIaItem] = Field(
        min_length=1,
    )

    subservicos: list[SubservicoIaItem] = Field(
        min_length=1,
    )


class AnaliseIaResponse(BaseModel):
    categoriaSugeridaId: int
    subservicoSugeridoId: int
    urgenciaSugerida: NivelUrgencia
    scorePrioridade: float
    nivelPrioridade: NivelPrioridade
    confianca: float
    justificativa: str
    nomeModelo: str
    versaoModelo: str


class HistoricoDemandaItem(BaseModel):
    solicitacaoId: int
    bairro: str = Field(
        min_length=1,
        max_length=100,
    )
    categoriaId: int
    categoriaNome: str = Field(
        min_length=1,
        max_length=100,
    )
    subservicoId: int
    subservicoNome: str = Field(
        min_length=1,
        max_length=150,
    )
    dataAbertura: datetime


class PrevisaoDemandaRequest(BaseModel):
    periodoHistoricoDias: int = Field(
        default=90,
        ge=30,
        le=730,
    )
    periodoPrevisaoDias: int = Field(
        default=30,
        ge=7,
        le=90,
    )
    minimoOcorrencias: int = Field(
        default=2,
        ge=1,
        le=100,
    )
    historico: list[HistoricoDemandaItem] = Field(
        min_length=1,
    )


class PrevisaoDemandaItem(BaseModel):
    bairro: str
    categoriaId: int
    categoriaNome: str
    subservicoId: int
    subservicoNome: str
    ocorrenciasHistoricas: int
    ocorrenciasPeriodoAnterior: int
    ocorrenciasPeriodoRecente: int
    mediaDiaria: float
    tendenciaPercentual: float
    tendencia: TendenciaDemanda
    quantidadePrevista: float
    nivelDemanda: NivelDemanda
    confianca: float
    justificativa: str
    nomeModelo: str
    versaoModelo: str


class PrevisaoDemandaResponse(BaseModel):
    dataGeracao: datetime
    periodoHistoricoDias: int
    periodoPrevisaoDias: int
    totalRegistrosRecebidos: int
    totalRegistrosAnalisados: int
    totalPrevisoes: int
    previsoes: list[PrevisaoDemandaItem]


@dataclass
class ResultadoPontuacao:
    subservico: SubservicoIaItem
    pontuacao: float
    termos_encontrados: list[str]


# =========================================================
# PALAVRAS IGNORADAS
# =========================================================


PALAVRAS_IGNORADAS = {
    "a",
    "ao",
    "aos",
    "as",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "esta",
    "este",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "para",
    "por",
    "que",
    "um",
    "uma",
}


# =========================================================
# REGRAS DAS CATEGORIAS
# =========================================================


REGRAS_CATEGORIAS: dict[str, list[str]] = {
    "infraestrutura urbana": [
        "buraco",
        "cratera",
        "asfalto",
        "pavimento",
        "recapeamento",
        "calcada",
        "semaforo",
        "sinalizacao",
        "placa de transito",
        "lombada",
        "redutor de velocidade",
    ],

    "iluminacao publica": [
        "lampada",
        "iluminacao",
        "luz",
        "poste",
        "luminaria",
        "rua escura",
        "praca escura",
        "area escura",
    ],

    "zeladoria e meio ambiente": [
        "arvore",
        "poda",
        "galho",
        "area verde",
        "praca",
        "parque",
        "capina",
        "mato",
        "vegetacao",
    ],

    "limpeza urbana": [
        "entulho",
        "lixo",
        "residuo",
        "sujeira",
        "limpeza",
        "varricao",
        "coleta",
        "reciclavel",
        "descarte",
    ],

    "fiscalizacao": [
        "denuncia",
        "irregular",
        "fiscalizacao",
        "terreno abandonado",
        "obra irregular",
        "comercio irregular",
        "barulho",
        "som alto",
        "ocupacao de calcada",
    ],

    "mobilidade urbana": [
        "onibus",
        "ponto de onibus",
        "linha de onibus",
        "abrigo",
        "acessibilidade",
        "rampa",
        "piso tatil",
        "cadeirante",
        "ciclovia",
        "ciclofaixa",
    ],
}


# =========================================================
# REGRAS DOS SUBSERVIÇOS
# =========================================================


REGRAS_SUBSERVICOS: dict[
    str,
    dict[str, list[str]],
] = {

    # =====================================================
    # INFRAESTRUTURA URBANA
    # =====================================================

    "buracos na via": {
        "frases": [
            "buraco na rua",
            "buraco na via",
            "buraco no asfalto",
            "buraco na avenida",
            "cratera na rua",
            "cratera na via",
            "asfalto afundado",
            "pavimento quebrado",
            "via danificada",
            "rua esburacada",
        ],
        "palavras": [
            "buraco",
            "cratera",
            "esburacado",
            "afundamento",
            "pavimento",
        ],
    },

    "recapeamento asfaltico": {
        "frases": [
            "recapeamento asfaltico",
            "recapear a rua",
            "recapear a avenida",
            "asfalto desgastado",
            "asfalto deteriorado",
            "pavimento desgastado",
            "rua sem asfalto",
            "via sem asfalto",
            "asfalto muito velho",
        ],
        "palavras": [
            "recapeamento",
            "recapear",
            "asfaltar",
            "pavimentacao",
            "asfalto",
        ],
    },

    "manutencao de calcadas": {
        "frases": [
            "calcada quebrada",
            "calcada danificada",
            "calcada irregular",
            "calcada com buraco",
            "piso da calcada solto",
            "passeio publico quebrado",
            "calcada afundada",
            "calcada destruida",
        ],
        "palavras": [
            "calcada",
            "passeio",
            "piso",
            "pedestre",
        ],
    },

    "sinalizacao viaria": {
        "frases": [
            "falta de sinalizacao",
            "placa de transito quebrada",
            "placa de transito ausente",
            "placa danificada",
            "placa caida",
            "sinalizacao apagada",
            "pintura da via apagada",
            "sinalizacao horizontal apagada",
            "sinalizacao vertical danificada",
        ],
        "palavras": [
            "sinalizacao",
            "placa",
            "pintura",
            "transito",
        ],
    },

    "manutencao de semaforos": {
        "frases": [
            "semaforo apagado",
            "semaforo quebrado",
            "semaforo travado",
            "semaforo com defeito",
            "semaforo piscando",
            "semaforo fora de funcionamento",
            "sinal vermelho queimado",
            "sinal verde queimado",
        ],
        "palavras": [
            "semaforo",
            "sinal",
        ],
    },

    "lombadas e redutores de velocidade": {
        "frases": [
            "instalacao de lombada",
            "solicitacao de lombada",
            "lombada danificada",
            "lombada sem pintura",
            "lombada sem sinalizacao",
            "redutor de velocidade",
            "carros em alta velocidade",
            "veiculos em alta velocidade",
            "excesso de velocidade na rua",
        ],
        "palavras": [
            "lombada",
            "redutor",
            "velocidade",
        ],
    },

    # =====================================================
    # ILUMINAÇÃO PÚBLICA
    # =====================================================

    "lampada queimada": {
        "frases": [
            "lampada queimada",
            "lampada apagada",
            "lampada piscando",
            "luminaria apagada",
            "luminaria queimada",
            "luz do poste apagada",
            "lampada com defeito",
        ],
        "palavras": [
            "lampada",
            "luminaria",
            "piscando",
            "queimada",
        ],
    },

    "falta de iluminacao em via publica": {
        "frases": [
            "rua sem iluminacao",
            "avenida sem iluminacao",
            "via sem iluminacao",
            "rua muito escura",
            "avenida muito escura",
            "trecho sem luz",
            "falta de iluminacao publica",
            "iluminacao insuficiente",
            "varios postes apagados",
        ],
        "palavras": [
            "escuro",
            "iluminacao",
            "luz",
            "via",
        ],
    },

    "manutencao de postes": {
        "frases": [
            "poste quebrado",
            "poste danificado",
            "poste inclinado",
            "poste caindo",
            "poste com risco de queda",
            "poste enferrujado",
            "poste com fiacao exposta",
            "fio solto no poste",
            "poste com faisca",
            "poste com curto circuito",
        ],
        "palavras": [
            "poste",
            "fiacao",
            "fio",
            "faisca",
            "inclinado",
        ],
    },

    "iluminacao em pracas": {
        "frases": [
            "praca sem iluminacao",
            "praca muito escura",
            "falta de luz na praca",
            "postes apagados na praca",
            "iluminacao da praca",
            "luminarias da praca apagadas",
        ],
        "palavras": [
            "praca",
            "iluminacao",
            "luz",
            "luminaria",
        ],
    },

    "iluminacao em areas de risco": {
        "frases": [
            "area de risco sem iluminacao",
            "local perigoso sem iluminacao",
            "viela muito escura",
            "passagem muito escura",
            "beco sem iluminacao",
            "local com risco de assalto",
            "area perigosa durante a noite",
            "reforco de iluminacao",
        ],
        "palavras": [
            "risco",
            "perigoso",
            "viela",
            "beco",
            "seguranca",
        ],
    },

    # =====================================================
    # ZELADORIA E MEIO AMBIENTE
    # =====================================================

    "poda de arvores": {
        "frases": [
            "poda de arvore",
            "arvore precisa de poda",
            "galhos muito grandes",
            "galhos sobre a rua",
            "galhos sobre a calcada",
            "galhos na rede eletrica",
            "galhos encostando nos fios",
            "copa da arvore muito grande",
        ],
        "palavras": [
            "poda",
            "arvore",
            "galho",
            "galhos",
            "copa",
        ],
    },

    "remocao de arvores em risco de queda": {
        "frases": [
            "arvore com risco de queda",
            "arvore prestes a cair",
            "arvore inclinada",
            "arvore caindo",
            "arvore morta",
            "arvore com raiz exposta",
            "tronco rachado",
            "arvore perigosa",
            "remocao de arvore",
        ],
        "palavras": [
            "arvore",
            "queda",
            "inclinada",
            "tronco",
            "raiz",
        ],
    },

    "limpeza de pracas e areas verdes": {
        "frases": [
            "praca suja",
            "area verde suja",
            "lixo na praca",
            "limpeza da praca",
            "limpeza de area verde",
            "folhas acumuladas na praca",
            "residuos na praca",
            "jardim publico sujo",
        ],
        "palavras": [
            "praca",
            "jardim",
            "area verde",
            "limpeza",
            "sujeira",
        ],
    },

    "capina de terrenos publicos": {
        "frases": [
            "mato alto em terreno publico",
            "terreno publico com mato",
            "capina de terreno publico",
            "vegetacao alta em area publica",
            "mato tomando a calcada",
            "mato alto em area municipal",
            "capina de area publica",
        ],
        "palavras": [
            "capina",
            "mato",
            "vegetacao",
            "terreno publico",
        ],
    },

    "manutencao de parques": {
        "frases": [
            "parque abandonado",
            "parque danificado",
            "manutencao do parque",
            "brinquedo quebrado no parque",
            "banco quebrado no parque",
            "equipamento quebrado no parque",
            "playground danificado",
            "estrutura do parque quebrada",
        ],
        "palavras": [
            "parque",
            "playground",
            "brinquedo",
            "equipamento",
            "banco",
        ],
    },

    # =====================================================
    # LIMPEZA URBANA
    # =====================================================

    "coleta de entulho": {
        "frases": [
            "entulho na rua",
            "entulho na calcada",
            "entulho acumulado",
            "restos de obra",
            "moveis velhos abandonados",
            "colchao abandonado",
            "madeira abandonada",
            "coleta de entulho",
        ],
        "palavras": [
            "entulho",
            "moveis",
            "colchao",
            "madeira",
            "restos",
        ],
    },

    "descarte irregular de lixo": {
        "frases": [
            "lixo descartado irregularmente",
            "descarte irregular de lixo",
            "lixo jogado na rua",
            "lixo jogado no terreno",
            "lixo acumulado na calcada",
            "sacos de lixo abandonados",
            "ponto viciado de lixo",
            "descarte clandestino",
        ],
        "palavras": [
            "lixo",
            "descarte",
            "residuo",
            "sacos",
        ],
    },

    "limpeza de vias publicas": {
        "frases": [
            "rua muito suja",
            "avenida muito suja",
            "falta de varricao",
            "limpeza da rua",
            "limpeza da avenida",
            "sujeira na via publica",
            "folhas acumuladas na rua",
            "lama na rua",
        ],
        "palavras": [
            "limpeza",
            "varricao",
            "sujeira",
            "lama",
        ],
    },

    "limpeza pos evento": {
        "frases": [
            "limpeza depois do evento",
            "limpeza pos evento",
            "lixo depois da festa",
            "sujeira depois do evento",
            "residuos depois da feira",
            "limpeza depois da feira",
            "limpeza depois do show",
            "praca suja depois do evento",
        ],
        "palavras": [
            "evento",
            "festa",
            "feira",
            "show",
        ],
    },

    "coleta seletiva": {
        "frases": [
            "coleta seletiva",
            "coleta de reciclaveis",
            "coleta de material reciclavel",
            "reciclagem no bairro",
            "ponto de coleta seletiva",
            "coleta de papel plastico e vidro",
            "lixo reciclavel",
        ],
        "palavras": [
            "reciclavel",
            "reciclagem",
            "papel",
            "plastico",
            "vidro",
        ],
    },

    # =====================================================
    # FISCALIZAÇÃO
    # =====================================================

    "denuncia de terreno abandonado": {
        "frases": [
            "terreno abandonado",
            "terreno particular abandonado",
            "terreno sem manutencao",
            "terreno com mato alto",
            "terreno com lixo",
            "terreno atraindo animais",
            "terreno com foco de dengue",
            "proprietario nao limpa o terreno",
        ],
        "palavras": [
            "terreno",
            "abandonado",
            "proprietario",
            "dengue",
        ],
    },

    "fiscalizacao de obras irregulares": {
        "frases": [
            "obra irregular",
            "construcao irregular",
            "obra sem alvara",
            "obra sem autorizacao",
            "construcao sem licenca",
            "obra invadindo a calcada",
            "construcao em area publica",
            "reforma irregular",
        ],
        "palavras": [
            "obra",
            "construcao",
            "alvara",
            "licenca",
            "reforma",
        ],
    },

    "fiscalizacao de comercio irregular": {
        "frases": [
            "comercio irregular",
            "estabelecimento irregular",
            "comercio sem licenca",
            "comercio sem alvara",
            "venda irregular",
            "ambulante irregular",
            "atividade comercial irregular",
            "estabelecimento sem autorizacao",
        ],
        "palavras": [
            "comercio",
            "estabelecimento",
            "ambulante",
            "venda",
            "alvara",
        ],
    },

    "poluicao sonora": {
        "frases": [
            "som muito alto",
            "barulho excessivo",
            "poluicao sonora",
            "ruido durante a madrugada",
            "festa com som alto",
            "barulho de estabelecimento",
            "musica alta durante a noite",
            "perturbacao do sossego",
        ],
        "palavras": [
            "barulho",
            "ruido",
            "som",
            "musica",
            "sossego",
        ],
    },

    "ocupacao irregular de calcadas": {
        "frases": [
            "ocupacao irregular de calcada",
            "calcada bloqueada por comercio",
            "mercadorias na calcada",
            "mesas ocupando a calcada",
            "objetos bloqueando a calcada",
            "construcao ocupando a calcada",
            "pedestre nao consegue passar",
            "passeio publico obstruido",
        ],
        "palavras": [
            "ocupacao",
            "calcada",
            "obstrucao",
            "mercadoria",
            "mesas",
        ],
    },

    # =====================================================
    # MOBILIDADE URBANA
    # =====================================================

    "solicitacao de ponto de onibus": {
        "frases": [
            "solicitacao de ponto de onibus",
            "instalacao de ponto de onibus",
            "novo ponto de onibus",
            "mudanca de ponto de onibus",
            "realocacao de ponto de onibus",
            "bairro sem ponto de onibus",
            "precisa de ponto de onibus",
        ],
        "palavras": [
            "ponto",
            "onibus",
            "instalacao",
            "mudanca",
        ],
    },

    "reclamacao de linha de onibus": {
        "frases": [
            "onibus atrasado",
            "linha de onibus atrasada",
            "onibus nao passou",
            "poucos onibus na linha",
            "linha de onibus lotada",
            "itinerario do onibus",
            "mudanca de itinerario",
            "reclamacao da linha de onibus",
            "demora do onibus",
        ],
        "palavras": [
            "linha",
            "onibus",
            "atraso",
            "itinerario",
            "lotado",
            "demora",
        ],
    },

    "falta de abrigo em ponto de onibus": {
        "frases": [
            "ponto de onibus sem abrigo",
            "ponto sem cobertura",
            "falta de abrigo no ponto",
            "abrigo de onibus quebrado",
            "cobertura do ponto quebrada",
            "ponto sem banco",
            "ponto de onibus sem cobertura",
        ],
        "palavras": [
            "abrigo",
            "cobertura",
            "ponto",
            "onibus",
            "banco",
        ],
    },

    "problemas de acessibilidade": {
        "frases": [
            "falta de acessibilidade",
            "rampa quebrada",
            "falta de rampa",
            "cadeirante nao consegue passar",
            "piso tatil danificado",
            "piso tatil ausente",
            "acesso para pessoa com deficiencia",
            "obstaculo para cadeirante",
            "calcada sem acessibilidade",
        ],
        "palavras": [
            "acessibilidade",
            "cadeirante",
            "rampa",
            "piso tatil",
            "deficiencia",
        ],
    },

    "manutencao de ciclovias": {
        "frases": [
            "ciclovia danificada",
            "ciclofaixa danificada",
            "buraco na ciclovia",
            "ciclovia sem sinalizacao",
            "ciclofaixa apagada",
            "obstrucao na ciclovia",
            "manutencao da ciclovia",
            "ciclovia em mau estado",
        ],
        "palavras": [
            "ciclovia",
            "ciclofaixa",
            "bicicleta",
            "ciclista",
        ],
    },
}


# =========================================================
# REGRAS DE URGÊNCIA
# =========================================================


TERMOS_CRITICOS = [
    "risco de morte",
    "risco de choque",
    "fio exposto",
    "fiacao exposta",
    "poste caindo",
    "poste prestes a cair",
    "arvore caindo",
    "arvore prestes a cair",
    "desabamento",
    "incendio",
    "curto circuito",
    "faiscas no poste",
    "via totalmente bloqueada",
    "semaforo apagado em cruzamento movimentado",
    "alagamento grave",
    "risco imediato",
]


TERMOS_ALTOS = [
    "risco de acidente",
    "buraco grande",
    "buraco profundo",
    "cratera",
    "via bloqueada",
    "rua bloqueada",
    "sem iluminacao",
    "muito escuro",
    "semaforo apagado",
    "arvore inclinada",
    "tronco rachado",
    "mobilidade reduzida",
    "cadeirante nao consegue passar",
    "ciclovia bloqueada",
    "acesso totalmente bloqueado",
    "lixo hospitalar",
]


TERMOS_MEDIOS = [
    "buraco",
    "lampada queimada",
    "poste apagado",
    "entulho",
    "lixo acumulado",
    "semaforo com defeito",
    "calcada quebrada",
    "poda",
    "mato alto",
    "placa quebrada",
    "abrigo quebrado",
    "ciclovia danificada",
    "barulho excessivo",
    "obra irregular",
]


# =========================================================
# TERMOS DE IMPACTO
# =========================================================


TERMOS_IMPACTO = {
    "hospital": 8,
    "escola": 6,
    "creche": 6,
    "posto de saude": 6,
    "pronto socorro": 8,
    "avenida movimentada": 6,
    "cruzamento": 5,
    "bairro inteiro": 8,
    "varias ruas": 6,
    "muitas pessoas": 5,
    "varios moradores": 5,
    "idoso": 3,
    "cadeirante": 5,
    "pessoa com deficiencia": 5,
    "crianca": 3,
    "ponto de onibus": 3,
    "entrada da escola": 5,
    "entrada do hospital": 6,
}


# =========================================================
# FUNÇÕES DE NORMALIZAÇÃO
# =========================================================


def normalizar_texto(texto: str) -> str:
    texto_normalizado = unicodedata.normalize(
        "NFD",
        texto,
    )

    texto_sem_acentos = "".join(
        caractere
        for caractere in texto_normalizado
        if unicodedata.category(caractere) != "Mn"
    )

    texto_sem_acentos = texto_sem_acentos.lower()

    texto_sem_simbolos = re.sub(
        r"[^a-z0-9\s]",
        " ",
        texto_sem_acentos,
    )

    texto_sem_espacos_extras = re.sub(
        r"\s+",
        " ",
        texto_sem_simbolos,
    )

    return texto_sem_espacos_extras.strip()


def tokenizar(texto: str) -> set[str]:
    return {
        palavra
        for palavra in texto.split()
        if (
            len(palavra) >= 3
            and palavra not in PALAVRAS_IGNORADAS
        )
    }


def termo_presente(
    texto: str,
    termo: str,
) -> bool:
    termo_normalizado = normalizar_texto(
        termo
    )

    padrao = (
        r"(?<!\w)"
        + re.escape(termo_normalizado)
        + r"(?!\w)"
    )

    return re.search(
        padrao,
        texto,
    ) is not None


# =========================================================
# BUSCA DE CATEGORIAS E REGRAS
# =========================================================


def localizar_categoria(
    categoria_id: int,
    categorias: list[CategoriaIaItem],
) -> CategoriaIaItem:
    for categoria in categorias:
        if categoria.id == categoria_id:
            return categoria

    raise HTTPException(
        status_code=422,
        detail=(
            "O subserviço informado possui "
            "uma categoria inexistente."
        ),
    )


def obter_regra_subservico(
    nome_subservico: str,
) -> dict[str, list[str]] | None:
    nome_normalizado = normalizar_texto(
        nome_subservico
    )

    return REGRAS_SUBSERVICOS.get(
        nome_normalizado
    )


# =========================================================
# PONTUAÇÃO DOS SUBSERVIÇOS
# =========================================================


def pontuar_subservico(
    texto: str,
    subservico: SubservicoIaItem,
    categoria: CategoriaIaItem,
) -> ResultadoPontuacao:
    pontuacao = 0.0
    termos_encontrados: list[str] = []

    nome_subservico = normalizar_texto(
        subservico.nome
    )

    nome_categoria = normalizar_texto(
        categoria.nome
    )

    # Nome completo do subserviço no texto.
    if termo_presente(
        texto,
        nome_subservico,
    ):
        pontuacao += 15

        termos_encontrados.append(
            nome_subservico
        )

    regra = obter_regra_subservico(
        subservico.nome
    )

    if regra:
        # Frases específicas possuem peso maior.
        for frase in regra["frases"]:
            if termo_presente(
                texto,
                frase,
            ):
                pontuacao += 8

                termos_encontrados.append(
                    normalizar_texto(frase)
                )

        # Palavras isoladas possuem peso menor.
        for palavra in regra["palavras"]:
            if termo_presente(
                texto,
                palavra,
            ):
                pontuacao += 2.5

                termos_encontrados.append(
                    normalizar_texto(palavra)
                )

    # Compara palavras do texto com o nome do subserviço.
    tokens_texto = tokenizar(texto)

    tokens_nome_subservico = tokenizar(
        nome_subservico
    )

    tokens_comuns = (
        tokens_texto
        & tokens_nome_subservico
    )

    pontuacao += (
        len(tokens_comuns) * 1.75
    )

    # Adiciona uma pontuação leve para termos da categoria.
    termos_categoria = REGRAS_CATEGORIAS.get(
        nome_categoria,
        [],
    )

    for termo_categoria in termos_categoria:
        if termo_presente(
            texto,
            termo_categoria,
        ):
            pontuacao += 0.6

    termos_unicos = list(
        dict.fromkeys(
            termos_encontrados
        )
    )

    return ResultadoPontuacao(
        subservico=subservico,
        pontuacao=round(
            pontuacao,
            2,
        ),
        termos_encontrados=termos_unicos,
    )


# =========================================================
# CLASSIFICAÇÃO DA SOLICITAÇÃO
# =========================================================


def classificar_solicitacao(
    texto: str,
    categorias: list[CategoriaIaItem],
    subservicos: list[SubservicoIaItem],
) -> tuple[
    CategoriaIaItem,
    ResultadoPontuacao,
    float,
]:
    if not categorias:
        raise HTTPException(
            status_code=422,
            detail=(
                "Nenhuma categoria foi "
                "enviada pelo backend."
            ),
        )

    if not subservicos:
        raise HTTPException(
            status_code=422,
            detail=(
                "Nenhum subserviço foi "
                "enviado pelo backend."
            ),
        )

    resultados: list[ResultadoPontuacao] = []

    for subservico in subservicos:
        categoria = localizar_categoria(
            subservico.categoriaId,
            categorias,
        )

        resultado = pontuar_subservico(
            texto,
            subservico,
            categoria,
        )

        resultados.append(
            resultado
        )

    resultados.sort(
        key=lambda resultado: (
            resultado.pontuacao
        ),
        reverse=True,
    )

    melhor_resultado = resultados[0]

    segunda_pontuacao = (
        resultados[1].pontuacao
        if len(resultados) > 1
        else 0.0
    )

    categoria_sugerida = localizar_categoria(
        melhor_resultado
        .subservico
        .categoriaId,
        categorias,
    )

    confianca = calcular_confianca(
        melhor_resultado.pontuacao,
        segunda_pontuacao,
    )

    return (
        categoria_sugerida,
        melhor_resultado,
        confianca,
    )


def calcular_confianca(
    maior_pontuacao: float,
    segunda_pontuacao: float,
) -> float:
    if maior_pontuacao <= 0:
        return 0.20

    cobertura = min(
        maior_pontuacao / 22,
        1,
    )

    diferenca = max(
        maior_pontuacao
        - segunda_pontuacao,
        0,
    )

    margem = min(
        diferenca
        / max(
            maior_pontuacao,
            1,
        ),
        1,
    )

    confianca = (
        0.28
        + cobertura * 0.38
        + margem * 0.30
    )

    return round(
        min(
            confianca,
            0.98,
        ),
        4,
    )


# =========================================================
# CLASSIFICAÇÃO DA URGÊNCIA
# =========================================================


def classificar_urgencia(
    texto: str,
) -> NivelUrgencia:
    possui_termo_critico = any(
        termo_presente(
            texto,
            termo,
        )
        for termo in TERMOS_CRITICOS
    )

    if possui_termo_critico:
        return "CRITICA"

    possui_termo_alto = any(
        termo_presente(
            texto,
            termo,
        )
        for termo in TERMOS_ALTOS
    )

    if possui_termo_alto:
        return "ALTA"

    possui_termo_medio = any(
        termo_presente(
            texto,
            termo,
        )
        for termo in TERMOS_MEDIOS
    )

    if possui_termo_medio:
        return "MEDIA"

    return "BAIXA"


# =========================================================
# IMPACTO E PRIORIDADE
# =========================================================


def calcular_impacto(
    texto: str,
) -> int:
    impacto = 0

    for termo, pontos in TERMOS_IMPACTO.items():
        if termo_presente(
            texto,
            termo,
        ):
            impacto += pontos

    return min(
        impacto,
        15,
    )


def calcular_prioridade(
    urgencia: NivelUrgencia,
    confianca: float,
    impacto: int,
) -> tuple[
    float,
    NivelPrioridade,
]:
    valores_base = {
        "BAIXA": 20.0,
        "MEDIA": 45.0,
        "ALTA": 72.0,
        "CRITICA": 90.0,
    }

    score = valores_base[urgencia]

    score += impacto

    score += min(
        confianca * 8,
        8,
    )

    score = round(
        min(
            score,
            100,
        ),
        2,
    )

    if score >= 90:
        nivel: NivelPrioridade = "CRITICA"

    elif score >= 70:
        nivel = "ALTA"

    elif score >= 40:
        nivel = "MEDIA"

    else:
        nivel = "BAIXA"

    return (
        score,
        nivel,
    )


# =========================================================
# JUSTIFICATIVA
# =========================================================


def criar_justificativa(
    categoria: CategoriaIaItem,
    resultado: ResultadoPontuacao,
    urgencia: NivelUrgencia,
    prioridade: NivelPrioridade,
    confianca: float,
    score_prioridade: float,
) -> str:
    termos = (
        resultado
        .termos_encontrados[:5]
    )

    if termos:
        evidencias = ", ".join(
            f"'{termo}'"
            for termo in termos
        )

        trecho_evidencias = (
            "Os principais termos identificados "
            f"foram {evidencias}. "
        )

    else:
        trecho_evidencias = (
            "Não foram encontrados termos "
            "fortemente específicos, portanto "
            "a classificação possui confiança "
            "reduzida. "
        )

    percentual_confianca = round(
        confianca * 100
    )

    return (
        f"A solicitação foi associada à categoria "
        f"'{categoria.nome}' e ao subserviço "
        f"'{resultado.subservico.nome}'. "
        f"{trecho_evidencias}"
        f"A urgência identificada foi {urgencia}, "
        f"resultando em prioridade {prioridade} "
        f"e score {score_prioridade}. "
        f"Confiança da classificação: "
        f"{percentual_confianca}%."
    )




# =========================================================
# PREVISÃO DE DEMANDAS
# =========================================================


def padronizar_bairro(
    bairro: str,
) -> str:
    bairro_sem_espacos = " ".join(
        bairro.strip().split()
    )

    return bairro_sem_espacos.title()


def normalizar_data_previsao(
    data: datetime,
) -> datetime:
    if (
        data.tzinfo is not None
        and data.utcoffset() is not None
    ):
        return (
            data.astimezone(timezone.utc)
            .replace(tzinfo=None)
        )

    return data.replace(tzinfo=None)


def classificar_tendencia_demanda(
    tendencia_percentual: float,
) -> TendenciaDemanda:
    if tendencia_percentual > 15:
        return "CRESCENTE"

    if tendencia_percentual < -15:
        return "DECRESCENTE"

    return "ESTAVEL"


def classificar_nivel_demanda(
    quantidade_prevista: float,
    periodo_previsao_dias: int,
) -> NivelDemanda:
    equivalente_trinta_dias = (
        quantidade_prevista
        * 30
        / periodo_previsao_dias
    )

    if equivalente_trinta_dias >= 15:
        return "CRITICA"

    if equivalente_trinta_dias >= 8:
        return "ALTA"

    if equivalente_trinta_dias >= 3:
        return "MEDIA"

    return "BAIXA"


def calcular_confianca_previsao(
    total_ocorrencias: int,
    ocorrencias_anteriores: int,
    ocorrencias_recentes: int,
    dias_ativos: int,
) -> float:
    fator_volume = min(
        total_ocorrencias / 20,
        1,
    )

    fator_dias_ativos = min(
        dias_ativos / 12,
        1,
    )

    if (
        ocorrencias_anteriores > 0
        and ocorrencias_recentes > 0
    ):
        fator_cobertura = 1.0
    else:
        fator_cobertura = 0.35

    confianca = (
        0.25
        + fator_volume * 0.35
        + fator_dias_ativos * 0.20
        + fator_cobertura * 0.15
    )

    return round(
        min(confianca, 0.95),
        4,
    )


def criar_justificativa_previsao(
    bairro: str,
    categoria_nome: str,
    subservico_nome: str,
    ocorrencias_anteriores: int,
    ocorrencias_recentes: int,
    tendencia: TendenciaDemanda,
    quantidade_prevista: float,
    periodo_previsao_dias: int,
) -> str:
    return (
        f"No bairro '{bairro}', o subserviço "
        f"'{subservico_nome}', da categoria "
        f"'{categoria_nome}', apresentou "
        f"{ocorrencias_anteriores} ocorrências "
        f"no período anterior e "
        f"{ocorrencias_recentes} no período recente. "
        f"A tendência identificada foi {tendencia}. "
        f"A previsão estimada é de "
        f"{quantidade_prevista} ocorrências "
        f"nos próximos {periodo_previsao_dias} dias."
    )


def gerar_previsoes_demanda(
    request: PrevisaoDemandaRequest,
) -> tuple[list[PrevisaoDemandaItem], int]:
    registros = [
        {
            "solicitacaoId": item.solicitacaoId,
            "bairro": padronizar_bairro(
                item.bairro
            ),
            "categoriaId": item.categoriaId,
            "categoriaNome": item.categoriaNome,
            "subservicoId": item.subservicoId,
            "subservicoNome": item.subservicoNome,
            "dataAbertura": normalizar_data_previsao(
                item.dataAbertura
            ),
        }
        for item in request.historico
    ]

    dataframe = pd.DataFrame(registros)

    dataframe["dataAbertura"] = pd.to_datetime(
        dataframe["dataAbertura"],
        errors="coerce",
    )

    dataframe = dataframe.dropna(
        subset=["dataAbertura"]
    )

    agora = pd.Timestamp(datetime.now())

    inicio_historico = (
        agora
        - pd.Timedelta(
            days=request.periodoHistoricoDias
        )
    )

    dataframe = dataframe[
        (
            dataframe["dataAbertura"]
            >= inicio_historico
        )
        & (
            dataframe["dataAbertura"]
            <= agora
        )
    ].copy()

    if dataframe.empty:
        raise HTTPException(
            status_code=422,
            detail=(
                "Nenhuma solicitação foi encontrada "
                "dentro do período histórico informado."
            ),
        )

    total_registros_analisados = len(dataframe)

    periodo_recente_dias = (
        request.periodoHistoricoDias // 2
    )

    periodo_anterior_dias = (
        request.periodoHistoricoDias
        - periodo_recente_dias
    )

    limite_periodo_recente = (
        agora
        - pd.Timedelta(
            days=periodo_recente_dias
        )
    )

    colunas_agrupamento = [
        "bairro",
        "categoriaId",
        "categoriaNome",
        "subservicoId",
        "subservicoNome",
    ]

    previsoes: list[PrevisaoDemandaItem] = []

    grupos = dataframe.groupby(
        colunas_agrupamento,
        dropna=False,
        sort=False,
    )

    for valores_grupo, grupo in grupos:
        (
            bairro,
            categoria_id,
            categoria_nome,
            subservico_id,
            subservico_nome,
        ) = valores_grupo

        total_ocorrencias = len(grupo)

        if (
            total_ocorrencias
            < request.minimoOcorrencias
        ):
            continue

        grupo_recente = grupo[
            grupo["dataAbertura"]
            >= limite_periodo_recente
        ]

        grupo_anterior = grupo[
            grupo["dataAbertura"]
            < limite_periodo_recente
        ]

        ocorrencias_recentes = len(
            grupo_recente
        )

        ocorrencias_anteriores = len(
            grupo_anterior
        )

        media_recente = (
            ocorrencias_recentes
            / periodo_recente_dias
        )

        media_anterior = (
            ocorrencias_anteriores
            / periodo_anterior_dias
        )

        if media_anterior > 0:
            tendencia_percentual = (
                (
                    media_recente
                    - media_anterior
                )
                / media_anterior
            ) * 100

        elif media_recente > 0:
            tendencia_percentual = 100.0

        else:
            tendencia_percentual = 0.0

        tendencia_percentual = round(
            max(
                min(
                    tendencia_percentual,
                    500,
                ),
                -100,
            ),
            2,
        )

        tendencia = classificar_tendencia_demanda(
            tendencia_percentual
        )

        taxa_diaria_ponderada = (
            media_recente * 0.70
            + media_anterior * 0.30
        )

        quantidade_prevista = round(
            taxa_diaria_ponderada
            * request.periodoPrevisaoDias,
            2,
        )

        nivel_demanda = classificar_nivel_demanda(
            quantidade_prevista,
            request.periodoPrevisaoDias,
        )

        dias_ativos = int(
            grupo["dataAbertura"]
            .dt.normalize()
            .nunique()
        )

        confianca = calcular_confianca_previsao(
            total_ocorrencias,
            ocorrencias_anteriores,
            ocorrencias_recentes,
            dias_ativos,
        )

        media_diaria = round(
            total_ocorrencias
            / request.periodoHistoricoDias,
            4,
        )

        justificativa = criar_justificativa_previsao(
            str(bairro),
            str(categoria_nome),
            str(subservico_nome),
            ocorrencias_anteriores,
            ocorrencias_recentes,
            tendencia,
            quantidade_prevista,
            request.periodoPrevisaoDias,
        )

        previsoes.append(
            PrevisaoDemandaItem(
                bairro=str(bairro),
                categoriaId=int(categoria_id),
                categoriaNome=str(categoria_nome),
                subservicoId=int(subservico_id),
                subservicoNome=str(subservico_nome),
                ocorrenciasHistoricas=(
                    total_ocorrencias
                ),
                ocorrenciasPeriodoAnterior=(
                    ocorrencias_anteriores
                ),
                ocorrenciasPeriodoRecente=(
                    ocorrencias_recentes
                ),
                mediaDiaria=media_diaria,
                tendenciaPercentual=(
                    tendencia_percentual
                ),
                tendencia=tendencia,
                quantidadePrevista=(
                    quantidade_prevista
                ),
                nivelDemanda=nivel_demanda,
                confianca=confianca,
                justificativa=justificativa,
                nomeModelo=(
                    "GovAtende Previsão de Demandas"
                ),
                versaoModelo="1.0.0",
            )
        )

    previsoes.sort(
        key=lambda previsao: (
            previsao.quantidadePrevista
        ),
        reverse=True,
    )

    return (
        previsoes,
        total_registros_analisados,
    )


# =========================================================
# ENDPOINTS
# =========================================================


@app.get("/health")
def verificar_saude() -> dict[str, object]:
    return {
        "status": "UP",
        "servico": "GovAtende IA",
        "versaoApi": "2.0.0",
        "modelos": {
            "classificacao": "1.2.0",
            "previsaoDemandas": "1.0.0",
        },
    }


@app.post(
    "/analisar",
    response_model=AnaliseIaResponse,
)
def analisar(
    request: AnaliseIaRequest,
) -> AnaliseIaResponse:
    # O título aparece duas vezes para possuir um peso
    # ligeiramente maior que a descrição.
    texto = normalizar_texto(
        f"{request.titulo} "
        f"{request.titulo} "
        f"{request.descricao}"
    )

    (
        categoria,
        resultado,
        confianca,
    ) = classificar_solicitacao(
        texto,
        request.categorias,
        request.subservicos,
    )

    urgencia = classificar_urgencia(
        texto
    )

    impacto = calcular_impacto(
        texto
    )

    (
        score_prioridade,
        nivel_prioridade,
    ) = calcular_prioridade(
        urgencia,
        confianca,
        impacto,
    )

    justificativa = criar_justificativa(
        categoria,
        resultado,
        urgencia,
        nivel_prioridade,
        confianca,
        score_prioridade,
    )

    return AnaliseIaResponse(
        categoriaSugeridaId=(
            categoria.id
        ),
        subservicoSugeridoId=(
            resultado.subservico.id
        ),
        urgenciaSugerida=urgencia,
        scorePrioridade=(
            score_prioridade
        ),
        nivelPrioridade=(
            nivel_prioridade
        ),
        confianca=confianca,
        justificativa=justificativa,
        nomeModelo=(
            "GovAtende Classificador Híbrido"
        ),
        versaoModelo="1.2.0",
    )


@app.post(
    "/prever-demandas",
    response_model=PrevisaoDemandaResponse,
)
def prever_demandas(
    request: PrevisaoDemandaRequest,
) -> PrevisaoDemandaResponse:
    (
        previsoes,
        total_registros_analisados,
    ) = gerar_previsoes_demanda(request)

    return PrevisaoDemandaResponse(
        dataGeracao=datetime.now(),
        periodoHistoricoDias=(
            request.periodoHistoricoDias
        ),
        periodoPrevisaoDias=(
            request.periodoPrevisaoDias
        ),
        totalRegistrosRecebidos=len(
            request.historico
        ),
        totalRegistrosAnalisados=(
            total_registros_analisados
        ),
        totalPrevisoes=len(previsoes),
        previsoes=previsoes,
    )
