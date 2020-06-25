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
            section = None
            startxref = self.increments[increment]['startxref']
            # skip increment if it is not ended by %%EOF
            if self.increments[increment]['eof']:
                startxref_found = True
                break
        if not startxref_found or startxref < 0:
            raise Exception('No valid startxref is found')
        while True:
            if startxref == 0:
                # TODO: dummy startxref?
                return None
            # check if the xref is either in raw/has been uncompressed
            if startxref not in self.offset_xref:
                try:
                    isXRefStm = self.offset_obj[startxref].value.dict['Type'] == 'XRef'
                    if not isXRefStm:
                        raise Exception('')
                except Exception as ex:
                    raise Exception('startxref refers to an object, but it is not a XRef stream') from ex
                # XRef streams are stream objects, which is indirect 
                xrefstm: PdfStreamObject = self.offset_obj[startxref]
                section = PdfXRefSection.from_xrefstm(xrefstm)
                # Cache the decoded xrefstm
                self.offset_xref[self.increments[increment]['startxref']] = section
            else:
                section = self.offset_xref[startxref]
            
            offset = section.get_obj_offset(obj_num, gen_num)
            if isinstance(offset, tuple):
                return self.compressed_obj[offset]
            if offset > 0:
                return self.offset_obj[offset]
            elif offset == 0:
                # offset = 0 <=> obj_num is free at gen_num
                return None
            else:
                # offset is None <=> obj_num not found
                trailer_dict = get_trailer_dict(increment)
                startxref = trailer_dict.get('Prev')
                # TODO: assuming Prev has direct object value
                if startxref is not None and isinstance(startxref, PdfNumericObject):
                    # TODO: converting from decimal directly to int
                    startxref = int(startxref.value)
                else:
                    break
                if startxref < 0:
                    break
        raise Exception('Object not found')
    
    def get_trailer_dict(self, increment=-1):
        if not self.ready:
            raise Exception('get_trailer_dict can only be called after the document is scanned completely.')
        
        isXRefStm = False
        startxref = self.increments[increment]['startxref']
        try:
            # TODO: assuming Type has direct obj value
            isXRefStm = self.offset_obj[startxref].value.dict['Type'] == 'XRef'
        except Exception as ex:
            raise Exception('startxref refers to an object, but it is not a XRef stream') from ex
        if isXRefStm:
            # The trailer dictionary entries are stored in the stream dictionary
            return self.offset_obj[startxref].value.dict
        else:
            return self.increments[increment]['trailers']

    def get_catalog(self, increment=-1):
        if not self.ready:
            raise Exception('get_catalog can only be called after the document is scanned completely.')
        return self.get_trailer_dict(increment)['Root'].value # indirect ref

    def get_page_dict(self, pageIndex, increment=-1):
        if not self.ready:
            raise Exception('get_page_dict can only be called after the document is scanned completely.')
        current_page = 0
        cat = self.get_catalog(increment)
        queue = []
        queue.append(cat['Pages'].value) # category dict.Pages is indirect ref
        while len(queue) > 0:
            visit = queue.pop()
            if visit['Type'] == 'Pages':
                if current_page + visit['Count'] > pageIndex:
                    for x in reversed(visit['Kids'].value):
                        # Kids is array of indrect ref
                        queue.append(x.value if isinstance(x, PdfReferenceObject) else x)
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
    
    def __init__(self, f):
        '''Initialize a PdfDocument from a opened PDF file f from the beginning'''
        def print_progress():
            print('', end="\r")
            print(f'{f.tell() / filesize * 100:5.2f}% processed', end='', flush=True)

        f.seek(0, io.SEEK_SET)
        filesize = os.fstat(f.fileno()).st_size

        self.increments = [{ 'body': [], 'xref_sections': {}, 'trailers': None, 'startxref': None, 'eof': False }]
        self.offset_obj = {}
        self.compressed_obj = {}
        self.startxref = 0
        self.offset_obj_streams = {}
        self.offset_xref = {}
        self.ready = False

        # print('Parsing xref sections...')
        # # read backward first, find xref sections and trailers
        # max_offset = None

        # eof_found = -1
        # startxref_found = -1
        # temp_line = b''
        # temp_count = 2
        # temp_offset = 0
        # for i, line in utils.rlines(f, MAX_OFFSET=max_offset):
        #     temp_offset -= len(line)
        #     if line.rstrip() == b'%%EOF':
        #         eof_found = temp_offset
        #     if eof_found != -1 and temp_count == 0:
        #         if line.rstrip() == b'startxref':
        #             startxref_found = temp_offset
        #             break
        #         else:
        #             raise Exception('startxref not found at 2 lines before EOF marker')
        #     elif eof_found != -1:
        #         temp_count -= 1
        #         temp_line = line
        # xref_offset = int(temp_line.decode('iso-8859-1'))
        # # The only require part for a trailer (and marks the end of an increment) is startxref and %%EOF
        # self.increments = [{ 'body': [], 'xref_sections': [], 'trailers': None }] + self.increments

        # f.seek(xref_offset, io.SEEK_SET)
        # xref_section = None
        # need_trailer_dict = False
        # xref_stream = None
        # # TODO: catch exception for parsing PdfXRefSection
        # if utils.read_until(f, syntax.EOL) == b'xref':
        #     # uncompressed xref section
        #     f.seek(xref_offset, io.SEEK_SET)
        #     self.increments[0]['xref_sections'] += [PdfXRefSection(f)]
        #     # find trailer dict and Prev
        #     # immediately preceding startxref line is trailer dict, consisting of the keyword trailer followed by a dict object
        #     # trailer dict CAN contain references
        #     trailer_lines = []
        #     for line in utils.rlines(f, MAX_OFFSET=startxref_found - 1):
        #         if line.rstrip() != b'trailer':
        #             trailer_lines.append(line)
        #         else:
        #             break
        #     trailer_dict = PdfDictionaryObject.create_from_file(io.BufferedReader(io.BytesIO(b''.join(reversed(trailer_lines)))), self)
        #     # TODO: check for objects between xref and trailer dict, and between trailer dict and startxref?
        #     self.increments[0]['trailers'] = trailer_dict
        # else:
        #     # may be compressed xref stream
        #     # trailer dict IS the stream dict, and CANNOT contain references
        #     f.seek(xref_offset, io.SEEK_SET)
        #     try:
        #         xref_stream = PdfIndirectObject.create_from_file(f, self)
        #     except Exception as ex:
        #         raise Exception('Invalid xref stream') from ex
        #     self.offset_obj[org_pos] = new_obj
        #     xref_section = PdfXRefSection.from_xrefstm(xref_stream)
        #     self.increments[0]['xref_sections'] += [xref_section]
        #     self.increments[0]['trailers'] = xref_stream.value.dict
        
        # # find prev %%EOF

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
                self.increments[-1]['xref_sections'][org_pos] = PdfXRefSection(f)
                self.offset_xref[org_pos] = self.increments[-1]['xref_sections'][org_pos]
                continue
            elif s == b'trailer':
                utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
                self.increments[-1]['trailers'] = PdfDictionaryObject.create_from_file(f, self)
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
                self.increments += [{ 'body': [], 'xref_sections': [], 'trailers': None, 'startxref': None, 'eof': False }]
            
            # TODO: how to handle object parse error?
            new_obj = PdfObject.create_from_file(f, self)
            self.increments[-1]['body'] += [new_obj]
            self.offset_obj[org_pos] = new_obj
            if isinstance(new_obj.value, PdfStreamObject) and new_obj.value.dict.get('Type') == 'ObjStm':
                self.offset_obj_streams[org_pos] = new_obj
            print_progress()
        
        print('', end="\r")
        print('100% processed')
        self.ready = True

        print('Decoding object streams...')
        for k in self.offset_obj_streams:
            from objstm import decode_objstm
            self.compressed_obj = { **(self.compressed_obj), **(decode_objstm(self.offset_obj_streams[k], self)) }
        print('Done')

        
        

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

    

