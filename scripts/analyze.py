from configparser import ConfigParser
from pathlib import Path
import pandas as pd
import statistics
import subprocess
import itertools
import threading
import datetime
import argparse
import operator
import time
import sys
import os


def dir_path(string):
    if os.path.isfile(string):
        return string
    else:
        raise OSError(2, 'No such file or directory', string)


parser = argparse.ArgumentParser(description="Analyzes a flight controller log file, and returns PASS/FAIL based on the config parameters")
parser.add_argument('-p', '--path', type=dir_path, required=True, help='Location of target binary')
args = parser.parse_args()


def getCSV(msg_type):

    cmd = createcmd(msg_type)
    return subprocess.Popen(cmd, shell=True)


def createcmd(msg_type):

    csv_op = os.path.join(intermediates_path, log_name + "_" + msg_type + ".csv")
    cmd_args = ['python3', logdump_loc, '--format', 'csv', '--types', msg_type, log_bin, '>', csv_op]
    cmd = " "
    cmd = cmd.join(cmd_args)

    return cmd


def result(val, lim, op):
    ops = {'g': operator.gt,
           'l': operator.lt,
           'ge': operator.ge,
           'le': operator.le,
           'e': operator.eq,
           }
    pf = ops[op](val, lim)
    if pf:
        return '\t(PASS)'
    else:
        global all_pass
        all_pass = False
        return '\t(FAIL)'


def printUnavail():
    global all_pass
    all_pass = False
    return 'Unavailable\t(FAIL)'


def animate():
    for c in itertools.cycle(['|', '/', '-', '\\']):
        if done:
            break
        sys.stdout.write('\rExtracting CSV Files...' + c)
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write('\rDone!                   \n')
    sys.stdout.flush()


def uniquify(path):
    filename, extension = os.path.splitext(path)
    counter = 1

    while os.path.isfile(path):
        path = filename + '(' + str(counter) + ')' + extension
        counter += 1

    return path


def getParam(param):
    return parser.getfloat('parameters', param)


if __name__ == "__main__":

    logdump_loc = str(Path(__file__).parent / 'mavlogdump.py')
    intermediates_path = str(Path(__file__).resolve().parents[1] / 'intermediates')
    log_bin = args.path
    log_name = os.path.basename(log_bin).rsplit('.', 1)[0]
    output_path = str(Path(__file__).resolve().parents[1] / 'output')
    output_file = os.path.join(output_path, log_name + '_result.txt')
    output_file = uniquify(output_file)
    config_file = str(Path(__file__).resolve().parents[1] / 'config.ini')

    parser = ConfigParser()
    parser.read(config_file)

    if not os.path.exists(intermediates_path):
        os.makedirs(intermediates_path)

    if not os.path.exists(output_path):
        os.makedirs(output_path)


    process_list = []
    process_list.append(getCSV('MSG'))
    process_list.append(getCSV('BAT'))
    process_list.append(getCSV('FT'))
    process_list.append(getCSV('BARO'))
    process_list.append(getCSV('PARM'))
    process_list.append(getCSV('RTLE'))
    process_list.append(getCSV('GPS'))
    process_list.append(getCSV('GPS2'))
    process_list.append(getCSV('RCOU'))
    process_list.append(getCSV('VIBE'))

    done = False
    t = threading.Thread(target=animate)
    t.start()
    exit_codes = [process.wait() for process in process_list]
    done = True

    all_pass = True

    with open(output_file, 'w') as f, open(config_file, 'r') as c:

        #Basic Flight Information
        try:
            df = pd.read_csv(os.path.join(intermediates_path, log_name + '_MSG.csv'))
            try:
                f.write('Firmware Version: ' + df.iloc[0]['Message'] + '\n')
            except Exception:
                f.write('Firmware Version: ' + 'Unavailable' + '\n')

            try:
                f.write('Autopilot ID: ' + df.iloc[2]['Message'] + '\n')
            except Exception:
                f.write('Autopilot ID: ' + 'Unavailable' + '\n')

            try:
                ts_epoch = df.iloc[0]['timestamp']
                ts = datetime.datetime.fromtimestamp(ts_epoch).strftime('%Y-%m-%d %H:%M:%S')
                f.write('Flight Date: ' + ts + '\n')
            except Exception:
                f.write('Flight Date: ' + 'Unavailable' + '\n')

        except pd.errors.EmptyDataError:
            f.write('Firmware Version: ' + 'Unavailable' + '\n')
            f.write('Autopilot ID: ' + 'Unavailable' + '\n')
            f.write('Flight Date: ' + 'Unavailable' + '\n')

        try:
            df = pd.read_csv(os.path.join(intermediates_path, log_name + '_FT.csv'))
            try:
                fl_seconds = int(df.iloc[-1]['flight_time'])
                fl_time = datetime.timedelta(seconds=fl_seconds)
                f.write('Flight Time: ' + str(fl_time) + '\n')
            except Exception:
                f.write('Flight Time: ' + 'Unavailable' + '\n')

        except pd.errors.EmptyDataError:
            f.write('Flight Time: ' + 'Unavailable' + '\n')

        try:
            df = pd.read_csv(os.path.join(intermediates_path, log_name + '_BARO.csv'))
            try:
                max_alt = df['Alt'].max().round(2)
                f.write('Max Altitude: ' + str(max_alt) + 'm' + '\n')
            except Exception:
                f.write('Max Altitude: ' + 'Unavailable' + '\n')

        except pd.errors.EmptyDataError:
            f.write('Max Altitude: ' + 'Unavailable' + '\n')

        try:
            df = pd.read_csv(os.path.join(intermediates_path, log_name + '_RTLE.csv'))
            max_rtl_cr_est = df['RtlCrEst'].max().round(2)
            df = pd.read_csv(os.path.join(intermediates_path, log_name + '_PARM.csv'))
            mah_cr_est = df[df['Name'] == 'MAH_CR_CONS_PM']['Value'].iloc[0]
            max_dth_est = (max_rtl_cr_est/mah_cr_est).round(2)
            f.write('Max Distance from Home (Estimate): ' + str(max_dth_est) + 'm' + '\n' * 2)
        except Exception:
            f.write('Max Distance from Home (Estimate): ' + 'Unavailable' + '\n' * 2)

        #Battery Information
        try:
            df = pd.read_csv(os.path.join(intermediates_path, log_name + '_BAT.csv'))
            try:
                avg_curr = df['Curr'].mean().round(2)
                f.write('Average Current Draw: ' + str(avg_curr) + 'A' + result(avg_curr, getParam('avg_curr'), 'l') + '\n')
            except Exception:
                f.write('Average Current Draw: ' + printUnavail() + '\n')

            try:
                min_voltage = df['Volt'].min().round(2)
                f.write('Minimum Battery Voltage: ' + str(min_voltage) + 'V' + result(min_voltage, getParam('bat_volt'), 'g') + '\n')
            except Exception:
                f.write('Minimum Battery Voltage: ' + printUnavail() + '\n')

        except Exception:
            f.write('Average Current Draw: ' + printUnavail() + '\n')
            f.write('Minimum Battery Voltage: ' + printUnavail() + '\n')

        try:
            bat_rem = df['BatRem'].min().round(2)
            df = pd.read_csv(os.path.join(intermediates_path, log_name + '_PARM.csv'))
            bat_capacity = df[df['Name'] == 'BATT_CAPACITY']['Value'].iloc[0]
            bat_cons = (bat_capacity - bat_rem).round(2)
            bat_perc = (bat_cons*100/bat_capacity).round(2)
            f.write('Battery Consumed (mAh): ' + str(bat_cons) + 'mAh' + '\n')
            f.write('Battery Consumed (%): ' + str(bat_perc) + '%' + result(bat_perc, getParam('bat_perc'), 'l') + '\n' * 2)

        except Exception:
            f.write('Battery Consumed: ' + printUnavail() + '\n')
            f.write('Battery Remaining: ' + printUnavail() + '\n' * 2)

        #GPS Health
        try:
            df = pd.read_csv(os.path.join(intermediates_path, log_name + '_GPS.csv'))
            try:
                avg_sats = df['NSats'].mean().round(2)
                f.write('Average Satellite Count (Primary): ' + str(avg_sats) + result(avg_sats, getParam('gps1_sat'), 'g') + '\n')
            except Exception:
                f.write('Average Satellite Count (Primary): ' + printUnavail() + '\n')

            try:
                avg_hdop = df['HDop'].mean().round(2)
                f.write('Average HDOP (Primary): ' + str(avg_hdop) + result(avg_hdop, getParam('gps1_hdop'), 'l') + '\n')
            except Exception:
                f.write('Average HDOP (Primary): ' + printUnavail() + '\n')

        except pd.errors.EmptyDataError:
            f.write('Average Satellite Count (Primary): ' + printUnavail() + '\n')
            f.write('Average HDOP (Primary): ' + printUnavail() + '\n')

        try:
            df = pd.read_csv(os.path.join(intermediates_path, log_name + '_GPS2.csv'))
            try:
                avg_sats2 = df['NSats'].mean().round(2)
                f.write('Average Satellite Count (Secondary): ' + str(avg_sats2) + result(avg_sats2, getParam('gps2_sat'), 'g') + '\n')
            except Exception:
                f.write('Average Satellite Count (Secondary): ' + printUnavail() + '\n')

            try:
                avg_hdop2 = df['HDop'].mean().round(2)
                f.write('Average HDOP (Secondary): ' + str(avg_hdop2) + result(avg_hdop, getParam('gps2_hdop'), 'l') + '\n' * 2)
            except Exception:
                f.write('Average HDOP (Secondary): ' + printUnavail() + '\n' * 2)

        except pd.errors.EmptyDataError:
            f.write('Average Satellite Count (Secondary): ' + printUnavail() + '\n')
            f.write('Average HDOP (Secondary): ' + printUnavail() + '\n' * 2)

        #Motor PWM
        try:
            df = pd.read_csv(os.path.join(intermediates_path, log_name + '_RCOU.csv'))
            try:
                c1 = df['C1'].mean().round(2)
                f.write('Average Motor 1 PWM: ' + str(c1) + result(c1, getParam('mot1_pwm'), 'l') + '\n')
            except Exception:
                f.write('Average Motor 1 PWM: ' + printUnavail() + '\n')

            try:
                c2 = df['C2'].mean().round(2)
                f.write('Average Motor 2 PWM: ' + str(c2) + result(c2, getParam('mot2_pwm'), 'l') + '\n')
            except Exception:
                f.write('Average Motor 2 PWM: ' + printUnavail() + '\n')

            try:
                c3 = df['C3'].mean().round(2)
                f.write('Average Motor 3 PWM: ' + str(c3) + result(c3, getParam('mot3_pwm'), 'l') + '\n')
            except Exception:
                f.write('Average Motor 3 PWM: ' + printUnavail() + '\n')

            try:
                c4 = df['C4'].mean().round(2)
                f.write('Average Motor 4 PWM: ' + str(c4) + result(c4, getParam('mot4_pwm'), 'l') + '\n')
            except Exception:
                f.write('Average Motor 4 PWM: ' + printUnavail() + '\n')

            try:
                sd = round(statistics.stdev([c1, c2, c3, c4]), 2)
                f.write('Standard Deviation: ' + str(sd) + result(sd, getParam('mot_sd'), 'l') + '\n' * 2)
            except Exception:
                f.write('Standard Deviation: ' + printUnavail() + '\n' * 2)

        except pd.errors.EmptyDataError:
            f.write('Average Motor 1 PWM: ' + printUnavail() + '\n')
            f.write('Average Motor 2 PWM: ' + printUnavail() + '\n')
            f.write('Average Motor 3 PWM: ' + printUnavail() + '\n')
            f.write('Average Motor 4 PWM: ' + printUnavail() + '\n')
            f.write('Standard Deviation: ' + printUnavail() + '\n' * 2)

        #Accelerometer Vibration Levels
        try:
            df = pd.read_csv(os.path.join(intermediates_path, log_name + '_VIBE.csv'))
            try:
                vibeX = df['VibeX'].mean().round(2)
                f.write('Average Vibration Levels (X): ' + str(vibeX) + 'm/s/s' + result(vibeX, getParam('vibe_x'), 'l') + '\n')
            except Exception:
                f.write('Average Vibration Levels (X): ' + printUnavail() + '\n')

            try:
                vibeY = df['VibeY'].mean().round(2)
                f.write('Average Vibration Levels (Y): ' + str(vibeY) + 'm/s/s' + result(vibeY, getParam('vibe_y'), 'l') + '\n')
            except Exception:
                f.write('Average Vibration Levels (Y): ' + printUnavail() + '\n')

            try:
                vibeZ = df['VibeZ'].mean().round(2)
                f.write('Average Vibration Levels (Z): ' + str(vibeZ) + 'm/s/s' + result(vibeZ, getParam('vibe_z'), 'l') + '\n' * 2)
            except Exception:
                f.write('Average Vibration Levels (Z): ' + printUnavail() + '\n' * 2)

        except pd.errors.EmptyDataError:
            f.write('Average Vibration Levels (X): ' + printUnavail() + '\n')
            f.write('Average Vibration Levels (Y): ' + printUnavail() + '\n')
            f.write('Average Vibration Levels (Z): ' + printUnavail() + '\n' * 2)

        if all_pass:
            f.write("Overall Result: PASS")
            sys.stdout.write("\rOverall Result: PASS\n")
        else:
            f.write("Overall Result: FAIL")
            sys.stdout.write("\rOverall Result: FAIL\n")

        sys.stdout.write('Output saved to ' + output_file + '\n')
