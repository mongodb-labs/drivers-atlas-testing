import inspect
import json
import os
import signal
import sys
import time
from collections import defaultdict

import pymongo

# we insert this path into the sys.path because we want to be able to import
# test.unified_format directly from the git repo that was used to install
# pymongo (this works because pymongo is installed with pip flag -e)
test_path = os.path.dirname(os.path.dirname(inspect.getfile(pymongo)))
sys.path.insert(0, test_path)
from test.unified_format import UnifiedSpecTestMixinV1  # noqa: E402
from test.unified_format_shared import interrupt_loop  # noqa: E402

WIN32 = sys.platform in ("win32", "cygwin")


def interrupt_handler(signum, frame):
    interrupt_loop()


if WIN32:
    # CTRL_BREAK_EVENT is mapped to SIGBREAK
    signal.signal(signal.SIGBREAK, interrupt_handler)
else:
    signal.signal(signal.SIGINT, interrupt_handler)


def workload_runner(mongodb_uri, test_workload):
    print(f"Running workload: {test_workload!r}")
    runner = UnifiedSpecTestMixinV1()
    runner.TEST_SPEC = test_workload
    UnifiedSpecTestMixinV1.TEST_SPEC = test_workload
    runner.setUp()
    # this is necessary because there isn't a mongo instance on
    # localhost:27017 on evergreen, so we have to patch it to use the client
    # specified in the workload runner
    runner.client = pymongo.MongoClient(mongodb_uri)
    print("Running scenario")
    try:
        assert len(test_workload["tests"]) == 1
        runner.run_scenario(test_workload["tests"][0], uri=mongodb_uri)
    except Exception as exc:
        runner.entity_map["errors"] = [
            {"error": str(exc), "time": time.time(), "type": type(exc).__name__}
        ]
    entity_map = defaultdict(list, runner.entity_map._entities)
    for entity_type in ["successes", "iterations"]:
        if entity_type not in entity_map:
            entity_map[entity_type] = -1

    results = {
        "numErrors": len(entity_map["errors"]),
        "numFailures": len(entity_map["failures"]),
        "numSuccesses": entity_map["successes"],
        "numIterations": entity_map["iterations"],
    }
    print(f"Workload statistics: {results!r}")

    events = {
        "events": entity_map["events"],
        "errors": entity_map["errors"],
        "failures": entity_map["failures"],
    }
    cur_dir = os.path.abspath(os.curdir)
    print(f"Writing statistics to directory {cur_dir!r}")
    with open("results.json", "w") as fr:
        json.dump(results, fr)
    with open("events.json", "w") as fr:
        json.dump(events, fr)


if __name__ == "__main__":
    print("Starting up workload executor")
    connection_string, driver_workload = sys.argv[1], sys.argv[2]
    try:
        workload_spec = json.loads(driver_workload)
    except json.decoder.JSONDecodeError:
        # We also support passing in a raw workload YAML file to this
        # script to make it easy to run the script in debug mode.
        # PyYAML is imported locally to avoid ImportErrors on EVG.
        import yaml

        with open(driver_workload) as fp:
            workload_spec = yaml.safe_load(fp, Loader=yaml.FullLoader)

    workload_runner(connection_string, workload_spec)
