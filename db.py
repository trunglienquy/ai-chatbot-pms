import mysql.connector

def get_db_connection(config):
    """
    Establish a connection to the MySQL database using the provided configuration.

    Thiết lập kết nối đến cơ sở dữ liệu MySQL sử dụng cấu hình đã cung cấp.
    """
    return mysql.connector.connect(**config)
