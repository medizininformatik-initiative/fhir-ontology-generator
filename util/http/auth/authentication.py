import math
from typing import Optional
from datetime import datetime
from requests import Session
from requests.auth import AuthBase
from util.log import get_class_logger


class OAuthClientCredentials(AuthBase):
    client_credentials: tuple[str, Optional[str]]
    token_access_url: str
    session: Session = None
    user_credentials: tuple[str, str] = None
    access_token: str = None
    expires_in: int = 0
    refresh_token: str = None
    refresh_expires_in: int = 0
    last_retrieval: float = 0

    __logger = get_class_logger("OAuthClientCredentials")

    def __init__(self, client_credentials: tuple[str, Optional[str]], token_access_url: str, session: Session = None,
                 user_credentials: Optional[tuple[str, str]] = None):
        self.client_credentials = client_credentials
        self.token_access_url = token_access_url
        self.session = session if session is not None else Session()
        self.user_credentials = user_credentials

    def __get_base_request_body(self) -> dict:
        body = {'client_id': self.client_credentials[0], 'client_secret': self.client_credentials[1], 'scope': "openid"}
        if self.user_credentials:
            body['grant_type'] = "password"
            body['username'] = self.user_credentials[0]
            body['password'] = self.user_credentials[1]
        else:
            body['grant_type'] = "client_credentials"
        return body

    def __process_response(self, response_body):
        if 'access_token' in response_body:
            self.access_token = response_body['access_token']
        else:
            raise KeyError("No access token in token request response")
        self.expires_in = response_body.get('expires_in', math.inf)
        self.refresh_token = response_body.get('refresh_token', None)
        self.refresh_expires_in = response_body.get('refresh_expires_in', math.inf)

    def __fetch_access_token(self):
        self.last_retrieval = datetime.now().timestamp()
        body = self.__get_base_request_body()
        response_body = self.session.post(url=self.token_access_url, data=body).json()
        self.__process_response(response_body)

    def __refresh_access_token(self):
        self.last_retrieval = datetime.now().timestamp()
        body = {'grant_type': "refresh_token", 'refresh_token': self.refresh_token, 'scope': "openid"}
        response_body = self.session.post(url=self.token_access_url, data=body).json()
        self.__process_response(response_body)

    def __check_access_token(self):
        ts = datetime.now().timestamp()
        if ts > self.last_retrieval + self.expires_in or self.access_token is None:
            if ts < self.last_retrieval + self.refresh_expires_in and self.refresh_token is not None:
                self.__refresh_access_token()
            else:
                self.__fetch_access_token()

    def __call__(self, r):
        self.__check_access_token()
        r.headers['Authorization'] = f"Bearer {self.access_token}"
        return r