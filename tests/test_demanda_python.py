import unittest
from datetime import datetime, timedelta

from main import (
    HistoricoDemandaItem,
    PrevisaoDemandaRequest,
    gerar_previsoes_demanda,
)


class GeracaoPrevisaoDemandaTest(unittest.TestCase):
    def test_ordenar_previsoes_por_quantidade_decrescente(
        self,
    ) -> None:
        agora = datetime.now()

        historico = [
            HistoricoDemandaItem(
                solicitacaoId=1,
                bairro="Centro",
                categoriaId=1,
                categoriaNome="Infraestrutura urbana",
                subservicoId=1,
                subservicoNome="Buracos na via",
                dataAbertura=agora - timedelta(days=1),
            ),
            HistoricoDemandaItem(
                solicitacaoId=2,
                bairro="Centro",
                categoriaId=1,
                categoriaNome="Infraestrutura urbana",
                subservicoId=1,
                subservicoNome="Buracos na via",
                dataAbertura=agora - timedelta(days=2),
            ),
            HistoricoDemandaItem(
                solicitacaoId=3,
                bairro="Centro",
                categoriaId=1,
                categoriaNome="Infraestrutura urbana",
                subservicoId=1,
                subservicoNome="Buracos na via",
                dataAbertura=agora - timedelta(days=3),
            ),
            HistoricoDemandaItem(
                solicitacaoId=4,
                bairro="Centro",
                categoriaId=1,
                categoriaNome="Infraestrutura urbana",
                subservicoId=1,
                subservicoNome="Buracos na via",
                dataAbertura=agora - timedelta(days=4),
            ),
            HistoricoDemandaItem(
                solicitacaoId=5,
                bairro="Pinheiros",
                categoriaId=2,
                categoriaNome="Iluminação pública",
                subservicoId=2,
                subservicoNome="Lâmpada queimada",
                dataAbertura=agora - timedelta(days=1),
            ),
            HistoricoDemandaItem(
                solicitacaoId=6,
                bairro="Pinheiros",
                categoriaId=2,
                categoriaNome="Iluminação pública",
                subservicoId=2,
                subservicoNome="Lâmpada queimada",
                dataAbertura=agora - timedelta(days=2),
            ),
        ]

        request = PrevisaoDemandaRequest(
            periodoHistoricoDias=30,
            periodoPrevisaoDias=30,
            minimoOcorrencias=2,
            historico=historico,
        )

        previsoes, total_analisado = (
            gerar_previsoes_demanda(request)
        )

        quantidades = [
            previsao.quantidadePrevista
            for previsao in previsoes
        ]

        self.assertEqual(total_analisado, 6)
        self.assertEqual(len(previsoes), 2)

        self.assertEqual(
            quantidades,
            sorted(
                quantidades,
                reverse=True,
            ),
        )

        self.assertEqual(
            previsoes[0].bairro,
            "Centro",
        )


if __name__ == "__main__":
    unittest.main()