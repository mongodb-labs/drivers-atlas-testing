for file in ../../../tests/*
do
   if [[ $file == *.yml ]]
   then
      echo $file
      python3 workload-executor.py "user:password@localhost" "$file"
   fi
done

