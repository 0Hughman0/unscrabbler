import random
import json
import itertools
from pathlib import Path

import pandas as pd
import numpy as np

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


class _Game:
    """
    Abstract base class for Scrabble game playing.

    Subclass and set config_dir attribute to configure.

    See example configurations in configs folder!
    """

    config_dir = None
    scrabble_bonus = 50

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

        self.bag = self.letter_freqs.copy()

        with open(f'{self.config_dir}/words.txt') as f:
            self.all_words = [word.strip().upper() for word in f if word.strip().isalpha() and word.strip().islower()]

        self.word_tree = WordTree(self.all_words)

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

    def resync_bag(self):
        """
        set `self.bag` by examining what we started with and what's on the board
        """
        new_bag = self.letter_freqs.copy()
        for row in self.board:
            for l in row:
                if l:
                    l = l if l.isupper() else '?'
                    new_bag[l] += -1

        self.bag = new_bag

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
        return random.choices(list(self.bag.keys()), list(self.bag.values()), k=7)

    def save(self, filename):
        np.savetxt(filename, self.board, '%s', delimiter=',')

    def load(self, filename):
        self.board = np.loadtxt(filename, '<U1', delimiter=',')

    def iter_lines(self):
        yield ACROSS, self.board
        yield DOWN, self.board.T

    def find_moves(self, hand):
        moves = list()
        hand = tuple(hand)
        for direction, board in self.iter_lines():
            for i, line in enumerate(board):
                for j, l in enumerate(line):
                    if j > 0 and line[j - 1]: # if letter before, need to leave space, so skip
                        continue
                    pattern = tuple(line[j:])
                    coord = np.array((i, j) if direction is ACROSS else (j, i))

                    for word in self.word_tree.find_playable(pattern, hand):
                        secondaries = list(self.find_secondary_words(word, coord, direction))

                        if secondaries and all(self.word_tree.is_word(word) for *_, word in secondaries):
                            score = self.calc_play_score(word, coord, direction, secondaries)
                            if not score:
                                continue
                            moves.append((word, coord, direction, score))
        moves.sort(key=lambda mv: (mv[-1], len(mv[0])), reverse=True)
        return moves

    def find_first_moves(self, hand):
        hand = tuple(hand)
        moves = list()

        words = itertools.chain.from_iterable(self.word_tree.find_playable(('',) * j, hand) for j, _ in enumerate(hand))

        for word in words:
            for dcol, _ in enumerate(word):
                col = 7 - dcol
                score = self.calc_word_score(word, (7, col), ACROSS)
                moves.append((word, (7, col), ACROSS, score))

        moves.sort(key=lambda mv: (mv[-1], len(mv[0])), reverse=True)
        return moves

    def play(self, word, start, direction):
        for (row, col), l in iter_word(word, start, direction):
            self.board[row, col] = l
        self.resync_bag()


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


class WordMaster(_Game):
    """
    Configured to play with WordMaster rules
    """
    config_dir = Path(__file__).parent / 'configs' / 'WordWars'
