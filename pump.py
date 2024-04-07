#!/usr/bin/python3
import subprocess
import threading
import time
from datetime import datetime, timedelta
import argparse
from kbhit import KBHit

KASA_COMMAND_TEMPLATE = "~/.local/bin/kasa --type plug --host {} {}"
ON = 2
DELAY = 30

kb=KBHit()

camip="192.168.4.131"
pumpip="192.168.4.180"
#ffplay_vf_args="scale=2*iw:-1, crop=iw/4:ih/4"
ffplay_vf_args="scale=5*iw:-1, crop=iw/2:ih/2:(in_w-out_w)/2:(in_h-out_h)*3/4"
USE_REMOTE_TIME=False

class KasaController:
    def __init__(self, ip_address, delay_mins=DELAY, on_mins=ON, show_cam=False, dry_run=False, start_off=False):
        self.ip_address = ip_address
        self.quit_event = threading.Event()
        self.reset_event = threading.Event()
        self.skip_event = threading.Event()
        self.double_event = threading.Event()
        self.dry_run = dry_run
        self.input_thread = threading.Thread(target=self.process_input)
        self.input_thread.start()
        self.show_cam = show_cam
        self.start_off = start_off
        self.delay_mins = (delay_mins or DELAY)
        self.on_mins = (on_mins or ON)
        self.use_remote_time = USE_REMOTE_TIME
        print("On for {}mins, delay for {}mins".format(self.on_mins, self.delay_mins))

    def countdown_timer(self, seconds):
        for i in range(int(seconds), 0, -1):
            if self.quit_event.is_set():
                print("\nExiting the script...")
                break
            elif self.skip_event.is_set():
                print(" - skipped!")
                return
            elif self.double_event.is_set():
                print(" - doubled!", )
                self.double_event.clear()
                self.countdown_timer(abs(i)*2)
                return
            elif self.reset_event.is_set():
                print(" - reset", )
                self.reset_event.clear()
                self.countdown_timer(seconds)
                return
            print("\rTime remaining: {:02d}:{:02d}".format(
                i // 60, i % 60), end="")
            time.sleep(1)
        if self.quit_event.is_set():
            print('Press any key to continue....')
            return
        print("\rTime remaining: 0         ")

    def process_input(self):

        q = "'q' to quit the script"
        s = "'s' to skip this wait"
        d = "'d' to double the wait"
        r = "'r' to restart the wait"
        instr=[q,s,d,r]
        print("\nPress\n" + "\n".join(instr) + "\n")
        while not self.quit_event.is_set():
            key=kb.getch()
            if key == 'q':
                self.quit_event.set()
            if key == 's':
                self.skip_event.set()
            if key == 'd':
                self.double_event.set()
            if key == 'r':
                self.reset_event.set()

    def sleep_with_output(self, duration_minutes, message="Sleep complete"):
        seconds = duration_minutes * 60

        countdown_thread = threading.Thread(
            target=self.countdown_timer, args=(seconds,))

        countdown_thread.start()

        try:
            countdown_thread.join()
        except:
            print('\n<<caught ctrl+C>>')
            self.quit_event.set()
    
        self.skip_event.clear()

        print("{}".format(message))

    # note: network conditions can cause errors here when use_remote_time
    def get_current_time(self):
        kasa_command = KASA_COMMAND_TEMPLATE.format(self.ip_address, "time")
        input_string = subprocess.check_output(
            kasa_command, shell=True).decode('utf-8')
        time_part = input_string.split(" ")[-1].strip()
        return time_part

    def execute_command(self, command):
        if self.dry_run:
            print("[DRYRUN] {}".format(command))
        else:
            print("running {}".format(command))
            subprocess.run(command, shell=True)

    def off_on_cycle(self, off_on_command="off"):
        off_on_command = KASA_COMMAND_TEMPLATE.format(self.ip_address, off_on_command)
        self.execute_command(off_on_command)

    def print_info(self, offOrOn, duration):
        if self.use_remote_time:
            current_time = self.get_current_time()
            current_time = datetime.strptime(current_time, "%H:%M:%S")
        else:
            current_time = datetime.now()
        turn_on_time = (current_time + timedelta(minutes=duration)).strftime("%H:%M:%S").split('.')[0]
        current_time = current_time.strftime("%H:%M:%S").split('.')[0]
        print("{}: Pump {} until {}".format(current_time, offOrOn, turn_on_time))
        self.sleep_with_output(duration, "Done {} phase...".format(offOrOn))

    def control_kasa_plug(self, duration_on, duration_between):
        self.off_on_cycle("on")
        self.print_info("on", duration_on)

        if self.quit_event.is_set():
            return
        
        self.off_on_cycle("off")
        self.print_info("off", duration_between)
    
    def main(self):
        if self.show_cam:
            subprocess.Popen([
                "ffplay",
                "rtsp://Realname:minerva22"+camip+":554/stream1",
                "-vf", ffplay_vf_args 
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if self.start_off:
            self.off_on_cycle("off")
            self.print_info("off", self.delay_mins)


        while not self.quit_event.is_set():
            self.control_kasa_plug(self.on_mins, self.delay_mins)
        
        self.input_thread.join()



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Kasa Controller')
    parser.add_argument('delay_mins', metavar='D', type=float, nargs='?', help='A number of minutes to have pump off')
    parser.add_argument('on_mins', metavar='M', type=float, nargs='?', help='A number of minutes to have pump on')
    parser.add_argument("--ip_address", type=str, default=pumpip, help="IP address of the Kasa plug")
    parser.add_argument('--startoff', action='store_true', help='Start off')
    parser.add_argument('--dryrun', action='store_true', help='Run in dry-run mode (print commands instead of executing)')
    parser.add_argument('--showcam', action='store_true', help='Open a window with a live video feed')
    args = parser.parse_args()

    controller = KasaController(
        delay_mins=args.delay_mins,
        on_mins=args.on_mins,
        ip_address=args.ip_address,
        dry_run=args.dryrun,
        show_cam=args.showcam,
        start_off=args.startoff)
    controller.main()
