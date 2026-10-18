import subprocess
import time

script = """
log_begin_msg() { echo -n "Begin: $1 ... "; }
log_end_msg() { echo "done."; }

rm -f /tmp/test-in.fifo /tmp/test-out.fifo
mkfifo /tmp/test-in.fifo
mkfifo /tmp/test-out.fifo

log_begin_msg "Testing FIFO in dash"
( echo "hi" ) > /tmp/test-out.fifo < /tmp/test-in.fifo &
pid=$!
log_end_msg
echo "Reached after log_end_msg, pid=$pid"
kill $pid 2>/dev/null || true
rm -f /tmp/test-in.fifo /tmp/test-out.fifo
"""

p = subprocess.Popen(["dash", "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
time.sleep(1)
if p.poll() is None:
    print("DASH HUNG! Poll is None!")
    p.kill()
else:
    print("Dash exited with rc:", p.returncode)
    print("Stdout:", p.stdout.read())
    print("Stderr:", p.stderr.read())
