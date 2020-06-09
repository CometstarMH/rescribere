import utils
from utils import b_
import io
import re
import syntax
import decimal
import collections
import time
from decimal import Decimal
from abc import abstractmethod, ABC
from typing import List, Dict

def val(pdfObj: PdfObject):
    if isinstance(pdfObj, PdfBooleanObject) or isinstance(pdfObj, PdfNumericObject) or isinstance(pdfObj, PdfLiteralStringObject)or isinstance(pdfObj, PdfHexStringObject):
        return pdfObj.value
    if isinstance(pdfObj, PdfNameObject):
        return pdfObj # TODO: reconsider?
    if isinstance(pdfObj, PdfArrayObject):
        return [val(obj) for obj in pdfObj.value]
    if isinstance(pdfObj, PdfDictionaryObject):
        return {k: val(pdfObj.value[k]) for k in pdfObj.value} # dict keys must be PdfNameObject
    if isinstance(pdfObj, PdfIndirectObject):
        return val(pdfObj.value) # TODO: reconsider?
    if isinstance(pdfObj, PdfStreamObject):
        return pdfObj.decode()
    if isinstance(pdfObj, PdfReferenceObject):
        return val(pdfObj.value)
    if isinstance(pdfObj, PdfNullObject):
        return None
    

# TODO: allow encryption

# adapted from PyPDF2
class PdfObject(ABC):
    @abstractmethod
    def write_to_file(self, f: io.BufferedReader):
        """Should not include any delimiters. Handled externally and manually"""
        pass

    # TODO: may be more abstract methods, e.g. for display, conversion from Python base types, etc.?

    @classmethod
    @abstractmethod
    def create_from_file(cls, f: io.BufferedReader, doc):
        char = f.peek(1)[0:1]
        # TODO: 
        if char == b't' or char == b'f':
            return PdfBooleanObject.create_from_file(f)
        elif char in [b'0', b'1', b'2', b'3', b'4', b'5', b'6', b'7', b'8', b'9', b'+', b'-']:
            o = f.tell()
            n = PdfNumericObject.create_from_file(f)
            if n.value < 0 or n.value - int(n.value) != 0: # a decimal or a negative number, never a indirect obj
                return n
            o2 = f.tell()

            utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
            n2, _ = utils.read_until(f, syntax.DELIMS + syntax.WHITESPACES)
            if re.match(rb'\d+$', n2) is None: # next token not a number, never an indirect obj
                f.seek(o2, io.SEEK_SET)
                return n
            else:
                utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
                s, _ = utils.read_until(f, syntax.DELIMS + syntax.WHITESPACES)
                if s == b'obj': # all 3 tokens are correct, an indirect obj
                    f.seek(o, io.SEEK_SET)
                    return PdfIndirectObject.create_from_file(f, doc)
                elif s == b'R': # all 3 tokens are correct, an indirect reference
                    f.seek(o, io.SEEK_SET)
                    return PdfReferenceObject.create_from_file(f, doc)
                else:
                    f.seek(o2, io.SEEK_SET)
                    return n
        elif char == b'(':
            return PdfLiteralStringObject.create_from_file(f)
        elif char == b'<':
            char = utils.peek_at_least(f, 2)[0:2]
            if char == b'<<':
                dictobj = PdfDictionaryObject.create_from_file(f, doc)
                return dictobj
            else:
                return PdfHexStringObject.create_from_file(f)
        elif char == b'/':
            return PdfNameObject.create_from_file(f)
        elif char == b'[':
            return PdfArrayObject.create_from_file(f, doc)
        elif char == b'n':
            return PdfNullObject.create_from_file(f)
        else:
            raise Exception(f'Unknown token at {f.tell()}')


class PdfBooleanObject(PdfObject):
    def __init__(self, value):
        self.value = value

    def write_to_file(self, f: io.BufferedReader):
        if self.value:
            f.write(b'true')
        else:
            f.write(b'false')
    
    def __repr__(self):
        return f'PdfBooleanObject({self.value})'
    
    def __str__(self):
        return str(self.value)

    @classmethod
    def create_from_file(cls, f: io.BufferedReader):
        org_pos = f.tell()
        token, _ = utils.read_until(f, syntax.DELIMS + syntax.WHITESPACES)
        if token == b'true':
            return PdfBooleanObject(True)
        elif token == b'false':
            return PdfBooleanObject(False)
        else:
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f'Parse Error: Not a valid Boolean object at offset {org_pos}.')

# TODO: may be also inherit from Decimal?
class PdfNumericObject(PdfObject):
    def __init__(self, value):
        self.value: Decimal = value

    def write_to_file(self, f: io.BufferedReader):
        f.write(b_(self.value))
    
    def __repr__(self):
        return f'PdfNumericObject({str(self.value)})'
    
    def __str__(self):
        return str(self.value)

    @classmethod
    def create_from_file(cls, f: io.BufferedReader):
        org_pos = f.tell()
        token, _ = utils.read_until(f, syntax.DELIMS + syntax.WHITESPACES)
        if re.match(br'^[+-]?\d+(?:\.\d*)?|[+-]?\.\d+$', token) is None:
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f'Parse Error: Not a valid Numeric object at offset {org_pos}.')
        return PdfNumericObject(Decimal(token.decode('iso-8859-1'))) 

class PdfLiteralStringObject(PdfObject):
    """internal value must be a normal Python string"""
    def __init__(self, value):
        if not isinstance(value, str): raise ValueError('internal value must be a normal Python string')
        self.value = value
    
    def __repr__(self):
        return f'PdfLiteralStringObject(\"{self.value}\")'
    
    def __str__(self):
        temp = self.value
        temp = temp.replace('\\', '\\\\')
        temp = temp.replace('(', '\\(')
        temp = temp.replace(')', '\\)')
        return f'({temp})'
        
    def write_to_file(self, f: io.BufferedReader):
        if not isinstance(self.value, str): raise ValueError('internal value must be a normal Python string')
        # https://stackoverflow.com/questions/3411771/best-way-to-replace-multiple-characters-in-a-string
        # conclusion: optimum is to use a char list, and do prelim check for presence
        for ch in ['\\', '(', ')', '\n', '\r', '\t', '\b', '\f'] + [chr(x) for x in range(128, 256)]:
            if ch in text:
                code = ord(ch)
                if ch in ['\\', '(', ')']:
                    text = text.replace(ch, '\\' + ch)
                elif code >= 128 and code < 256:
                    text = text.replace(ch, '\\' + oct(code)[2:])
                else:
                    text.translate(str.maketrans({'\n': '\\n', '\r': '\\r', '\t': '\\t', '\b': '\\b', '\f': '\\f'}))
    
    @classmethod
    def create_from_file(cls, f: io.BufferedReader):
        org_pos = f.tell()
        token: bytes = f.read(1)
        if token != b'(':
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f'Parse Error: Not a valid string at offset {org_pos}.')
        result = bytearray(b'')
        stack = 1 # 1 for initial (
        while True:
            # Balanced pairs of parentheses within a string require no special treatment.
            # backslash ( \ ) is used as an escape character for various purposes, 
            # such as to include ... unbalanced parentheses ...
            token, endtoken = utils.read_until(f, [b'(', b')', b'\\(', b'\\)'])
            result.extend(token)
            if endtoken in [b'\\(', b'\\)']: # escaped, read it for now
                f.seek(2, io.SEEK_CUR)
                result.extend(endtoken)
                continue
            elif endtoken == b'(': # open bracket, stack += 1, read it for now
                stack += 1
                f.seek(1, io.SEEK_CUR)
                result.extend(endtoken)
                continue
            elif endtoken == b')': # close bracket, stack -= 1, read it for now if string not done
                stack -= 1
                f.seek(1, io.SEEK_CUR)
                if stack == 0: # string is done
                    break
                else:
                    result.extend(endtoken)
                    continue
            elif endtoken == b'' and stack > 0:
                f.seek(org_pos, io.SEEK_SET)
                raise Exception(f'Parse Error: Not a valid string at offset {org_pos}.')
        
        # If a string is too long to be conveniently placed on a single line, it may be split
        # across multiple lines by using the backslash character at the end of a line to
        # indicate that the string continues on the following line. The backslash and the
        # end-of-line marker following it are not considered part of the string.
        result = result.replace(b'\\\r\n', b'')
        result = result.replace(b'\\\r', b'')
        result = result.replace(b'\\\n', b'')

        # If an end-of-line marker appears within a literal string without a preceding
        # backslash, the result is equivalent to \n (regardless of whether the end-of-line
        # marker was a carriage return, a line feed, or both).
        result = result.replace(b'\r\n', b'\n')
        result = result.replace(b'\r', b'\n')

        # TABLE 3.2 Escape sequences in literal strings
        result = result.replace(b'\\n', b'\n')
        result = result.replace(b'\\r', b'\r')
        result = result.replace(b'\\t', b'\t')
        result = result.replace(b'\\b', b'\b')
        result = result.replace(b'\\f', b'\f')
        result = result.replace(b'\\(', b'(')
        result = result.replace(b'\\)', b')')
        result = result.replace(b'\\\\', b'\\')
        result = re.sub(rb'\\([0-7]{1,3})', lambda m: chr(int(m.group(1), 8)).encode('iso-8859-1') if int(m.group(1), 8) < 256 else b'\\' + m.group(1), result)

        return PdfLiteralStringObject(result.decode('iso-8859-1'))

class PdfHexStringObject(PdfObject):
    """internal value can be either bytes or bytearray"""
    def __init__(self, value):
        self.value = value
        
    def write_to_file(self, f: io.BufferedReader):
        f.write(b_('<' + self.value.hex().upper() + '>'))

    @classmethod
    def create_from_file(cls, f: io.BufferedReader):
        org_pos = f.tell()
        token: bytes = f.read(1)
        if token != b'<':
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f'Parse Error: Not a valid hexadecimal string at offset {org_pos}.')
        token, endtoken = utils.read_until(f, [b'>'])
        if re.match(br'^[0-9A-Fa-f]*$', token) is None or endtoken != b'>':
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f'Parse Error: Not a valid hexadecimal string at offset {org_pos}.')
        if len(token) == 0:
            return PdfHexStringObject(b'')
        else:
            f.read(1) # read '>'
            token = token.decode('iso-8859-1') # bytes.fromhex only accepts str. Moreover, we need to cater for odd length
            if len(token) % 2 != 0: # PDF Reference 3.2.3, Hexadecimal Strings: if there is an odd number of digits, the final digit is assumed to be 0
                token += '0'
            return PdfHexStringObject(bytes.fromhex(token))

PdfNameObjectBase = collections.namedtuple('_C_{:.0f}'.format(time.time()), ['value'])
class PdfNameObject(PdfNameObjectBase, PdfObject):
    """Immutable.
    
    The byte sequence of a name object should be interpreted as a UTF-8 sequence, after expanding # sequences (# followed by 2-digit hex)
    
    This object stores the raw bytes as the primary value, as it is needed for equality checking. The interpreted string can be obtained by calling the get_name() method"""
    __slots__ = []
    def __new__(cls, s):
        b = bytes()
        if isinstance(s, bytes) or isinstance(s, bytearray):
            b = s
        elif isinstance(s, str):
            b = bytearray(s, 'utf_8')
            from itertools import chain
            for c in chain(range(33), range(127, 256)):
                if c in b:
                    b = b.replace(bytes([c]), b_(('#' + hex(c)[2:]).upper()))
        else:
            raise ValueError()
        return PdfNameObjectBase.__new__(cls, b)
    
    def __hash__(self):
        return hash(self.get_name())

    def __eq__(self, other):
        return (isinstance(other, PdfNameObject) and other.value == self.value) or ((isinstance(other, bytes) or isinstance(other, bytearray)) and self.value == other) or (isinstance(other, str) and self.get_name() == other)
    
    def __repr__(self):
        return f'PdfNameObject("{self.get_name()}")'
    
    def __str__(self):
        return f'/{self.value.decode("iso-8859-1")}'

    def get_name(self, encoding='utf_8') -> str:
        '''Get the interpreted string from the raw bytes, i.e. #nn characters are interpreted'''
        # expand all #-hex first
        # TODO: char code 0 is not banned here, which is not allowed by spec
        s = re.sub(rb'#([0-9A-Z]{2})', lambda m: bytes(int(m.group(1), 16)), self.value, flags=re.IGNORECASE)
        return s.decode(encoding, 'ignore')
    
    def write_to_file(self, f: io.BufferedReader):
        f.write(b'/' + self.value)
    
    @classmethod
    def create_from_file(cls, f: io.BufferedReader):
        org_pos = f.tell()
        token: bytes = f.read(1)
        if token != b'/':
            raise Exception(f'Parse Error: Not a valid name object at offset {org_pos}.')
        result, _ = utils.read_until(f, syntax.DELIMS + syntax.WHITESPACES)
        return PdfNameObject(result)

class PdfArrayObject(PdfObject):
    def __init__(self, value: List[PdfObject]):
        self.value = value
    
    def __repr__(self):
        return f'PdfArrayObject([{" ".join([repr(e) for e in self.value])}])'
    
    def __str__(self):
        return f'[{" ".join([str(e) for e in self.value])}]'
    
    def write_to_file(self, f: io.BufferedReader):
        f.write(b'[')
        for o in self.value:
            o.write_to_file(f)
            if self.value[-1] != o: f.write(b' ')
        f.write(b']')

    @classmethod
    def create_from_file(cls, f: io.BufferedReader, doc):
        org_pos = f.tell()
        token: bytes = f.read(1)
        if token != b'[':
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f'Parse Error: Not a valid array object at offset {org_pos}.')
        result = []
        while True:
            utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
            if f.peek(1)[0:1] != b']':
                try:
                    result += [PdfObject.create_from_file(f, doc)]
                except Exception as ex:
                    raise Exception(f'Parse Error: Not a valid array object at offset {org_pos}.') from ex
            else: 
                f.read(1)
                break
        return PdfArrayObject(result)

class PdfDictionaryObject(PdfObject):
    """Specifying the null object as the value of a dictionary entry (Section 3.2.6, “Dictionary Objects”) is equivalent to omitting the entry entirely."""
    
    def __init__(self, value: Dict[PdfNameObject, PdfObject]):
        self.value = value
    
    def __getitem__(self, key):
        if not(isinstance(key, PdfNameObject) or isinstance(key, bytes) or isinstance(key, bytearray) or isinstance(key, str)):
            raise TypeError()
        return self.value[key]
    
    def __setitem__(self, key, value):
        if not(isinstance(key, PdfNameObject) or isinstance(key, bytes) or isinstance(key, bytearray) or isinstance(key, str)):
            raise TypeError()
        if not isinstance(value, PdfObject):
            raise TypeError()
        self.value[PdfNameObject(key)] = value
    
    def get(self, key, default = None):
        return self.value.get(key, default)
    
    def keys(self) -> List[str]:
        return [kn.get_name() for kn in self.value.keys()]
        
    def __repr__(self):
        return f'PdfDictionaryObject({"{" + ", ".join([f"{k}: {repr(self[k])}" for k in self.keys()]) + "}"})'
    
    def __str__(self):
        return f'{"<<" + ", ".join([f"/{k} {str(self[k])}" for k in self.keys()]) + ">>"}'
    
    def write_to_file(self, f: io.BufferedReader):
        f.write(b'<<')
        for k, v in self.value.items():
            k.write_to_file(f)
            if not(isinstance(v, PdfArrayObject) or isinstance(v, PdfDictionaryObject)):
                f.write(b' ')
            v.write_to_file(f)
        f.write(b'>>')
        
    @classmethod
    def create_from_file(cls, f: io.BufferedReader, doc):
        org_pos = f.tell()
        token: bytes = f.read(2)
        if token != b'<<':
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f'Parse Error: Not a valid dictionary object at offset {org_pos}.')
        result = {}
        while True:
            utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
            if f.peek(1)[0:1] == b'/':
                try:
                    # key, must be a name
                    k = PdfNameObject.create_from_file(f)
                    # value
                    utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
                    v = PdfObject.create_from_file(f, doc)
                    # TODO: check if dict use __eq__ for key equality and existence check
                    result[k] = v
                except Exception as ex:
                    raise Exception(f'Parse Error: Not a valid dictionary object at offset {org_pos}.') from ex
                continue
            elif utils.peek_at_least(f, 2)[0:2] == b'>>':
                f.read(2)
                break
            else:
                f.seek(org_pos, io.SEEK_SET)
                raise Exception(f'Parse Error: Not a valid dictionary object at offset {org_pos}.')
        return PdfDictionaryObject(result)

class PdfIndirectObject(PdfObject):
    def __init__(self, value, obj_no: int, gen_no: int):
        self.value = value
        self.obj_no = obj_no
        self.gen_no = gen_no

    def write_to_file(self, f: io.BufferedReader):
        # TODO: EOL is not needed in some cases
        f.write(b_(self.obj_no))
        f.write(b' ')
        f.write(b_(self.gen_no))
        f.write(b' obj')
        f.write(b'\n')
        self.value.write_to_file(f)
        f.write(b'\n')
        f.write(b'endobj')
        
    def __repr__(self):
        return f'PdfIndirectObject(obj_no={self.obj_no}, gen_no={self.gen_no}, value={repr(self.value)})'
    
    def __str__(self):
        return f'{self.obj_no} {self.gen_no} obj {str(self.value)} endobj'

    @classmethod
    def create_from_file(cls, f: io.BufferedReader, doc):
        org_pos = f.tell()
        num, _ = utils.read_until(f, syntax.WHITESPACES)
        if re.match(rb'\d+$', num) is None:
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f'Parse Error: Not a valid indirect object at offset {org_pos}.')
        obj_no = int(num)
        utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
        num, _ = utils.read_until(f, syntax.WHITESPACES)
        if re.match(rb'\d+$', num) is None:
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f'Parse Error: Not a valid indirect object at offset {org_pos}.')
        gen_no = int(num)
        utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
        tok, _ = utils.read_until(f, syntax.DELIMS + syntax.WHITESPACES)
        if tok != b'obj':
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f'Parse Error: Not a valid indirect object at offset {org_pos}.')

        utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
        inner_content_pos = f.tell()

        # parse inner object
        def inner2():
            f.seek(inner_content_pos, io.SEEK_SET)
            obj = PdfObject.create_from_file(f, doc)
            utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
            return obj
        inner_obj = inner2()

        # if inner object is a dict, and is followed by a stream extent, then the object should be stream object
        # otherwise, if there is no endobj token, it is an error
        temp = f.tell()
        utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
        token, endtoken = utils.read_until(f, syntax.DELIMS + syntax.WHITESPACES, maxsize=7)
        f.seek(temp, io.SEEK_SET)
        if not (token == b'endobj' and (endtoken != b'' or endtoken is None)):  # endtoken None to indicate EOF
            if utils.peek_at_least(f, 7)[0:7] == b'stream\n' or utils.peek_at_least(f, 8)[0:8] == b'stream\r\n':
                f.seek(inner_content_pos, io.SEEK_SET)
                streamObj = PdfStreamObject.create_from_file(f, doc)
                utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
                token, endtoken = utils.read_until(f, syntax.DELIMS + syntax.WHITESPACES, maxsize=7)
                if not (token == b'endobj' and (endtoken != b'' or endtoken is None)):
                    f.seek(org_pos, io.SEEK_SET)
                    raise Exception(f'Parse Error: Not a valid indirect object at offset {org_pos}.')
                inner_obj = streamObj
                if streamObj.dict.get('Type') == 'ObjStm': # Object Stream, decode and parse the content
                    objbytestream = io.BufferedReader(io.BytesIO(streamObj.decode()))
                    # N pairs of integers 
                    # 1st int is obj no of the compressed object 
                    # 2nd int is byte offset of that object, relative to the first obj
                    objbytestream.seek(0, io.SEEK_SET)
                    utils.seek_until(objbytestream, syntax.NON_WHITESPACES, ignore_comment=True)
                    numbers = []
                    N = 0
                    First = 0
                    try:
                        N = int(str(streamObj.dict['N'].value))
                        First = int(str(streamObj.dict['First'].value))
                        if N < 0 or First < 0:
                            raise Exception(f'Invalid N or First field in ObjStm at offset {org_pos}.')
                    except Exception as ex:
                        raise Exception(f'Invalid N or First field in ObjStm at offset {org_pos}.') from ex
                    for _ in range(2 * N):
                        utils.seek_until(objbytestream, syntax.NON_WHITESPACES, ignore_comment=True)
                        numobj = PdfNumericObject.create_from_file(objbytestream)
                        try:
                            temp = int(str(numobj.value))
                            if temp < 0:
                                raise Exception(f'Invalid obj no./offset in ObjStm at offset {org_pos}.')
                            numbers += [temp]
                        except Exception as ex:
                            raise Exception(f'Invalid ObjStm at offset {org_pos}.') from ex
                    for idx, p in enumerate(utils.chunks(numbers, 2)):
                        # gen no, of object stream and of any compressed object is implicitly 0
                        objbytestream.seek(First + p[1], io.SEEK_SET)
                        doc.compressed_obj[obj_no,idx] = PdfIndirectObject(PdfObject.create_from_file(objbytestream, doc) , p[0], 0)
                        # TODO: check for orphaned bytes between compressed objectes?
                        
            else:
                f.seek(org_pos, io.SEEK_SET)
                raise Exception(f'Parse Error: Not a valid indirect object at offset {org_pos}.')
        else:
            f.seek(6, io.SEEK_CUR)
        
        return PdfIndirectObject(inner_obj, obj_no, gen_no)

class PdfStreamObject(PdfObject):
    def __init__(self, stream_dict: PdfDictionaryObject, raw_stream: bytes):
        self.dict = stream_dict
        self.raw_stream = raw_stream
        self.decoded_stream = None
    
    def decode(self) -> bytes:
        import decode
        if self.decoded_stream is not None:
            return self.decoded_stream
        
        if self.dict.get('Filter') is None:
            self.decoded_stream = self.raw_stream
            return self.decoded_stream
        
        # /Filter array is just like matrix multiplication to ENCODE
        # 1st filter is the last to be applied, and therefore 1st to be used for DECODE
        filters = self.dict['Filter']
        if isinstance(filters, PdfArrayObject):
            filters = filters.value
        if isinstance(filters, PdfNameObject):
            filters = [filters]
        # DecodeParms must be a single dict if there is only 1 filter
        # or a array of dict/null
        filters_params = self.dict.get('DecodeParms')
        if isinstance(filters_params, PdfDictionaryObject):
            filters_params = [filters_params]
        if isinstance(filters_params, PdfArrayObject):
            filters_params = filters_params.values
        
        self.decoded_stream = self.raw_stream
        for i, filt in enumerate(filters): # filters is now list of PdfNameObject
            decoder = getattr(decode, filt.get_name(), None)
            if decoder is None:
                raise Exception(f'Unrecognized decoder {filt.get_name()}')
            self.decoded_stream = decoder(self.decoded_stream, filters_params[i] if filters_params else None)
        
        return self.decoded_stream
    
    def write_to_file(self, f: io.BufferedReader):
        pass

    @classmethod
    def create_from_file(cls, f: io.BufferedReader, doc):
        org_pos = f.tell()
        
        stream_dict = PdfObject.create_from_file(f, doc)
        utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)

        if not (utils.peek_at_least(f, 7)[0:7] == b'stream\n' or utils.peek_at_least(f, 8)[0:8] == b'stream\r\n'):
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f'Parse Error: Not a valid stream object at offset {org_pos}.')
        token, _ = utils.read_until(f, syntax.DELIMS + syntax.WHITESPACES)
        utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)

        # check if dict has the required key /Length with valid values
        if not isinstance(stream_dict, PdfDictionaryObject):
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f'Parse Error: Not a valid stream object at offset {org_pos}.')
        if stream_dict.get('Length') is None or not isinstance(stream_dict.get('Length'), PdfNumericObject):
            raise Exception(f'Parse Error: Not a valid stream object at offset {org_pos}.')
        
        size = stream_dict['Length'].value
        if size.as_integer_ratio()[0] <= 0 or size.as_integer_ratio()[1] != 1:
            raise Exception(f'Parse Error: Not a valid stream object at offset {org_pos}.')
        size = size.as_integer_ratio()[0]

        # check for filters
        filt = None
        if stream_dict.get('Filter') is not None:
            filt = stream_dict['Filter']
            if isinstance(filt, PdfArrayObject):
                if any(not isinstance(x, PdfNameObject) for x in filt.value):
                    raise Exception(f'Parse Error: Not a valid stream object at offset {org_pos}.')
                filt = filt.value[0]
            # /Filter (or first element of the array) must specify a Name
            if not isinstance(filt, PdfNameObject):
                raise Exception(f'Parse Error: Not a valid stream object at offset {org_pos}.')
            
        # read only /Length bytes
        # filter implementation is reponsible for checking if the data length is correct
        # e.g. if any needed end-of-data marker is present at only the end
        raw = f.read(size)
        

        # check if stream ends with b'endstream', optionally preceeded by b'\r', 'b'\n' or b'\r\n'
        if utils.peek_at_least(f, 2)[0:2] == b'\r\n':
            f.seek(2, io.SEEK_CUR)
        elif utils.peek_at_least(f, 1)[0:1] == b'\r' or utils.peek_at_least(f, 1)[0:1] == b'\n':
            f.seek(1, io.SEEK_CUR)    
        token, _ = utils.read_until(f, syntax.DELIMS + syntax.WHITESPACES)
        if token != b'endstream':
            raise Exception(f'Parse Error: Not a valid stream object at offset {org_pos}.')

        # actual decoding is done in constructor
        return PdfStreamObject(stream_dict, raw)

class PdfReferenceObject(PdfObject):
    def __init__(self, doc, obj_no: int, gen_no: int):
        if obj_no - int(obj_no) != 0 or gen_no - int(gen_no) != 0:
            raise ValueError('obj number and generation number must be integer')
        self.doc = doc
        self.obj_no = obj_no
        self.gen_no = gen_no
    
    @property
    def value(self):
        return self.doc.get_obj(self.obj_no, self.gen_no)
    
    def __repr__(self):
        return f'PdfReferenceObject(obj_no={self.obj_no}, gen_no={self.gen_no})'
    
    def __str__(self):
        return f'{self.obj_no} {self.gen_no} R'

        
    def write_to_file(self, f: io.BufferedReader):
        # TODO: 
        pass

    
    @classmethod
    def create_from_file(cls, f: io.BufferedReader, doc):
        org_pos = f.tell()
        num, _ = utils.read_until(f, syntax.WHITESPACES)
        if re.match(rb'\d+$', num) is None:
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f'Parse Error: Not a valid reference at offset {org_pos}.')
        obj_no = int(num)
        utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
        num, _ = utils.read_until(f, syntax.WHITESPACES)
        if re.match(rb'\d+$', num) is None:
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f'Parse Error: Not a valid reference at offset {org_pos}.')
        gen_no = int(num)
        utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
        tok, _ = utils.read_until(f, syntax.DELIMS + syntax.WHITESPACES)
        if tok != b'R':
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f'Parse Error: Not a valid reference at offset {org_pos}.')
        return PdfReferenceObject(doc, obj_no, gen_no)

class PdfNullObject(PdfObject):
    """The null object has a type and value that are unequal to those of any other object. There is only one object of type null, denoted by the keyword null."""
    
    def write_to_file(self, f: io.BufferedReader):
        f.write(b'null')
    
    def __eq__(self, other):
        return False
    
    def __repr__(self):
        return 'PdfNullObject()'
    
    def __str__(self):
        return 'null'
    
    @classmethod
    def create_from_file(cls, f: io.BufferedReader):
        org_pos = f.tell()
        token: bytes = f.read(4)
        if token != b'null':
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f'Parse Error: Not a valid null object at offset {org_pos}.')
        return PdfNullObject()

