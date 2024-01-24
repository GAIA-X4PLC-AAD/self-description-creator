import uuid
import os
from did_store import DIDStoreObject

class DIDStore:
    """
    Class can be used to create a local did store and create did documents and did:web IDs.
    """

    def __init__(self, storage_type: str="None", storage_path: str="None"):
        self._storage_path = storage_path
        self._storage_type = storage_type
        self._saved_objects = []

    def get_type(self) -> str:
        return self._storage_type
    
    def create_did_store_object(self, object_content: str, object_uuid=uuid.uuid4.hex()) -> DIDStoreObject:
        did_store_object = DIDStoreObject(self, object_content, object_uuid)
        return did_store_object

    def save_object_into_storage(self, did_store_object_to_save: DIDStoreObject) -> None:
        self._saved_objects.append(did_store_object_to_save)
        if self._storage_type == "local":
            did_store_object_to_save.set_storage_path(os.path.join(self._storage_path, did_store_object_to_save.get_uuid() + "_did.json"))
            with open(did_store_object_to_save.get_storage_path(), "w") as did_file:
                did_file.write(str(object))
        elif self._storage_type == "cloud":
            print("function not implemented yet")
        else:
            print("no valid storage location configured")


class DIDStoreObject:

    def __init__(self, related_did_store: DIDStore, object_content: str, object_uuid: str) -> None:
        self._uuid = object_uuid
        self._stored_path = None
        self._did_store = related_did_store
        self._object_content = object_content

    def set_storage_path(self, new_path: str) -> None:
        self._stored_path = new_path

    def get_uuid(self) -> str:
        return self._uuid
    
    def get_storage_path(self) -> str:
        if self._stored_path == None:
            raise Exception("No")
        else:
            return self._stored_path