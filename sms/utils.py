from rest_framework import settings

from sms.sms_provider_clients.magfa import MagfaProvider


def get_client_api(sender: str):
    if sender.startswith("3000"):
        return MagfaProvider(
            settings.MAGFA_USERNAME, settings.MAGFA_PASSWORD, settings.MAGFA_DOMAIN, sender
        )
    elif sender.startswith("5000"):
        # TODO return Arad sms client
        return None
    return None
