import os

# Function to parse log files in the './data/logs/' directory
def parse_logs(directory_path):
    log_files = os.listdir(directory_path)
    log_data = {}
    
    for log_file in log_files:
        with open(os.path.join(directory_path, log_file), 'r') as file:
            log_data[log_file] = file.readlines()
    
    return log_data

# Now parse the logs
log_directory_path = './data/logs/'
parsed_logs = parse_logs(log_directory_path)
print("Parsed Log Data:", parsed_logs)