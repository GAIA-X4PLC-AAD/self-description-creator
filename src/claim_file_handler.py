import json
import logging
import os
import shutil
import time

from federated_catalogue_client import FederatedCatalogueClient
from self_description_processor import SelfDescriptionProcessor

logger = logging.getLogger()


def move_file(src_file_path: str, dest_dir: str):
    """
    Move a file to another directory.
    :param src_file_path: The file to be moved
    :param dest_dir: Directory, where the file is supposed to be moved to
    """
    try:
        os.makedirs(name=dest_dir, exist_ok=True)
        # We need to use shutil instead of os.rename since the latter only works for moving files on the same disk
        shutil.move(src=src_file_path, dst=dest_dir)
    except Exception as e:
        logger.error(
            "An error occurred while moving file [file: {file_path}, error: {error}]".format(file_path=src_file_path,
                                                                                             error=e.args))


class ClaimFileHandler:
    """
    Class can be used to create Self Descriptions from Claims provided as files and sends them to a Federated Catalogue
    instance.
    """

    def __init__(self,
                 claim_files_dir: str,
                 claim_files_cleanup_max_file_age_days: int,
                 self_description_processor: SelfDescriptionProcessor,
                 federated_catalogue_client: FederatedCatalogueClient):
        """

        :param claim_files_dir: Folder where Claim files should be read from
        :param claim_files_cleanup_max_file_age_days: The maximum age of processed files in the folder
        `claim_files_dir` to decide whether they should be cleaned up
        :param self_description_processor: An instance of `SelfDescriptionProcessor` that will be
        used to create Self Descriptions from Claim files
        :param federated_catalogue_client: An instance of `FederatedCatalogueClient` that will be
        used to send Self Descriptions to an instance of the Federated Catalogue
        """
        self.__claim_files_dir = claim_files_dir
        self.__processed_files_dir = os.path.join(claim_files_dir, "processed")
        self.__failed_files_dir = os.path.join(claim_files_dir, "failed")
        self.__claim_files_cleanup_max_file_age_days = claim_files_cleanup_max_file_age_days
        self.__self_description_processor = self_description_processor
        self.__federated_catalogue_client = federated_catalogue_client

    def process_claim_files(self):
        """
        Read Claim files from file system and create Self Descriptions for them. File content must contain
        JSON-LD based Claims.
        """
        file_list = os.listdir(self.__claim_files_dir)
        for file_name in file_list:
            file_path = os.path.join(self.__claim_files_dir, file_name)
            if file_path.endswith("json"):
                try:
                    logger.info("Start processing file [file: {file_path}]".format(file_path=file_path))
                    with open(file_path, "r") as file_content:
                        claims = json.load(file_content)
                    self_description = self.__self_description_processor.create_self_description(claims=claims)
                    self.__federated_catalogue_client.send_to_federated_catalogue(self_description)
                    move_file(file_path, self.__processed_files_dir)
                    logger.info("File has been processed successfully [file: {file}]".format(file=file_path))
                except Exception as e:
                    logger.warning("An error occurred while processing file [file: {file}, error: {error}]"
                                   .format(file=file_path, error=e.args))
                    move_file(file_path, self.__failed_files_dir)

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
