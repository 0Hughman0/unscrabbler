import functools


class Node:

    __slots__ = ['letter', 'is_word', 'branches']

    def __init__(self, letter):
        self.letter = letter
        self.is_word = False
        self.branches = {}

    def get(self, value):
        return self.branches.get(value)

    def __getitem__(self, key):
        return self.branches[key]

    def __setitem__(self, key, value):
        if key in self.branches:
            return
        self.branches[key] = value

    def __repr__(self):
        return f"<Node {self.letter} ({self.is_word})"

    def __contains__(self, value):
        return value in self.branches


class WordTree:
    """
    Probably could be a function...
    """

    def __init__(self, words):
        self.tree = {}
        self.build_tree(words)

    def build_tree(self, words):
        self.tree = {}
        for word in words:
            branch = self.tree
            for l in word:
                if l in branch:
                    branch = branch[l]
                else:
                    branch[l] = branch = Node(l)
            branch.is_word = True

        self.find_playable.cache_clear()  # being thorough

    @functools.lru_cache(None)  # safe to cache
    def find_playable(self, pattern, hand):
        pattern = [l.upper() if l else '' for l in pattern]
        hand = [l.upper() for l in hand]

        trunks = {'': (self.tree, list(hand))}

        words = []  # used to be a generator, but that messes with caching.

        for i, letter in enumerate(pattern):
            branches = {}
            try:
                next_letter = pattern[i + 1]
            except IndexError:
                next_letter = ''

            for root, (trunk, hand) in trunks.items():
                if not letter:  # blank space
                    has_blanks = '?' in hand

                    for node in trunk.values():  # all letters
                        if node.letter in hand or has_blanks:
                            l = node.letter.lower() if has_blanks else node.letter
                        else:
                            continue

                        word = root + l
                        if node.is_word and not next_letter:
                            words.append(word)

                        new_hand = hand.copy()
                        if not has_blanks:
                            new_hand.remove(l)
                        else:
                            new_hand.remove('?')

                        branches[word] = (node.branches, new_hand)
                else:
                    node = trunk.get(letter)
                    if node:
                        if node.is_word and not next_letter:
                            words.append(root + node.letter)
                        branches[root + node.letter] = (node.branches, hand)
            trunks = branches

        return words

    def is_word(self, word):
        p = self.tree
        for i, l in enumerate(word):
            p = p.get(l)
            if p is None:
                return False

        return p.is_word
