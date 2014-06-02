"""
Definitions for reader and writer modules

"""
import csv

__all__ = ['ListContainer', 'TupleContainer', 'ObjectContainer', 'FetchableObject',
           'ListWriter', 'TupleWriter', 'ObjectWriter', 'WriteableObject']


class SimpleCsv(csv.excel):
    """Describe the usual properties of CSV files."""
    delimiter = ';'
    quotechar = '"'
    doublequote = True
    skipinitialspace = False
    lineterminator = '\r\n'
    quoting = csv.QUOTE_MINIMAL


csv.register_dialect("simplecsv", SimpleCsv)


class SimpleTsv(SimpleCsv):
    """Simple tsv file"""
    delimiter = '\t'
    doublequote = True
    quotechar = None
    quoting = csv.QUOTE_NONE


csv.register_dialect("simpletsv", SimpleTsv)


class Writer(object):
    """Datas for writing datas to files"""

    def __init__(self, columns = None):
        if columns is None: columns = []
        self._columns = columns

    @property
    def columns(self):
        return self._columns

    def write(self, row):
        return row


class ObjectWriter(Writer):
    """Write object to files"""

    def __init__(self, objectClass, mappings = None):
        if mappings is None : mappings = {}
        assert issubclass(objectClass, WriteableObject), "Object must implement FetchableObject"
        # if not objectClass().check(mappings):
        #             raise Exception("Object does not have the required methods")
        self._objectClass = objectClass
        self._mappings = mappings
        Writer.__init__(self, self.mappings.values())

    @property
    def mappings(self):
        return self._mappings

    def write(self, obj):
        ret = {}
        for method, column in self.mappings.iteritems():
            ret[column] = getattr(obj, method)

        return ret


class TupleWriter(Writer):
    """Write a tuple to a file"""

    def write(self, data):
        return list(data)


class ListWriter(Writer):
    """Write list to file"""
    pass


class WriteableObject(object):
    """Control class for objects to write"""
    pass


class FetchableObject(object):
    """An object whose values will be inserted while parsing"""

    def check(self, mappings):
        """check if the given object has the required methods for fetch
        mappings - dictionnary methodName : [args] where args are names of columns in the data sheet
        """
        for method in mappings.keys():
            if not (method in dir(self)):
                return False

        return True


class Container(object):
    pass


class ObjectContainer(Container):
    """Fetch results into an object"""

    def __init__(self, objectClass, mappings = None):
        """Create a new container
        objectClass - a class subclassing FetchableObject
        mappings - data columns to method mappings dict : methodName : [args]
        
        """
        if mappings is None : mappings = {}
        assert issubclass(objectClass, FetchableObject), "Object must implement FetchableObject"
        if not objectClass().check(mappings):
            raise Exception("Object does not have the required methods")
        self._objectClass = objectClass
        self._mappings = mappings

    @property
    def object(self):
        return self._objectClass()

    @property
    def mappings(self):
        return self._mappings

    def fetch(self, d):
        """Fetches data from a row into a object"""
        obj = self.object
        # fill the objects with values
        for method, args in self.mappings.iteritems():
            try:
                getattr(obj, method)(*[d[arg] for arg in args])
            except KeyError:
                raise Exception("Object mappings are wrong, column names not found in file")
        return obj


class ConstrainedContainer(Container):
    """Apply constraints on given rows"""

    def __init__(self, constraintList = None):
        """Define given constraints in the order given"""
        self._constaints = constraintList

    @property
    def constraints(self):
        return self._constaints

    def fetch(self, datas):
        if self.constraints is None:
            return datas
        for i in range(0, len(datas)):
            try:
                datas[i] = self.constraints[i](datas[i])
            except ValueError as e:
                raise Exception("Type conversion impossible : %s" % e)

        return datas


class ListContainer(ConstrainedContainer):
    """Fetch data into a list"""

    def fetch(self, data):
        return ConstrainedContainer.fetch(self, data)


class TupleContainer(ConstrainedContainer):
    """Fetch Data into a tuple"""

    def fetch(self, data):
        return tuple(ConstrainedContainer.fetch(self, data))

