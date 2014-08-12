import logging
import threading
import time
from dirbalak.rackrun import config
from dirbalak.server import tojs


class HostThread(threading.Thread):
    def __init__(self, queue, queueLock, host, removeCallback):
        self._queue = queue
        self._queueLock = queueLock
        self._host = host
        self._removeCallback = removeCallback
        self._host.setForceReleaseCallback(self._allocationForcelyReleased)
        threading.Thread.__init__(self)
        self.daemon = True
        threading.Thread.start(self)

    def run(self):
        try:
            logging.info("Setting up host")
            self._host.setUp(config.GITHUB_NETRC_FILE)
            logging.info("Done setting up host")
            tojs.addToBuildHostsList(self._host.ipAddress())
            self._jobToJS(None)
            while True:
                self._buildOne()
        except:
            logging.exception("rack run host thread dies")
        finally:
            self._removeCallback(self)
            tojs.removeFromBuildHostsList(self._host.ipAddress())

    def _jobToJS(self, job):
        tojs.set("buildHost/%s" % self._host.ipAddress(), dict(ipAddress=self._host.ipAddress(), job=job))
        self._event("Became Idle" if job is None else "Started %s/%s" % (job['gitURL'], job['hexHash']))

    def _event(self, text):
        tojs.appendEvent("buildHost/%s" % self._host.ipAddress(), text)

    def _projectEvent(self, job, format):
        tojs.appendEvent("project/" + job['basename'], format % dict(
            job, ipAddress=self._host.ipAddress()))

    def _allocationForcelyReleased(self):
        self._host.close()

    def _buildOne(self):
        with self._queueLock:
            job = self._queue.next()
        if job is None:
            time.sleep(15)
            return
        logging.info("Received job, building: '%(job)s'", dict(job=job))
        self._jobToJS(job)
        self._projectEvent(job, "Host '%(ipAddress)s' starts to build hash '%(hexHash)s'")
        try:
            self._host.build(job['gitURL'], job['hexHash'], job['submit'], job['buildRootFS'])
        except:
            logging.exception("Job failed: '%(job)s'", dict(job=job))
            with self._queueLock:
                self._queue.done(job, False)
            self._event("Job failed")
            self._projectEvent(job, "Host '%(ipAddress)s' failed building hash '%(hexHash)s'")
            raise
        else:
            logging.info("Job succeeded: '%(job)s'", dict(job=job))
            with self._queueLock:
                self._queue.done(job, True)
            self._projectEvent(job, "Host '%(ipAddress)s' successfully built hash '%(hexHash)s'")
            self._event("Job succeeded")
        finally:
            self._jobToJS(None)
