"""
Functions related to CP2K
"""

from io import BufferedIOBase


def dict2line_iter(nested, ilevel=0):
    """
    Iterator to convert a nested python dict to a CP2K input file.
    """

    for key, val in nested.items():
        if isinstance(val, dict):
            yield "{}&{} {}".format(' '*ilevel, key.upper(), val.pop('_', ''))
            for line in dict2line_iter(val, ilevel + 3):
                yield line
            yield "{}&END {}".format(' '*ilevel, key.upper())

        elif isinstance(val, list):
            for listitem in val:
                for line in dict2line_iter({key: listitem}, ilevel):
                    yield line

        elif isinstance(val, tuple):
            yield "{}{} {}".format(' '*ilevel, key.upper(),
                                   ' '.join(str(v) for v in val))

        elif isinstance(val, bool):
            yield "{}{} {}".format(
                ' '*ilevel, key.upper(),
                '.TRUE.' if val else '.FALSE.')

        else:
            yield "{}{} {}".format(' '*ilevel, key.upper(), val)


def dict2cp2k(data, output=None, parameters=None):
    """Convert and write a nested python dict to a CP2K input file.

    Some of this code is either taken from AiiDA or heavily
    inspired from there.

    Writes to a file if a handle or filename is given
    or returns the generated file as a string if not.

    The parameters are passed to a .format() call on the final input string.
    """

    if output:
        if isinstance(output, str):
            with open(output, 'w') as fhandle:
                fhandle.write("\n"
                              .join(dict2line_iter(data))
                              .format(**parameters))
        elif isinstance(output, BufferedIOBase):
            # bytes-like object, need to encode
            output.write("\n"
                         .join(dict2line_iter(data))
                         .format(**parameters)
                         .encode('utf-8'))
        else:
            output.write("\n".join(dict2line_iter(data)))
    else:
        return ("\n"
                .join(dict2line_iter(data))
                .format(**parameters))


def mergedicts(dict1, dict2):
    """
    Original version from http://stackoverflow.com/a/7205672/1400465
    """
    for k in set(dict1.keys()).union(dict2.keys()):
        if k in dict1 and k in dict2:
            if isinstance(dict1[k], dict) and isinstance(dict2[k], dict):
                yield (k, dict(mergedicts(dict1[k], dict2[k])))
            elif dict2[k] is None:
                # blank-out values in dict1 if their value in dict2 is None
                pass
            else:
                # If one of the values is not a dict, you can't continue merging it.
                # Value from second dict overrides one in first and we move on.
                yield (k, dict2[k])
                # Alternatively, replace this with exception raiser
                # to alert you of value conflicts
        elif k in dict1:
            yield (k, dict1[k])
        else:
            yield (k, dict2[k])
