import io
import re
import syntax
import math
from typing import Union, Tuple, Iterable
from functools import wraps
from itertools import tee

def pairwise(iterable):
    '''s -> (s0,s1), (s1,s2), (s2, s3), ...'''
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)

# https://stackoverflow.com/a/1751478
def chunks(l, n):
    '''Split sequence l into chunks of size n. Last chunk can be of smaller size.'''
    l = list(l)
    n = max(1, n)
    return (l[i:i+n] for i in range(0, len(l), n))

# https://wiki.python.org/moin/PythonDecoratorLibrary#Memoize
def memoize(obj):
    cache = obj.cache = {}

    @wraps(obj)
    def memoizer(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = obj(*args, **kwargs)
        return cache[key]
    return memoizer

def peek_at_least(f: io.BufferedReader, size: int):
    peeked = f.peek(size)
    if len(peeked) > 0 and len(peeked) < size: # peek may return less bytes than specified even if actually available
        org_pos = f.tell()
        peeked = f.read(size)
        f.seek(org_pos, io.SEEK_SET)
    return peeked

def read_until(f: io.BufferedReader, patterns: Iterable, *, maxsize: int = 0):
    """until earliest, if tie, longest, one in patterns. Note: f must support seek().
    
    If f produces bytes, patterns should also be bytes literals (string literals with b prefix)"""
    maxsize = 0 if maxsize < 0 else maxsize
    max_len = max(len(p) for p in patterns)
    result: bytes = bytes()
    violation = b''
    def append_result(s): # necessary as read data may be bytes or str
        if len(s) == 0: return
        nonlocal result
        if len(result) == 0:
            result = s
        else:
            result += s
            result = bytes(result)
    while True:
        peeked = peek_at_least(f, max_len)
        temp = [(p, peeked.find(p)) for p in patterns if peeked.find(p) >= 0]
        if len(temp) == 0:
            next_violate = len(peeked)
            violation = None if len(peeked) < max_len else violation  # None to inidcate EOF
        else:
            violation, next_violate = min(temp, key=lambda x: x[1] + 1 / (1 + len(x[0])))
        if maxsize != 0 and len(result) + len(peeked[:next_violate]) > maxsize:
            d = maxsize - len(result)
            append_result(peeked[:d])
            f.seek(d, io.SEEK_CUR)
            violation = b'' # inidcate max size reached
            break
        elif maxsize != 0 and len(result) + len(peeked[:next_violate]) == maxsize:
            append_result(peeked[:next_violate])
            f.seek(next_violate, io.SEEK_CUR)
            break
        else:
            append_result(peeked[:next_violate])
            f.seek(next_violate, io.SEEK_CUR)
            if next_violate != len(peeked): break
    return result, violation

def seek_until(f: io.BufferedReader, patterns: Iterable, *, ignore_comment: bool = False) -> int:
    """until earliest, if tie, longest, one in patterns, though it does not matter as this function does not return violation"""
    max_len = max(len(p) for p in patterns)
    violation = b''
    while True:
        peeked = peek_at_least(f, max(128, max_len))
        violation, next_violate = min(((p, float('inf') if peeked.find(p) <= -1 else peeked.find(p)) for p in list(patterns) + ([b'%'] if ignore_comment and b'%' not in patterns else [])), key=lambda x: x[1] + 1 / (1 + len(x[0])))
        if math.isinf(next_violate) and next_violate > 0:
            next_violate = len(peeked)
        f.seek(next_violate, io.SEEK_CUR)
        if next_violate != len(peeked): break
        if max(128, max_len) > len(peeked): break
    if ignore_comment and violation == b'%':
        _, eol_maker = read_until(f, syntax.EOL)
        #f.seek(len(eol_maker), io.SEEK_CUR)
        # PDF ignores comments, up to but not including the end of the line, treating them as if they were single white-space character
        # _\r => \x00\r, \x20\r, \t\r, \f\r
        # _\n => \x00\n, \x20\n, \t\n, \f\n
        # _\r\n => \x00\r\n, \x20\r\n, \t\r\n, \f\r\n
        # 
        return seek_until(f, patterns, ignore_comment=ignore_comment)
    else:
        return f.tell()

@memoize
def b_(sth) -> bytes:
    return bytes(str(sth), 'iso-8859-1') # latin-1, full 8-bit
