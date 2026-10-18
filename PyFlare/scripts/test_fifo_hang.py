import subprocess
import time

script = """
rm -f /tmp/test-in.fifo /tmp/test-out.fifo
mkfifo /tmp/test-in.fifo
mkfifo /tmp/test-out.fifo

echo "1. Starting background process"
# Background process that exits immediately (like if debconf-communicate fails or exits)
( exit 1 ) > /tmp/test-out.fifo < /tmp/test-in.fifo &
pid=$!

echo "2. Trying to exec 4</tmp/test-out.fifo"
exec 4</tmp/test-out.fifo 3>/tmp/test-in.fifo
echo "3. Successfully opened FIFOs!"
"""

p = subprocess.Popen(["dash", "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
time.sleep(2)
if p.poll() is None:
    print("DASH HUNG ON EXEC 4<! Poll is None!")
    p.kill()
else:
    print("Dash exited with rc:", p.returncode)
    print("Stdout:", p.stdout.read())
    print("Stderr:", p.stderr.read())
