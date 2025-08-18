import subprocess

cmd = ["mcpd", "add", "memory", "npx::@modelcontextprotocol/server-memory@latest"]
print(f"Running: {' '.join(cmd)}")
result = subprocess.run(cmd, capture_output=True, text=True)
print(f"Return code: {result.returncode}")
print(f"Stdout: {result.stdout}")
print(f"Stderr: {result.stderr}")