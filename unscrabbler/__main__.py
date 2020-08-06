from unscrabbler.core import WordWarsGame, DOWN, ACROSS, WWFGame
import pandas as pd
import numpy as np
g = WWFGame()

g.play('AMAZING', (10, 3), ACROSS)
g.play('VERTICLE', (2, 11), DOWN)
g.play('FLOPPY', (4, 8), DOWN)
g.show()

list(g.find_secondary_words('FISHIES', (7, 7), ACROSS))
