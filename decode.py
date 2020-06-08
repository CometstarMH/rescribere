import zlib
from enum import IntEnum
from typing import Union, List
from objects import PdfDictionaryObject, PdfNumericObject
from decimal import Decimal
import math

class Predictor(IntEnum):
    NoPrediction = 1
    TIFFPredictor2 = 2
    PNGNone = 10
    PNGSub = 11
    PNGUp = 12
    PNGAvg = 13
    PNGPaeth = 14
    PNGOptimum = 15

def FlateDecode(dataBytes: Union[bytes, bytearray], params: PdfDictionaryObject) -> bytes:
    '''Flate method is based on the public-domain zlib/deflate compression method.'''
    def paethPredictor(left, up, up_left):
        p = left + up - up_left
        dist_left = abs(p - left)
        dist_up = abs(p - up)
        dist_up_left = abs(p - up_left)

        if dist_left <= dist_up and dist_left <= dist_up_left:
            return left
        elif dist_up <= dist_up_left:
            return up
        else:
            return up_left
    
    data = zlib.decompress(dataBytes)
    predictor = Predictor.NoPrediction

    if params:
        try:
            predictor = Predictor(params.get('Predictor', Predictor.NoPrediction).value)
        except AttributeError: # get not exist
            pass
    
    if predictor != Predictor.NoPrediction:
        columns = params.get('Columns', PdfNumericObject(Decimal(1)))
        if not isinstance(columns, PdfNumericObject) or columns.value.as_integer_ratio()[1] != 1:
            raise ValueError("The optional parameter for FlateDecode filter 'Columns' is not an integer")
        columns = columns.value.as_integer_ratio()[0]

        # PNG Predictors:
        if predictor >= 10 and predictor <= 15:
            output = bytearray()
            rowlength = columns + 1
            assert len(data) % rowlength == 0
            prev_rowdata = [0] * rowlength
            for row in range(len(data) // rowlength):
                rowdata: List[int] = [x for x in data[(row*rowlength):((row+1)*rowlength)]]
                filterByte = rowdata[0]
                if filterByte == 0:
                    pass
                elif filterByte == 1:
                    for i in range(2, rowlength):
                        rowdata[i] = (rowdata[i] + rowdata[i-1]) % 256
                elif filterByte == 2:
                    for i in range(1, rowlength):
                        rowdata[i] = (rowdata[i] + prev_rowdata[i]) % 256
                elif filterByte == 3:
                    for i in range(1, rowlength):
                        left = rowdata[i-1] if i > 1 else 0
                        floor = math.floor(left + prev_rowdata[i])/2
                        rowdata[i] = (rowdata[i] + int(floor)) % 256
                elif filterByte == 4:
                    for i in range(1, rowlength):
                        left = rowdata[i - 1] if i > 1 else 0
                        up = prev_rowdata[i]
                        up_left = prev_rowdata[i - 1] if i > 1 else 0
                        paeth = paethPredictor(left, up, up_left)
                        rowdata[i] = (rowdata[i] + paeth) % 256
                else:
                    # unsupported PNG filter
                    raise ValueError(f"Unsupported PNG filter {filterByte}")
                prev_rowdata = rowdata
                output += bytearray(rowdata[1:])
            data = bytes(output)
        else:
            # unsupported predictor
            raise ValueError(f"Unsupported flatedecode predictor {predictor}")
    return data

# DCTDecode filter decodes grayscale or color image data that has been encoded in the JPEG baseline format
# All except one parameter are stored in the encoded data
# Thus the raw data needs no filtering and is simply handed over to any image readers
def DCTDecode(dataBytes: Union[bytes, bytearray], params: PdfDictionaryObject) -> bytes:
    '''DCTDecode filter decodes grayscale or color image data that has been encoded in the JPEG baseline format.
All except one parameter are stored in the encoded data.
Thus the raw data needs no filtering and is simply handed over to any image readers.'''
    return bytearray(dataBytes)