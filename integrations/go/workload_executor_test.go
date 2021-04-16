package main

import (
	"fmt"
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

func TestAtlasPlannedMaintenance(t *testing.T) {
	connstring := os.Args[1]
	workloadSpec := []byte(os.Args[2])

	setupOpts := mtest.NewSetupOptions().SetURI(connstring)
	if err := mtest.Setup(setupOpts); err != nil {
		panic(err)
	}
	defer func() {
		if err := mtest.Teardown(); err != nil {
			panic(err)
		}
	}()

	// killAllSessions will return an auth error if it's run
	fileReqs, runners := unified.ParseTestFile(t, workloadSpec, unified.NewOptions().SetRunKillAllSessions(false))

	mtOpts := mtest.NewOptions().
		RunOn(fileReqs...).
		CreateClient(false)
	mt := mtest.New(t, mtOpts)
	defer mt.Close()

	// a testfile can parse to multiple runners, though we only expect to get one per file
	for _, runner := range runners {
		mtOpts := mtest.NewOptions().
			RunOn(runner.RunOnRequirements...).
			CreateClient(false)

		mt.RunOpts(runner.Description, mtOpts, func(mt *mtest.T) {
			// the workload executor should be able to run non-looping tests and EndLoop() will panic
			// if the test has already finished
			if hasLoop(runner) {
				// Waits for the termination signal from astrolabe and terminates the loop operation
				go func() {
					c := make(chan os.Signal, 1)
					signal.Notify(c, os.Interrupt, syscall.SIGTERM)

					<-c
					runner.EndLoop()
				}()
			}

			testErr := runner.Run(mt)

			em := runner.GetEntities()

			// structs for marshaling json results
			results := struct {
				NumErrors     int   `bson:"numErrors"`
				NumFailures   int   `bson:"numFailures"`
				NumSuccesses  int32 `bson:"numSuccesses"`
				NumIterations int32 `bson:"numIterations"`
			}{}
			allEvents := struct {
				Events   []bson.Raw `bson:"events"`
				Errors   []bson.Raw `bson:"errors"`
				Failures []bson.Raw `bson:"failures"`
			}{}

			var err error
			if results.NumIterations, err = em.Iterations("iterations"); err != nil {
				results.NumIterations = -1
			}
			if results.NumSuccesses, err = em.Successes("successes"); err != nil {
				results.NumSuccesses = -1
			}

			allEvents.Failures, _ = em.BSONArray("failures")
			allEvents.Errors, _ = em.BSONArray("errors")
			allEvents.Events, _ = em.EventList("events")
			// a non-nil testErr should be added to the appropriate slice
			if testErr != nil {
				errDoc := bson.Raw(bsoncore.NewDocumentBuilder().
					AppendString("error", testErr.Error()).
					AppendInt64("time", time.Now().Unix()).
					Build())
				switch {
				// check for the failure substring
				case strings.Contains(testErr.Error(), " verification failed:"):
					allEvents.Failures = append(allEvents.Failures, errDoc)
				default:
					allEvents.Errors = append(allEvents.Errors, errDoc)
				}
			}

			results.NumErrors = len(allEvents.Errors)
			results.NumFailures = len(allEvents.Failures)

			// make sure that empty slices marshal as slices instead of null
			if len(allEvents.Events) == 0 {
				allEvents.Events = make([]bson.Raw, 0)
			}
			if results.NumErrors == 0 {
				allEvents.Errors = make([]bson.Raw, 0)
			}
			if results.NumFailures == 0 {
				allEvents.Failures = make([]bson.Raw, 0)
			}

			path, _ := os.Getwd()

			resultJSON, err := bson.MarshalExtJSON(&results, false, false)
			if err != nil {
				str := fmt.Sprintf("marshal results failed: %v", err)
				panic(str)
			}
			err = ioutil.WriteFile(path+"/results.json", resultJSON, 0644)
			if err != nil {
				str := fmt.Sprintf("write to file failed: %v", err)
				panic(str)
			}

			// MarshalExtJSON is used to print out bson.Raw properly
			eventJSON, err := bson.MarshalExtJSON(&allEvents, false, false)
			if err != nil {
				str := fmt.Sprintf("marshal results failed: %v", err)
				panic(str)
			}
			err = ioutil.WriteFile(path+"/events.json", eventJSON, 0644)
			if err != nil {
				str := fmt.Sprintf("write to file failed: %v", err)
				panic(str)
			}
		})
	}
}
