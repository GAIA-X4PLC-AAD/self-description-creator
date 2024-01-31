from __future__ import annotations # used for linting (type annotations)
import uuid
import os



class DIDStore:
    """
    Class can be used to create a local did store and create did documents and did:web IDs.
    """

    def __init__(self, storage_type: str, storage_path: str) -> None:
        self._storage_path = storage_path
        if storage_type == "local" or storage_type == "cloud":
            self._storage_type = storage_type  
        else: 
            raise Exception("Storage Type for DIDStore is not supported.")            
        self._saved_objects = []

    def get_type(self) -> str:
        return self._storage_type
    
    def get_path(self) -> str:
        return self._storage_path
    
    def get_saved_object(self, id: str) -> str:      
        for filename in os.listdir(self.get_path()):
            if id in filename:
                return open_file_and_get_file_content(os.path.join(self.get_path(), filename))
        raise Exception("UUID has not been found")

    def get_saved_objects(self) -> list[DIDStoreObject]:
        return self._saved_objects
    
    def create_did_store_object(self, object_content: dict[str, str]) -> DIDStoreObject:
        object_uuid = uuid.uuid4().hex
        object_id = "did:web:sd-creator.gxfs.gx4fm.org:id-documents:" + object_uuid
        did_store_object = DIDStoreObject(self, object_uuid, object_id, object_content)
        self.save_object_into_storage(did_store_object)
        return did_store_object

    def save_object_into_storage(self, did_store_object_to_save: DIDStoreObject) -> None:
        try:
            if self._storage_type == "local":
                did_store_object_to_save.set_storage_path(os.path.join(self._storage_path, did_store_object_to_save.get_uuid() + ".json"))
                with open(did_store_object_to_save.get_storage_path(), "w") as did_file:
                    did_file.write(str(did_store_object_to_save.get_object_content()))
            else:
                raise Exception("Storage type is not implemented yet")
        except Exception as e:
            did_store_object_to_save.set_storage_path(None)
            print("Could not save DIDStoreObject: " + str(e.args))
        else:
            self._saved_objects.append(did_store_object_to_save)

class DIDStoreObject:
    """
    Class can be used to create a new object, which can be saved in the regarding DIDStore.
    """

    def __init__(self, related_did_store: DIDStore, object_uuid: str, object_id: str, object_content: dict[str, str]) -> None:
        self._id = object_id
        self._uuid = object_uuid
        self._stored_path = None
        self._did_store = related_did_store
        object_content["id"] = self._id
        self._object_content = object_content

    def set_storage_path(self, new_path: str | None) -> None:
        self._stored_path = new_path

    def get_id(self) -> str:
        return self._id
    
    def get_uuid(self) -> str:
        return self._uuid
    
    def get_object_content(self) -> dict[str, str]:
        return self._object_content

    def get_storage_path(self) -> str:
        if self._stored_path == None:
            raise Exception("No filepath specified")
        else:
            return self._stored_path



# convenience function to simplify code
def open_file_and_get_file_content(filepath: str) -> str:
    f = open(filepath, "r")
    document_content = f.read()
    f.close()
    return document_content