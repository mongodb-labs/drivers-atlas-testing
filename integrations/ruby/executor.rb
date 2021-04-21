require 'json'
require 'mongo'
require 'runners/unified'

Mongo::Logger.logger.level = Logger::WARN

class UnknownOperation < StandardError; end
class UnknownOperationConfiguration < StandardError; end

class Executor
  def initialize(uri, spec)
    @uri, @spec = uri, spec
    @iteration_count = @success_count = @failure_count = @error_count = 0
  end

  attr_reader :uri, :spec
  attr_reader :iteration_count, :failure_count, :error_count

  def run
    unified_tests

    set_signal_handler
    unified_tests.each do |test|
      test.create_entities
      test.set_initial_data
      test.run
      test.assert_outcome
      test.assert_events
      test.cleanup
    end
    write_result
    puts "Result: #{result.inspect}"
  end

  private

  def set_signal_handler
    Signal.trap('INT') do
      @stop = true
      unified_tests.each do |test|
        test.stop!
      end
    end
  end

  def unified_group
    @unified_group ||= Unified::TestGroup.new(spec, client_args: uri)
  end

  def unified_tests
    @tests ||= unified_group.tests
  end

  def result
    {
      numIterations: @iteration_count,
      numSuccessfulOperations: @success_count,
      numSuccesses: @success_count,
      numErrors: @error_count,
      numFailures: @failure_count,
    }
  end

  def write_result
    {}.tap do |event_result|
      @iteration_count = -1
      @success_count = -1
      @events = []
      @errors = []
      @failures = []
      unified_tests.map do |test|
        begin
          @iteration_count += test.entities.get(:iteration_count, 'iterations')
        rescue Unified::Error::EntityMissing
        end
        begin
          @success_count += test.entities.get(:success_count, 'successes')
        rescue Unified::Error::EntityMissing
        end
        begin
          @events += test.entities.get(:event_list, 'events')
        rescue Unified::Error::EntityMissing
        end
        begin
          @errors += test.entities.get(:error_list, 'errors')
        rescue Unified::Error::EntityMissing
        end
        begin
          @failures += test.entities.get(:failure_list, 'failures')
        rescue Unified::Error::EntityMissing
        end
      end
      @error_count += @errors.length
      @failure_count += @failures.length
      File.open('events.json', 'w') do |f|
        f << JSON.dump(
          errors: @errors,
          failures: @failures,
          events: @events,
        )
      end
    end
    File.open('results.json', 'w') do |f|
      f << JSON.dump(result)
    end
  end
end
