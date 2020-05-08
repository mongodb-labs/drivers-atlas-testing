require 'json'
require 'mongo'

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

  def run
    set_signal_handler
    # Normally, the orchestrator loads test data.
    # If the executor is run by itself, uncomment the next line.
    #load_data
    while true
      break if @stop
      perform_operations
    end
    puts "Result: #{result.inspect}"
    write_result
  end

  private

  def set_signal_handler
    Signal.trap('INT') do
      @stop = true
    end
  end

  def load_data
    collection.delete_many
    if data = spec['testData']
      collection.insert_many(data)
    end
  end

  def perform_operations
    spec['operations'].each do |op_spec|
      begin
        case op_spec['name']
        when 'find'
          unless op_spec['object'] == 'collection'
            raise UnknownOperationConfiguration, "Can only find on a collection"
          end

          args = op_spec['arguments'].dup
          op = collection.find(args.delete('filter') || {})
          if sort = args.delete('sort')
            op = op.sort(sort)
          end
          unless args.empty?
            raise UnknownOperationConfiguration, "Unhandled keys in args: #{args}"
          end

          docs = op.to_a

          if expected_docs = op_spec['result']
            if expected_docs != docs
              puts "Failure"
              @failure_count += 1
            end
          end
        when 'insertOne'
          unless op_spec['object'] == 'collection'
            raise UnknownOperationConfiguration, "Can only find on a collection"
          end

          args = op_spec['arguments'].dup
          document = args.delete('document')
          unless args.empty?
            raise UnknownOperationConfiguration, "Unhandled keys in args: #{args}"
          end

          collection.insert_one(document)
        when 'updateOne'
          unless op_spec['object'] == 'collection'
            raise UnknownOperationConfiguration, "Can only find on a collection"
          end

          args = op_spec['arguments'].dup
          scope = collection
          if filter = args.delete('filter')
            scope = collection.find(filter)
          end
          if update = args.delete('update')
            scope.update_one(update)
          end
          unless args.empty?
            raise UnknownOperationConfiguration, "Unhandled keys in args: #{args}"
          end
        else
          raise UnknownOperation, "Unhandled operation #{op_spec['name']}"
        end
      #rescue Mongo::Error => e
      # The validator intentionally gives us invalid operations, figure out
      # how to handle this requirement while maintaining diagnostics.
      rescue => e
        STDERR.puts "Error: #{e.class}: #{e}"
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
  end

  def collection
    @collection ||= client.use(spec['database'])[spec['collection']]
  end

  def client
    @client ||= Mongo::Client.new(uri)
  end
end
