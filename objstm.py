from objects import PdfStreamObject, PdfNumericObject, PdfIndirectObject, PdfObject
import io
import utils
import syntax

def decode_objstm(objstmobj, doc):
    result = {}
    streamObj = objstmobj.value
    objstmobj_no = objstmobj.obj_no
    if not isinstance(streamObj, PdfStreamObject):
        raise ValueError('objstmobj is not a PdfIndirectObject containing a PdfStreamObject')

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
        # TODO: assuming both N and First have direct obj values
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
        result[objstmobj_no,idx] = PdfIndirectObject(PdfObject.create_from_file(objbytestream, doc) , p[0], 0)
        # TODO: check for orphaned bytes between compressed objectes?

    return result