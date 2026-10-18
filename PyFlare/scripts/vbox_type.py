import sys
import subprocess
import time

# Scancode map for US keyboard (set 1)
SCANCODES = {
    'a': ('1e', '9e'), 'b': ('30', 'b0'), 'c': ('2e', 'ae'), 'd': ('20', 'a0'),
    'e': ('12', '92'), 'f': ('21', 'a1'), 'g': ('22', 'a2'), 'h': ('23', 'a3'),
    'i': ('17', '97'), 'j': ('24', 'a4'), 'k': ('25', 'a5'), 'l': ('26', 'a6'),
    'm': ('32', 'b2'), 'n': ('31', 'b1'), 'o': ('18', '98'), 'p': ('19', '99'),
    'q': ('10', '90'), 'r': ('13', '93'), 's': ('1f', '9f'), 't': ('14', '94'),
    'u': ('16', '96'), 'v': ('2f', 'af'), 'w': ('11', '91'), 'x': ('2d', 'ad'),
    'y': ('15', '95'), 'z': ('2c', 'ac'),
    '1': ('02', '82'), '2': ('03', '83'), '3': ('04', '84'), '4': ('05', '85'),
    '5': ('06', '86'), '6': ('07', '87'), '7': ('08', '88'), '8': ('09', '89'),
    '9': ('0a', '8a'), '0': ('0b', '8b'),
    ' ': ('39', 'b9'), '-': ('0c', '8c'), '=': ('0d', '8d'),
    ';': ('27', 'a7'), '/': ('35', 'b5'), '.': ('34', 'b4'),
    '\n': ('1c', '9c'),
    '|': ('2a', '2b', 'ab', 'aa'), # shift + backslash
    '>': ('2a', '34', 'b4', 'aa'), # shift + .
    ':': ('2a', '27', 'a7', 'aa'), # shift + ;
}

def type_string(vm_name: str, text: str):
    vbox = r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
    codes = []
    for ch in text:
        if ch in SCANCODES:
            codes.extend(SCANCODES[ch])
        elif ch.isupper() and ch.lower() in SCANCODES:
            # Shift down (2a), key down, key up, Shift up (aa)
            down, up = SCANCODES[ch.lower()]
            codes.extend(['2a', down, up, 'aa'])
    
    # Send in chunks of 20
    chunk_size = 20
    for i in range(0, len(codes), chunk_size):
        chunk = codes[i:i+chunk_size]
        subprocess.run([vbox, "controlvm", vm_name, "keyboardputscancode"] + chunk, check=True)
        time.sleep(0.05)

if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else ""
    if text:
        type_string("Pyflare", text)
