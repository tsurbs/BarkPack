import os
from dotenv import dotenv_values
import subprocess

env_vars = dotenv_values(".env")
commands = ["railway", "variables", "--service", "bark-bot"]

for key, value in env_vars.items():
    # Skip DB and S3 since Railway provisions DB and we haven't linked remote S3 yet
    if key and value and key not in ["DATABASE_URL", "S3_ENDPOINT_URL", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"]:
        commands.append("--set")
        commands.append(f"{key}={value}")

if len(commands) > 4:
    subprocess.run(commands)
    print("Environment variables uploaded to Railway!")
else:
    print("No valid variables to upload.")
