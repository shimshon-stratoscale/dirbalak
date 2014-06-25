import tempfile
import subprocess
import logging


class Graph:
    def __init__(self):
        self._arcs = {}
        self._attributes = {}

    def saveDot(self, filename):
        with open(filename, "w") as f:
            f.write(self._dotContents())

    def savePng(self, filename):
        assert filename.endswith(".png")
        dot = tempfile.NamedTemporaryFile(suffix=".dot")
        dot.write(self._dotContents())
        dot.flush()
        _run(["dot", dot.name, "-Tpng", "-o", filename])

    def addArc(self, source, dest, **attributes):
        self._arcs.setdefault(source, dict())[dest] = attributes

    def setNodeAttributes(self, node, **attributes):
        self._attributes[node] = attributes

    def _attributesToString(self, attributes):
        withQuotations = dict(attributes)
        for toQuote in ['label', 'color']:
            if toQuote in withQuotations:
                withQuotations[toQuote] = '"' + withQuotations[toQuote] + '"'
        return ", ".join(["%s=%s" % (k, v) for k, v in withQuotations.iteritems()])

    def _dotContents(self):
        result = ["digraph G {"]
        for source, arcs in self._arcs.iteritems():
            for dest, attributes in arcs.iteritems():
                result.append('"%s" -> "%s" [ %s ];' % (
                    source, dest, self._attributesToString(attributes)))
        for node, attributes in self._attributes.iteritems():
            result.append('"%s" [ %s ];' % (node, self._attributesToString(attributes)))
        result.append("}")
        return "\n".join(result)

    def _digraphSource(self):
        withoutIncomingArcs = set(self._arcs.keys()) | set(self._attributes.keys())
        for froms, dests in self._arcs.iteritems():
            for d in dests:
                withoutIncomingArcs.discard(d)
        assert len(withoutIncomingArcs) == 1
        return withoutIncomingArcs.pop()

    def renderAsTreeText(self, indentation="    "):
        result = self._treeIterate(self._digraphSource(), 0)
        return "\n".join(indentation * l[1] + l[0] for l in result)

    def _treeIterate(self, node, depth):
        label = self._attributes.get(node, dict(label=node)).get('label', node).replace("\n", "\t")
        result = [(label, depth)]
        for dest in self._arcs.get(node, dict()):
            result += self._treeIterate(dest, depth + 1)
        return result


def _run(command, cwd=None):
    try:
        return subprocess.check_output(
            command, cwd=cwd, stderr=subprocess.STDOUT,
            stdin=open("/dev/null"), close_fds=True)
    except subprocess.CalledProcessError as e:
        logging.error("Failed command '%s' output:\n%s" % (command, e.output))
        raise


if __name__ == "__main__":
    g = Graph()
    g.addArc("here", "there")
    g.addArc("there", "back again")
    g.setNodeAttributes("back again", label="first line\nsecond line")
    g.savePng("/tmp/t.png")
