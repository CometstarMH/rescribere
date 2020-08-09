import io
import os
import utils
import syntax
from decimal import Decimal
import re
from objects import PdfObject, PdfDictionaryObject, PdfReferenceObject, PdfStreamObject, PdfIndirectObject, val
from xref import PdfXRefSection
from collections import OrderedDict

class PdfDocument:
    @property
    def startxref(self):
        '''Get or set the byte offset from the beginning of the file to the beginning of the 'xref' keyword in the last, i.e. the most current, cross-reference section.'''
        return self.__startxref__

    @startxref.setter
    def startxref(self, value):
        if not isinstance(value, int) or value < 0:
            raise ValueError('startxref must be non-positive integer')
        else:
            self.__startxref__ = value

    @property
    def version(self):
        '''Get or set the version of the PDF specification to which this file conforms.

        Beginning with PDF 1.4, this value can be overridden by the Version entry in the document's catalog dictionary'''
        return self.__version__

    @version.setter
    def version(self, value):
        if not isinstance(value, Decimal):
            raise ValueError('Version must be a Decimal')
        else:
            self.__version__ = value

    def get_obj(self, obj_num, gen_num):
        if not self.ready:
            raise Exception('get_obj can only be called after the document is scanned completely.')
        startxref_found = False
        startxref = -1
        for increment in range(len(self.increments)):
            increment = -(increment + 1) # increment from -1 to -len
            xref_section = self.increments[increment]['xref_section']

            offset = xref_section.get_obj_offset(obj_num, gen_num)
            if offset is None:
                # offset is None <=> obj_num not found
                continue
            elif isinstance(offset, tuple):
                # TODO: handle the case where obj is not already cached
                return self.compressed_obj[offset]
            elif offset > 0:
                if self.offset_obj.get(offset) is None:
                    temp_f = open(self.__f.name, 'rb')
                    temp_f.seek(offset, io.SEEK_SET)
                    self.offset_obj[offset] = PdfObject.create_from_file(temp_f, self)
                return self.offset_obj[offset]
            elif offset == 0:
                # offset = 0 <=> obj_num is free at gen_num
                return None

        raise Exception('Object not found')

    def get_trailer_dict(self, increment=-1):
        if not self.ready:
            raise Exception('get_trailer_dict can only be called after the document is scanned completely.')
        return self.increments[increment]['trailer']

        # isXRefStm = False
        # startxref = self.increments[increment]['startxref']
        # try:
        #     # TODO: assuming Type has direct obj value
        #     isXRefStm = self.offset_obj[startxref].value.dict['Type'] == 'XRef'
        # except Exception as ex:
        #     raise Exception('startxref refers to an object, but it is not a XRef stream') from ex
        # if isXRefStm:
        #     # The trailer dictionary entries are stored in the stream dictionary
        #     return self.offset_obj[startxref].value.dict
        # else:
        #     if self.increments[increment]['trailer'] is None:
        #         raise Exception('No trailer is found is increment ' + str(increment))
        #     return self.increments[increment]['trailer']

    def get_catalog(self, increment=-1):
        if not self.ready:
            raise Exception('get_catalog can only be called after the document is scanned completely.')
        return self.get_trailer_dict(increment)['Root'].deref() # Root value must be indirect ref

    def get_page_dict(self, pageIndex, increment=-1):
        if not self.ready:
            raise Exception('get_page_dict can only be called after the document is scanned completely.')
        current_page = 0
        cat = self.get_catalog(increment)
        queue = []
        queue.append(cat['Pages'].deref())
        while len(queue) > 0:
            visit = queue.pop()
            if visit['Type'] == 'Pages':
                if current_page + visit['Count'] > pageIndex:
                    for x in reversed(visit['Kids'].value):
                        # Kids is array of indrect ref
                        queue.append(x.deref() if isinstance(x, PdfReferenceObject) else x)
                    continue
                else:
                    current_page += visit['Count']
                    continue
            elif visit['Type'] == 'Page':
                if current_page == pageIndex:
                    return visit
                current_page += 1
                continue
            else:
                raise Exception('invalid Pages dictionary')
        return None

    def get_all_page_dicts(self):
        if not self.ready:
            raise Exception('get_all_page_dict can only be called after the document is scanned completely.')
        current_page = 0
        cat = self.get_catalog().value
        pages = []
        queue = []
        queue.append(cat['Pages'].deref()) # category_dict.Pages must be indirect ref
        while len(queue) > 0:
            visit = queue.pop()
            if visit['Type'] == 'Pages':
                for x in reversed(visit['Kids'].value): # Kids value is an array of indirect ref => x is indirect ref
                    queue.append(x.deref() if isinstance(x, PdfReferenceObject) else x)
            elif visit['Type'] == 'Page':
                pages.append(visit)
                current_page += 1
                continue
            else:
                raise Exception('invalid Pages dictionary')
        return pages

    def __init__(self, f, progress_cb):
        self.increments = [{ 'body': [], 'xref_section': None, 'trailer': None, 'startxref': None, 'eof': False }]
        self.offset_obj = {} # [offset]: obj
        self.compressed_obj = {} # [objstmobj_no, idx]: decompressed_obj
        self.startxref = 0
        self.offset_obj_streams = {} # [offset]: objstm
        self.offset_xref = {}
        self.ready = False
        self.offset_xref_trailer = {} # [offset]: (PdfXRefSection, trailer_dict)
        self.__f = f
        self.parse_normal(f, progress_cb)

    def get_xref_trailer_at_offset(self, f, offset):
        # read xref, trailer should directly follow, and MUST be read TOGETHER with xref
        # linearized PDF specified the last appering trailer DOES NOT have Prev entry, and startxref points to 1st page xref table near start of file
        # which has its own trailer, making the last trailer technically the 'first' trailer
        # therefore, searching for trailer dict from end of file would get the wrong trailer dict
        # moreover, in a xref stream, the xref and trailer dict is lumped together as the stream object
        if offset in self.offset_xref_trailer:
            return self.offset_xref_trailer[offset]
        f.seek(offset, io.SEEK_SET)
        temp, _ = utils.read_until(f, syntax.EOL)
        f.seek(offset, io.SEEK_SET)
        # TODO: catch exception for parsing PdfXRefSection
        if temp == b'xref':
            # uncompressed xref section
            utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
            xref_section = PdfXRefSection(f)
            # find trailer dict and Prev
            # trailer dict CAN contain references
            utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
            temp, _ = utils.read_until(f, syntax.EOL)
            if temp == b'trailer':
                utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
                trailer_dict = PdfDictionaryObject.create_from_file(f, self)
                self.offset_xref_trailer[offset] = (xref_section, trailer_dict)
            else:
                # TODO: check for objects between xref and trailer dict, and between trailer dict and startxref?
                raise Exception(f'trailer dict not found after xref table at {f.tell() - 7}')
        else:
            # may be compressed xref stream
            # trailer dict IS the stream dict, and CANNOT contain references
            try:
                xref_stream = PdfIndirectObject.create_from_file(f, self)
            except Exception as ex:
                raise Exception('Invalid xref stream') from ex
            xref_section = PdfXRefSection.from_xrefstm(xref_stream)
            self.offset_xref_trailer[offset] = (xref_section, xref_stream.value.dict)

        return self.offset_xref_trailer[offset]

    def parse_normal(self, f, progress_cb=None):
        '''Initialize a PdfDocument from a opened PDF file f by reading xref and trailers. After this is called, offset_obj, offset_obj_streams, compressed_obj, offset_xref_trailer, all xref sections are ready'''
        f.seek(0, io.SEEK_SET)
        filesize = os.fstat(f.fileno()).st_size
        # First line is header
        s, eol_marker = utils.read_until(f, syntax.EOL)
        header = re.match(rb'%PDF-(\d+\.\d+)', s)
        if header:
            self.version = Decimal(header.group(1).decode('iso-8859-1'))
            f.seek(len(eol_marker), io.SEEK_CUR)
        else:
            raise Exception('Not a PDF file')

        # read from end of file, find xref
        eof_found = -1
        startxref_found = -1
        temp_line = b''
        temp_count = 2
        temp_offset = 0
        for line in utils.rlines(f):
            temp_offset -= len(line)
            if line.rstrip() == b'%%EOF':
                eof_found = temp_offset
            if eof_found != -1 and temp_count == 0:
                if line.rstrip() == b'startxref':
                    startxref_found = temp_offset
                    break
                else:
                    raise Exception('startxref not found at 2 lines before EOF marker')
            elif eof_found != -1:
                temp_count -= 1
                temp_line = line
        xref_offset = int(temp_line.decode('iso-8859-1'))
        self.startxref = xref_offset
        # The only required part for a trailer (and marks the end of an increment) is startxref and %%EOF
        self.increments[-1]['startxref'] = xref_offset
        self.increments[-1]['eof'] = True

        inuse_count = 0
        while True:
            f.seek(xref_offset, io.SEEK_SET)
            xref_section, trailer = self.get_xref_trailer_at_offset(f, xref_offset)
            self.offset_xref_trailer[xref_offset] = (xref_section, trailer)
            for subsec in xref_section.subsections:
                inuse_count += len(subsec.inuse_entry)
            self.increments[0]['xref_section'] = xref_section
            self.increments[0]['trailer'] = trailer
            if trailer.get('Prev') is None:
                break
            if trailer['Prev'].value - int(trailer['Prev'].value) != 0:
                raise Exception(f'Prev must be an integer, in trailer dict at offset {xref_offset}')
            xref_offset = int(trailer['Prev'].value) # must not be indirect
            self.increments = [{ 'body': [], 'xref_section': None, 'trailer': None, 'startxref': None, 'eof': False }] + self.increments
            self.increments[0]['startxref'] = xref_offset
        self.ready = True

        inuse_parsed_count = 0
        # parse each in use obj num
        for inc in self.increments:
            for subsec in inc['xref_section'].subsections:
                for entry in subsec.inuse_entry:
                    if entry.get('compressed'):
                        inuse_parsed_count += 1
                        continue
                    offset = entry['offset']
                    f.seek(offset, io.SEEK_SET)
                    new_obj = PdfObject.create_from_file(f, self)
                    if not isinstance(new_obj, PdfIndirectObject) or new_obj.obj_no != entry['obj_no'] or new_obj.gen_no != entry['gen_no']:
                        raise Exception(f'Invalid obj referenced by xref at offset {offset}')
                    self.offset_obj[offset] = new_obj
                    if isinstance(new_obj.value, PdfStreamObject) and new_obj.value.dict.get('Type') == 'ObjStm':
                        self.offset_obj_streams[offset] = new_obj
                    inuse_parsed_count += 1
                    print('', end="\r")
                    print(f'{inuse_parsed_count / inuse_count * 100:5.2f}% processed', end='', flush=True)
                    if progress_cb is not None: progress_cb(f'{inuse_parsed_count / inuse_count * 100:5.2f}% processed', read=inuse_parsed_count, total=inuse_count)

        print('Decoding object streams...')
        if progress_cb is not None: progress_cb('Decoding object streams...', read=inuse_parsed_count, total=inuse_count)
        for k in self.offset_obj_streams:
            from objstm import decode_objstm
            self.compressed_obj = { **(self.compressed_obj), **(decode_objstm(self.offset_obj_streams[k], self)) }
        print('', end="\r")
        print('100% processed    ')
        if progress_cb is not None: progress_cb('100% processed', read=inuse_parsed_count, total=inuse_count)
        print('Done')
        if progress_cb is not None: progress_cb('Done', read=inuse_parsed_count, total=inuse_count)

    def parse_linear(self, f, progress_cb=None):
        '''Initialize a PdfDocument from a opened PDF file f from the beginning'''
        def print_progress():
            print('', end="\r")
            print(f'{f.tell() / filesize * 100:5.2f}% processed', end='', flush=True)
            if progress_cb is not None: progress_cb(f'{f.tell() / filesize * 100:5.2f}% processed', read=f.tell(), total=filesize)

        f.seek(0, io.SEEK_SET)
        filesize = os.fstat(f.fileno()).st_size

        print_progress()

        # First line is header
        s, eol_marker = utils.read_until(f, syntax.EOL)
        header = re.match(rb'%PDF-(\d+\.\d+)', s)
        if header:
            self.version = Decimal(header.group(1).decode('iso-8859-1'))
            f.seek(len(eol_marker), io.SEEK_CUR)
        else:
            raise Exception('Not a PDF file')

        while True:
            utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=False)
            if f.tell() >= filesize:
                break
            org_pos = f.tell()
            s, eol_marker = utils.read_until(f, syntax.EOL)
            if s == b'startxref': # the last startxref always override the ones before
                utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
                t, _ = utils.read_until(f, syntax.EOL)
                self.startxref = int(t)
                self.increments[-1]['startxref'] = self.startxref
                continue
            elif s == b'xref':
                f.seek(-4, io.SEEK_CUR)
                self.increments[-1]['xref_section'] = PdfXRefSection(f)
                self.offset_xref[org_pos] = self.increments[-1]['xref_section']
                continue
            elif s == b'trailer':
                utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
                self.increments[-1]['trailer'] = PdfDictionaryObject.create_from_file(f, self)
                continue
            elif s == b'%%EOF':
                # TODO: check if trailer dict immediately precedes %%EOF
                # since we are seeking until non-ws, the only case EOF marker
                # does not appear by itself it when it is preceded by some
                # whitespaces, which should be ignored
                self.increments[-1]['eof'] = True
                f.seek(5 + len(eol_marker), io.SEEK_CUR)
                continue
            elif s[0:1] == b'%':
                # otherwise, it is a comment, ignore the whole remaining line
                utils.seek_until(f, syntax.EOL)
                continue
            #else:

            f.seek(org_pos, io.SEEK_SET)
            if self.increments[-1]['eof']:
                self.increments += [{ 'body': [], 'xref_section': None, 'trailer': None, 'startxref': None, 'eof': False }]

            # TODO: how to handle object parse error?
            new_obj = PdfObject.create_from_file(f, self)
            self.increments[-1]['body'] += [new_obj]
            self.offset_obj[org_pos] = new_obj
            if isinstance(new_obj.value, PdfStreamObject) and new_obj.value.dict.get('Type') == 'ObjStm':
                self.offset_obj_streams[org_pos] = new_obj
            print_progress()

        print('', end="\r")
        print('100% processed    ')
        if progress_cb is not None: progress_cb('100% processed', read=f.tell(), total=filesize)
        self.ready = True

        print('Decoding object streams...')
        if progress_cb is not None: progress_cb('Decoding object streams...', read=f.tell(), total=filesize)
        for k in self.offset_obj_streams:
            from objstm import decode_objstm
            self.compressed_obj = { **(self.compressed_obj), **(decode_objstm(self.offset_obj_streams[k], self)) }
        print('Done')
        if progress_cb is not None: progress_cb('Done', read=f.tell(), total=filesize)




    def __repr__(self):
        version_str = f'version={self.version}'
        startxref_str = f'startxref={self.startxref}'
        result = f'PdfDocument(\n\t{version_str},\n\t{startxref_str},\n\t'
        body_repr = ''
        for increment in self.increments:
            body_repr += 'body=[\n\t\t'
            for obj in increment['body']:
                body_repr += f'{repr(obj)},\n\t\t'
            body_repr += f'\b],\n\ttrailer={increment["trailers"]},\n\t'
        result += body_repr + ')'
        return result

    def __str__(self):
        version_str = f'%PDF-{self.version}'
        body_repr = ''
        for increment in self.increments:
            for obj in increment['body']:
                body_repr += str(obj) + '\n'
        return f'{version_str}\n{body_repr}'



