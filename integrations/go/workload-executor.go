package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io/ioutil"
	"math"
	"os"
	"os/signal"
	"reflect"
	"syscall"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

var emptyDoc = []byte{5, 0, 0, 0, 0}

type driverWorkload struct {
	Collection string
	Database   string
	Operations []*operation
}

type operation struct {
	Object    string
	Name      string
	Arguments bson.Raw
	Result    interface{}
}

var specTestRegistry = bson.NewRegistryBuilder().
	RegisterTypeMapEntry(bson.TypeEmbeddedDocument, reflect.TypeOf(bson.Raw{})).Build()

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
			str := fmt.Sprintf("unrecognized insertOne option: %v", key)
			panic(str)
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
		case "sort":
			opts = opts.SetSort(val.Document())
		default:
			str := fmt.Sprintf("unrecognized find option: %v", key)
			panic(str)
		}
	}

	return coll.Find(context.Background(), filter, opts)
}

// create an update document or pipeline from a bson.RawValue
func createUpdate(updateVal bson.RawValue) (interface{}, error) {
	switch updateVal.Type {
	case bson.TypeEmbeddedDocument:
		return updateVal.Document(), nil
	case bson.TypeArray:
		var updateDocs []bson.Raw
		docs, _ := updateVal.Array().Values()
		for _, doc := range docs {
			updateDocs = append(updateDocs, doc.Document())
		}

		return updateDocs, nil
	default:
		str := fmt.Sprintf("unrecognized update type: %v", updateVal.Type)
		panic(str)
	}

	return nil, nil
}

func executeUpdateOne(coll *mongo.Collection, args bson.Raw) (*mongo.UpdateResult, error) {
	filter := emptyDoc
	var update interface{} = emptyDoc
	var err error
	opts := options.Update()

	elems, _ := args.Elements()
	for _, elem := range elems {
		key := elem.Key()
		val := elem.Value()

		switch key {
		case "filter":
			filter = val.Document()
		case "update":
			update, err = createUpdate(val)
			if err != nil {
				return nil, err
			}
		default:
			str := fmt.Sprintf("unrecognized updateOne option: %v", key)
			panic(str)
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
	if result == nil {
		return true
	}

	if cur == nil {
		return false
	}

	defer func() {
		cur.Close(context.Background())
	}()

	for _, expected := range result.(bson.A) {
		if !cur.Next(context.Background()) {
			return false
		}
		if !bytes.Equal(expected.(bson.Raw), cur.Current) {
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
	return expected.UpsertedCount == actualUpsertedCount
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
	return false, errors.New("unrecognized collection operation: " + op.Name)
}

func runOperation(coll *mongo.Collection, op *operation) (bool, error) {
	// execute the command on the given object
	if op.Object == "collection" {
		return executeCollectionOperation(coll, op)
	}
	return false, errors.New("unrecognized object: " + op.Name)
}

func main() {
	connstring := os.Args[1]
	workloadSpec := os.Args[2]

	var workload driverWorkload
	err := bson.UnmarshalExtJSONWithRegistry(specTestRegistry, []byte(workloadSpec), false, &workload)
	if err != nil {
		panic(err)
	}

	client, err := mongo.Connect(context.Background(), options.Client().ApplyURI(connstring))
	if err != nil {
		panic(err)
	}
	defer func() { _ = client.Disconnect(context.Background()) }()

	db := client.Database(workload.Database)
	coll := db.Collection(workload.Collection)

	results := struct {
		NumErrors    int `json:"numErrors"`
		NumFailures  int `json:"numFailures"`
		NumSuccesses int `json:"numSuccesses"`
	}{}

	done := make(chan struct{})

	// Waits for the termination signal from astrolabe and terminates the operation loop
	go func() {
		c := make(chan os.Signal, 1)
		signal.Notify(c, os.Interrupt, syscall.SIGTERM)

		<-c
		close(done)
	}()

	defer func() {
		data, err := json.Marshal(results)
		if err != nil {
			str := fmt.Sprintf("marshal results failed: %v", err)
			panic(str)
		}
		path, _ := os.Getwd()
		err = ioutil.WriteFile(path+"/results.json", data, 0644)
		if err != nil {
			str := fmt.Sprintf("write to file failed: %v", err)
			panic(str)
		}
	}()

	for {
		select {
		case <-done:
			return
		default:
		}
		for _, operation := range workload.Operations {
			select {
			case <-done:
				return
			default:
				pass, err := runOperation(coll, operation)
				switch {
				case err != nil:
					results.NumErrors++
				case !pass:
					results.NumFailures++
				default:
					results.NumSuccesses++
				}
			}
		}
	}
}
