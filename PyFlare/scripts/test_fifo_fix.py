import subprocess
import time

script = """
rm -f /tmp/test-in.fifo /tmp/test-out.fifo
mkfifo /tmp/test-in.fifo
mkfifo /tmp/test-out.fifo

echo -n "Begin: Fixed FIFO in dash ... "
# Open read-write descriptor so opening fifo never blocks!
exec 3<>/tmp/test-in.fifo
exec 4<>/tmp/test-out.fifo

chroot / echo "hi" > /tmp/test-out.fifo < /tmp/test-in.fifo &
pid=$!
echo "done."
echo "Pid is $pid, successfully reached past log_end_msg!"
"""

p = subprocess.Popen(["dash", "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
time.sleep(2)
if p.poll() is None:
    print("STILL HUNG!")
    p.kill()
else:
    print("SUCCESS! Output:")
    print(p.stdout.read())
