# Unscrabbler

Fun project, trying to find the best implementation for creating a scrabble playing bot!

In its current state I think Unscrabbler will tell you the highest scoring go possible - whether this is strategically
the best move is another challenge!

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/0Hughman0/unscrabbler/master?filepath=play.ipynb)

## To play

* Open up `play.ipynb`.
* Coords are in form `(row, col)`.
* Blanks in your hand are represented by `?`, blanks on the board are denoted by `lowercase` all other letters should be
`UPPERCASE`

## Some programming lessons I learnt

1. Planning stuff on paper is good.
2. Pandas is great, but `iloc` is really slow compared to slicing a numpy array. If you have homogeneous data with
`RangeIndex`s the trade off might not be worth it.
3. Tree data structures are rad! You _can_ write something faster than `'word' in all_words`.
4. Using `functools.lru_cache` on a generator is not smart.
5. Annoying indexing problems can often be circumvented by using iteration and slicing instead.

## Some lessons on implementation

My first angle of attack on this project was to generate regex's for each row programmatically. Generating the regex's
was slow and running them against the dictionary was too.

I decided to try the tree structure seen in `word_search.py`, not expecting it to be better than `regex`... it was.

I then came up with a super smart algorithm that split lines up into chunks that you could play in, then ran this
through my tree. This worked pretty well.

However this wouldn't spot 'secondary words' e.g. the word `ON` when playing `NEW`:

```
BAMBOO
     NEW
```

Where `ON` is a word that's also formed when you play `NEW`.

At this stage I realised that for a go to be valid, it just needs at least 1 'secondary word' and that word needs to be
in the dictionary.

