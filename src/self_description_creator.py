import json
import os
import shutil
from logging.config import dictConfig
import time
from datetime import datetime, timedelta
from hashlib import sha256
from threading import Thread

import requests
from flask import Flask, request
from jwcrypto import jwk, jws
from jwcrypto.common import base64url_encode
from pyld import jsonld

import keycloak_client

# -- Environment variables --
KEYCLOAK_SERVER_URL = os.environ.get("KEYCLOAK_SERVER_URL", default="")
FEDERATED_CATALOGUE_USER_NAME = os.environ.get("FEDERATED_CATALOGUE_USER_NAME", default="")
FEDERATED_CATALOGUE_USER_PASSWORD = os.environ.get("FEDERATED_CATALOGUE_USER_PASSWORD", default="")
KEYCLOAK_CLIENT_SECRET = os.environ.get("KEYCLOAK_CLIENT_SECRET", default="")
FEDERATED_CATALOGUE_URL = os.environ.get("FEDERATED_CATALOGUE_URL", default="")
CREDENTIAL_ISSUER = os.environ.get("CREDENTIAL_ISSUER")
CREDENTIAL_ISSUER_PRIVATE_KEY_PEM_PATH = os.environ.get("CREDENTIAL_ISSUER_PRIVATE_KEY_PEM_PATH")
CLAIM_FILES_DIR = os.environ.get("CLAIM_FILES_DIR", default=os.path.join(os.path.dirname(__file__), "..", "data"))
CLAIM_FILES_POLL_INTERVAL_SEC = os.environ.get("CLAIM_FILES_POLL_INTERVAL_SEC", default=2.0)
CLAIM_FILES_CLEANUP_MAX_FILE_AGE_DAYS = os.environ.get("CLAIM_FILES_CLEANUP_MAX_FILE_AGE_DAYS", default=1)

# -- Global variables --
PROCESSED_FILES_DIR = os.path.join(CLAIM_FILES_DIR, "processed")
FAILED_FILES_DIR = os.path.join(CLAIM_FILES_DIR, "failed")
SIGNATURE_JWK = None  # Will be read during initialization
OPERATING_MODE = os.environ.get("OPERATING_MODE", default="API")  # Can be either API | HYBRID


def read_signature_private_key():
    """
    Create a JWK that can be used to sign VCs and VPs.
    """
    # We're using an example private key from the Gaia-X Wizard which is a RSA2048 key
    with open(CREDENTIAL_ISSUER_PRIVATE_KEY_PEM_PATH, "rb") as key_file:
        pem_data = key_file.read()

    global SIGNATURE_JWK
    # Create a JWK from private key
    SIGNATURE_JWK = jwk.JWK.from_pem(pem_data)


def init_app():
    """
    Initialize the core application.
    """
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

    app = Flask(__name__)

    # Flask-internal logger has been disabled since it logs every request by default which pollutes the log output
    # (especially when receiving health requests in k8s environments) -> could potentially be optimized
    global SIGNATURE_JWK
    with app.app_context():
        # before_first_request equivalent here
        app.logger.info("Before First Request")
        read_signature_private_key()
        if SIGNATURE_JWK is None:
            exit(-1)
        app.logger.info("Signing key is successfully configured")
        return app


app = init_app()


def add_proof(credential: dict) -> dict:
    """
    Add a Proof to given Credential.
    :param credential: The credential where a Proof will be added to
    :return: The Credential including a Proof
    """
    credential = add_proof_jws_2020(credential)
    return credential


def add_proof_jws_2020(credential: dict) -> dict:
    """
    Sign a Credential with `JSON Web Signature 2020`. Relevant information can be found in the related Specification
    (see https://www.w3.org/TR/vc-jws-2020/#proof-representation).
    :param credential: The credential where a Proof will be added to
    :return: The Credential including a Proof
    """
    signing_algorithm = "PS256"
    proof = {
        "type": "JsonWebSignature2020",
        "created": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "verificationMethod": CREDENTIAL_ISSUER,
        "proofPurpose": "assertionMethod",
    }
    # Important info: The @context provided in the proof object is required to successfully perform the normalization
    # with the used pyld library. This is what the corresponding Java implementation does as well, but
    # with API version 'v3', instead of 'v3-unstable'. But the 'v3' just returns a HTTP 404. Not sure at the moment, why
    # it works with the Java implementation. The actual proof fields don't need this context.
    proof_for_normalization = proof.copy()
    proof_for_normalization["@context"] = "https://w3id.org/security/v3-unstable"
    # The content to be signed must be converted into a canonical JSON representation to ensure that the verification
    # of the signature on different systems leads to the same results
    normalization_options = {
        "algorithm": "URDNA2015",
        "format": "application/n-quads"}
    canonical_proof = jsonld.normalize(proof_for_normalization, options=normalization_options)
    canonical_credential = jsonld.normalize(credential, options=normalization_options)
    hashed_proof = sha256(canonical_proof.encode('utf-8')).digest()
    hashed_credential = sha256(canonical_credential.encode('utf-8')).digest()
    hashed_signature_payload = hashed_proof + hashed_credential

    # In the following the actual signing process takes place
    # Important info: The following headers must have this exact format (which is defined in the related Specification)
    jws_protected_header = '{"b64":false,"crit":["b64"],"alg":"%s"}' % signing_algorithm
    jws_token = jws.JWS(hashed_signature_payload)
    #  Important info: Internally, the signer uses the following input for the signing process:
    #  signing_input = encoded_jws_protected_header + b'.' + hashed_signature_payload
    jws_token.add_signature(SIGNATURE_JWK, protected=jws_protected_header, alg=signing_algorithm)

    # According to W3C Json Web Signature for Data Integrity Proof
    # (https://www.w3.org/TR/vc-jws-2020/#proof-representation) for proof type 'JSonWebSignature2020' the jws property
    # MUST contain a detached JWS which omits the actual payload
    b64_encoded_header = base64url_encode(jws_token.objects["protected"])
    b64_encoded_signature = base64url_encode(jws_token.objects["signature"])
    detached_jws_string = b64_encoded_header + '..' + b64_encoded_signature
    proof["jws"] = detached_jws_string
    credential["proof"] = proof
    return credential


def create_verifiable_credential(claims: dict) -> dict:
    """
    Create a W3C Verifiable Credential (VC). Relevant information can be found in the related Specification
    (see https://www.w3.org/TR/vc-data-model/).
    :param claims: Set of Claims made about certain subject
    :return: A W3C Verifiable Credential
    """
    issuance_date = datetime.utcnow().replace(microsecond=0)
    expiration_date = issuance_date + timedelta(weeks=24)
    credential = {
        "@context": [
            "https://www.w3.org/2018/credentials/v1",
            "https://www.w3.org/2018/credentials/examples/v1"],
        "type": ["VerifiableCredential"],
        "issuer": CREDENTIAL_ISSUER,
        "issuanceDate": issuance_date.isoformat() + "Z",
        "expirationDate": expiration_date.isoformat() + "Z",
        "credentialSubject": claims}
    credential["credentialSubject"].update(claims)
    vc = add_proof(credential)
    return vc


def create_verifiable_presentation(verifiable_credentials: list) -> dict:
    """
    Create a W3C Verifiable Presentation (VP). Relevant information can be found in the related Specification
    (see https://www.w3.org/TR/vc-data-model/).
    :param verifiable_credentials: Verifiable Credentials that are supposed to be embedded into the VP.
    :return: A W3C Verifiable Presentation
    """
    holder = CREDENTIAL_ISSUER
    presentation = {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "id": "http://example.org/presentations/3731",
        "type": ["VerifiablePresentation"],
        "holder": holder,
        "verifiableCredential": verifiable_credentials
    }
    vp = add_proof(presentation)
    return vp


def create_self_description(claims: dict) -> dict:
    """
    Create a Gaia-X Self Description for given Claims which basically corresponds to a W3C Verifiable Presentation.
    :param claims: JSON-LD based Claims.
    :return:
    """
    verifiable_credential = create_verifiable_credential(claims)
    verifiable_presentation = create_verifiable_presentation([verifiable_credential])
    return verifiable_presentation


def send_to_federated_catalogue(self_description: dict):
    """
    Send Self Description to GXFS Federated Catalogue.
    :param self_description: Self Description to be send
    """
    headers = {"Content-Type": "application/json"}
    add_federated_catalogue_auth_header(headers)
    request_body = json.dumps(self_description)
    # Request body is passed via parameter `data` instead of `json` to avoid issues because
    # of the encoding of the request body
    response = requests.post(FEDERATED_CATALOGUE_URL + "/self-descriptions", headers=headers, data=request_body)
    if response.ok:
        app.logger.debug("SD successfully sent to Federated Catalogue")
    else:
        raise Exception("An error occurred while sending Self Description to Federated Catalogue")


def move_file(file: os.DirEntry, dest_dir: str):
    """
    Move a file to another directory.
    :param file: The file to be moved
    :param dest_dir: Directory, where the file is supposed to be moved to
    """
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
    # We need to use shutil instead of os.rename since the latter only works for moving files on the same disk
    shutil.move(file.path, dest_dir)


def process_claim_files():
    """
    Read Claim files from file system and create Self Descriptions for them. File content must contain
    JSON-LD based Claims.
    """
    for file in os.scandir(CLAIM_FILES_DIR):
        if file.name.endswith("json"):
            try:
                app.logger.info("Start processing file [file: {file}]".format(file=file.path))
                with open(file.path, "r") as file_content:
                    claims = json.load(file_content)
                self_description = create_self_description(claims=claims)
                send_to_federated_catalogue(self_description)
                move_file(file, PROCESSED_FILES_DIR)
                app.logger.info("File has been processed successfully [file: {file}]".format(file=file.path))
            except Exception as e:
                app.logger.warning("An error occurred while processing file [file: {file}, error: {error}]"
                                   .format(file=file.path, error=e.args))
                move_file(file, FAILED_FILES_DIR)


def add_federated_catalogue_auth_header(header: dict):
    """
    Add auth header for authorization against GXFS Federated Catalogue.
    :param header: Set of HTTP headers the auth header is supposed to be added to
    """
    if not KEYCLOAK_SERVER_URL or \
            not FEDERATED_CATALOGUE_USER_NAME or \
            not FEDERATED_CATALOGUE_USER_PASSWORD or \
            not KEYCLOAK_CLIENT_SECRET:
        app.logger.warning("Request to Federated Catalogue cannot be performed due to missing "
                           "environment variables")
    token = keycloak_client.get_keycloak_token(server_url=KEYCLOAK_SERVER_URL, user=FEDERATED_CATALOGUE_USER_NAME,
                                               password=FEDERATED_CATALOGUE_USER_PASSWORD,
                                               client_secret=KEYCLOAK_CLIENT_SECRET)
    header.update({"Authorization": "Bearer {}".format(token["access_token"])})


def cleanup_old_files():
    """
    Cleanup old Claim files.
    """
    max_file_age_sec = int(CLAIM_FILES_CLEANUP_MAX_FILE_AGE_DAYS) * 3600 * 24
    now = time.time()
    if os.path.exists(PROCESSED_FILES_DIR):
        for file in os.scandir(PROCESSED_FILES_DIR):
            # Check if file is older than specified age
            if os.stat(file.path).st_mtime < now - max_file_age_sec:
                os.remove(file.path)

    if os.path.exists(FAILED_FILES_DIR):
        for file in os.scandir(FAILED_FILES_DIR):
            # Check if file is older than specified age
            if os.stat(file.path).st_mtime < now - max_file_age_sec:
                os.remove(file.path)


def background_task():
    """
    Main function to handle background work.
    """
    while True:
        process_claim_files()
        cleanup_old_files()
        time.sleep(CLAIM_FILES_POLL_INTERVAL_SEC)


@app.route("/health")
def health():
    data = {"status": "success"}
    return data, 200


@app.route("/self-description", methods=["POST"])
def post_self_description():
    if request.method == "POST":
        try:
            claims = request.get_json()
            self_description = create_self_description(claims=claims)
            return self_description, 200
        except Exception as e:
            error_msg = "An error occurred while processing the request [error: {error_details}]".format(
                error_details=e.args)
            app.logger.warning(error_msg)
            data = {"status": "failed", "error": error_msg}
            return data, 500


@app.route("/federated-catalogue/self-descriptions", methods=["POST"])
def post_self_description_to_federated_catalogue():
    if request.method == "POST":
        try:
            claims = request.get_json()
            self_description = create_self_description(claims=claims)
            send_to_federated_catalogue(self_description)
            data = {"status": "success"}
            return data, 201
        except Exception as e:
            error_msg = "An error occurred while processing the request [error: {body}]".format(body=e.args)
            app.logger.warning(error_msg)
            data = {"status": "failed", "error": error_msg}
            return data, 500


if __name__ == "__main__":
    # The file-based SD creation runs in the background to be able to serve the API and create SDs from files
    # independently
    if OPERATING_MODE == "HYBRID":
        background_thread = Thread(target=background_task)
        background_thread.start()
        app.run(debug=False, host="0.0.0.0", port=8080)
        background_thread.join()
    elif OPERATING_MODE == "API":
        app.run(debug=False, host="0.0.0.0", port=8080)
