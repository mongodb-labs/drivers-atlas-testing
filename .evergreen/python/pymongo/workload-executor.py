from __future__ import print_function

import copy
import json
import re
import signal
import sys
import traceback

from pymongo import MongoClient
from pymongo.cursor import Cursor
from pymongo.command_cursor import CommandCursor
from bson.py3compat import iteritems


NUM_FAILURES = 0
NUM_ERRORS = 0
WIN32 = sys.platform == 'win32'


def handler(signum, frame):
    global NUM_ERRORS, NUM_FAILURES
    print("Caught KeyboardInterrupt. Exiting gracefully.")
    print(
        json.dumps(
            {"numErrors": NUM_ERRORS, "numFailures": NUM_FAILURES}),
        file=sys.stderr)
    exit(0)


if WIN32:
    signal.signal(signal.SIGBREAK, handler)
else:
    signal.signal(signal.SIGINT, handler)


def camel_to_snake(camel):
    # Regex to convert CamelCase to snake_case.
    snake = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', snake).lower()


def prepare_operation(operation_spec):
    target_name = operation_spec["object"]
    cmd_name = camel_to_snake(operation_spec["name"])
    arguments = operation_spec["arguments"]
    for arg_name in list(arguments):
        if arg_name == "sort":
            sort_dict = arguments[arg_name]
            arguments[arg_name] = list(iteritems(sort_dict))
    return target_name, cmd_name, arguments, operation_spec.get('result')


def run_operation(objects, prepared_operation):
    target_name, cmd_name, arguments, expected_result = prepared_operation

    if cmd_name.lower().startswith('insert'):
        # PyMongo's insert* methods mutate the inserted document, so we
        # duplicate it to avoid the DuplicateKeyError.
        arguments = copy.deepcopy(arguments)

    target = objects[target_name]
    cmd = getattr(target, cmd_name)
    result = cmd(**dict(arguments))

    if expected_result is not None:
        if isinstance(result, Cursor) or isinstance(result, CommandCursor):
            result = list(result)
        assert result == expected_result


def connect(srv_address):
    if WIN32:
        import certifi
        return MongoClient(srv_address, tlsCAFile=certifi.where())
    return MongoClient(srv_address)


def workload_runner(srv_address, workload_spec):
    # Do not modify connection string and do not add any extra options.
    client = connect(srv_address)

    # Create test entities.
    database = client.get_database(workload_spec["database"])
    collection = database.get_collection(workload_spec["collection"])
    objects = {"database": database, "collection": collection}

    # Run operations
    operations = workload_spec["operations"]
    global NUM_FAILURES, NUM_ERRORS

    ops = [prepare_operation(op) for op in operations]
    while True:
        try:
            for op in ops:
                run_operation(objects, op)
        except AssertionError:
            traceback.print_exc(file=sys.stdout)
            NUM_FAILURES += 1
        except Exception:  # Don't catch Keyboard Interrupt here or you can never exit
            traceback.print_exc(file=sys.stdout)
            NUM_ERRORS += 1


if __name__ == '__main__':
    srv_address, workload_ptr = sys.argv[1], sys.argv[2]
    try:
        workload_spec = json.loads(workload_ptr)
    except json.decoder.JSONDecodeError:
        # We also support passing in a raw test YAML file to this
        # script to make it easy to run the script in debug mode.
        # PyYAML is imported locally to avoid ImportErrors on EVG.
        import yaml
        with open(workload_ptr, 'r') as fp:
            testspec = yaml.load(fp, Loader=yaml.FullLoader)
            workload_spec = testspec['driverWorkload']

    workload_runner(srv_address, workload_spec)
