import subprocess
import time

script = """
rm -f /tmp/test-in.fifo /tmp/test-out.fifo
mkfifo /tmp/test-in.fifo
mkfifo /tmp/test-out.fifo

echo -n "Begin: Simple command with fifo in dash ... "
chroot / echo "hi" > /tmp/test-out.fifo < /tmp/test-in.fifo &
pid=$!
echo "done."
"""

p = subprocess.Popen(["dash", "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
time.sleep(2)
if p.poll() is None:
    print("DASH HUNG ON SIMPLE COMMAND! Poll is None!")
    p.kill()
else:
    print("Dash exited with rc:", p.returncode)
    print("Stdout:", p.stdout.read())
    print("Stderr:", p.stderr.read())
