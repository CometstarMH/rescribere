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

        self.increments = [{ 'body': [], 'xref_sections': [], 'trailers': [] }]

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
                print('trailer found!')
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

    
    def get_obj(self, obj_num, gen_num):
        pass

