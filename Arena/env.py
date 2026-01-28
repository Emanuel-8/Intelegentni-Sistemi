class Arenaenv:
    
    def __init__(self, player):

        self.width = 800
        self.height = 600

        self.player = player
        

    def border(self):
        self.player.x = max(0,min(self.player.x,self.width - self.player.radius))
        self.player.y = max(0,min(self.player.y,self.height - self.player.radius))

    def get_state(self):
        return [self.player.x, self.player.y, self.player.stamina]