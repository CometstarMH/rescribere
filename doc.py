import io
import os
import utils
import syntax
from decimal import Decimal
import re
from objects import PdfObject, PdfDictionaryObject, PdfReferenceObject, PdfStreamObject
from xref import PdfXRefSection

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
        if self.offset_obj[self.startxref] is not None:
            try:
                isXRefStm = self.offset_obj[self.startxref].value.dict['Type'] == 'XRef'
                if not isXRefStm:
                    raise Exception('')
            except Exception as ex:
                raise Exception('startxref refers to an object, but it is not a XRef stream') from ex
            # XRef streams are stream objects, which is indirect 
            xrefstm: PdfStreamObject = self.offset_obj[self.startxref].value

        for section in self.increments[-1]['xref_sections']:
            offset = section.get_obj_offset(obj_num, gen_num)
            if offset is None:
                continue
            elif offset > 0:
                return self.offset_obj[0]
        return None
    
    def get_trailer(self, increment=-1):
        pass

    def get_catalog(self, increment=-1):
        return self.get_trailer(increment)['Root'].value # indirect ref

    def get_page_dict(self, pageIndex, increment=-1):
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
        print_progress()

        self.increments = [{ 'body': [], 'xref_sections': [], 'trailers': [] }]
        self.offset_obj = {}
        self.compressed_obj = {}

        # First line is header
        s, eol_marker = utils.read_until(f, syntax.EOL)
        header = re.match(rb'%PDF-(\d+\.\d+)', s)
        if header:
            self.version = Decimal(header.group(1).decode('iso-8859-1'))
            f.seek(len(eol_marker), io.SEEK_CUR)
        else:
            raise Exception('Not a PDF file')

        eof_found = False
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
                continue
            elif s == b'xref':
                f.seek(-4, io.SEEK_CUR)
                self.increments[-1]['xref_sections'] += [PdfXRefSection(f)]
                continue
            elif s == b'trailer':
                utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
                self.increments[-1]['trailers'] += [PdfDictionaryObject.create_from_file(f, self)]
                continue
            elif s == b'%%EOF': 
                # since we are seeking until non-ws, the only case EOF marker 
                # does not appear by itself it when it is preceded by some 
                # whitespaces, which should be ignored
                eof_found = True
                f.seek(5 + len(eol_marker), io.SEEK_CUR)
                continue
            elif s[0:1] == b'%':
                # otherwise, it is a comment, ignore the whole remaining line
                utils.seek_until(f, syntax.EOL)
                continue
            else:
                f.seek(org_pos, io.SEEK_SET)
                if eof_found:
                    self.increments += [{ 'body': [], 'xref_sections': [], 'trailers': [] }]
                    eof_found = False
            
            self.increments[-1]['body'] += [PdfObject.create_from_file(f, self)]
            self.offset_obj[org_pos] = self.increments[-1]['body'][-1]
            print_progress()
        
        print('', end="\r")
        print('100% processed')
        

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

    

