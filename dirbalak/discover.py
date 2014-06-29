from dirbalak import traverse
from dirbalak import graph
from dirbalak import repomirrorcache
from dirbalak import describetime
from upseto import gitwrapper
from upseto import run


class Discover:
    _CONTINUOUS_INTEGRATION_VIOLATION_TIME = 14 * 24 * 60 * 60

    def __init__(self, projects, objectStore):
        self._rootProjects = projects
        self._objectStore = objectStore
        self._dependencies = []
        self._cachedGraph = None
        self._traverse = traverse.Traverse()
        for project in projects:
            for dependency in self._traverse.traverse(project, 'origin/master'):
                self._dependencies.append(dependency)

    def renderText(self):
        return "\n".join([str(d) for d in self._dependencies]) + \
                "\n\n" + self.makeGraph().renderAsTreeText()

    def makeGraph(self):
        if self._cachedGraph is None:
            self._cachedGraph = self._makeGraph()
        return self._cachedGraph

    def _makeGraph(self):
        graphInstance = graph.Graph()
        for dep in self._dependencies:
            self._addNodeToGraph(graphInstance, dep.gitURL)
            if dep.requiringURL is not None:
                if dep.requiringURLHash != 'origin/master':
                    continue
                self._addNodeToGraph(graphInstance, dep.requiringURL)
                self._addArcToGraph(graphInstance, dep)
        return graphInstance

    def _lineStyleFromDependencyType(self, type):
        if type == 'upseto':
            return 'solid'
        elif type == 'solvent':
            return 'dashed'
        else:
            raise AssertionError("Unknown type %s" % type)

    def _addArcToGraph(self, graphInstance, dep):
        basename = gitwrapper.originURLBasename(dep.gitURL)
        mirror = repomirrorcache.get(dep.gitURL)
        distance = mirror.distanceFromMaster(dep.hash)
        requiringBasename = gitwrapper.originURLBasename(dep.requiringURL)
        graphInstance.addArc(
            requiringBasename, basename, style=self._lineStyleFromDependencyType(dep.type),
            ** self._attributesFromDistanceFromMaster(distance))

    def _addNodeToGraph(self, graphInstance, gitURL):
        basename = gitwrapper.originURLBasename(gitURL)
        mirror = repomirrorcache.get(gitURL)
        graphInstance.setNodeAttributes(
            basename, label=basename, cluster=self._cluster(basename),
            ** self._fillColor(mirror, basename))

    def _attributesFromDistanceFromMaster(self, distance):
        if distance is None:
            return {}
        else:
            label = "behind:\\n%d commits" % distance['commits']
            color = "#000000"
            if 'time' in distance:
                label += "\\n%s" % describetime.describeTime(distance['time'])
                if distance['time'] > self._CONTINUOUS_INTEGRATION_VIOLATION_TIME:
                    color = "#FF0000"
                else:
                    color = "#990000"
            return dict(color=color, label=label)

    def _cluster(self, basename):
        return 'rootfs' if basename.startswith('rootfs-') else 'projects'

    def _fillColor(self, mirror, basename):
        if self._objectStore is None:
            return {}
        hash = mirror.hash('origin/master')
        labelBase = 'solvent__%s__build__%s__' % (basename, hash)
        labels = run.run([
            'osmosis', 'listlabels', '^' + labelBase,
            '--objectStores', self._objectStore]).strip().split("\n")
        states = [label[len(labelBase):] for label in labels]
        if 'official' in states:
            return dict()
        elif 'clean' in states:
            return dict(style="filled", color="#DDDDDD", peripheries=1)
        else:
            return dict(style="filled", color="#888888", peripheries=1, text_build="NOT BUILT")
