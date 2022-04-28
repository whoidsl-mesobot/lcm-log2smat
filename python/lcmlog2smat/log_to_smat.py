#!/usr/bin/python
#
# Converts a LCM log to a "structured" format that is easier to work with
# external tools such as Matlab or Python. The set of messages on a given
# channel can be represented as a structure preserving the original lcm message
# structure.
#
# lcm-log2smat is based on libbot2 script bot-log2mat.
# Modified by G.Troni

import sys
import getopt
import pickle

# check which version for mio location
from typing import Any, Tuple

import scipy.io.matlab.mio

from lcm import EventLog, Event
from scan_for_lcmtypes import *

longOpts = ["help", "lcm_type_path="]


def print_usage():
    pname, sname = os.path.split(sys.argv[0])
    sys.stderr.write("usage: % s %s < filename > \n" % (sname, str(longOpts)))
    print("""
    -h --help                 print this message
    --lcm_type_path=path      Path to the lcm type definitions 
    """)
    sys.exit()


def parse_options(args, opts=[]) -> Tuple[str, Dict[str, Any]]:
    options: Dict[str, Any] = {}

    # Parse the input log file name
    if isinstance(args, (list, tuple)):
        file = args[0]
    elif isinstance(args, str):
        file = args
    else:
        print_usage()
        exit()

    # Parse the other options
    for option, value in opts:
        if option == "-v":
            options["verbose"] = True
        elif option in ("-h", "--help"):
            print_usage()
            exit()
        # The root directory for lcm types. Needs added to path for `pyclbr` to work
        elif option in ("--lcm_type_path="):
            sys.path.insert(0, value)
            options["lcmtype_root"] = value
        else:
            raise KeyError(f"Unrecognised option {option} with value {value}")

    return file, options


def convert_to_loggable(data, timestamp=None):
    """
        Converts the given data to a loggable quantity.

        - Primitive types are returned as-is,
        - Lists are expanded recursively
    """
    # Return primitive types as-is
    if (isinstance(data, int) or
            isinstance(data, float) or
            isinstance(data, str) or
            isinstance(data, bytes) or
            isinstance(data, tuple)):  # todo - Tuples should probably be handled separately
        return data

    # Expand lists recursively
    elif isinstance(data, list):
        if any(hasattr(item, "__slots__") for item in data):
            dict = {}
            for item in data:
                msg_dict = convert_to_loggable(item, timestamp)
                for field in msg_dict.keys():
                    dict.setdefault(field[:31], []).append(msg_dict[field])
            return dict
        else:
            return [convert_to_loggable(item, timestamp) for item in data]

    # Handle custom lcm types
    # All message fields are listed in its __slots__ attribute
    elif hasattr(data, "__slots__"):
        # todo - get constants

        msg_dict = {"timestamp": timestamp}
        for field in data.__slots__:
            value = getattr(data, field)
            msg_dict[field[:31]] = convert_to_loggable(value, timestamp)

        return msg_dict
    else:
        print(f"Unrecognised type {type(data)}")
        exit()


def parse_log(log: EventLog, lcm_types: Dict) -> Dict:
    first_timestamp = None
    events: Dict[str, Dict[str, List]] = {}  # {CHANNEL: {FIELD1: [values], FIELD2: [values]}}

    for event in log:
        assert isinstance(event, Event)
        # Record the time of the first event as start time
        if not first_timestamp:
            first_timestamp = event.timestamp

        # todo - ignored channels

        # Match the message to an lcm type
        fingerprint = event.data[:8]
        lcm_type = lcm_types.get(fingerprint, None)
        if not lcm_type:
            sys.stderr.write(f"Unable to find lcm type for event on channel {event.channel}\n")
            continue

        # Decode the message into a python object
        try:
            message = lcm_type.decode(event.data)
        except:
            sys.stderr.write(f"Error decoding event on channel {event.channel}\n")
            continue

        # Convert the message into loggable form & store
        message_dict = convert_to_loggable(message, event.timestamp - first_timestamp)

        # Convert to list of values for each field
        for field in message_dict.keys():
            events.setdefault(event.channel, {}).setdefault(field, []).append(message_dict[field])

    return events


def dump_to_matlab(data: Dict, outputfile: str):
    scipy.io.matlab.mio.savemat(outputfile, data, oned_as='column')


def parse_and_save(file: str, options: Dict[str, Any]):
    # Get the input & output files
    input_file = os.path.abspath(file)
    output_file = os.path.basename(input_file).replace(".", "_").replace("-", "_")
    output_file = os.path.abspath(output_file + ".mat")

    # Find the lcm type definitions
    print("Searching for LCM types...")
    lcm_types = make_lcmtype_dictionary(options.get("lcmtype_root", os.getcwd()))

    # Open the log file as an LCM EventLog object
    print("Parsing log file")
    log = EventLog(input_file, "r")
    events = parse_log(log, lcm_types)

    # Dump to matlab file
    print("Writing mat file")
    dump_to_matlab(events, output_file)


if __name__ == "__main__":
    # Parse command line arguments
    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], "h", longOpts)
    except getopt.GetoptError as err:
        # print help information and exit:
        print(str(err))  # will print something like "option -a not recognized"
        print_usage()

    # fixme DEBUG
    # args = ["lcmlog-2019-09-15.00"]
    # opts = [("lcm_type_path=", "/Users/cailean/Dropbox/whoi/mesobot/lcm_types/Generated/python")]
    # fixme DEBUG

    if len(args) != 1:
        print_usage()

    # Run main parser
    file, options = parse_options(args, opts)
    parse_and_save(file, options)
