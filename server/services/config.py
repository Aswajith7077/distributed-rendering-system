from dotenv import dotenv_values


class ConfigService:
    
    def __init__(self,files = [".env"]):
        self.config = {}
        for file in files:
            self.config.update(dotenv_values(file))
    
    def __getattr__(self, name):
        return self.config.get(name)
    
