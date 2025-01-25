class Workflow:
    def __init__(self, logger, strategy):
        self.logger = logger
        self.strategy = strategy

    def execute(self, **kwargs):
        raise NotImplementedError("Subclasses must implement the 'execute' method")
