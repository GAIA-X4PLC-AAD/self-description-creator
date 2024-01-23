import uuid
import os

class DIDStore:
    """
    Class can be used to create a local did store and create did documents and did:web IDs.
    """

    ### def __init__(self, credential_issuer: str, signature_jwk: JWK, use_legacy_catalogue_signature: bool):
    def __init__(self, storage_path: str):
        self._uuid = uuid.uuid4().hex
        self._storage_path = storage_path

    def get_uuid_for_object(self, object):
        with open(os.path.join(self._storage_path, self._uuid + "_did.json"), "w") as did_file:
            did_file.write(str(object))
        return self._uuid

  