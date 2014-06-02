"""Module to debug python programs"""

import sys
import traceback

def getAllStacks():
    code = []
    for threadId, stack in sys._current_frames().items():
        code.append("\n# ThreadID: %s" % threadId)
        for filename, lineno, name, line in traceback.extract_stack(stack):
            code.append('File: "%s", line %d, in %s' % (filename,
                                                        lineno, name))
            if line:
                code.append("  %s" % (line.strip()))
    return code

def strStacks():
    out = "\n*** STACKTRACE - START ***\n"
    out += "\n".join(getAllStacks())
    out += "\n*** STACKTRACE - END ***\n"
    return out

