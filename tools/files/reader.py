"""Module to read diverse format of structured files

Module based on the csv module (with tweaks)

Container can be used to put results in objects, list or tuples, with or without constraints

See tests (in __main__) for more detailed examples

"""

__all__ = ['TsvReader', 'CsvReader', 'StructuredReader']

from csv import DictReader
import csv
from .definitions import ObjectContainer, TupleContainer, ListContainer


class StructuredReader(object):
    def __init__(self, filename, container = None, dialect = 'simplecsv'):
        self._container = None
        if isinstance(container, ObjectContainer):
            self._container = container
            self._reader = DictReader(filename, fieldnames = None, restkey = "restkey", restval = "restval", dialect = dialect)
        elif isinstance(container, TupleContainer) or isinstance(container, ListContainer):
            self._container = container
            self._reader = csv.reader(filename, dialect = dialect)
        else:
            raise Exception("Given container is not valid")

    def next(self):
        # do not treat the header row
        if self._reader.line_num == 0:
            self._reader.next()

        row = self._reader.next()
        return self._container.fetch(row)


    def __iter__(self):
        return self


class CsvReader(StructuredReader):
    def __init__(self, fileObj, container = None):
        StructuredReader.__init__(self, fileObj, container, dialect = 'simplecsv')


class TsvReader(StructuredReader):
    def __init__(self, fileObj, container = None):
        StructuredReader.__init__(self, fileObj, container, dialect = 'simpletsv')

# class Reader(object):
# def __init__(self, filename, resultContainer = None):
#         '''Create a new file reader
#
#         filename - path to the file to read
#         ncolumns - number of columns to read
#         columnMapping'''
#         self.__filename = filename
#         self.results = resultContainer
#
#     def readFile(self):
#         if os.path.isfile(self.__filename):
#             with open(self.__filename, 'r') as readFile:
#                 for singleLine in readFile:
#                     self.processLine(singleLine)
#
#     def processLine(self, line):
#         self.results.append(line)
# class StructuredReader(Reader):
#     LINE_SEPARATOR = r"\n"
#     COLUMN_SEPARATOR = r"\t"
#     COMMENT_CHARACTER = None
#
# #     FETCH_TUPLE = 1
# #     FETCH_OBJECT = 2
# #
# #     FETCH_LIST = 10
# #     FETCH_DICT = 20
#
#     def __init__(self, filename, ncolumns, fetchContainer, resultContainer):
#         '''Create a new file reader
#
#         filename - path to the file to read
#         ncolumns - number of columns to read
#         columnMapping'''
#         Reader.__init__(self, filename, resultContainer)
#         self.__ncolumns = ncolumns
#         self.__matcher = self.getMatcher()
#
#     def processLine(self, line):
#         match = self.__matcher.match(line)
#         if match is not None:
#             for colNum in range(1, self.getColumnNumber()):
#                 val = match.group(colNum)
#
#     def getLineSeparator(self):
#         return self.LINE_SEPARATOR
#
#     def getColumnSeparator(self):
#         return self.COLUMN_SEPARATOR
#
#     def getColumnNumber(self):
#         return self.__ncolumns
#
#     def getCommentCharacter(self):
#         return self.COMMENT_CHARACTER
#
#     def getMatcher(self):
#         # match a single column
#         match = r"(.*?)%s" % self.getColumnSeparator()
#         # multiply by the number of columns
#         match = match * self.getColumnNumber()
#         # match the rest of the line
#         match += r".*%s" % self.getLineSeparator()
#
#         if self.COMMENT_CHARACTER is not None:
#             match = r"[^%s]" % self.getCommentCharacter() + match
#
#         return re.compile(match)
