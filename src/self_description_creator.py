from __future__ import annotations  # used for linting (type annotations)

import logging
import os
import time
import yaml
from logging.config import dictConfig
from threading import Thread

from flask import Flask, redirect, Request, request
from flasgger import Swagger, swag_from
from flask_restful import Api, Resource
from jwcrypto import jwk
from jwcrypto.jwk import JWK

from src.claim_file_handler import ClaimFileHandler
from src.federated_catalogue_client import FederatedCatalogueClient
from src.self_description_processor import SelfDescriptionProcessor
from src.did_store import DIDStore

# -- Environment variables --
KEYCLOAK_SERVER_URL = os.environ.get("KEYCLOAK_SERVER_URL", default="")
FEDERATED_CATALOGUE_USER_NAME = os.environ.get(
    "FEDERATED_CATALOGUE_USER_NAME", default="")
FEDERATED_CATALOGUE_USER_PASSWORD = os.environ.get(
    "FEDERATED_CATALOGUE_USER_PASSWORD", default="")
USE_LEGACY_CATALOGUE_SIGNATURE = os.environ.get(
    "USE_LEGACY_CATALOGUE_SIGNATURE", default="").lower() in ("true", "1")
KEYCLOAK_CLIENT_SECRET = os.environ.get("KEYCLOAK_CLIENT_SECRET", default="")
FEDERATED_CATALOGUE_URL = os.environ.get("FEDERATED_CATALOGUE_URL", default="")
CREDENTIAL_ISSUER = os.environ.get("CREDENTIAL_ISSUER", default="")
CREDENTIAL_ISSUER_PRIVATE_KEY_PEM_PATH = os.environ.get(
    "CREDENTIAL_ISSUER_PRIVATE_KEY_PEM_PATH", default="")
CLAIM_FILES_DIR = os.environ.get(
    "CLAIM_FILES_DIR", default=os.path.join("..", "data"))
CLAIM_FILES_POLL_INTERVAL_SEC = float(os.environ.get(
    "CLAIM_FILES_POLL_INTERVAL_SEC", default=2.0))
CLAIM_FILES_CLEANUP_MAX_FILE_AGE_DAYS = os.environ.get(
    "CLAIM_FILES_CLEANUP_MAX_FILE_AGE_DAYS", default=1)
DID_STORAGE_TYPE = os.environ.get("DID_STORAGE_TYPE", default="None")
DID_STORAGE_PATH = os.environ.get("DID_STORAGE_PATH", default="")

# -- Global variables --
OPERATING_MODE = os.environ.get(
    "OPERATING_MODE", default="API")  # Can be either API | HYBRID

# Variable will be initialized in method init_app() on application startup
signature_jwk: JWK | None = None


def read_signature_private_key() -> JWK:
    """
    Read a private key from PEM file that is used to create a JWK which is utilized to sign VCs and VPs.
    :return: The initialized JWK
    """
    with open(CREDENTIAL_ISSUER_PRIVATE_KEY_PEM_PATH, "rb") as key_file:
        pem_data = key_file.read()

    # Create a JWK from private key
    return jwk.JWK.from_pem(pem_data)


def init_app():
    """
    Initialize the core application.
    """

    class HealthCheckFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return record.getMessage().find("/health") == -1

    dictConfig({
        'version': 1,
        'formatters': {'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }},
        'handlers': {'wsgi': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://flask.logging.wsgi_errors_stream',
            'formatter': 'default'
        }},
        'root': {
            'level': 'INFO',
            'handlers': ['wsgi']
        }
    })

    logging.getLogger("werkzeug").addFilter(HealthCheckFilter())
    app = Flask(__name__)
    
    # openapi_spec=""
    # with open(os.path.join("openapi-spec.yaml"), 'r') as file:
    #     openapi_spec = yaml.safe_load(file)
    Swagger(app, template_file='../openapi-spec.yaml', parse=True, merge=True)
    app.logger.info("Initializing app")

    # Flask-internal logger has been disabled since it logs every request by default which pollutes the log output
    # (especially when receiving health requests in k8s environments) -> could potentially be optimized
    global signature_jwk, self_description_processor
    with app.app_context():
        # before_first_request equivalent here
        app.logger.info("Read signing key")
        signature_jwk = read_signature_private_key()
        if signature_jwk is None:
            app.logger.error(
                "An error occurred while initializing JWK for signatures")
            exit(-1)

        app.logger.info("Signing key has been successfully configured")
        app.logger.info("Initialization has been finished")
        return app

app = init_app()

did_store = DIDStore(storage_path=DID_STORAGE_PATH,
                     storage_type=DID_STORAGE_TYPE)
self_description_processor = SelfDescriptionProcessor(credential_issuer=CREDENTIAL_ISSUER,
                                                      signature_jwk=signature_jwk, # type: ignore needed for linting, type error would indicate that signature_jwk could ne None, but in init_app() we check, if signature_jwk is None.
                                                      use_legacy_catalogue_signature=USE_LEGACY_CATALOGUE_SIGNATURE,
                                                      did_store=did_store)


def background_task():
    """
    Main function to handle background work.
    """
    federated_catalogue_client = FederatedCatalogueClient(federated_catalogue_url=FEDERATED_CATALOGUE_URL,
                                                          keycloak_server_url=KEYCLOAK_SERVER_URL,
                                                          federated_catalogue_user_name=FEDERATED_CATALOGUE_USER_NAME,
                                                          federated_catalogue_user_password=FEDERATED_CATALOGUE_USER_PASSWORD,
                                                          keycloak_client_secret=KEYCLOAK_CLIENT_SECRET)
    claim_file_handler = ClaimFileHandler(claim_files_dir=CLAIM_FILES_DIR,
                                          claim_files_cleanup_max_file_age_days=int(
                                              CLAIM_FILES_CLEANUP_MAX_FILE_AGE_DAYS),
                                          self_description_processor=self_description_processor,
                                          federated_catalogue_client=federated_catalogue_client)
    while True:
        claim_file_handler.process_claim_files()
        claim_file_handler.cleanup_old_files()
        time.sleep(CLAIM_FILES_POLL_INTERVAL_SEC)

def get_json_request_body(request: Request):
    body = request.get_json()
    if body is None:
        raise Exception("No proper request body found")
    else:
        return body
    
def check_if_id_is_present(dictionary_to_check):
    if "id" not in dictionary_to_check.keys():
            app.logger.warning("No ID has been specified")
            return False
    return True
    


@app.route("/health")
def health():
    data = {"status": "success"}
    return data, 200



# This endpoint is deprecated, use /vp-from-claims instead
@app.route("/self-description", methods=["POST"])
def post_self_description():
    return redirect(location="/vp-from-claims", code=308)


@app.route("/vp-from-claims", methods=["POST"])
def create_vp_from_claims():
    try:
        claims: dict = get_json_request_body(request)
        check_if_id_is_present(claims)
        verifiable_presentation = self_description_processor.create_self_description(
            claims=claims)  # type: ignore
        return verifiable_presentation, 200
    except Exception as e:
        error_msg = "An error occurred while processing the request [error: {error_details}]".format(
            error_details=e.args)
        app.logger.warning(error_msg)
        data = {"status": "failed", "error": error_msg}
        return data, 500


# This endpoint is deprecated, use /federated-catalogue/upload-from-claims instead
@app.route("/federated-catalogue/self-descriptions", methods=["POST"])
def post_self_description_to_federated_catalogue():
    return redirect(location="/federated-catalogue/upload-from-claims", code=308)

@app.route("/federated-catalogue/upload-from-claims", methods=["POST"])
def post_claims_to_federated_catalogue():
    try:
        federated_catalogue_client = FederatedCatalogueClient(federated_catalogue_url=FEDERATED_CATALOGUE_URL,
                                                              keycloak_server_url=KEYCLOAK_SERVER_URL,
                                                              federated_catalogue_user_name=FEDERATED_CATALOGUE_USER_NAME,
                                                              federated_catalogue_user_password=FEDERATED_CATALOGUE_USER_PASSWORD,
                                                              keycloak_client_secret=KEYCLOAK_CLIENT_SECRET)
        claims: dict = get_json_request_body(request)
        check_if_id_is_present(claims)
        self_description = self_description_processor.create_self_description(
            claims=claims)  # type: ignore
        federated_catalogue_client.send_to_federated_catalogue(
            self_description)
        data = {"status": "success"}
        return data, 201
    except Exception as e:
        error_msg = "An error occurred while processing the request [error: {body}]".format(
            body=e.args)
        app.logger.warning(error_msg)
        data = {"status": "failed", "error": error_msg}
        return data, 500

    
@app.route("/vp-from-vp-without-proof", methods=["POST"])
def create_vp_from_vp_without_proof():
    try:
        vp_without_proof: dict = get_json_request_body(request)
        check_if_id_is_present(vp_without_proof)
        self_description = self_description_processor.add_proof(
            credential=vp_without_proof)  # type: ignore
        return self_description, 200
    except Exception as e:
        error_msg = "An error occurred while processing the request [error: {error_details}]".format(
            error_details=e.args)
        app.logger.warning(error_msg)
        data = {"status": "failed", "error": error_msg}
        return data, 500


@app.route("/vc-from-claims", methods=["POST"])
def create_vc_from_claims():
    try:
        claims: dict = get_json_request_body(request)
        check_if_id_is_present(claims)
        self_description = self_description_processor.create_verifiable_credential(
            claims=claims)  # type: ignore
        return self_description, 200
    except Exception as e:
        error_msg = "An error occurred while processing the request [error: {error_details}]".format(
            error_details=e.args)
        app.logger.warning(error_msg)
        data = {"status": "failed", "error": error_msg}
        return data, 500


@app.route("/vp-from-vcs", methods=["POST"])
def create_vp_from_vcs():
    try:
        vcs: list[dict] = get_json_request_body(request)
        for vc in vcs:
            check_if_id_is_present(vc)
        self_description = self_description_processor.create_verifiable_presentation(
            verifiable_credentials=vcs)  # type: ignore
        return self_description, 200
    except Exception as e:
        error_msg = "An error occurred while processing the request [error: {error_details}]".format(
            error_details=e.args)
        app.logger.warning(error_msg)
        data = {"status": "failed", "error": error_msg}
        return data, 500


@app.route("/id-documents", methods=["GET"])
# -> tuple[str, Literal[200]] | tuple[dict[str, str], Literal[...:
def get_id_documents():
    try:
        request_uuid = request.args.get("uuid")
        if request_uuid is not None:
            did_document = did_store.get_saved_object(request_uuid)
            return did_document, 200
        data = []
        cnt = 0
        for uuid in did_store.get_saved_uuids():
            if cnt < 500:
                data.append(uuid)
                cnt += 1
        return data, 200
    except Exception as e:
        error_msg = "An error occurred while processing the request [error: {error_details}]".format(
            error_details=e.args)
        app.logger.warning(error_msg)
        data = {"status": "failed", "error": error_msg}
        return data, 500


    



if __name__ == "__main__":
    # The file-based SD creation runs in the background to be able to serve the API and create SDs from files
    # independently
    if OPERATING_MODE == "HYBRID":
        app.logger.info("Starting app in operating mode = 'HYBRID'")
        background_thread = Thread(target=background_task)
        background_thread.start()
        app.run(debug=False, host="0.0.0.0", port=8080)
        background_thread.join()
    elif OPERATING_MODE == "API":
        app.logger.info("Starting app in operating mode = 'API'")
        app.run(debug=False, host="0.0.0.0", port=8080)
