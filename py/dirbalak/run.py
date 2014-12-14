import subprocess
import upseto.run
import tempfile
import shutil
import os
import select
import time


run = upseto.run.run


def runAndBeamLog(logName, command, cwd=None):
    with open("/dev/null") as devNull:
        popen = subprocess.Popen(
            command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=devNull, close_fds=True)
    outputLines = []
    TIMEOUT = 10 * 60
    OVERALL_TIMEOUT = 4 * 60 * 60
    before = time.time()
    while True:
        ready = select.select([popen.stdout], [], [], TIMEOUT)[0]
        if ready == []:
            outputLines.append(
                "\n\n\nNo output from command '%s' for over %s seconds, timeout" % (
                    command, TIMEOUT))
            returnCode = -1
            break
        if time.time() - before > OVERALL_TIMEOUT:
            outputLines.append(
                "\n\n\nCommand '%s' is taking over %s seconds, timeout" % (
                    command, OVERALL_TIMEOUT))
            returnCode = -1
            break
        line = popen.stdout.readline()
        if line == '':
            returnCode = popen.wait()
            break
        outputLines.append(line)
        print line,
    output = "".join(outputLines)
    beamLog(logName, output, returnCode)
    if returnCode != 0:
        raise Exception("The command '%s' failed, output:\n%s" % (command, output))


def beamLog(logName, output, returnCode):
    dir = tempfile.mkdtemp()
    try:
        logFilename = os.path.join(dir, logName + ".log.txt")
        with open(logFilename, "w") as f:
            f.write(output)
            f.write("\nRETURN_CODE %d" % returnCode)
        run(["logbeam", "upload", logFilename])
    finally:
        shutil.rmtree(dir, ignore_errors=True)


def beamLogsDir(under, path):
    run(["logbeam", "upload", path, "--under", under])
