import logging
import os
import struct
from urllib.parse import quote_plus

from azure.identity import InteractiveBrowserCredential
from dotenv import load_dotenv
from sqlalchemy import create_engine, event

load_dotenv()
logger = logging.getLogger(__name__)

logger.debug(f"Loaded environment for user: {os.getenv('USERNAME')}")

SERVER_C = os.getenv("SERVER_C")
DATABASE_C = os.getenv("DATABASE_C")
DRIVER = "ODBC+Driver+18+for+SQL+Server"

DATABASE_B = os.getenv("DATABASE_B")
SERVER_B = os.getenv("SERVER_B")
USERNAME_B = os.getenv("USERNAME_B")
PASSWORD_B = os.getenv("PASSWORD_B")

DATABASE_A = os.getenv("DATABASE_A")
SERVER_A = os.getenv("SERVER_A")
USERNAME_A = os.getenv("USERNAME_A")
PASSWORD_A = os.getenv("PASSWORD_A")

db_b_odbc_str = (
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={SERVER_B};"
    f"DATABASE={DATABASE_B};"
    f"UID={USERNAME_B};"
    f"PWD={PASSWORD_B};"
    f"TrustServerCertificate=yes;"
)

db_a_odbc_str = (
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={SERVER_A};"
    f"DATABASE={DATABASE_A};"
    f"UID={USERNAME_A};"
    f"PWD={PASSWORD_A};"
    f"TrustServerCertificate=yes;"
)

db_c__connection_string = (
    f"mssql+pyodbc://@{SERVER_A}/{DATABASE_A}"
    f"?driver={DRIVER}&Encrypt=yes&TrustServerCertificate=no"
)
db_b_connection_url = f"mssql+pyodbc:///?odbc_connect={quote_plus(db_b_odbc_str)}"
db_a_connection_url = f"mssql+pyodbc:///?odbc_connect={quote_plus(db_a_odbc_str)}"


def provide_token(dialect, conn_rec, cargs, cparams):
    cargs[0] = cargs[0].replace(";Trusted_Connection=Yes", "")

    logger.info("Requesting Azure InteractiveBrowserCredential token...")

    credential = InteractiveBrowserCredential(response_mode="form_post")
    token_object = credential.get_token("https://database.windows.net/.default")

    token_bytes = token_object.token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    cparams["attrs_before"] = {1256: token_struct}


def get_db_c__engine():
    engine = create_engine(
        db_c__connection_string, pool_pre_ping=True, fast_executemany=True
    )
    event.listen(engine, "do_connect", provide_token)

    return engine


db_c__engine = get_db_c__engine()
db_b_engine = create_engine(db_b_connection_url)
db_a_engine = create_engine(db_a_connection_url)
