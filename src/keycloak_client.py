from keycloak import KeycloakOpenID


def get_keycloak_token(server_url: str, user: str, password: str, client_secret: str):
    """
    Retrieve JWT from Keycloak.
    :param server_url: Server URL
    :param user: The users used to retrieve token
    :param password: The password belonging to the user
    :param client_secret: The secret used to authorize for the client
    :return: The retrieved JWT
    """
    KEYCLOAK_OPENID = KeycloakOpenID(server_url=server_url,
                                     client_id="federated-catalogue",
                                     realm_name="gaia-x",
                                     client_secret_key=client_secret)
    token = KEYCLOAK_OPENID.token(user, password)
    return token