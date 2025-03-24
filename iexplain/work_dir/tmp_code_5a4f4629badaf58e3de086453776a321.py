import os

# List files in the './data/metadata/' directory
directory_path = './data/metadata/'
intent_files = os.listdir(directory_path)
print("Intent Files:", intent_files)