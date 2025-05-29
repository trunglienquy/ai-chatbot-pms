import configparser

def load_config(file_path="config.ini"):
    config = configparser.ConfigParser()
    config.read(file_path)
    try:
        return {
            "GEMINI_API_KEY": config["gemini"]["api_key"],
            "DB": {
                "host": config["db"]["host"],
                "user": config["db"]["user"],
                "password": config["db"]["password"],
                "database": config["db"]["database"]
            }
        }
    except KeyError as e:
        raise Exception(f"Missing config: {e}")