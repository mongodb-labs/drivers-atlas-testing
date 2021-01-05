require 'json'
require 'mongo'
require 'runners/unified'

Mongo::Logger.logger.level = Logger::WARN

class UnknownOperation < StandardError; end
class UnknownOperationConfiguration < StandardError; end

class MetricsCollector
  def initialize
    @operations = {}
    @command_events = []
    @connection_events = []
    @errors = []
    @failures = []
  end

  attr_reader :command_events, :connection_events, :errors, :failures

  def started(event)
    @operations[event.operation_id] = [event, Time.now]
  end

  def succeeded(event)
    started_event, started_at = @operations.delete(event.operation_id)
    raise "Started event for #{event.operation_id} not found" unless started_event
    @command_events << {
      commandName: started_event.command_name,
      duration: event.duration,
      startTime: started_at.to_f,
      address: started_event.address.seed,
    }
  end

  def failed(event)
    started_event, started_at = @operations.delete(event.operation_id)
    raise "Started event for #{event.operation_id} not found" unless started_event
    @command_events << {
      commandName: started_event.command_name,
      duration: event.duration,
      failure: event.failure,
      startTime: started_at.to_f,
      address: started_event.address.seed,
    }
  end

  def published(event)
    @connection_events << {
      name: event.class.name.sub(/.*::/, ''),
      time: Time.now.to_f,
      address: event.address.seed,
    }.tap do |entry|
      if event.respond_to?(:connection_id)
        entry[:connectionId] = event.connection_id
      end
      if event.respond_to?(:reason)
        entry[:reason] = event.reason
      end
    end
  end
end

class Executor
  def initialize(uri, spec)
    @uri, @spec = uri, spec
    @operation_count = @failure_count = @error_count = 0
    @metrics_collector = MetricsCollector.new
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
    end
  end

  def unified_group
    @unified_group ||= Unified::TestGroup.new(spec)
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
        metrics_collector.failures << {
          failure: "#{e.class}: #{e}",
          time: Time.now.to_f,
        }
        @failure_count += 1
      rescue => e
      raise
        STDERR.puts "Error: #{e.class}: #{e}"
        metrics_collector.errors << {
          error: "#{e.class}: #{e}",
          time: Time.now.to_f,
        }
        @error_count += 1
      end
      @operation_count += 1
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
    File.open('events.json', 'w') do |f|
      f << JSON.dump(
        commands: metrics_collector.command_events,
        connections: metrics_collector.connection_events,
        errors: metrics_collector.errors,
      )
    end
  end
end
