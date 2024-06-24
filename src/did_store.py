from __future__ import annotations  # used for linting (type annotations)
from collections.abc import Iterator
import uuid
import os
import glob
import json


class DIDStore:
    """
    Class can be used to create a local did store and create did documents and did:web IDs.
    """

    def __init__(self, storage_type: str, storage_path: str) -> None:
        self._storage_path = storage_path
        if storage_type in ("local", "cloud"):
            self._storage_type = storage_type
        else:
            raise ValueError(f"Storage Type ({storage_type}) for DIDStore is not supported.")

    def get_type(self) -> str:
        return self._storage_type

    def get_path(self) -> str:
        return self._storage_path

    def get_saved_object(self, id: str) -> str:
        matches = glob.glob(self.get_path() + '/' + "*" + id + "*")
        if matches:
            return open_file_and_get_file_content(matches[0])
        raise ValueError("UUID has not been found")

    def get_saved_uuids(self) -> Iterator[str]:
        for entry in os.scandir(self._storage_path):
            yield entry.name[:-5]

    def create_did_store_object(self, object_content: dict[str, str]) -> DIDStoreObject:
        object_uuid = uuid.uuid4().hex
        object_id = "did:web:sd-creator.gxfs.gx4fm.org:id-documents:" + object_uuid
        storage_path = self.determine_storage_path(object_uuid)
        did_store_object = DIDStoreObject(
            self, object_uuid, object_id, object_content, storage_path)
        return did_store_object

    def save_object_into_storage(self, did_store_object_to_save: DIDStoreObject) -> None:
        try:
            if self._storage_type == "local":
                with open(did_store_object_to_save.get_storage_path(), "w") as did_file:
                    json.dump(did_store_object_to_save.get_object_content(), did_file)
            else:
                raise ValueError(
                    f"Storage type {self._storage_type} is not implemented yet")
        except Exception as e:
            did_store_object_to_save.set_storage_path(None)
            print("Could not save DIDStoreObject: " + str(e.args))

    def determine_storage_path(self, uuid: str) -> str:
        return os.path.join(self._storage_path, uuid + ".json")


class DIDStoreObject:
    """
    Class can be used to create a new object, which must be saved in the regarding DIDStore.
    """

    def __init__(self, related_did_store: DIDStore, object_uuid: str, object_id: str, object_content: dict[str, str], stored_path: str) -> None:
        self._id = object_id
        self._uuid = object_uuid
        self._stored_path = stored_path
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

    def set_object_content(self, new_content: dict[str, str]) -> None:
        self._object_content = new_content

    def get_storage_path(self) -> str:
        if self._stored_path is None:
            raise ValueError("No filepath for DIDStoreObject specified")
        return self._stored_path


def open_file_and_get_file_content(filepath: str) -> str:
    f = open(filepath, "r")
    document_content = f.read()
    f.close()
    return document_content
