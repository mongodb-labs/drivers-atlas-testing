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
    end
    while true
      break if @stop
      perform_operations
    end
    puts "Result: #{result.inspect}"
    write_result
  end

  def load_data
    unified_tests.each do |test|
      test.set_initial_data
    end
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

  def perform_operations
    unified_tests.each do |test|
      begin
        test.run
      rescue Unified::Error => e
        STDERR.puts "Failure: #{e.class}: #{e}"
        @failure_count += 1
      rescue => e
        STDERR.puts "Error: #{e.class}: #{e}"
        @error_count += 1
      end
      @operation_count += test.entities.get(:iteration_count, 'iterations')
      @error_count += test.entities.get(:error_list, 'errors').length
    end
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
    File.open('results.json', 'w') do |f|
      f << JSON.dump(result)
    end
    {}.tap do |event_result|
      unified_tests.map do |test|
        test.entities[:event_list]&.each do |name, events|
          event_result[name] ||= []
          event_result[name] += events
        end
        test.entities[:error_list]&.each do |name, errors|
          event_result[name] ||= []
          event_result[name] += errors
        end
      end
      File.open('events.json', 'w') do |f|
        f << JSON.dump(event_result)
      end
    end
  end
end
