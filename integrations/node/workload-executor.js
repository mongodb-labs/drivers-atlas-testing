#!/usr/bin/env node

const MongoClient = require(process.env.PROJECT_DIRECTORY).MongoClient;
const fs = require('fs');
const assert = require('assert');
const omit = require('lodash.omit');

const NOOP_DELAY = 1000;

let interrupted = false;
process.on('SIGINT', () => (interrupted = true));

const operations = new Map();
operations.set(
  'find',
  (collection, args) => collection.find(args.filter || {}, omit(args, ['filter'])).toArray()
);
operations.set(
  'insertOne',
  (collection, args) => collection.insertOne(args.document /*, { forceServerObjectId: true }*/)
);
operations.set(
  'updateOne',
  (collection, args) => collection.updateOne(args.filter, args.update)
);

async function main(uri, spec) {
  const runOperations = makeRunOperations(spec);

  const client = new MongoClient(uri);
  try {
    await client.connect();

    const results = { numSuccesses: 0, numFailures: 0, numErrors: 0 };

    while (!interrupted) {
      try {
        await runOperations(client, results);
      } catch (err) {
        ++results.numErrors;
      }
    }

    fs.writeFileSync('results.json', JSON.stringify(results));
  } catch (error) {
    console.error(error);
  } finally {
    await client.close();
  }

  process.exit(0);
}

function makeRunOperations(spec) {
  const operations = spec.operations;
  return function(client, results) {
    if (!Array.isArray(operations) || operations.length === 0) {
      return new Promise(resolve => setTimeout(resolve, NOOP_DELAY));
    }

    const database = client.db(spec.database);
    const collection = database.collection(spec.collection);
    return operations.reduce(
      (chain, op) => chain.then(() => runOperation.call({ database, collection }, op))
        .then(result => {
          try {
            if (op.result != null) {
              assert.deepStrictEqual(result, op.result);
            }
            ++results.numSuccesses;
          } catch (failure) {
            ++results.numFailures;
          }
        })
        .catch(() => (++results.numErrors)),
      Promise.resolve()
    );
  };
}

function runOperation(op) {
  const object = this[op.object];
  if (!object) {
    throw new Error(`Unsupported object: ${op.object}`);
  }
  if (!operations.has(op.name)) {
    throw new Error(`Unsupported operation: ${op.name}`);
  }
  const operation = operations.get(op.name);
  return operation(object, op.arguments);
}


const argv = require('yargs').command(
  '$0 <connectionString> <workloadSpecification>',
  '',
  yargs => {
    yargs
      .positional('connectionString', {
        describe: 'a connection string for the driver to connect to',
        type: 'string'
      })
      .positional('workloadSpecification', {
        describe: 'a JSON blob of operations to run during workload execution',
        type: 'string'
      });
  }
).argv;

const spec = JSON.parse(argv.workloadSpecification);
main(argv.connectionString, spec).catch(console.err);
