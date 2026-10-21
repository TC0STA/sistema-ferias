import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import render_template

from app import app
from services.monthly_theme import (
    MONTHLY_CAMPAIGNS,
    TIME_ZONE,
    get_login_monthly_theme,
    get_monthly_theme,
)


class MonthlyThemeTests(unittest.TestCase):
    def test_calendar_contains_all_twelve_campaigns(self):
        expected = {
            1: ("janeiro-branco", "Janeiro Branco"),
            2: ("fevereiro-roxo", "Fevereiro Roxo"),
            3: ("marco-lilas", "Março Lilás"),
            4: ("abril-azul", "Abril Azul"),
            5: ("maio-amarelo", "Maio Amarelo"),
            6: ("junho-vermelho", "Junho Vermelho"),
            7: ("julho-amarelo", "Julho Amarelo"),
            8: ("agosto-dourado", "Agosto Dourado"),
            9: ("setembro-amarelo", "Setembro Amarelo"),
            10: ("outubro-rosa", "Outubro Rosa"),
            11: ("novembro-azul", "Novembro Azul"),
            12: ("dezembro-vermelho", "Dezembro Vermelho"),
        }
        self.assertEqual(set(MONTHLY_CAMPAIGNS), set(expected))
        for month, (theme_id, name) in expected.items():
            with self.subTest(month=month):
                self.assertEqual(
                    get_login_monthly_theme(month),
                    {"id": theme_id, "name": name},
                )
                expected_shared_theme = (
                    None
                    if month == 9
                    else {"id": theme_id, "name": name}
                )
                self.assertEqual(
                    get_monthly_theme(month),
                    expected_shared_theme,
                )

    def test_selects_october_campaign(self):
        self.assertEqual(
            get_monthly_theme(10),
            {"id": "outubro-rosa", "name": "Outubro Rosa"},
        )

    def test_selects_november_campaign(self):
        self.assertEqual(
            get_monthly_theme(11),
            {"id": "novembro-azul", "name": "Novembro Azul"},
        )

    def test_september_campaign_is_limited_to_login(self):
        self.assertEqual(
            get_login_monthly_theme(9),
            {"id": "setembro-amarelo", "name": "Setembro Amarelo"},
        )
        self.assertIsNone(get_monthly_theme(9))

    def test_month_without_campaign_uses_default_theme(self):
        with patch.dict(MONTHLY_CAMPAIGNS, {}, clear=True):
            self.assertIsNone(get_login_monthly_theme(12))
            self.assertIsNone(get_monthly_theme(12))

    def test_invalid_month_and_campaign_configuration_use_default_theme(self):
        self.assertIsNone(get_monthly_theme(0))
        self.assertIsNone(get_monthly_theme(13))
        self.assertIsNone(get_monthly_theme(True))
        with patch.dict(
            MONTHLY_CAMPAIGNS,
            {10: {"id": "custom-untrusted-theme", "name": "Campanha"}},
        ):
            self.assertIsNone(get_monthly_theme(10))

    def test_timezone_error_uses_default_theme(self):
        with patch(
            "services.monthly_theme.ZoneInfo",
            side_effect=ZoneInfoNotFoundError(TIME_ZONE),
        ):
            with self.assertLogs("services.monthly_theme", level="WARNING"):
                self.assertIsNone(get_monthly_theme())

    def test_uses_explicit_brazil_timezone_for_current_month(self):
        current_time = datetime(2026, 11, 1, 1, tzinfo=ZoneInfo(TIME_ZONE))
        with patch("services.monthly_theme.datetime") as datetime_mock:
            datetime_mock.now.return_value = current_time
            self.assertEqual(get_monthly_theme(), get_monthly_theme(11))
            datetime_mock.now.assert_called_once()
            self.assertEqual(datetime_mock.now.call_args.args[0].key, TIME_ZONE)

    def test_campaign_name_renders_in_login_and_sidebar(self):
        campaign = {"id": "setembro-amarelo", "name": "Setembro Amarelo"}
        with (
            patch("app.get_login_monthly_theme", return_value=campaign),
            patch("app.get_monthly_theme", return_value=None),
        ):
            with app.test_request_context("/login"):
                login_html = render_template(
                    "login.html",
                    erro=None,
                    usuario="",
                    next_url="/dashboard",
                    login_monthly_theme=campaign,
                )
                sidebar_html = render_template(
                    "_sidebar.html",
                    current_user=SimpleNamespace(
                        iniciais="TC",
                        perfil="consulta",
                        nome="Usuário de teste",
                    ),
                )

        self.assertIn('data-month-theme="setembro-amarelo"', login_html)
        self.assertIn("Setembro Amarelo", login_html)
        self.assertNotIn("Setembro Amarelo", sidebar_html)

    def test_login_request_receives_monthly_campaign_context(self):
        campaign = {"id": "setembro-amarelo", "name": "Setembro Amarelo"}
        with (
            patch("app.get_login_monthly_theme", return_value=campaign),
            patch("app.get_monthly_theme", return_value=None),
        ):
            response = app.test_client().get("/login")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b'data-month-theme="setembro-amarelo"',
            response.data,
        )
        self.assertIn(b"Setembro Amarelo", response.data)

    def test_login_request_without_campaign_receives_default_context(self):
        with (
            patch("app.get_login_monthly_theme", return_value=None),
            patch("app.get_monthly_theme", return_value=None),
        ):
            response = app.test_client().get("/login")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'data-month-theme=""', response.data)
        self.assertNotIn(b'class="monthly-campaign login-campaign"', response.data)

    def test_default_theme_renders_login_without_campaign_label(self):
        with patch("app.get_login_monthly_theme", return_value=None):
            with app.test_request_context("/login"):
                login_html = render_template(
                    "login.html",
                    erro=None,
                    usuario="",
                    next_url="/dashboard",
                    login_monthly_theme=None,
                )

        self.assertIn('data-month-theme=""', login_html)
        self.assertNotIn("monthly-campaign", login_html)


if __name__ == "__main__":
    unittest.main()
