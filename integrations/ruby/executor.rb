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
    @unified_group ||= Unified::TestGroup.new(spec,
      client_args: uri, kill_sessions: false)
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
      unified_tests.map do |test|
        @iteration_count += test.entities.get(:iteration_count, 'iterations')
        @success_count += test.entities.get(:success_count, 'successes')
        test.entities[:event_list]&.each do |name, events|
          event_result[name] ||= []
          event_result[name] += events
        end
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
