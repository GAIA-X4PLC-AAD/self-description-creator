from datetime import datetime, timedelta
from hashlib import sha256

from jwcrypto import jws
from jwcrypto.common import base64url_encode
from jwcrypto.jwk import JWK
from pyld import jsonld

from did_store import DIDStore


class SelfDescriptionProcessor:
    """
    Class can be used to create Self Descriptions from Claims provided as input.
    """

    def __init__(self, credential_issuer: str, signature_jwk: JWK, use_legacy_catalogue_signature: bool, did_store: DIDStore) -> None:
        """
        :param credential_issuer:
        :param signature_jwk:
        """
        self.__credential_issuer = credential_issuer
        self.__signature_jwk = signature_jwk
        self.__use_legacy_catalogue_signature = use_legacy_catalogue_signature
        self.__did_storage_type = did_store.get_type()
        if self.__did_storage_type != "None":
            self.__did_store = did_store

    def create_self_description(self, claims: dict) -> dict:
        """
        Create a Gaia-X Self Description for given Claims which basically corresponds to a W3C Verifiable Presentation.
        :param claims: JSON-LD based Claims.
        :return:
        """
        verifiable_credential = self.create_verifiable_credential(claims)
        verifiable_presentation = self.create_verifiable_presentation(
            [verifiable_credential])
        return verifiable_presentation

    def create_verifiable_credential(self, claims: dict) -> dict:
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
            "issuer": self.__credential_issuer,
            "issuanceDate": issuance_date.isoformat() + "Z",
            "expirationDate": expiration_date.isoformat() + "Z",
            "credentialSubject": claims}
        if self.__did_storage_type != "None":
            did_store_object = self.__did_store.create_did_store_object(
                credential)
            credential = did_store_object.get_object_content()
        vc = self.add_proof(credential)
        return vc

    def create_verifiable_presentation(self, verifiable_credentials: list, create_proof: bool=True) -> dict:
        """
        Create a W3C Verifiable Presentation (VP). Relevant information can be found in the related Specification
        (see https://www.w3.org/TR/vc-data-model/).
        :param verifiable_credentials: Verifiable Credentials that are supposed to be embedded into the VP.
        :return: A W3C Verifiable Presentation
        """
        holder = self.__credential_issuer
        presentation = {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiablePresentation"],
            "holder": holder,
            "verifiableCredential": verifiable_credentials
        }
        if self.__did_storage_type != "None":
            did_store_object = self.__did_store.create_did_store_object(
                presentation)
            presentation = did_store_object.get_object_content()
        if create_proof:
            vp = self.add_proof(presentation)
            return vp
        return presentation

    def add_proof(self, credential: dict) -> dict:
        """
        Add a Proof to given Credential.
        :param credential: The credential where a Proof will be added to
        :return: The Credential including a Proof
        """
        credential = self._add_proof_jws_2020(credential)
        return credential

    def _add_proof_jws_2020(self, credential: dict) -> dict:
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
            "verificationMethod": self.__credential_issuer+"#JWK2020-RSA",
            "proofPurpose": "assertionMethod",
        }
        # Important info (legacy catalogue): The @context provided in the proof object is required to successfully perform the
        # normalization with the used pyld library. This is what the corresponding Java implementation does as well,
        # but with API version 'v3', instead of 'v3-unstable'. But the 'v3' just returns a HTTP 404. Not sure at the
        # moment, why it works with the Java implementation. The actual proof fields don't need this context.
        proof_for_normalization = proof.copy()
        proof_for_normalization["@context"] = "https://w3id.org/security/v3-unstable"
        # The content to be signed must be converted into a canonical JSON representation to ensure that the
        # verification of the signature on different systems leads to the same results
        normalization_options = {
            "algorithm": "URDNA2015",
            "format": "application/n-quads"}
        canonical_proof = jsonld.normalize(
            proof_for_normalization, options=normalization_options)
        canonical_credential = jsonld.normalize(
            credential, options=normalization_options)
        hashed_proof = sha256(canonical_proof.encode('utf-8')).hexdigest()
        hashed_credential = sha256(
            canonical_credential.encode('utf-8')).hexdigest()

        hashed_signature_payload = hashed_credential
        if self.__use_legacy_catalogue_signature:
            hashed_signature_payload = bytes.fromhex(
                hashed_proof + hashed_credential)

        # In the following the actual signing process takes place Important info: The following headers must have
        # this exact format (which is defined in the related Specification)
        jws_protected_header = '{"b64":false,"crit":["b64"],"alg":"%s"}' % signing_algorithm
        jws_token = jws.JWS(hashed_signature_payload)
        #  Important info: Internally, the signer uses the following input for the signing process:
        #  signing_input = encoded_jws_protected_header + b'.' + hashed_signature_payload
        jws_token.add_signature(
            self.__signature_jwk, protected=jws_protected_header, alg=signing_algorithm)

        # According to W3C Json Web Signature for Data Integrity Proof (
        # https://www.w3.org/TR/vc-jws-2020/#proof-representation) for proof type 'JsonWebSignature2020' the jws
        # property MUST contain a detached JWS which omits the actual payload
        b64_encoded_header = base64url_encode(jws_token.objects["protected"])
        b64_encoded_signature = base64url_encode(
            jws_token.objects["signature"])
        detached_jws_string = b64_encoded_header + '..' + b64_encoded_signature
        proof["jws"] = detached_jws_string
        credential["proof"] = proof
        return credential
