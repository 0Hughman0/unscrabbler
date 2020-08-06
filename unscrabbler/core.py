import random
import json
import itertools

import pandas as pd
import numpy as np

from unscrabbler.word_search import WordTree

ACROSS = (0, 1)
DOWN = (1, 0)
DW = 'DW'
DL = 'DL'
TW = 'TW'
TL = 'TL'


def iter_word(word, start, direction):
    for j, l in enumerate(word):
        yield start + j * direction, l


def id_func(val):
    return val


class _Game:

    config_dir = None

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
        self.board = pd.DataFrame(index=range(15), columns=range(15), dtype=str)
        self.board.iloc[:, :] = ''

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
        self.board.iloc[:, :] = ''

    def show(self):
        bonus_format = self.bonus_grid.copy()
        bonus_format = bonus_format.applymap(self._color_bonus_cell)
        return self.board.style.apply(lambda df: bonus_format, axis=None)

    def playable_lines(self):
        for row, line in self.board.iterrows():
            yield row, ACROSS, line
        for col, line in self.board.iteritems():
            yield col, DOWN, line

    def bag_val(self):
        return sum(self.letter_scores[l] * n for l, n in self.bag.items())

    def letters_left(self):
        return sum(self.bag.values())

    def resync_bag(self):
        new_bag = self.letter_freqs.copy()
        for _, row in self.board.items():
            for l in row:
                if l:
                    l = l if l.isupper() else '?'
                    new_bag[l] += -1

        self.bag = new_bag

    def calc_turn_val(self, word, score, hand):
        played = [l for l in word if l in hand or l.islower()]
        raw = self.calc_raw_score(word)
        benefit = score + len(played) * (self.bag_val() / self.letters_left())
        return benefit

    def find_secondary_words(self, word, start, direction):
        """
        Head up to top of word, note the start, then head back down again.
        """
        backwards = (-direction[1], -direction[0])  # perpendicular and up
        forwards = (direction[1], direction[0])  # perpendicular and down
        for j, l in enumerate(word):
            row0, col0 = start[0] + direction[0] * j, start[1] + direction[1] * j

            row, col = row0 + backwards[0], col0 + backwards[1]

            if not 0 <= row <= 14 or not 0 <= col <= 14:
                continue

            existing = self.board.iloc[row, col]

            there = 1
            while existing:
                row, col = row0 + backwards[0] * there, col0 + backwards[1] * there

                if not 0 <= row <= 14 or not 0 <= col <= 14:  # this or was an and and that was what caused the crash!
                    break

                existing = self.board.iloc[row, col]
                there += 1

            row1, col1 = row + forwards[0], col + forwards[1]

            existing_word = []
            back = 0

            while True:
                row, col = row1 + forwards[0] * back, col1 + forwards[1] * back
                if not 0 <= row <= 14 or not 0 <= col <= 14:
                    break

                if row == row0 and col == col0:
                    existing = l
                else:
                    existing = self.board.iloc[row, col]

                if not existing:
                    break

                existing_word.append(existing)
                back += 1

            if len(existing_word) == 1 and not self.board.iloc[row0, col0]:  # it's just the new letter
                continue

            if existing_word:
                yield (row1, col1), forwards, ''.join(existing_word)

    def calc_raw_score(self, word):
        return sum(map(lambda l: self.letter_scores[l], word))

    def calc_word_score(self, word, start, direction):
        """
        Finds score for a go, accounts for existing word rules. - Doesn't understand secondary words.
        """
        is_news = []
        for j, l in enumerate(word):
            coord = start[0] + direction[0] * j, start[1] + direction[1] * j
            is_news.append(self.board.iat[coord[0], coord[1]])
        if all(is_news):
            return 0

        word_bonuses = []
        total = 0
        for i, l in enumerate(word):
            row, col = start[0] + direction[0] * i, start[1] + direction[1] * i
            raw_score = self.letter_scores[l]

            if self.board.iloc[row, col]:  # already on board
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

        if (len(word) - len(list(filter(None, is_news)))) >= 7:
            total += 50

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
        self.board.to_csv(filename)

    def load(self, filename):
        save = pd.read_csv(filename).drop('Unnamed: 0', axis=1)
        self.board = save.where(save.notna(), '')
        self.board.index = range(15)
        self.board.columns = range(15)

    def find_top_moves(self, hand):
        words = set()
        hand = tuple(hand)

        for i, direction, line in self.playable_lines():

            for j, l in line.items():
                if j > 0 and l and line[j - 1] or j > 0 and not l and line[j - 1]:
                    continue
                pattern = tuple(line[j:])
                coord = (i, j) if direction is ACROSS else (j, i)

                for word in self.word_tree.find_playable(pattern, hand):
                    secondaries = list(self.find_secondary_words(word, coord, direction))

                    if secondaries and all(word in self.all_words for *_, word in secondaries):
                        score = self.calc_play_score(word, coord, direction, secondaries)
                        if not score:
                            continue
                        words.add((word, coord, direction, pattern, tuple(secondaries), score, self.calc_turn_val(word, score, hand)))
        words = list(words)
        words.sort(key=lambda w: w[-1], reverse=True)
        return words

    def find_top_first_move(self, hand, top=10):
        words = set()

        for j in range(8):
            for word in self.word_tree.find_playable([''] * j, hand):
                score = self.calc_word_score(word, (7, j), ACROSS)
                words.add((word, (7, j), ACROSS, score))
        words = list(words)
        words.sort(key=lambda w: w[-1], reverse=True)
        return words[:top]

    def play(self, word, start, direction):
        for i, l in enumerate(word):
            self.board.iloc[start[0] + direction[0] * i, start[1] + direction[1] * i] = l
        self.resync_bag()


class ScrabbleGame(_Game):
    config_dir = 'scrabble'


class WWFGame(_Game):
    config_dir = 'wwf'


class WordWarsGame(_Game):
    config_dir = 'WordWars'
