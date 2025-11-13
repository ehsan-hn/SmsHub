import json

import requests
from requests.auth import HTTPBasicAuth

from sms.sms_provider_clients import SmsProvider


class MagfaProvider(SmsProvider):
    def __init__(
        self,
        username: str,
        password: str,
        domain: str,
        sender: str | None = None,
        endpoint: str = "https://sms.magfa.com/api/http/sms/v2/",
        *args,
        **kwargs,
    ):
        self.base_url = endpoint
        self.username = username
        self.password = password
        self.domain = domain
        self.sender = sender
        self.auth = HTTPBasicAuth(f"{username}/{domain}", password)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update(
            {"Accept": "application/json", "Content-Type": "application/json"}
        )

    def _request(self, method, endpoint, **kwargs):
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as http_err:
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"status": -99, "error": "HTTP Error", "message": str(http_err)}
        except requests.exceptions.RequestException as req_err:
            return {"status": -100, "error": "Request Error", "message": str(req_err)}
        except json.JSONDecodeError:
            return {"status": -101, "error": "JSON Decode Error", "message": ""}

    def get_balance(self):
        return self._request("GET", "balance")

    def send_sms(self, sender: str, destination: str, message: str, uid: int) -> dict:
        return self.send_bulk_sms(sender, [destination], message, [uid])

    def check_status(self, mid: str) -> dict:
        return self._request("GET", f"statuses/{mid}")

    def send_bulk_sms(
        self, sender: str, destinations: list[str], message: str, uids: list[int]
    ) -> dict:
        payload = {
            "senders": [self.sender] * len(destinations),
            "recipients": destinations,
            "messages": [message] * len(destinations),
            "uids": uids,
        }
        return self._request("POST", "send", json=payload)

    def get_message_by_uid(self, uid: int):
        endpoint = f"mid/{uid}"
        return self._request("GET", endpoint)

    def get_statuses(self, message_ids: list):
        mids_str = ",".join(map(str, message_ids))
        endpoint = f"statuses/{mids_str}"
        return self._request("GET", endpoint)
