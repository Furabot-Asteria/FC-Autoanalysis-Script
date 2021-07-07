# Flight Controller Log Analyzer
A script written in python to generate a Pass/Fail report for a flight log.

## Usage
Run the script with the argument "--path" providing the path of the target log file. For example:
```bash
python log_autoanalysis.py --path C:\00000019.log
```

Alternatively, Windows users can simply drag and drop the log file onto analyze.bat

The output report will be present in the 'output' folder, and the CSV files used for analysis will be present in the 'intermediates' folder. The intermediates can be deleted once analysis is complete.

The pass criteria can be changed using the config.ini file.

## Issues
As of now, whitespace characters in the file path of the script, or the flight log are prohibited. The script folder and the logs folder can be placed in the root of the C drive to avoid this issue.
