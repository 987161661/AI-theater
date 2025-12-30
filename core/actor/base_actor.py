class Actor:
    """
    Data class representing an actor in the theater.
    """
    def __init__(self, name: str, model_config_name: str, system_prompt: str = "", memory: str = ""):
        self.name = name
        self.model_config_name = model_config_name 
        self.system_prompt = system_prompt
        self.memory = memory

    def __repr__(self):
        return f"<Actor name={self.name} model={self.model_config_name}>"
