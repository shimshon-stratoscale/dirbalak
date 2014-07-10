from realtimewebui import server
from realtimewebui import rootresource
from realtimewebui import render
import argparse
from dirbalak.server import fetchthread
from dirbalak.server import multiverse
from dirbalak.server import resources
from dirbalak.server import graphsresource
from dirbalak.server import callbacks
from dirbalak.server import queue
import logging

logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser()
parser.add_argument("--webPort", type=int, default=6001)
parser.add_argument("--webSocketPort", type=int, default=6002)
parser.add_argument("--reservePort", type=int, default=6003)
parser.add_argument("--githubListenerPort", type=int, default=6004)
parser.add_argument("--username", default="stratotest")
parser.add_argument("--password", default="2good2betruebettercallchucknorris")
parser.add_argument("--multiverseFile", required=True)
parser.add_argument("--officialObjectStore", required=True)
parser.add_argument("--unsecured", action="store_true")
args = parser.parse_args()

fetchThread = fetchthread.FetchThread()
multiverseInstance = multiverse.Multiverse.load(args.multiverseFile, fetchThread=fetchThread)
multiverseInstance.needsFetch("Dirbalak starting")
fetchThread.start(multiverseInstance)
callbacks.Callbacks(multiverseInstance)
queueInstance = queue.Queue(args.officialObjectStore, multiverseInstance)
fetchThread.addPostTraverseCallback(queueInstance.recalculate)

render.addTemplateDir("html")
render.DEFAULTS['title'] = "Dirbalak"
render.DEFAULTS['brand'] = "Dirbalak"
render.DEFAULTS['mainMenu'] = [dict(title="Projects", href="/projects"), dict(title="Queue", href="/queue")]
root = rootresource.rootResource()
root.putChild("projects", rootresource.Renderer("projects.html", dict(activeMenuItem="Projects")))
root.putChild("project", resources.Projects())
graphResource = graphsresource.GraphsResource(multiverseInstance)
root.putChild("graphs", graphResource)
fetchThread.addPostTraverseCallback(graphResource.update)
root.putChild("queue", rootresource.Renderer("queue.html", dict(activeMenuItem="Queue")))
if args.unsecured:
    server.runUnsecured(root, args.webPort, args.webSocketPort)
else:
    server.runSecured(root, args.webPort, args.webSocketPort, args.username, args.password)
