from __future__ import print_function

import sys
import json
import os

from test.unified_format import UnifiedSpecTestMixinV1


def workload_runner(mongodb_uri, test_workload):
    # Run operations
    runner = UnifiedSpecTestMixinV1()
    runner.TEST_SPEC = test_workload
    UnifiedSpecTestMixinV1.TEST_SPEC = test_workload
    runner.setUpClass()
    runner.setUp()
    for i in test_workload["tests"][0]["operations"]:
        if i.get("name") == "loop":
            i["arguments"]["numIterations"] = 5
    runner.run_scenario(test_workload["tests"][0], uri=mongodb_uri)
    entity_map = runner.entity_map
    if "failures" not in entity_map and "errors" in entity_map:
        entity_map["failures"] = [i for i in entity_map["errors"] if i[
            "type"] == AssertionError]
        entity_map._entities["errors"] = [i for i in entity_map["errors"] if i[
            "type"] != AssertionError]
    if "errors" not in entity_map and "failures" in entity_map:
        entity_map["failures"] = [i for i in entity_map["errors"] if i[
            "type"] == AssertionError]
        entity_map._entities["errors"] = [i for i in entity_map["errors"] if i[
            "type"] != AssertionError]
    for i in ["errors", "failures"]:
        if i not in entity_map:
            entity_map[i] = []
    for i in ["successes", "iterations"]:
        if i not in entity_map:
            entity_map[i] = -1
    
    results = {"numErrors": len(entity_map["errors"]), "numFailures":
        len(entity_map["failures"]), "numSuccesses": entity_map["successes"],
               "numIterations": entity_map["iterations"]}

    events = {"events": entity_map["events"], "errors": entity_map[
        "errors"], "failures": entity_map["failures"]}
    print("Workload statistics: {!r}".format(results))
    print("Workload events: {!r}".format(events))
    sentinel = os.path.join(os.path.abspath(os.curdir), 'results.json')
    print("Writing statistics to sentinel file {!r}".format(sentinel))
    with open('results.json', 'w') as fr:
        json.dump(results, fr)
    with open('events.json', 'w') as fr:
        json.dump(events, fr)
    exit(0 or len(entity_map["errors"]) or len(entity_map[
        "failures"]))


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
