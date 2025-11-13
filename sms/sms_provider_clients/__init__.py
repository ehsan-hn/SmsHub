from abc import ABC, abstractmethod


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
