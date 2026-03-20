import mysql.connector

def dbconnect():
    con = mysql.connector.connect(
        host = "localhost",
        user = "root",
        password = "kuki",
        database = "transport_management"
    )
    return con