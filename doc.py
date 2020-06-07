import io
import os
import utils
import syntax
from decimal import Decimal
import re
from objects import PdfObject, PdfDictionaryObject
from xref import PdfXRefSection

class PdfDocument:
    @property
    def startxref(self):
        '''Get or set the byte offset from the beginning of the file to the beginning of the 'xref' keyword in the last, i.e. the most current, cross-reference section.'''
        return self.__startxref
    
    @startxref.setter
    def startxref(self, value):
        if not isinstance(value, int) or value < 0:
            raise ValueError('startxref must be non-positive integer')
        else:
            self.__startxref = value

    @property
    def version(self):
        '''Get or set the version of the PDF specification to which this file conforms. 

        Beginning with PDF 1.4, this value can be overridden by the Version entry in the document's catalog dictionary'''
        return self.__version

    @version.setter
    def version(self, value):
        if not isinstance(value, Decimal):
            raise ValueError('Version must be a Decimal')
        else:
            self.__version = value
    
    def __init__(self, f):
        '''Initialize a PdfDocument from a opened PDF file f from the beginning'''
        def print_progress():
            print('', end="\r")
            print(f'{f.tell() / filesize * 100:5.2f}% processed', end='', flush=True)

        f.seek(0, io.SEEK_SET)
        filesize = os.fstat(f.fileno()).st_size
        print_progress()

        self.body = []
        self.xref_sections = []
        self.trailers = []

        # First line is header
        s, _ = utils.read_until(f, syntax.EOL)
        temp = re.match(rb'%PDF-(\d+\.\d+)', s)
        if temp:
            self.version = Decimal(temp.group(1).decode('iso-8859-1'))
        else:
            raise Exception('Not a PDF file')

        while True:
            utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
            if f.tell() >= filesize:
                break
            org_pos = f.tell()
            s, _ = utils.read_until(f, syntax.EOL)
            if s == b'startxref': # the last startxref always override the ones before
                utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
                t, _ = utils.read_until(f, syntax.EOL)
                self.startxref = int(t)
                continue
            elif s == b'xref':
                f.seek(-4, io.SEEK_CUR)
                self.xref_sections += [PdfXRefSection(f)]
                print(f'now at {f.tell()}')
                continue
            elif s == b'trailer':
                utils.seek_until(f, syntax.NON_WHITESPACES, ignore_comment=True)
                self.trailers += [PdfDictionaryObject.create_from_file(f, self)]
                continue
            else:
                f.seek(org_pos, io.SEEK_SET)
            self.body += [PdfObject.create_from_file(f, self)]
            print_progress()
        
        print('', end="\r")
        print('100% processed')
        #print(self.body)
        print(f'{self.body[-1]}')
        

    def __repr__(self):
        version_str = f'version={self.version}'
        startxref_str = f'startxref={self.startxref}'
        body_repr = ''
        for obj in self.body:
            body_repr += repr(obj) + '\n\t\t'
        return f'PdfDocument(\n\t{version_str},\n\t{startxref_str},\n\tbody=[\n\t\t{body_repr}\b])'
    
    def __str__(self):
        version_str = f'%PDF-{self.version}'
        body_repr = ''
        for obj in self.body:
            body_repr += str(obj) + '\n'
        return f'{version_str}\n{body_repr}'

    
    def get_obj(self, obj_num, gen_num):
        pass

