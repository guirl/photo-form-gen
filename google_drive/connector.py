import socket
import os.path
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import logging
from random import random
from time import sleep


# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"]
DEFAULT_TIMEOUT = 5 * 60
retriable_status_codes = [409, 413, 429, 502, 503, 504]
backoff_factor = 2
max_retries = 5


def random_delay(base_delay=0):
    total_delay = base_delay + random()
    sleep(total_delay)
    return total_delay


def format_sec(seconds):
    return "{:,.3f} sec".format(seconds)


def handle_http_error(e, attempts, all_delays):
    logging.warning(f"Received {e.status_code} response on attempt {attempts}. Details: `{e.error_details}`")
    if e.status_code not in retriable_status_codes or attempts > max_retries:
        logging.error(f"Request failed after {attempts} tries with total delay time of {format_sec(all_delays)}.")
        raise e
    delay = backoff_factor * (2 ** (attempts - 2))
    total_delay = random_delay(delay)
    all_delays += total_delay
    logging.debug(f"Delayed for {format_sec(total_delay)}, retrying")


def execute_request(request):
    response = None
    attempts = 0
    success = False
    all_delays = random_delay()
    logging.debug(f"Starting retryable request execution after {format_sec(all_delays)} delay")
    while not success:
        attempts += 1
        try:
            response = request.execute()
        except HttpError as e:
            handle_http_error(e, attempts, all_delays)
        else:
            msg = f"Succeeded executing request in {attempts} tries with total delay time of {format_sec(all_delays)}."
            if attempts > 1:
                logging.warning(msg)
            else:
                logging.debug(msg)
            success = True
    return response


def sheet_url(doc_id, sheet_id):
    return f"https://docs.google.com/spreadsheets/d/{doc_id}/edit#gid={sheet_id}"


class GoogleConnector:
    __service = None
    __creds = None
    def __init__(self, service_name, namespace, creds_file='credentials.json', token_file='token.json'):
        self.__creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists(token_file):
            self.__creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not self.__creds or not self.__creds.valid:
            if self.__creds and self.__creds.expired and self.__creds.refresh_token:
                self.__creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
                self.__creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(token_file, 'w') as token:
                token.write(self.__creds.to_json())
        socket.setdefaulttimeout(DEFAULT_TIMEOUT)
        if service_name and namespace:
            self.build_service(service_name, namespace)

    def build_service(self, service_name, namespace):
        self.__service = build(service_name, namespace, credentials=self.__creds)

    def service(self):
        assert self.__service, "Google API service has not been built for a specific API. First call `build_service('sheets', 'v4')` for example."
        return self.__service

