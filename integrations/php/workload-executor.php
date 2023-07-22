<?php declare(strict_types=1);

use MongoDB\Tests\UnifiedSpecTests\EntityMap;
use MongoDB\Tests\UnifiedSpecTests\Loop;
use MongoDB\Tests\UnifiedSpecTests\UnifiedTestCase;
use MongoDB\Tests\UnifiedSpecTests\UnifiedTestRunner;
use function MongoDB\BSON\fromJSON;
use function MongoDB\BSON\toPHP;

require_once __DIR__ . '/vendor/autoload.php';
require_once __DIR__ . '/vendor/bin/.phpunit/phpunit/vendor/autoload.php';

class Logger
{
    private $events = [];
    private $errors = [];
    private $failures = [];
    private $numSuccesses = -1;
    private $numIterations = -1;

    public function applyEntityMap(EntityMap $entityMap) : void
    {
        if ($entityMap->offsetExists('events')) {
            $this->events = array_merge($this->events, (array) $entityMap['events']);

            /* TODO: Add placeholder CMAP events to satisfy assertions in
             * ValidateWorkloadExecutor. This may be removed pending outcome of
             * DRIVERS-1660. */
            $this->events[] = ['name' => 'PoolCreatedEvent', 'observedAt' => microtime(true)];
            $this->events[] = ['name' => 'ConnectionCreatedEvent', 'observedAt' => microtime(true)];
        }

        if ($entityMap->offsetExists('errors')) {
            $this->errors = array_merge($this->errors, (array) $entityMap['errors']);
        }

        if ($entityMap->offsetExists('failures')) {
            $this->failures = array_merge($this->failures, (array) $entityMap['failures']);
        }

        if ($entityMap->offsetExists('successes')) {
            $this->numSuccesses = $entityMap['successes'];
        }

        if ($entityMap->offsetExists('iterations')) {
            $this->numIterations = $entityMap['iterations'];
        }
    }

    public function handleTestRunnerError(Throwable $e) : void
    {
        /* While we could attempt to differentiate between errors and failures
         * here, the spec permits the workload executor to report all propagated
         * exceptions from test runner as errors. This is helpful because an
         * unsupported operation, which the ValidateWorkloadExecutor tests use
         * for an error, is an assertion failure that we would otherwise
         * consider a failure. */
        $this->errors[] = [
            'error' => $e->getMessage(),
            'time' => microtime(true),
        ];
    }

    public function write() : void
    {
        file_put_contents('events.json', json_encode([
            'errors' => $this->errors,
            'failures' => $this->failures,
            'events' => $this->events,
        ], JSON_PRETTY_PRINT));

        file_put_contents('results.json', json_encode([
            'numErrors' => count($this->errors),
            'numFailures' => count($this->failures),
            'numSuccesses' => $this->numSuccesses,
            'numIterations' => $this->numIterations,
        ]));
    }
}

function appendToQueryString(string $uri, $option): string
{
    $parts = parse_url($uri);

    if (isset($parts['query'])) {
        return $uri . '&' . $option;
    } elseif (isset($parts['path'])) {
        return $uri . '?' . $option;
    } else {
        return $uri . '/?' . $option;
    }
}

// Atlas testing expects all drivers to use a server selection loop
$uri = appendToQueryString($argv[1], 'serverSelectionTryOnce=false');
$json = toPHP(fromJSON($argv[2]));

$logger = new Logger;
$runner = new UnifiedTestRunner($uri);
$runner->setEntityMapObserver([$logger, 'applyEntityMap']);

/* TODO: This reduces the size of events.json, but may be removed pending the
 * outcome of DRIVERS-1691. */
Loop::setSleepUsecBetweenIterations(10000);

pcntl_async_signals(true);
pcntl_signal(SIGINT, function() {
    Loop::allowIteration(false);
});

$tests = iterator_to_array(UnifiedTestCase::fromJSON($json), false);

if (count($tests) !== 1) {
    throw new UnexpectedValueException('Expected exactly one test but received: ' . count($tests));
}

try {
    $runner->run($tests[0]);
} catch (Throwable $e) {
    $logger->handleTestRunnerError($e);
} finally {
    $logger->write();
}
