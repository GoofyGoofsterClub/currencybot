class Command:
    def __init__(self, commands, func):
        self.commands = commands
        self.func = func
    
    def run(self, message, args, _globals):
        return self.func(message, args, _globals)