"""Local monthly campaign palette for the Fokus Férias interface."""

from collections.abc import Mapping
from datetime import datetime
import logging
from typing import TypedDict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


TIME_ZONE = "America/Sao_Paulo"
logger = logging.getLogger(__name__)


class MonthlyTheme(TypedDict):
    id: str
    name: str


MONTHLY_CAMPAIGNS: dict[int, dict[str, str | bool]] = {
    1: {"id": "janeiro-branco", "name": "Janeiro Branco"},
    2: {"id": "fevereiro-roxo", "name": "Fevereiro Roxo"},
    3: {"id": "marco-lilas", "name": "Março Lilás"},
    4: {"id": "abril-azul", "name": "Abril Azul"},
    5: {"id": "maio-amarelo", "name": "Maio Amarelo"},
    6: {"id": "junho-vermelho", "name": "Junho Vermelho"},
    7: {"id": "julho-amarelo", "name": "Julho Amarelo"},
    8: {"id": "agosto-dourado", "name": "Agosto Dourado"},
    9: {"id": "setembro-amarelo", "name": "Setembro Amarelo", "login_only": True},
    10: {"id": "outubro-rosa", "name": "Outubro Rosa"},
    11: {"id": "novembro-azul", "name": "Novembro Azul"},
    12: {"id": "dezembro-vermelho", "name": "Dezembro Vermelho"},
}

_THEME_IDS = frozenset({
    "janeiro-branco",
    "fevereiro-roxo",
    "marco-lilas",
    "abril-azul",
    "maio-amarelo",
    "junho-vermelho",
    "julho-amarelo",
    "agosto-dourado",
    "setembro-amarelo",
    "outubro-rosa",
    "novembro-azul",
    "dezembro-vermelho",
})


def _get_monthly_theme(
    month: int | None,
    include_login_only: bool,
) -> MonthlyTheme | None:
    if month is None:
        try:
            month = datetime.now(ZoneInfo(TIME_ZONE)).month
        except (OSError, ValueError, ZoneInfoNotFoundError):
            logger.warning(
                "Monthly campaign disabled because timezone %s is unavailable.",
                TIME_ZONE,
                exc_info=True,
            )
            return None

    if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
        return None

    campaigns = MONTHLY_CAMPAIGNS
    if not isinstance(campaigns, Mapping):
        logger.warning("Monthly campaign configuration is not a mapping.")
        return None
    campaign = campaigns.get(month)
    if not isinstance(campaign, Mapping):
        if campaign is not None:
            logger.warning(
                "Invalid monthly campaign configuration for month %s.", month
            )
        return None

    theme_id = campaign.get("id")
    name = campaign.get("name")
    login_only = campaign.get("login_only", False)
    if (
        not isinstance(theme_id, str)
        or theme_id not in _THEME_IDS
        or not isinstance(name, str)
        or not name.strip()
        or not isinstance(login_only, bool)
    ):
        logger.warning(
            "Invalid monthly campaign configuration for month %s.", month
        )
        return None

    if login_only and not include_login_only:
        return None

    return {"id": theme_id, "name": name.strip()}


def get_monthly_theme(month: int | None = None) -> MonthlyTheme | None:
    """Return campaigns enabled for the shared application interface."""
    return _get_monthly_theme(month, include_login_only=False)


def get_login_monthly_theme(month: int | None = None) -> MonthlyTheme | None:
    """Return any configured campaign for the login page."""
    return _get_monthly_theme(month, include_login_only=True)
