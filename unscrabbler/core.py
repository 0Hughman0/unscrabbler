import random
import json
import itertools
from pathlib import Path
import abc

import pandas as pd
import numpy as np

from IPython.display import display
from ipywidgets import Output

from .word_search import WordTree

ACROSS = np.array([0, 1])
DOWN = np.array([1, 0])
DW = 'DW'
DL = 'DL'
TW = 'TW'
TL = 'TL'


def iter_word(word, start, direction):
    for j, l in enumerate(word):
        yield (start + j * direction), l


class InvalidMove(Exception):
    pass


class _Game:
    """
    Abstract base class for Scrabble game playing.

    Subclass and set config_dir attribute to configure.

    See example configurations in configs folder!
    """

    config_dir = None
    scrabble_bonus = 50
    hand_size = 7

    @staticmethod
    def _color_bonus_cell(val):
        if val == 'DW':
            return 'background-color: #faa896'
        elif val == 'TW':
            return 'background-color: #ec1c2d'
        elif val == 'DL':
            return 'background-color: #7ecaf3'
        elif val == 'TL':
            return 'background-color: #7fc8eb'
        return ''

    def __init__(self):
        self.board = np.full((15, 15), '')

        self.bonus_grid = pd.read_csv(f'{self.config_dir}/bonus_grid.csv', names = range(15))

        with open(f'{self.config_dir}/letter_score.json') as f:
            self.letter_scores = json.load(f)
            for l in list(self.letter_scores):
                self.letter_scores[l.lower()] = 0

        with open(f'{self.config_dir}/letter_freq.json') as f:
            self.letter_freqs = json.load(f)

        self.bag = []
        self.first_move = None

        with open(f'{self.config_dir}/words.txt') as f:
            self.all_words = [word.strip().upper() for word in f if word.strip().isalpha() and word.strip().islower()]

        self.word_tree = WordTree(self.all_words)
        self.players = []

    def clear(self):
        """
        Clear the contents of the board
        """
        self.board[:, :] = ''

    def show(self):
        """
        Generates, then returns a nicely formatted DataFrame representation of the board
        """
        df = pd.DataFrame(data=self.board)
        bonus_format = self.bonus_grid.copy()
        bonus_format = bonus_format.applymap(self._color_bonus_cell)
        return df.style.apply(lambda df: bonus_format, axis=None)

    def start(self, players, cpu_players):
        self.bag = list(itertools.chain.from_iterable(l * f for l, f in self.letter_freqs.items()))
        players = [Player(self, i) for i in range(players)] + [CPUPlayer(self, i) for i in range(cpu_players)]
        random.shuffle(players)
        self.players = players
        self.first_move = True

        for player in players:
            player.pickup()

        return players

    def find_secondary_words(self, word, start, direction):
        """
        iterator that finds words that branch off from the one you played
        """
        trans = DOWN if direction is ACROSS else ACROSS # perpendicular and up
        for (row, col), l in iter_word(word, start, direction):
            if direction is ACROSS:
                # 1) slices from edge of board, stopping at l
                # 2) iterate backwards
                # 3) evaluate bool on each square
                # 4) stop when a square is empty i.e. bool(sqr) = False
                trans_back = list(itertools.takewhile(bool, self.board[None:row, col].flatten()[::-1]))
                trans_forward = list(itertools.takewhile(bool, self.board[None:row:-1, col].flatten()[::-1]))
            else:
                trans_back = list(itertools.takewhile(bool, self.board[row, None:col].flatten()[::-1]))
                trans_forward = list(itertools.takewhile(bool, self.board[row, None:col:-1].flatten()[::-1]))

            if not trans_back and not trans_forward:
                continue

            secondary = trans_back[::-1] + [l] + trans_forward
            yield (row, col) - len(trans_back) * trans, trans, ''.join(secondary)

    def calc_raw_score(self, word):
        """
        Just counts up values of letters in word
        """
        return sum(map(lambda l: self.letter_scores[l], word))

    def calc_word_score(self, word, start, direction):
        """
        Finds score for a go, accounts for existing word rules. - Doesn't understand secondary words.
        """
        existing = []
        for (row, col), l in iter_word(word, start, direction):
            existing.append(self.board[row, col])
        if all(existing):
            return 0

        word_bonuses = []
        total = 0
        for (row, col), l in iter_word(word, start, direction):
            raw_score = self.letter_scores[l]

            if self.board[row, col]:  # already on board
                total += raw_score
                continue

            bonus = self.bonus_grid.iloc[row, col]
            if bonus in [DW, TW]:
                word_bonuses.append(bonus)

            if bonus == DL:
                total += raw_score * 2
            elif bonus == TL:
                total += raw_score * 3
            else:
                total += raw_score

        for word_bonus in word_bonuses:
            if word_bonus == 'DW':
                total *= 2
            if word_bonus == 'TW':
                total *= 3

        if (len(word) - len(list(filter(None, existing)))) >= 7:
            total += self.scrabble_bonus

        return total

    def calc_play_score(self, word, start, direction, secondaries=None):
        """
        if you don't provide secondaries, it'll find them!
        """
        if secondaries is None:
            secondaries = self.find_secondary_words(word, start, direction)
        score = self.calc_word_score(word, start, direction)
        score += sum(self.calc_word_score(word, coord, direction) for coord, direction, word in secondaries)
        return score

    def make_hand(self):
        size = self.hand_size
        if len(self.bag) < size:
            size = len(self.bag)
        return random.sample(self.bag, k=size)

    def save(self, filename):
        np.savetxt(filename, self.board, '%s', delimiter=',')

    def load(self, filename):
        self.board = np.loadtxt(filename, '<U1', delimiter=',')

    def iter_lines(self):
        yield ACROSS, self.board
        yield DOWN, self.board.T

    def iter_playable_spaces(self):
        for direction, board in self.iter_lines():
            for i, line in enumerate(board):
                for j, l in enumerate(line):
                    if j > 0 and line[j - 1]: # if letter before, need to leave space, so skip
                        continue
                    pattern = tuple(line[j:])
                    coord = np.array((i, j) if direction is ACROSS else (j, i))
                    yield coord, direction, pattern

    def move_valid(self, word, start, direction):
        validator = self.first_move_valid if self.first_move else self.normal_move_valid

        try:
            validator(word, start, direction)
        except InvalidMove as e:
            raise e

        return True

    def normal_move_valid(self, word, start, direction):
        if not self.word_tree.is_word(word.upper()):
            raise InvalidMove(f"Word {word} not found in dictionary")

        secondaries = list(self.find_secondary_words(word, start, direction))

        if secondaries and all(self.word_tree.is_word(word.upper()) for *_, word in secondaries):
            return True
        else:
            raise InvalidMove("Word doesn't connect to existing")

    def first_move_valid(self, word, start, direction):
        if not self.word_tree.is_word(word.upper()):
            return InvalidMove(f"Word {word} not found in dictionary")
        if (7, 7) in (tuple(coord) for coord, _ in iter_word(word, start, direction)):
            return True

        raise InvalidMove("Word doesn't pass through centre")

    def play(self, word, start, direction, validate=True):
        if validate:
            self.move_valid(word, start, direction)

        score = self.calc_play_score(word, start, direction)

        for (row, col), l in iter_word(word, start, direction):
            self.board[row, col] = l

        self.first_move = False

        return score


class Player:

    def __init__(self, game, name):
        self.name = name
        self.game: _Game = game
        self.hand = []
        self.score = 0

    def play(self, word, start, direction):
        to_lay = list(l if l.isupper() else '?' for ((row, col), l)
                      in iter_word(word, start, direction) if not self.game.board[row, col])

        missing = [l for l in set(to_lay) if self.hand.count(l) < to_lay.count(l)]

        if missing:
            raise InvalidMove(f"Missing {missing} to lay {word}")

        score = self.game.play(word, start, direction)

        self.score += score

        for l in to_lay:
            if l in self.hand:
                self.hand.remove(l)

        return score

    def pickup(self):
        random.shuffle(self.game.bag)
        while len(self.hand) < self.game.hand_size and self.game.bag:
            l = self.game.bag.pop(0)
            self.hand.append(l)

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"


class BaseCPUPlayer(Player):

    @abc.abstractmethod
    def get_move(self):
        pass


class CPUPlayer(BaseCPUPlayer):

    def __init__(self, game, name):
        super().__init__(game, name)

    def get_move(self):
        if self.game.first_move:
            moves = self.find_first_moves()
        else:
            moves = self.find_normal_moves()
        if moves:
            return moves[0][:3]
        else:
            return None

    def find_normal_moves(self):
        hand = tuple(self.hand)  # required for caching on find_playable
        moves = []
        for coord, direction, pattern in self.game.iter_playable_spaces():
            for word in self.game.word_tree.find_playable(pattern, hand):
                secondaries = list(self.game.find_secondary_words(word, coord, direction))

                if secondaries and all(self.game.word_tree.is_word(word) for *_, word in secondaries):
                    score = self.game.calc_play_score(word, coord, direction, secondaries)

                    if not score:
                        continue

                    moves.append((word, coord, direction, score))
        moves.sort(key=lambda play: (play[-1], len(play[0])), reverse=True)
        return moves

    def find_first_moves(self):
        hand = tuple(self.hand)
        moves = list()

        words = itertools.chain.from_iterable(
            self.game.word_tree.find_playable(('',) * j, hand) for j, _ in enumerate(hand))

        for word in words:
            for dcol, _ in enumerate(word):
                col = 7 - dcol
                score = self.game.calc_word_score(word, (7, col), ACROSS)
                moves.append((word, (7, col), ACROSS, score))

        moves.sort(key=lambda mv: (mv[-1], len(mv[0])), reverse=True)
        return moves


class ScrabbleGame(_Game):
    """
    Configured to play using OG board game rules
    """

    config_dir = Path(__file__).parent / 'configs' / 'Scrabble'


class WWFGame(_Game):
    """
    Configured to play with Words With Friends rules
    """
    scrabble_bonus = 35

    config_dir = Path(__file__).parent / 'configs' / 'WWF'


class WordMasterGame(_Game):
    """
    Configured to play with WordMaster rules
    """
    config_dir = Path(__file__).parent / 'configs' / 'WordWars'


game_modes = {'Scrabble': ScrabbleGame,
         'WWF': WWFGame,
         'WordMaster': WordMasterGame}


def ask_move():
    confirmed = False
    word = row = col= direction = None

    while not confirmed:
        word = input("Enter word: ")
        coord = input("Enter position in form row, col: ").strip()
        if coord:
            coord = coord.split(',')
            row, col = int(coord[0]), int(coord[1])
        else:
            row = col = None

        raw_direction = input("Enter direction (a for across, d for down): ").strip().lower()
        direction = ACROSS if 'a' in raw_direction else DOWN
        confirmed = 'y' in input(f"Confirm move: {move_repr(word, (row, col), direction)} (y/n): ").lower()

    return (word, (row, col), direction) if word else None


def move_repr(word, start, direction):
    return f"{word} {start} {'ACROSS' if direction is ACROSS else 'DOWN'}"


def play_game(human_players=1, cpu_players=1, game_mode='WWF'):
    game = game_modes[game_mode]()
    game.start(human_players, cpu_players)

    print("Game order")
    print(game.players)

    board_out = Output()
    display(board_out)

    def update_board():
        board_out.clear_output()
        with board_out:
            display(game.show())

    update_board()

    game_over = False
    while not game_over:
        moves = []

        for player in game.players:
            print(f"{player}'s turn:")
            print("Your hand:", player.hand)

            while True:
                if isinstance(player, BaseCPUPlayer):
                    move = player.get_move()
                else:
                    move = ask_move()

                if not move:
                    print(f"{player} passed")
                    break

                try:
                    score = player.play(*move)
                    print(f"{player} played: {move_repr(*move)} for {score} points")
                    update_board()
                    break
                except InvalidMove as e:
                    print(e)

            moves.append(move)
            player.pickup()

            if not player.hand:  # first player ran out
                print(f"{player} has played all their letters!")
                game_over = True
                break

        if not any(moves):  # round of no-one playing
            print("No players able to play.")
            game_over = True

    print("The game is up!")

    for player in game.players:
        hand_score = game.calc_raw_score(player.hand)
        player.score -= hand_score
        print(f"{player} deducted {hand_score} points for remaining letters {player.hand}")

    game.players.sort(key=lambda p: p.score, reverse=True)
    print("Final Ranking")

    for i, player in enumerate(game.players):
        print(f"{i + 1}) {player} - {player.score} points")
