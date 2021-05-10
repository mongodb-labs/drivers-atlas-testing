package main

import (
	"io/ioutil"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"testing"
	"time"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo/integration/mtest"
	"go.mongodb.org/mongo-driver/mongo/integration/unified"
	"go.mongodb.org/mongo-driver/x/bsonx/bsoncore"
)

// hasLoop returns whether or not testCase tc contains a loop operation
func hasLoop(tc *unified.TestCase) bool {
	if tc == nil {
		return false
	}
	for _, op := range tc.Operations {
		if op.Name == "loop" {
			return true
		}
	}
	return false
}

// marshalStructToFile marshals the given object and writes to filePath
func marshalStructToFile(t *testing.T, obj interface{}, filePath string) {
	t.Helper()
	// MarshalExtJSON is used to print out bson.Raw properly
	marshaled, err := bson.MarshalExtJSON(obj, false, false)
	if err != nil {
		t.Fatalf("marshal results failed: %v", err)
	}
	err = ioutil.WriteFile(filePath, marshaled, 0644)
	if err != nil {
		t.Fatalf("write to file failed: %v", err)
	}
}

func TestAtlasPlannedMaintenance(t *testing.T) {
	connstring := os.Args[1]
	workloadSpec := []byte(os.Args[2])

	setupOpts := mtest.NewSetupOptions().SetURI(connstring)
	if err := mtest.Setup(setupOpts); err != nil {
		t.Fatal(err)
	}
	defer func() {
		if err := mtest.Teardown(); err != nil {
			t.Fatal(err)
		}
	}()

	// killAllSessions will return an auth error if it's run
	fileReqs, testCases := unified.ParseTestFile(t, workloadSpec, unified.NewOptions().SetRunKillAllSessions(false))
	// a workload must use a single test
	if len(testCases) != 1 {
		t.Fatalf("expected 1 test case, got %v", len(testCases))
	}

	mtOpts := mtest.NewOptions().
		RunOn(fileReqs...).
		CreateClient(false)
	mt := mtest.New(t, mtOpts)
	defer mt.Close()

	testCase := testCases[0]
	testOpts := mtest.NewOptions().
		RunOn(testCase.RunOnRequirements...).
		CreateClient(false)

	mt.RunOpts(testCase.Description, testOpts, func(mt *mtest.T) {
		// the workload executor should be able to run non-looping tests and EndLoop() will panic
		// if the test has already finished
		if hasLoop(testCase) {
			// Waits for the termination signal from astrolabe and terminates the loop operation
			go func() {
				c := make(chan os.Signal, 1)
				signal.Notify(c, os.Interrupt, syscall.SIGTERM)

				<-c
				testCase.EndLoop()
			}()
		}

		testErr := testCase.Run(mt)
		entityMap := testCase.GetEntities()

		// store resulting bson documents in events.json
		var allEvents struct {
			Events   []bson.Raw `bson:"events"`
			Errors   []bson.Raw `bson:"errors"`
			Failures []bson.Raw `bson:"failures"`
		}

		allEvents.Failures, _ = entityMap.BSONArray("failures")
		allEvents.Errors, _ = entityMap.BSONArray("errors")
		allEvents.Events, _ = entityMap.EventList("events")

		// a non-nil testErr should be added to the appropriate slice
		if testErr != nil {
			errDoc := bson.Raw(bsoncore.NewDocumentBuilder().
				AppendString("error", testErr.Error()).
				AppendDouble("time", float64(time.Now().Unix())).
				Build())
			switch {
			// check for the failure substring
			// GODRIVER-1950: use error types to distinguish errors instead of error contents
			case strings.Contains(testErr.Error(), " verification failed:"):
				allEvents.Failures = append(allEvents.Failures, errDoc)
			default:
				allEvents.Errors = append(allEvents.Errors, errDoc)
			}
		}

		// make sure that empty slices marshal as slices instead of null
		if allEvents.Events == nil {
			allEvents.Events = make([]bson.Raw, 0)
		}
		if allEvents.Errors == nil {
			allEvents.Errors = make([]bson.Raw, 0)
		}
		if allEvents.Failures == nil {
			allEvents.Failures = make([]bson.Raw, 0)
		}

		path, err := os.Getwd()
		if err != nil {
			t.Fatalf("error getting path: %v", err)
		}
		marshalStructToFile(t, allEvents, path+"/events.json")

		// store results.json
		var results struct {
			NumErrors     int   `bson:"numErrors"`
			NumFailures   int   `bson:"numFailures"`
			NumSuccesses  int32 `bson:"numSuccesses"`
			NumIterations int32 `bson:"numIterations"`
		}

		if results.NumIterations, err = entityMap.Iterations("iterations"); err != nil {
			results.NumIterations = -1
		}
		if results.NumSuccesses, err = entityMap.Successes("successes"); err != nil {
			results.NumSuccesses = -1
		}
		results.NumErrors = len(allEvents.Errors)
		results.NumFailures = len(allEvents.Failures)

		marshalStructToFile(t, results, path+"/results.json")
	})
}
