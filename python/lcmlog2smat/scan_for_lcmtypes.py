#!/usr/bin/python
import re
import os
import sys
import pyclbr
from io import open
from typing import List, Dict, Type


def find_lcmtypes(root_path: str) -> List[str]:
    """
        Scans every subdirectory of root_path searching for lcm-types
    """
    filename_validator = re.compile(r"[a-zA-Z][a-zA-Z0-9_]*\.py")
    file_validator = re.compile("_get_packed_fingerprint")

    found_lcmtypes: List[str] = []

    print("SCANNING FOR LCM TYPES".format(root_path))
    for root, dirs, files in os.walk(root_path):
        print("Searching directory {}".format(root))

        # The python package will be the relative path to the file
        python_package = os.path.relpath(root, root_path).replace(os.sep, ".")

        for file in files:
            # Ensure file name (and hence lcm-type name) is importable to matlab
            if not filename_validator.fullmatch(file):
                continue

            lcmtype_name = file[:-3]

            # quick-test -- check if the file contains the required `_get_packed_fingerprint` method
            try:
                with open(os.path.join(root, file), "r") as f:
                    if not file_validator.search(f.read()):
                        continue
            except IOError:
                continue

            # More thorough check to see if the file corresponds to a
            # LCM type module genereated by lcm-gen.  Parse the
            # file using pyclbr, and check if it contains a class
            # with the right name and methods
            if python_package:
                module_name = f"{python_package}.{lcmtype_name}"
            else:
                module_name = lcmtype_name
            try:
                klass = pyclbr.readmodule(module_name)[lcmtype_name]
                if "decode" in klass.methods and "_get_packed_fingerprint" in klass.methods:
                    found_lcmtypes.append(module_name)
            except (ImportError, KeyError):
                continue

    # Raise error if no lcm type definitions found (nothing will be decoded)
    if not found_lcmtypes:
        raise FileNotFoundError("No lcm type definitions found")
    return found_lcmtypes


def make_lcmtype_dictionary(root_path: str) -> Dict[bytes, Type]:
    """Create a dictionary of LCM types keyed by fingerprint.

    Searches the specified python package directories for modules
    corresponding to LCM types, imports all the discovered types into the
    global namespace, and returns a dictionary mapping packed fingerprints
    to LCM type classes.

    The primary use for this dictionary is to automatically identify and
    decode an LCM message.

    """
    lcm_types = find_lcmtypes(root_path)
    print(f"Found {len(lcm_types)} lcm types")

    result: Dict[bytes, Type] = {}

    for lcm_type in lcm_types:
        print(lcm_type)
        try:
            __import__(lcm_type)
            mod = sys.modules[lcm_type]
            type_basename = lcm_type.split(".")[-1]
            klass = getattr(mod, type_basename)
            fingerprint = klass._get_packed_fingerprint()
            result[fingerprint] = klass
        except Exception as error:
            print("Error importing %s" % lcm_type)
            raise error
    return result


if __name__ == "__main__":
    import binascii

    print("Searching for LCM types...")
    sys.path.insert(0, "/Users/cailean/Dropbox/whoi/mesobot/lcm_types/Generated/python")
    lcmtypes = make_lcmtype_dictionary("/Users/cailean/Dropbox/whoi/mesobot/lcm_types/Generated/python")
    num_types = len(lcmtypes)
    print("Found %d type%s" % (num_types, num_types == 1 and "" or "s"))
    for fingerprint, klass in lcmtypes.items():
        print(binascii.hexlify(fingerprint), klass.__module__)
