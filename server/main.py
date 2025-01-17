from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import traceback
import fuzzy

hostName = "localhost"
serverPort = 8080


@dataclass
class UserDoesNotExistException(Exception):
    similar: str


class Database:
    def parse(self, content: str) -> dict:
        return json.loads(content)

    def __init__(self, file="db.json"):
        self.file = file
        self.refresh()
    
    def refresh(self):
        with open(self.file, "r") as f:
            self.db = self.parse(f.read())

    def save(self, name=None):
        with open(self.file, "w") as f:
           f.write(json.dumps(self.db))

    def write(self, name: str, score: int):
        if name not in self.db:
            similar = fuzzy.fuzzy_search(name, self.db.keys())
            raise UserDoesNotExistException(similar[0])

        # always use higher score
        if score > self.db[name]["score"]:
            self.db[name] = {"score": score}
            self.save(name)
    
    # suggest a correct name if name not in db
    def verify(self, name: str) -> None | str:
        if name not in self.db:
            similar = fuzzy.fuzzy_search(name, self.db.keys())
            return similar[0]
        return None

    def read(self, name: str) -> dict:
        if name in self.db:
            return self.db[name]

    def ranking(self) -> dict:
        return {name: self.db[name]["score"] for name in self.db.keys()}

    def createUser(self, name: str) -> bool:
        if name in self.db:
            return False # existiert schon
        self.db[name.replace(",", "")] = {"score": 0}
        self.save(name)
        return True


class MyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/register":
            htmlStr = open("register.html", "r").read()
            self._set_headers()
            self.wfile.write(bytes(htmlStr + "\r\n\r\n", "utf-8"))

        else: # get ranking
            r = "\n".join([name + "," + str(score) for name, score in db.ranking().items()])
            self._set_headers()
            self.wfile.write(bytes(r + "\r\n\r\n", "utf-8"))
            self.wfile.write(bytes("END", "utf-8"))

    def _set_headers(self, status=200):
        self.send_response(status)
        self.end_headers()

    def do_POST(self):
        if self.path == "/createUser":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length).decode("utf-8")
            if not db.createUser(post_data[post_data.find("=")+1:]):
                self._set_headers(409)

        if self.path == "/verify":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length).decode("utf-8")
            print("verify: " + post_data)
            similar = db.verify(post_data)
            self._set_headers()
            if similar == None:
                self.wfile.write(bytes("EXISTS", "utf-8"))
            else:
                self.wfile.write(bytes("Der Nutzer existiert nicht. Meintest du " + similar + "?", "utf-8"))

        if self.path == "/score":
            content_length = int(self.headers["Content-Length"])

            try:
                post_data = self.rfile.read(content_length).decode("utf-8")
                print("score: " + post_data)
                data = json.loads(post_data)
                db.write(data["name"], data["score"])
                self._set_headers()

            except UserDoesNotExistException as e:
                self._set_headers(status=400)
                self.wfile.write(
                    bytes("Der nutzer existiert nicht. Meintest du " + e.similar + "?", "utf-8")
                )
            
            except Exception as ex:
                print("".join(traceback.TracebackException.from_exception(ex).format()))
                self._set_headers(status=400)
        
        self.wfile.write(bytes("END", "utf-8"))


db = Database()
webServer = HTTPServer((hostName, serverPort), MyServer)
print("Server started http://%s:%s" % (hostName, serverPort))

try:
    webServer.serve_forever()
except KeyboardInterrupt:
    pass

webServer.server_close()
print("Server stopped.")
