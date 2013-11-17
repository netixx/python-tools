'''
Module to write data to files in a orderly fashion

'''

from csv import DictWriter
import csv
from definitions import ObjectWriter, TupleWriter, ListWriter

__all__ = ['StructuredWriter', 'TsvWriter', 'CsvWriter']

class StructuredWriter(object):
    """Write sets of data to a file, given the dialect
    filename - a file object
    container - an instance of a Writer object
    dialect - format of the output (see csv module)
    
    """
    def __init__(self, filename, container = None, dialect = 'simplecsv'):
        self._container = None
        if isinstance(container, ObjectWriter):
            self._container = container
            self._writer = DictWriter(filename, fieldnames = container.columns, dialect = dialect)
            self.fieldnames = None
        elif isinstance(container, TupleWriter) or isinstance(container, ListWriter):
            self._container = container
            self._writer = csv.writer(filename, dialect = dialect)
            self.fieldnames = container.columns
        else :
            raise Exception("Given writer is not valid")

    def writerows(self, datas):
        for row in datas:
            self.writerow(row)

    def writerow(self, data):
        self._writer.writerow(self._container.write(data))

    def writeheader(self):
        if not ('writeheader' in dir(self._writer)):
            if len(self.fieldnames) > 0:
                self._writer.writerow(self.fieldnames)
        else:
            self._writer.writeheader()

    def __iter__(self):
        return self

class CsvWriter(StructuredWriter):
    def __init__(self, fileObj, container = None):
        StructuredWriter.__init__(self, fileObj, container, dialect = 'simplecsv')

class TsvWriter(StructuredWriter):
    def __init__(self, fileObj, container = None):
        StructuredWriter.__init__(self, fileObj, container, dialect = 'simpletsv')
