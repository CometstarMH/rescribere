import io
import re
import syntax
import math
from typing import Union, Tuple, Iterable
from functools import wraps
from itertools import tee, islice

def pairwise(iterable):
    '''s -> (s0,s1), (s1,s2), (s2, s3), ...'''
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)

# https://stackoverflow.com/a/1751478
def chunks_(l, n):
    '''Split sequence l into chunks of size n. Last chunk can be of smaller size. Depends on len of l being known.'''
    l = list(l)
    n = max(1, n)
    return (l[i:i+n] for i in range(0, len(l), n))

def chunks(l, n):
    '''Split sequence l into chunks of size n. Last chunk can be of smaller size.'''
    x = [None] * n # This seems to be optimized by at least CPython https://stackoverflow.com/a/7733316/2157240
    i = 0
    for e in l:
        if i >= n:
            yield x
            x = [None] * n
            i = 0
        x[i] = e
        i += 1
    x = x[0:i]
    yield x

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

def tail(f, lines):
    BLOCK_SIZE = 1024
    f.seek(0, io.SEEK_END)
    block_end_byte = f.tell()
    lines_to_go = lines + 1 # read 1 extra line, which can be partial if the block boundary lies in the middle of the line
    block_number = -1
    blocks = [] # blocks of size BLOCK_SIZE, in reverse order starting
                # from the end of the file
    while lines_to_go > 0 and block_end_byte > 0:
        if (block_end_byte > BLOCK_SIZE):
            # read the last block we haven't yet read
            f.seek(block_number*BLOCK_SIZE, io.SEEK_END)
            blocks.append(f.read(BLOCK_SIZE))
        else:
            # file too small, start from begining
            f.seek(0, io.SEEK_SET)
            # only read what was not read
            blocks.append(f.read(block_end_byte))
        lines_found = len(re.findall(rb'\r\n|\r(?!\n)|(?<!\r)\n', blocks[-1])) ## Changed in version 3.7: Non-empty matches can now start just after a previous empty match.
        lines_to_go -= lines_found
        block_end_byte -= BLOCK_SIZE
        block_number -= 1
    all_read_text = b''.join(reversed(blocks)) # this includes the characters after the last EOL
    return re.split(rb'\r\n|\r(?!\n)|(?<!\r)\n', all_read_text)[-lines:]


def rlines(f, BLOCK_SIZE = 1024, *, MAX_OFFSET = None):
    f.seek(0, io.SEEK_END)
    block_end_byte = f.tell()
    block_number = -1
    blocks = []
    if MAX_OFFSET is not None:
        if MAX_OFFSET < 0: MAX_OFFSET = block_end_byte + MAX_OFFSET
        if MAX_OFFSET >= block_end_byte: MAX_OFFSET = block_end_byte - 1
    else:
        MAX_OFFSET = block_end_byte
    while block_end_byte > 0:
        if (block_end_byte > BLOCK_SIZE):
            # read the last block we haven't yet read
            f.seek(MAX_OFFSET + 1 + block_number*BLOCK_SIZE, io.SEEK_SET)
            #f.seek(block_number*BLOCK_SIZE, io.SEEK_END)
            blocks.append(f.read(BLOCK_SIZE))
        else:
            # file too small, start from begining
            f.seek(0, io.SEEK_SET)
            # only read what was not read
            blocks.append(f.read(block_end_byte))
        block_end_byte -= BLOCK_SIZE
        block_number -= 1
        # this includes the characters after the last EOL
        all_read_text = b''.join(reversed(blocks)) 
        # yield all lines except the last line, which may be partial
        temp = re.split(rb'(\r\n|\r(?!\n)|(?<!\r)\n)', all_read_text)
        # re.split always output odd nunber of elements when there is exactly 1 capture group in the delim
        # the last element is the remainder of unsplit text, which can be empty
        if temp[-1] == b'': temp = temp[:-1] 
        yield from reversed(list(islice((b''.join(x) for x in chunks(temp, 2)), 1, None)))
        # save the remaining characters
        temp = re.split(rb'(\r\n|\r(?!\n)|(?<!\r)\n)', all_read_text, 1) # max len = 3
        blocks = [b''.join(temp[0:2])] if len(temp) > 1 else [temp]
        if len(blocks[-1]) == 0:
            blocks = []
    if len(blocks) > 0: yield blocks[0] 

@memoize
def b_(sth) -> bytes:
    return bytes(str(sth), 'iso-8859-1') # latin-1, full 8-bit
