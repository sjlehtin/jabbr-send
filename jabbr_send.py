__author__ = "sjl@ssh.com"
__license__ = "BSD" # See LICENSE.

import requests
import time
import logging
import json
from collections import OrderedDict
import uuid
import urllib

logger = logging.getLogger(__name__)

class ConnectionError(Exception):
    """
    This exception is raised if the sending does not end well.
    """

class Client(object):
    """
    Send a message to a JabbR chat room.
    """

    version = "1.0.4875.39771"
    """
    Fake version.
    """

    transport = "serverSentEvents"

    def connect(self, url, username, password, room=None):
        self.url = url
        self.username = username
        self.password = password
        self.room = room
        self.id = 0

        headers = {"Content-Type": "application/x-www-form-urlencoded",
                   "origin": self.url,
                   # If Host is required, it will need to parsed from the URL.
                   }
        # NCRSF token does not appear to be needed.
        self.session = requests.Session()
        r = self.session.post("{0}/account/login".format(self.url),
                   {"username": self.username,
                    "password": self.password },
                   allow_redirects=False, headers=headers)
        if r.status_code != 303:
            raise ConnectionError("login failed with {0}".format(r.status_code))
        logger.debug("Got cookies: {0}".format(self.session.cookies))
        logger.debug("Got headers: {0}".format(r.headers))
        headers = {}
        r = self.session.get("{0}/signalr/negotiate".format(self.url),
                  params={'version': self.version, '_': int(time.time())},
                  headers=headers)
        if r.status_code != 200:
            raise ConnectionError(
                "negotiate failed with {0}".format(r.status_code))

        data = r.json()
        logger.info("got data from negotiation: {0}".format(data))
        self.connection_token = data['ConnectionToken']

        headers = {'accept': 'text/event-stream'}
        self.params = OrderedDict((('transport', self.transport),
                                 ('connectionToken', self.connection_token),
                                 ('connectionData', '[{"name":"chat"}]'),
                                 ('version', self.version),
                                 # tid was sent by the javascript, does not
                                 # appear to be needed.
                                 ))
        r = self.session.get("{0}/signalr/connect".format(self.url),
                  # Required even if changing content-type to
                  # application/json. The server starts sending stuff in
                  # streaming mode, and we need to account for that.
                  stream=True,
                  params=self.params,
                  headers=headers)
        logger.debug("URL: {0}".format(r.url))
        if r.status_code != 200:
            raise ConnectionError(
                "connect failed with {0}".format(r.status_code))

    def get_id(self):
        new_id = self.id
        self.id += 1
        return new_id

    def send(self, msg, room=None):
        """
        Send a message to existing connection.  It is unknown how long the
        connection persists, and how sending behaves after that.

        Messages can only be sent to rooms the account has subscribed to,
        and this script does not do that, at least not yet.
        """
        if not room:
            room = self.room
        if not room:
            raise RuntimeError("Room must be specified")

        def guid():
            return str(uuid.uuid4())

        r = self.session.post("{0}/signalr/send".format(self.url),
                   urllib.urlencode(
                       {"data": json.dumps({"H": "chat",
                                            "M": "Send",
                                            "A": [{"id": guid(),
                                                   "content": msg,
                                                   "room": room }],
                                                   "I": self.get_id(),
                                            "S": {"activeRoom": room,
                                                  "id": guid(),
                                                  "name": self.username,
                                                  "unreadNotifications": 0 }
                                                  })}),
                   params=self.params)
        if r.status_code != 200:
            raise ConnectionError("send failed with {0}".format(r.status_code))


if __name__ == "__main__":
    c = Client()
    logging.basicConfig(level=logging.DEBUG)
