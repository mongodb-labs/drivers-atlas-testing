from __future__ import print_function

import sys
import json
import os
import time
import signal

from test.unified_format import UnifiedSpecTestMixinV1, interrupt_loop

WIN32 = sys.platform in ("win32", "cygwin")


def interrupt_handler(signum, frame):
    interrupt_loop()


if WIN32:
    # CTRL_BREAK_EVENT is mapped to SIGBREAK
    signal.signal(signal.SIGBREAK, interrupt_handler)
else:
    signal.signal(signal.SIGINT, interrupt_handler)


def filter_failures_errors(entity_map):
    e, f = [], []
    pre_filter_arr = []
    for entity_type in ["failures", "errors"]:
        if entity_type in entity_map:
            pre_filter_arr.extend(entity_map[entity_type])
    for entity in pre_filter_arr:
        (e, f)[entity["type"] == AssertionError].append(entity)
    entity_map._entities["failures"], entity_map._entities["errors"] = f, e


def workload_runner(mongodb_uri, test_workload):
    runner = UnifiedSpecTestMixinV1()
    runner.TEST_SPEC = test_workload
    UnifiedSpecTestMixinV1.TEST_SPEC = test_workload
    runner.setUpClass()
    runner.setUp()
    # should be removed in final version, but useful for testing right now
    for op in test_workload["tests"][0]["operations"]:
        if op.get("name") == "loop":
            op["arguments"]["numIterations"] = 10
    try:
        runner.run_scenario(test_workload["tests"][0], uri=mongodb_uri)
    except Exception as exc:
        if "errors" not in runner.entity_map:
            runner.entity_map["errors"] = []
        runner.entity_map["errors"].append({
            "error": type(exc).__name__+" "+str(exc),
            "time": time.time(),
            "type": type(exc)
        })
    entity_map = runner.entity_map
    filter_failures_errors(entity_map)
    if "events" not in entity_map:
        entity_map["events"] = []
    for entity_type in ["successes", "iterations"]:
        if entity_type not in entity_map:
            entity_map[entity_type] = -1

    results = {"numErrors": len(entity_map["errors"]),
               "numFailures": len(entity_map["failures"]),
               "numSuccesses": entity_map["successes"],
               "numIterations": entity_map["iterations"]}
    print("Workload statistics: {!r}".format(results))

    # need to do this so that it can be json serialized
    for target in ["errors", "failures"]:
        for i in range(len(entity_map[target])):
            entity_map[target][i].pop("type")

    events = {"events": entity_map["events"],
              "errors": entity_map["errors"],
              "failures": entity_map["failures"]}
    #print("Workload events: {!r}".format(events))

    cur_dir = os.path.abspath(os.curdir)
    print("Writing statistics to directory {!r}".format(cur_dir))
    with open("results.json", 'w') as fr:
        json.dump(results, fr)
    with open("events.json", 'w') as fr:
        json.dump(events, fr)
    exit(0 or len(entity_map["errors"]) or len(entity_map["failures"]))


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
