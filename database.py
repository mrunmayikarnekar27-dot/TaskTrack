import mysql.connector
from mysql.connector import Error
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Mrunmayi@123",
    "database": "tasktrack_db"
}


def get_db_connection():

    try:

        connection = mysql.connector.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"]
        )

        return connection

    except Error as e:

        print("DATABASE CONNECTION ERROR:", e)

        return None
