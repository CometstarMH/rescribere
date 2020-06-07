import utils
import io
import re
import syntax
import collections.abc

class PdfXRefSection(collections.abc.Sequence):
    def __init__(self, f):
        '''Initialize a PdfXRefSection from a opened PDF file f. 
        
        The file object’s current position should be at the beginning of the 
        line with the sole keyword 'xref' '''
        self.subsections = []
        org_pos = f.tell()
        s, eol_marker = utils.read_until(f, syntax.EOL)
        if s != b'xref':
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f"cross-reference section should begin with keyword 'xref' at offset {org_pos}")
        f.seek(len(eol_marker), io.SEEK_CUR)
        # Following 'xref' line are one or more cross-reference subsections
        while True:
            s, eol_marker = utils.read_until(f, syntax.EOL)
            matches = re.match(rb'^\s*(\d+)\s+(\d+)\s*$', s)
            f.seek(-len(s), io.SEEK_CUR)
            if matches:
                # start of subsection
                self.subsections += [PdfXRefSubSection(f)]
            else:
                break

    
    def __getitem__(self, key):
        pass

    def __len__(self):
        pass

class PdfXRefSubSection(collections.abc.Sequence):
    def __init__(self, f):
        '''Initialize a PdfXRefSubSection from a opened PDF file f. 

        The file object’s current position should be at the line with two 
        numbers, object number of the first object in this subsection and the 
        umber of entries, separated by a space'''
        self.inuse_entry = []
        self.free_entry = []
        org_pos = f.tell()
        s, eol_marker = utils.read_until(f, syntax.EOL)
        matches = re.match(rb'^\s*(\d+)\s+(\d+)\s*$', s)
        if matches is None:
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f"cross-reference subsection should begin with two numbers at offset {org_pos}")
        self.first_objno = int(matches.group(1))
        count = int(matches.group(2))
        if self.first_objno < 0 or count < 0:
            f.seek(org_pos, io.SEEK_SET)
            raise Exception(f"cross-reference subsection at offset {org_pos} has invalid object number or object count")

        f.seek(len(eol_marker), io.SEEK_CUR)
        # Each entry is exactly 20 bytes long, including EOL marker. 
        for i in range(count):
            entry = f.read(20)
            current_obj_no = self.first_objno + i
            # nnnnnnnnnn ggggg n/f
            matches = re.match(rb'^(\d{10})\s(\d{5})\s([nf])(?: \r| \n|\r\n)', entry)
            if matches is None:
                f.seek(org_pos, io.SEEK_SET)
                raise Exception(f"cross-reference subsection contains an invalid entry at offset {f.tell() - 20}")
            # obj no 0 is always free and has a generation number of 65535
            if current_obj_no == 0 and int(matches.group(2)) != 65535:
                f.seek(org_pos, io.SEEK_SET)
                raise Exception(f"cross-reference subsection contains an invalid entry at offset {f.tell() - 20}")
            # in-use entry: 1st 10-digit number is byte offset, free entry: 1st 10-digit number is an obj no of the next free object
            if matches.group(3) == b'n':
                self.inuse_entry += [{'obj_no': current_obj_no, 'gen_no': int(matches.group(2)), 'used': True, 'offset': int(matches.group(1))}]
            elif matches.group(3) == b'f':
                if (len(self.free_entry) > 0 and self.free_entry[-1]['next_free_obj_no'] != current_obj_no):
                    f.seek(org_pos, io.SEEK_SET)
                    raise Exception(f"cross-reference subsection contains an invalid entry at offset {f.tell() - 20}")
                self.free_entry += [{'obj_no': current_obj_no, 'gen_no': int(matches.group(2)), 'used': False, 'next_free_obj_no': int(matches.group(1))}]
            else:
                f.seek(org_pos, io.SEEK_SET)
                raise Exception(f"cross-reference subsection contains an invalid entry at offset {f.tell() - 20}")
            # last free entry (the tail of the linked list) links back to obj no 0 
            if len(self.free_entry) > 0 and self.free_entry[-1]['next_free_obj_no'] != 0:
                f.seek(org_pos, io.SEEK_SET)
                raise Exception(f"cross-reference subsection contains an invalid entry at offset {f.tell() - 20}")
    
    def __getitem__(self, key):
        pass

    def __len__(self):
        pass




            



