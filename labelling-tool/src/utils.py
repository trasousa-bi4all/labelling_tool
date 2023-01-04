from email.mime import base
import os
import glob
from dotenv import load_dotenv
import redis
import pyodbc
import pandas as pd
from azure.identity import ManagedIdentityCredential
from azure.storage.blob import BlobServiceClient
import io

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_PWD = os.getenv("REDIS_PWD")
SQL_URL = os.getenv("SQL_URL")
BLOB_CON_STR = os.getenv("BLOB_CON_STR")




class redis_db:
    def __init__(self) -> None:
        if REDIS_HOST is None:
            raise ValueError("Expecting a valid Redis Host URL. Got None instead.")
        self.redis_conn = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PWD, decode_responses=True
        )
        pass

    def get_user_pwd_pairs(self, username: str):

        user_pwd_pairs = {}
        try:
            user = self.redis_conn.keys(username)[0]
        except:
            raise ValueError("Invalid Username")
        pwd = self.redis_conn.get(user)
        user_pwd_pairs[user] = pwd

        return user_pwd_pairs

    def get_pwd(self, username):
        try:
            user = self.redis_conn.keys(username)[0]
        except:
            raise ValueError("Invalid Username")
        pwd = self.redis_conn.get(user)
        return pwd


def get_image_list(directory, extensions=["png"]):
    if isinstance(extensions, str):
        extensions = [extensions]

    base_pattern = "{}/*.{}".format
    filelist = []
    for extension in extensions:
        filelist.extend(glob.glob(base_pattern(directory, extension)))

    return filelist


class sql_db:
    def __init__(self) -> None:
        self.sql_conn = pyodbc.connect(SQL_URL)

    def get_ortho(self):
        SQL_ORTHO_TABLE_NAME = "dbo.db_ortho"
        ortho_df = pd.read_sql_query(
            "SELECT * FROM {}".format(SQL_ORTHO_TABLE_NAME), self.sql_conn
        )
        ortho_df.sort_values(by="ortho_diagnostic_count", ascending=True, inplace=True)
        try:
            ortho = ortho_df.iloc[0]
            ortho_path = ortho["ortho_path"]
            ortho_id = ortho["ortho_id"]
        except:
            raise Exception("There are no registers in DB")
        if ortho["ortho_diagnostic_count"] >= 3:
            return None, None
        return ortho_id, ortho_path

    def get_n_orthos(self, n):
        SQL_ORTHO_TABLE_NAME = "dbo.db_ortho"
        ortho_df = pd.read_sql_query(
            "SELECT * FROM {}".format(SQL_ORTHO_TABLE_NAME), self.sql_conn
        )
        ortho_df.sort_values(by="ortho_diagnostic_count", ascending=True, inplace=True)
        ortho = ortho_df[ortho_df["ortho_diagnostic_count"] < 3].iloc[:n]
        ortho_path = ortho["ortho_path"]
        ortho_id = ortho["ortho_id"]
        if len(ortho) == 0:
            raise Exception("There are no registers in DB")
        return ortho_id.to_list(), ortho_path.to_list()

    def get_medic(self, medic_name: str):
        SQL_MEDIC_TABLE_NAME = "dbo.db_medic"
        medic_df = pd.read_sql_query(
            "SELECT * FROM {}".format(SQL_MEDIC_TABLE_NAME), self.sql_conn
        )
        medic = medic_df[medic_df["medic_name"] == medic_name]
        if len(medic) == 0:
            raise Exception(
                "The Medic name you are trying to access is not registered in the database"
            )
        return True

    def update_ortho_count(self, ortho_id: int):
        SQL_ORTHO_TABLE_NAME = "dbo.db_ortho"
        ortho_df = pd.read_sql_query(
            "SELECT * FROM {}".format(SQL_ORTHO_TABLE_NAME), self.sql_conn
        )
        if len(ortho_df[ortho_df["ortho_id"] == ortho_id]) == 0:
            raise Exception("Ortho ID is not valid")
        else:
            cursor = self.sql_conn.cursor()
            cursor.execute(
                "UPDATE dbo.db_ortho SET ortho_diagnostic_count = ortho_diagnostic_count + 1 WHERE ortho_id = ?",
                ortho_id,
            )
            self.sql_conn.commit()

    # def log_diagnostic(self, diagnostic):
    # read json and upload to DB


class blob_storage:
    def __init__(self) -> None:

        self.blob_service = BlobServiceClient.from_connection_string(BLOB_CON_STR)

    def get_image_from_container(self, container, image_path):

        blob = self.blob_service.get_blob_client(container=container, blob=image_path)
        return io.BytesIO(blob.download_blob().readall())
