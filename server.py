import json
import socketserver
import time
from http.server import BaseHTTPRequestHandler

import mysql.connector

MYSQL_DB_PASSWORD = 'Passw0rd'

MYSQL_DB_USER = 'root'

CACHE_LIFETIME = 10

INDEX_HTML = """<html><body>
            <a href="/realtime">first</a> | <a href="/cached">second</a> | <a href="/joined">third</a>
            </body></html>"""

PORT = 8000

# Запустить пару виртуальных машин (можно 2)
# Из базы достать: 
# SELECT uuid, display_name from instances where vm_state = 'active'
# SELECT mac_address, device_id from ports
# Написать HTTP сервис, который выдает следующий json: [
# {
# instance_id: «xxxxxx»,
# interfaces: [
#  «mac_address»
# ]
# }
# ]

query_instances = "SELECT uuid, display_name from instances where vm_state = 'active'"
query_ports = "SELECT mac_address, device_id from neutron.ports"
query_one_port = "SELECT mac_address, device_id from neutron.ports WHERE device_id = %(uuid)s"
query_combined = "SELECT uuid, display_name, mac_address FROM instances JOIN neutron.ports ON device_id = uuid WHERE vm_state = 'active'"

# Global variables used for cache
ports_dict = {}
ports_ts = 0


class OpenstackHandler(BaseHTTPRequestHandler):

    def ok_headers(self, content_type='application/json'):
        self.send_response(200)
        # Send headers
        self.send_header('Content-type', content_type)
        self.end_headers()

    # This method is used for list comprehensions in /realtime
    @staticmethod
    def one_instance(ports_cursor, uuid):
        ports_cursor.execute(query_one_port, {"uuid": uuid})
        return {"instance_id": uuid, "interfaces": [mac for (mac, device_id) in ports_cursor.fetchall()]}

    def realtime(self):
        instances_cursor, ports_cursor = conn.cursor(), conn.cursor()
        try:
            instances_cursor.execute(query_instances)
            response = [self.one_instance(ports_cursor, uuid) for (uuid, display_name) in instances_cursor.fetchall()]
            self.wfile.write(bytes(json.dumps(response, indent=True), 'utf8'))
        finally:
            instances_cursor.close()
            ports_cursor.close()

    # This method is used for updating ports data in /cached
    @staticmethod
    def maybe_update_cached_ports():
        global ports_ts, ports_dict
        if time.time() > ports_ts + CACHE_LIFETIME:
            ports_ts = time.time()
            ports_cursor = conn.cursor()
            try:
                ports_cursor.execute(query_ports)
                ports_dict.clear()

                for (mac_address, device_id) in ports_cursor.fetchall():
                    if device_id in ports_dict:
                        ports_dict[device_id].append(mac_address)
                    else:
                        ports_dict[device_id] = [mac_address]

            finally:
                ports_cursor.close()

    def cached(self):
        self.maybe_update_cached_ports()
        instances_cursor = conn.cursor()
        try:
            instances_cursor.execute(query_instances)
            response = [{"instance_id": uuid, "interfaces": ports_dict[uuid]} for (uuid, display_name) in
                        instances_cursor.fetchall()]
            self.wfile.write(bytes(json.dumps(response, indent=True), 'utf8'))
        finally:
            instances_cursor.close()

    def joined(self):
        combined_cursor = conn.cursor()
        try:
            combined_cursor.execute(query_combined)
            response_dict = {}
            for (uuid, display_name, mac_address) in combined_cursor.fetchall():
                if uuid in response_dict:
                    response_dict[uuid].append(mac_address)
                else:
                    response_dict[uuid] = [mac_address]

            response = [{"instance_id": uuid, "interfaces": response_dict[uuid]} for uuid in response_dict]
            self.wfile.write(bytes(json.dumps(response, indent=True), 'utf8'))
        finally:
            combined_cursor.close()

    def do_GET(self):
        # Send response status code
        if self.path == '/':
            self.ok_headers("text/html")
            self.wfile.write(bytes(INDEX_HTML, "utf8"))
        elif self.path == '/realtime':
            self.ok_headers()
            self.realtime()
        elif self.path == '/cached':
            self.ok_headers()
            self.cached()
        elif self.path == '/joined':
            self.ok_headers()
            self.joined()
        else:
            self.send_response_only(404, "Not found")


if __name__ == '__main__':
    conn = mysql.connector.connect(user=MYSQL_DB_USER, password=MYSQL_DB_PASSWORD, database='nova_cell1')
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("", PORT), OpenstackHandler)
    print("Listening on {}".format(PORT))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Server stopped on keyboard interrupt")
    except Exception:
        print("Server stopped on exception")
    finally:
        httpd.server_close()
        conn.close()

    print("DONE")
