from upseto import gitwrapper
from dirbalak.rackrun import solventofficiallabels
from dirbalak.rackrun import buildstate
from dirbalak import repomirrorcache
from dirbalak.server import tojs
import collections


class Queue:
    NON_MASTER_DEPENDENCIES = 1
    MASTERS_NOT_BUILT = 2
    MASTERS_WHICH_BUILD_ONLY_FAILED = 3
    MASTERS_REBUILD = 4

    def __init__(self, officialObjectStore, multiverse):
        self._officialObjectStore = officialObjectStore
        self._multiverse = multiverse
        self._buildState = buildstate.BuildState()
        self._queue = dict()
        self._reversedMap = dict()
        self._cantBeBuilt = dict()
        self._rebuildRotate = 0

    def next(self):
        for key in sorted(self._queue.keys()):
            for job in self._queue[key]:
                if not self._buildState.get(job['gitURL'], job['hexHash'])['inProgress']:
                    self._buildState.inProgress(job['gitURL'], job['hexHash'])
                    if key == self.MASTERS_REBUILD:
                        self._rotateMastersRebuild(self._queue)
                        self._toJS()
                    return job

    def done(self, job, success):
        self._buildState.done(job['gitURL'], job['hexHash'], success)
        self.recalculate()

    def queue(self):
        return self._queue

    def cantBeBuilt(self):
        return self._cantBeBuilt

    def recalculate(self):
        labels = solventofficiallabels.SolventOfficialLabels(self._officialObjectStore)
        self._reversedMap = dict()
        self._cantBeBuilt = dict()
        for dep in self._multiverse.getTraverse().dependencies():
            basename = gitwrapper.originURLBasename(dep.gitURL)
            project = self._multiverse.projects[basename]
            hexHash = dep.hash if dep.hash != 'origin/master' else dep.masterHash
            projectDict = dict(
                basename=basename, hash=dep.hash, gitURL=dep.gitURL, submit=True,
                hexHash=hexHash, buildRootFS=project.buildRootFS())
            buildState = self._buildState.get(dep.gitURL, hexHash)
            projectDict.update(buildState)
            unbuiltRequirements = self._unbuiltRequirements(dep.gitURL, dep.hash, labels)
            if unbuiltRequirements:
                self._cantBeBuilt[(basename, dep.hash)] = unbuiltRequirements
                continue
            if dep.hash == "origin/master":
                mirror = repomirrorcache.get(dep.gitURL)
                if labels.built(basename, mirror.hash('origin/master')):
                    if buildState['failures'] > 0 and buildState['successes'] == 0:
                        self._put(projectDict, self.MASTERS_WHICH_BUILD_ONLY_FAILED)
                    else:
                        projectDict['submit'] = False
                        self._put(projectDict, self.MASTERS_REBUILD)
                else:
                    self._put(projectDict, self.MASTERS_NOT_BUILT)
            else:
                if not labels.built(basename, dep.hash):
                    projectDict['requiringBasename'] = gitwrapper.originURLBasename(dep.requiringURL)
                    self._put(projectDict, self.NON_MASTER_DEPENDENCIES)
        self._reverseMap()
        self._toJS()

    def _toJS(self):
        tojs.set('queue/queue', self._queue)
        tojs.set('queue/cantBeBuilt', [
            dict(basename=basename, hash=hash, unbuiltRequirements=unbuiltRequirements)
            for (basename, hash), unbuiltRequirements in self._cantBeBuilt.iteritems()])

    def _unbuiltRequirements(self, gitURL, hash, labels):
        result = []
        for dep in self._multiverse.getTraverse().dependencies():
            if dep.requiringURL != gitURL or dep.requiringURLHash != hash:
                continue
            basename = gitwrapper.originURLBasename(dep.gitURL)
            mirror = repomirrorcache.get(dep.gitURL)
            hexHash = dep.hash if dep.hash != 'origin/master' else mirror.hash('origin/master')
            if not labels.built(basename, hexHash):
                result.append(dict(basename=basename, hash=dep.hash))
        return result

    def _reverseMap(self):
        queue = dict()
        for priority, project in self._reversedMap.values():
            queue.setdefault(priority, []).append(project)
        if self.MASTERS_REBUILD in queue:
            deque = collections.deque(queue[self.MASTERS_REBUILD])
            deque.rotate(self._rebuildRotate)
            queue[self.MASTERS_REBUILD] = list(deque)
        self._queue = queue

    def _rotateMastersRebuild(self, queue):
        if self.MASTERS_REBUILD not in queue:
            return
        self._rebuildRotate -= 1
        deque = collections.deque(queue[self.MASTERS_REBUILD])
        deque.rotate(-1)
        queue[self.MASTERS_REBUILD] = list(deque)

    def _put(self, project, priority):
        key = (project['basename'], project['hash'])
        currentPriority = self._reversedMap.get(key, (10000, None))[0]
        if currentPriority > priority:
            project['priority'] = priority
            self._reversedMap[key] = (priority, project)
