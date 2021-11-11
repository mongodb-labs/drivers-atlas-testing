from __future__ import print_function
import site
import sys
import json
import os
import time
import signal
import inspect

from collections import defaultdict
import pymongo
test_path = os.path.dirname(os.path.dirname(inspect.getfile(pymongo)))
print("sys.path before patching:", sys.path)
sys.path.insert(0, test_path)
print("sys.path after patching:", sys.path)
from test.unified_format import UnifiedSpecTestMixinV1, interrupt_loop
print("where is UnifiedSpecTestMixinV1 from", inspect.getfile("UnifiedSpecTestMixinV1"))
WIN32 = sys.platform in ("win32", "cygwin")


def interrupt_handler(signum, frame):
    interrupt_loop()


if WIN32:
    # CTRL_BREAK_EVENT is mapped to SIGBREAK
    signal.signal(signal.SIGBREAK, interrupt_handler)
else:
    signal.signal(signal.SIGINT, interrupt_handler)


def workload_runner(mongodb_uri, test_workload):
    runner = UnifiedSpecTestMixinV1()
    runner.TEST_SPEC = test_workload
    UnifiedSpecTestMixinV1.TEST_SPEC = test_workload
    runner.setUpClass()
    runner.setUp()
    try:
        assert len(test_workload["tests"]) == 1
        runner.run_scenario(test_workload["tests"][0], uri=mongodb_uri)
    except Exception as exc:
        runner.entity_map["errors"] = [{
            "error": str(exc),
            "time": time.time(),
            "type": type(exc).__name__
        }]
    entity_map = defaultdict(list, runner.entity_map._entities)
    for entity_type in ["successes", "iterations"]:
        if entity_type not in entity_map:
            entity_map[entity_type] = -1

    results = {"numErrors": len(entity_map["errors"]),
               "numFailures": len(entity_map["failures"]),
               "numSuccesses": entity_map["successes"],
               "numIterations": entity_map["iterations"]}
    print("Workload statistics: {!r}".format(results))

    events = {"events": entity_map["events"],
              "errors": entity_map["errors"],
              "failures": entity_map["failures"]}

    cur_dir = os.path.abspath(os.curdir)
    print("Writing statistics to directory {!r}".format(cur_dir))
    with open("results.json", 'w') as fr:
        json.dump(results, fr)
    with open("events.json", 'w') as fr:
        json.dump(events, fr)


if __name__ == '__main__':
    connection_string, driver_workload = sys.argv[1], sys.argv[2]
    try:
        workload_spec = json.loads(driver_workload)
    except json.decoder.JSONDecodeError:
        # We also support passing in a raw test YAML file to this
        # script to make it easy to run the script in debug mode.
        # PyYAML is imported locally to avoid ImportErrors on EVG.
        import yaml
        with open(driver_workload, 'r') as fp:
            testspec = yaml.load(fp, Loader=yaml.FullLoader)
            workload_spec = testspec['driverWorkload']

    workload_runner(connection_string, workload_spec)
