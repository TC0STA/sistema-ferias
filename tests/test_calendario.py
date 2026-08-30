import unittest
from datetime import date

from routes.dashboard import _eventos_na_data, _montar_eventos_calendario


def periodo(event_id, nome, inicio, fim, status_classe="scheduled"):
    return {
        "id": event_id,
        "nome": nome,
        "inicio": inicio,
        "fim": fim,
        "data_retorno": fim,
        "status": "Programada",
        "status_classe": status_classe,
    }


class CalendarMilestoneTests(unittest.TestCase):
    def test_ferias_aparecem_somente_no_inicio_e_retorno_somente_no_fim(self):
        eventos = _montar_eventos_calendario([
            periodo(1, "João", date(2026, 8, 5), date(2026, 8, 17)),
        ])

        inicio = _eventos_na_data(eventos, date(2026, 8, 5))
        self.assertEqual(
            [(item["nome"], item["tipo"]) for item in inicio],
            [("João", "ferias")],
        )

        for dia in (6, 10, 16):
            with self.subTest(dia=dia):
                self.assertEqual(
                    _eventos_na_data(eventos, date(2026, 8, dia)),
                    [],
                )

        retorno = _eventos_na_data(eventos, date(2026, 8, 17))
        self.assertEqual(
            [(item["nome"], item["tipo"]) for item in retorno],
            [("João", "retorno")],
        )

    def test_nenhuma_data_intermediaria_recebe_evento_de_ferias(self):
        eventos = _montar_eventos_calendario([
            periodo(1, "João", date(2026, 8, 5), date(2026, 8, 17)),
        ])

        for dia in range(6, 17):
            with self.subTest(dia=dia):
                self.assertEqual(
                    _eventos_na_data(eventos, date(2026, 8, dia)),
                    [],
                )

    def test_colaboradores_com_inicios_diferentes_ficam_em_datas_diferentes(self):
        eventos = _montar_eventos_calendario([
            periodo(1, "João", date(2026, 8, 5), date(2026, 8, 17)),
            periodo(2, "Maria", date(2026, 8, 10), date(2026, 8, 20)),
        ])

        dia_cinco = _eventos_na_data(eventos, date(2026, 8, 5))
        dia_dez = _eventos_na_data(eventos, date(2026, 8, 10))

        self.assertEqual(
            [(item["nome"], item["tipo"]) for item in dia_cinco],
            [("João", "ferias")],
        )
        self.assertEqual(
            [(item["nome"], item["tipo"]) for item in dia_dez],
            [("Maria", "ferias")],
        )

    def test_varios_inicios_no_mesmo_dia_sao_preservados(self):
        eventos = _montar_eventos_calendario([
            periodo(1, "João", date(2026, 8, 5), date(2026, 8, 17)),
            periodo(2, "Maria", date(2026, 8, 5), date(2026, 8, 20)),
        ])

        eventos_do_dia = _eventos_na_data(eventos, date(2026, 8, 5))
        self.assertEqual(
            [(item["nome"], item["tipo"]) for item in eventos_do_dia],
            [("João", "ferias"), ("Maria", "ferias")],
        )


if __name__ == "__main__":
    unittest.main()
