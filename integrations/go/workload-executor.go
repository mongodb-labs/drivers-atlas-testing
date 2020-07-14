package main

import (
	"bytes"
	"context"
	"encoding/json"
	"io/ioutil"
	"log"
	"math"
	"os"
	"os/signal"
	"runtime"
	"syscall"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

var emptyDoc = []byte{5, 0, 0, 0, 0}

type driverWorkload struct {
	Collection string
	Database   string
	TestData   []bson.Raw 	`bson:"testData"`
	Operations []*operation
}

type operation struct {
	Object    string
	Name      string
	Arguments bson.Raw
	Result 	  interface{}
}

func executeInsertOne(coll *mongo.Collection, args bson.Raw) (*mongo.InsertOneResult, error) {
	doc := emptyDoc
	opts := options.InsertOne()

	elems, _ := args.Elements()
	for _, elem := range elems {
		key := elem.Key()
		val := elem.Value()

		switch key {
		case "document":
			doc = val.Document()
		default:
			panic("unrecognized insertOne option")
		}
	}

	return coll.InsertOne(context.Background(), doc, opts)
}

func executeFind(coll *mongo.Collection, args bson.Raw) (*mongo.Cursor, error) {
	filter := emptyDoc
	opts := options.Find()

	elems, _ := args.Elements()
	for _, elem := range elems {
		key := elem.Key()
		val := elem.Value()

		switch key {
		case "filter":
			filter = val.Document()
		default:
			panic("unrecognized find option")
		}
	}

	return coll.Find(context.Background(), filter, opts)
}

// create an update document or pipeline from a bson.RawValue
func createUpdate(updateVal bson.RawValue) interface{} {
	switch updateVal.Type {
	case bson.TypeEmbeddedDocument:
		return updateVal.Document()
	case bson.TypeArray:
		var updateDocs []bson.Raw
		docs, _ := updateVal.Array().Values()
		for _, doc := range docs {
			updateDocs = append(updateDocs, doc.Document())
		}

		return updateDocs
	default:
		panic("unrecognized update type")
	}

	return nil
}

func executeUpdateOne(coll *mongo.Collection, args bson.Raw) (*mongo.UpdateResult, error) {
	filter := emptyDoc
	var update interface{} = emptyDoc
	opts := options.Update()

	elems, _ := args.Elements()
	for _, elem := range elems {
		key := elem.Key()
		val := elem.Value()

		switch key {
		case "filter":
			filter = val.Document()
		case "update":
			update = createUpdate(val)
		default:
			panic("unrecognized updateOne option")
		}
	}
	if opts.Upsert == nil {
		opts = opts.SetUpsert(false)
	}

	return coll.UpdateOne(context.Background(), filter, update, opts)
}

func verifyInsertOneResult(actualResult *mongo.InsertOneResult, expectedResult interface{}) bool {
	if expectedResult == nil {
		return true
	}

	var expected mongo.InsertOneResult
	if bson.Unmarshal(expectedResult.(bson.Raw), &expected) != nil {
		return false
	}

	expectedID := expected.InsertedID
	if f, ok := expectedID.(float64); ok && f == math.Floor(f) {
		expectedID = int32(f)
	}

	return expectedID == nil || (actualResult != nil && expectedID == actualResult.InsertedID)
}

func verifyCursorResult(cur *mongo.Cursor, result interface{}) bool {
	defer func() {
		cur.Close(context.Background())
	} ()

	if result == nil {
		return true
	}

	if cur == nil {
		return false
	}
	for _, expected := range result.(bson.A) {
		if !cur.Next(context.Background()) {
			return false
		}
		if !bytes.Equal(expected.([]byte), cur.Current) {
			return false
		}
	}

	if cur.Next(context.Background()) {
		return false
	}
	return cur.Err() == nil
}

func verifyUpdateResult(res *mongo.UpdateResult, result interface{}) bool {
	if result == nil {
		return true
	}

	var expected struct {
		MatchedCount  int64 `bson:"matchedCount"`
		ModifiedCount int64 `bson:"modifiedCount"`
		UpsertedCount int64 `bson:"upsertedCount"`
	}
	err := bson.Unmarshal(result.(bson.Raw), &expected)
	if err != nil {
		return false
	}

	if expected.MatchedCount != res.MatchedCount {
		return false
	}
	if expected.ModifiedCount != res.ModifiedCount {
		return false
	}

	actualUpsertedCount := int64(0)
	if res.UpsertedID != nil {
		actualUpsertedCount = 1
	}
	return expected.UpsertedCount ==  actualUpsertedCount
}

func executeCollectionOperation(coll *mongo.Collection, op *operation) (bool, error) {
	switch op.Name {
	case "insertOne":
		res, err := executeInsertOne(coll, op.Arguments)
		return verifyInsertOneResult(res, op.Result), err
	case "find":
		cursor, err := executeFind(coll, op.Arguments)
		return verifyCursorResult(cursor, op.Result), err
	case "updateOne":
		res, err := executeUpdateOne(coll, op.Arguments)
		return verifyUpdateResult(res, op.Result), err
	}
	panic("unrecognized collection operation")
}

func runOperation(coll *mongo.Collection, op *operation) (bool, error) {
	// execute the command on the given object
	if op.Object == "collection"{
		return executeCollectionOperation(coll, op)
	}
	panic("unrecognized object")
	//panic
}

func main() {
	log.Printf("GO VERSION: %s\n", runtime.Version())

    connstring := os.Args[1]
    workloadSpec := os.Args[2]

    var workload driverWorkload

   	err := json.Unmarshal([]byte(workloadSpec), workload)
   	if err != nil {
   		panic("failed to unmarshal data")
   	}

	client, err := mongo.NewClient(options.Client().ApplyURI(connstring))
	if err != nil {
   		panic("failed to connect to client")
   	}
	db := client.Database(workload.Database)
	coll := db.Collection(workload.Collection)

	results := struct {
		numErrors int 	 `json:"numErrors"`
		numFailures int  `json:"numFailures"`
		numSuccesses int `json:"numSuccesses"`
	} {}


	done := make(chan struct{})

	go func() {
		c := make(chan os.Signal, 1)
		signal.Notify(c, os.Interrupt, syscall.SIGTERM)
		
		<-c
		close(done)
	}()

	// insert testdata
	if len(workload.TestData) > 0 {
		docs := make([]interface{}, len(workload.TestData))

		for i, val := range workload.TestData {
			docs[i] = val
		}
		_, err := coll.InsertMany(context.Background(), docs)
		if err != nil {
			panic("inserting testData failed")
		}
	}

	defer func() {
        data, _ := json.Marshal(results)
		_ = ioutil.WriteFile("results.json", data, 0644)
    }()

	for {
		select {
		case <-done:
			return
		default:
			for _, operation := range workload.Operations {
				select {
				case <-done:
					return
				default:
					pass, err := runOperation(coll, operation)
					switch {
					case !pass:
						results.numFailures++
					case err != nil:
						results.numErrors++
					default:
						results.numSuccesses++
					}
				}
			}
		}
	}
}