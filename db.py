import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

host     = os.getenv('DB_HOST', 'postgres')
database = os.getenv('DB_NAME', 'gestionactivos')
username = os.getenv('DB_USER', 'admin')
password = os.getenv('DB_PASSWORD', 'Admin@1234')
port     = os.getenv('DB_PORT', '5432')

conn_str = f"host={host} port={port} dbname={database} user={username} password={password}"

try:
    conn = psycopg2.connect(conn_str)
    conn.autocommit = True
    cursor = conn.cursor()
    print("Conexión exitosa a PostgreSQL")
except Exception as e:
    print(f"Error de conexión: {e}")
    raise