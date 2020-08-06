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

    def __getitem__(self, keys):
        trunks = {'': self.tree}
        word_length = len(keys)
        if not isinstance(keys, tuple):
            keys = (keys,)

        for i, key in enumerate(keys):
            branches = {}
            for root, trunk in trunks.items():
                if isinstance(key, slice):
                    for node in trunk.values():
                        if node.is_word and i + 1 == word_length:
                            yield root + node.letter
                        branches[root + node.letter] = node.branches

                elif isinstance(key, str):
                    node = trunk.get(key)
                    if node:
                        if node.is_word and i + 1 == word_length:
                            yield root + node.letter
                        branches[root + node.letter] = node.branches
            trunks = branches

    def find_playable(self, pattern, hand, lbuff=None):
        pattern = [l.upper() if l else '' for l in pattern]
        hand = [l.upper() for l in hand]

        if lbuff is None:
            for lbuff, l in enumerate(pattern):
                if l:
                    break

        trunks = {'': (self.tree, list(hand))}

        for i, letter in enumerate(pattern):
            branches = {}
            try:
                next_letter = pattern[i + 1]
            except IndexError:
                next_letter = ''

            for root, (trunk, hand) in trunks.items():
                if not letter:  # any letter
                    blanks = hand.count('?')
                    for node in trunk.values():
                        if node.letter in hand or blanks:
                            l = node.letter.lower() if blanks else node.letter
                        else:
                            continue

                        word = root + l
                        if node.is_word and not next_letter:
                            yield word

                        new_hand = hand.copy()
                        if not blanks:
                            new_hand.remove(l)
                        else:
                            new_hand.remove('?')

                        branches[word] = (node.branches, new_hand)
                else:
                    node = trunk.get(letter)
                    if node:
                        if (node.is_word and not next_letter):
                            yield root + node.letter
                        branches[root + node.letter] = (node.branches, hand)
            trunks = branches

    def check_word(self, word):
        p = self.tree
        for i, l in enumerate(word):
            p = p.get(l)

            if p.is_word:
                return True