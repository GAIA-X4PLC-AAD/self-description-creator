import json
import logging
import os
import shutil
import time

from src.federated_catalogue_client import FederatedCatalogueClient
from src.self_description_processor import SelfDescriptionProcessor

logger = logging.getLogger()


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


class ClaimFileHandler:
    """
    Class is used to create Self Descriptions from Claims provided as files and sends them to a Federated Catalogue
    instance.
    """

    def __init__(self,
                 claim_files_dir: str,
                 processed_files_dir: str,
                 failed_files_dir: str,
                 claim_files_cleanup_max_file_age_days: int,
                 self_description_creator: SelfDescriptionProcessor,
                 federated_catalogue_client: FederatedCatalogueClient):
        """

        :param claim_files_dir:
        :param processed_files_dir:
        :param failed_files_dir:
        :param claim_files_cleanup_max_file_age_days:
        :param self_description_creator:
        :param federated_catalogue_client:
        """
        self.__claim_files_dir = claim_files_dir
        self.__processed_files_dir = processed_files_dir
        self.__failed_files_dir = failed_files_dir
        self.__claim_files_cleanup_max_file_age_days = claim_files_cleanup_max_file_age_days
        self.__self_description_creator = self_description_creator
        self.__federated_catalogue_client = federated_catalogue_client

    def process_claim_files(self):
        """
        Read Claim files from file system and create Self Descriptions for them. File content must contain
        JSON-LD based Claims.
        """
        for file in os.scandir(self.__claim_files_dir):
            if file.name.endswith("json"):
                try:
                    logger.info("Start processing file [file: {file}]".format(file=file.path))
                    with open(file.path, "r") as file_content:
                        claims = json.load(file_content)
                    self_description = self.__self_description_creator.create_self_description(claims=claims)
                    self.__federated_catalogue_client.send_to_federated_catalogue(self_description)
                    move_file(file, self.__processed_files_dir)
                    logger.info("File has been processed successfully [file: {file}]".format(file=file.path))
                except Exception as e:
                    logger.warning("An error occurred while processing file [file: {file}, error: {error}]"
                                   .format(file=file.path, error=e.args))
                    move_file(file, self.__failed_files_dir)

    def cleanup_old_files(self):
        """
        Cleanup old Claim files.
        """
        max_file_age_sec = self.__claim_files_cleanup_max_file_age_days * 3600 * 24
        now = time.time()
        if os.path.exists(self.__processed_files_dir):
            for file in os.scandir(self.__processed_files_dir):
                # Check if file is older than specified age
                if os.stat(file.path).st_mtime < now - max_file_age_sec:
                    os.remove(file.path)

        if os.path.exists(self.__failed_files_dir):
            for file in os.scandir(self.__failed_files_dir):
                # Check if file is older than specified age
                if os.stat(file.path).st_mtime < now - max_file_age_sec:
                    os.remove(file.path)
