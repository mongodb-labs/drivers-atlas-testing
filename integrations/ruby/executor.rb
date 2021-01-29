require 'json'
require 'mongo'
require 'runners/unified'

Mongo::Logger.logger.level = Logger::WARN

class UnknownOperation < StandardError; end
class UnknownOperationConfiguration < StandardError; end

class Executor
  def initialize(uri, spec)
    @uri, @spec = uri, spec
    @operation_count = @failure_count = @error_count = 0
  end

  attr_reader :uri, :spec
  attr_reader :operation_count, :failure_count, :error_count
  attr_reader :metrics_collector

  def run
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
      numOperations: @operation_count,
      numSuccessfulOperations: @operation_count-@error_count-@failure_count,
      numSuccesses: @operation_count-@error_count-@failure_count,
      numErrors: @error_count,
      numFailures: @failure_count,
    }
  end

  def write_result
    {}.tap do |event_result|
      unified_tests.map do |test|
        @operation_count += test.entities.get(:iteration_count, 'iterations')
        test.entities[:event_list]&.each do |name, events|
          event_result[name] ||= []
          event_result[name] += events
        end
        test.entities[:error_list]&.each do |name, errors|
          @error_count += errors.length
          event_result[name] ||= []
          event_result[name] += errors
        end
        test.entities[:failure_list]&.each do |name, failures|
          @failure_count += failures.length
          event_result[name] ||= []
          event_result[name] += failures
        end
      end
      File.open('events.json', 'w') do |f|
        f << JSON.dump(event_result)
      end
    end
    File.open('results.json', 'w') do |f|
      f << JSON.dump(result)
    end
  end
end
