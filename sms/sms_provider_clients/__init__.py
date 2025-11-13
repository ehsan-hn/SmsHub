from abc import ABC, abstractmethod

from django.conf import settings

from sms.sms_provider_clients.magfa import MagfaProvider


class SmsProvider(ABC):
    @abstractmethod
    def send_sms(self, sender: str, destination: str, message: str, uid: int) -> dict:
        """Send a single SMS"""
        pass

    @abstractmethod
    def send_bulk_sms(
        self, sender: str, destinations: list[str], message: str, uids: list[int]
    ) -> dict:
        """Send bulk SMS"""
        pass

    @abstractmethod
    def check_status(self, batch_id: str) -> dict:
        """Check delivery status"""
        pass


def get_client_api(sender: str):
    if sender.startswith("3000"):
        return MagfaProvider(
            settings.MAGFA_USERNAME, settings.MAGFA_PASSWORD, settings.MAGFA_DOMAIN, sender
        )
    elif sender.startswith("5000"):
        # TODO return Arad sms client
        return None
    return None
