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

WIN32 = sys.platform in ("win32", "cygwin")


def interrupt_handler(signum, frame):
    # Deferred import
    from test.unified_format import interrupt_loop
    interrupt_loop()


if WIN32:
    # CTRL_BREAK_EVENT is mapped to SIGBREAK
    signal.signal(signal.SIGBREAK, interrupt_handler)
else:
    signal.signal(signal.SIGINT, interrupt_handler)


def workload_runner(mongodb_uri, test_workload):
    from pymongo.uri_parser import parse_uri
    parts = parse_uri(mongodb_uri)
    os.environ['DB_IP'] = parts['nodelist'][0][0]
    os.environ['DB_PORT'] = str(parts['nodelist'][0][1])
    if parts['username']:
        os.environ['DB_USER'] = parts['username']
        os.environ['DB_PASSWORD'] = parts['password']
    if 'tlsCertificateKeyFile' in parts['options']:
        os.environ['CLIENT_PEM'] = parts['options']['tlsCertificateKeyFile']
        os.environ['CA_PEM'] = parts['options']['tlsCAFile']

    # Deferred import to pick up os.environ changes.
    from test.unified_format import UnifiedSpecTestMixinV1
    runner = UnifiedSpecTestMixinV1()
    runner.TEST_SPEC = test_workload
    runner.setUpClass()
    runner.setUp()
    try:
        assert len(test_workload["tests"]) == 1
        runner.run_scenario(test_workload["tests"][0], uri=mongodb_uri)
    except Exception as exc:
        runner.entity_map["errors"] = [
            {"error": str(exc), "time": time.time(), "type": type(exc).__name__}
        ]
    finally:
        runner.tearDown()
        runner.tearDownClass()
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
