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


IS_INTERRUPTED = False
WIN32 = sys.platform in ("win32", "cygwin")


def interrupt_handler(signum, frame):
    global IS_INTERRUPTED
    # Set the IS_INTERRUPTED flag here and perform the necessary cleanup
    # before actually exiting in workload_runner. This is because signals
    # are handled asynchronously which can cause the interrupt handlers to
    # fire more than once. Consequently, the handler itself should be
    # re-entrant (invokable multiple times without needing to wait for prior
    # invocations to return/complete) which is made possible by this pattern.
    IS_INTERRUPTED = True


if WIN32:
    # CTRL_BREAK_EVENT is mapped to SIGBREAK
    signal.signal(signal.SIGBREAK, interrupt_handler)
else:
    signal.signal(signal.SIGINT, interrupt_handler)


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


def connect(connection_string):
    if WIN32:
        # TODO: remove this once BUILD-10841 is done.
        import certifi
        return MongoClient(connection_string, tlsCAFile=certifi.where())
    return MongoClient(connection_string)


def workload_runner(srv_address, workload_spec):
    # Do not modify connection string and do not add any extra options.
    client = connect(srv_address)

    # Create test entities.
    database = client.get_database(workload_spec["database"])
    collection = database.get_collection(workload_spec["collection"])
    objects = {"database": database, "collection": collection}

    # Run operations
    num_failures = 0
    num_errors = 0
    num_operations = 0
    global IS_INTERRUPTED

    operations = workload_spec["operations"]
    ops = [prepare_operation(op) for op in operations]

    while True:
        if IS_INTERRUPTED:
            break
        try:
            for op in ops:
                run_operation(objects, op)
        except AssertionError:
            traceback.print_exc(file=sys.stdout)
            num_failures += 1
        except Exception:
            traceback.print_exc(file=sys.stdout)
            num_errors += 1
        else:
            num_operations += 1

    if IS_INTERRUPTED:
        print("Handling SIGINT and exiting gracefully.", file=sys.stdout)
        print(json.dumps({
            "numErrors": num_errors, "numFailures": num_failures,
            "numSuccessfulOperations": num_operations}), file=sys.stderr)
        exit(0 or num_errors or num_failures)


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
