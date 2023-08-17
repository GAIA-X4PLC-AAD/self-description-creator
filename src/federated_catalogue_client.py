import json
import logging

import requests
from keycloak import KeycloakOpenID

logger = logging.getLogger()


class FederatedCatalogueClient:
    """
    Class can be used to interact with the XFSC Federated Catalogue.
    """

    def __init__(self, federated_catalogue_url: str, keycloak_server_url: str, federated_catalogue_user_name: str,
                 federated_catalogue_user_password: str, keycloak_client_secret: str):
        """

        :param federated_catalogue_url:
        :param keycloak_server_url:
        :param federated_catalogue_user_name:
        :param federated_catalogue_user_password:
        :param keycloak_client_secret:
        """
        if not federated_catalogue_url or \
                not keycloak_server_url or \
                not federated_catalogue_user_name or \
                not federated_catalogue_user_password or \
                not keycloak_client_secret:
            err_msg = "Request to Federated Catalogue cannot be performed due to missing environment variables"
            logger.warning(err_msg)
            raise Exception(err_msg)
        self.__federated_catalogue_url = federated_catalogue_url
        self.__keycloak_server_url = keycloak_server_url
        self.__federated_catalogue_user_name = federated_catalogue_user_name
        self.__federated_catalogue_user_password = federated_catalogue_user_password
        self.__keycloak_client_secret = keycloak_client_secret

    def send_to_federated_catalogue(self, self_description: dict):
        """
        Send Self Description to GXFS Federated Catalogue.
        :param self_description: Self Description to be send
        """
        headers = {"Content-Type": "application/json"}
        self._add_federated_catalogue_auth_header(headers)
        request_body = json.dumps(self_description)
        # Request body is passed via parameter `data` instead of `json` to avoid issues because
        # of the encoding of the request body
        response = requests.post(self.__federated_catalogue_url + "/self-descriptions", headers=headers,
                                 data=request_body)
        if response.ok:
            logger.debug("SD successfully sent to Federated Catalogue")
        else:
            error_msg = "An error occurred while sending Self Description to Federated Catalogue " \
                        "[status_code: {}, response_body: {}".format(response.status_code, response.text)
            raise Exception(error_msg)

    def _add_federated_catalogue_auth_header(self, header: dict):
        """
        Add auth header for authorization against GXFS Federated Catalogue.
        :param header: Set of HTTP headers the auth header is supposed to be added to
        """
        token = self._get_keycloak_token()
        header.update({"Authorization": "Bearer {}".format(token["access_token"])})

    def _get_keycloak_token(self):
        """
        Retrieve JWT from Keycloak.
        :return: The retrieved JWT
        """
        keycloak_openid = KeycloakOpenID(server_url=self.__keycloak_server_url,
                                         client_id="federated-catalogue",
                                         realm_name="gaia-x",
                                         client_secret_key=self.__keycloak_client_secret)
        token = keycloak_openid.token(self.__federated_catalogue_user_name, self.__federated_catalogue_user_password)
        return token
