from flask import Flask, Markup, render_template, request, Response
import os
import json
import httplib
import urllib
import re
import socket
import sys
import indexer, config, async, client

app = Flask('webapp', template_folder=os.getcwd() + "/templates")

@app.route("/")
def index():
    return render_template("index.html", peers=config.neighbors, port=config.webapp)

@app.route("/query", methods=["GET"])
def query():
    print  request.data

    x = {}
    for i in request.data.split("&"):
        k,v = i.split("=")
        x[k]=v
    return indexer.search(x["search"], x["ip"])

@app.route("/neighbors", methods=['GET'])
def neighbors():
    print config.neighbors
    print request.remote_addr
    if not request.remote_addr in config.neighbors:
        async.event.asynchronous_callback(
            client.SandwichGetter.bootstrap_into_network,
            (request.remote_addr))
    return json.dumps(config.neighbors)


@app.route("/files/<path:filepath>")
def files(filepath):
    # scary bad things can happen here if the bad people do the bad things
    # to the filepath. Let's try and avoid that.
    if filepath[0] in ['.', '/', '\\','~']:
        return "Your filepath was bad, and you should feel bad."

    full_filepath = config.shared_directory + os.sep + filepath

    if not os.path.isfile(full_filepath):
        return "That file doesn't exist. Have a blank page instead.", 404

    cl = os.path.getsize(full_filepath)

    def download():
        with open(full_filepath, "rb") as f:
            while True:
                block = f.read(config.chunk_size)
                if not block: break
                yield block

    response = Response(download(), direct_passthrough=True)
    response.headers["Content-Type"] = "application/octet-stream"
    response.headers["Content-Length"] = cl
    return response


@app.route("/download", methods=["GET"])
def down_to_shared():
    url = str(request.args.get("url"))
    ip = url[str.find(url,"//")+2 :  str.find(url,"/",8)]
    res = urllib.unquote(url[str.find(url,"/files/") + 6 : ])
    url = url[str.find(url, "/files/") : ]
    size = str(request.args.get("size"))
    return client.SandwichGetter.get_res(url, ip, res, size)

@app.route("/search", methods=["GET"])
def search():
    x = []
    try:
        conn = None
        if not request.args.get("host"):
            for n in config.neighbors:
                conn = httplib.HTTPConnection("%s:%d" % (n, config.webapp),
                                            timeout=config.timeout)
                conn.request("GET", "/query",
                        urllib.urlencode({'search': request.args.get("search"), 'ip': n}))
                x += json.loads(conn.getresponse().read())
                conn.close()
                conn = None
        else:
            conn = httplib.HTTPConnection("%s:%d" % (request.args.get("host"),
                                                    config.webapp), timeout=config.timeout)

            conn.request("GET", "/query", urllib.urlencode({'search': "", 'ip': request.args.get("host")}))
            x += json.loads(conn.getresponse().read())
    except socket.error:
        print "Search failed"
        if config.debug:
            print str(sys.exc_info())

    if conn != None:
        conn.close()

    return render_template("query_result.html", index=x)

def run():

    app.debug = config.debug
    # flask is dumb and tries to restart infinitely if we fork it into a subprocess.
    # this is bad. So we disable it, and hate on flask a bit.
    app.run(port=config.webapp, use_reloader=False, host='0.0.0.0')

if __name__ == '__main__':
    app.debug = True
    app.run()
