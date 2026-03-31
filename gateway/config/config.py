from dotenv import dotenv_values


class ConfigService:
    def __init__(self):
        self.config = dotenv_values()

    def __getattr__(self, name):
        return self.config.get(name)
