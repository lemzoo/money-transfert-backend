#! /usr/bin/env python3
from flask.ext.script import Manager

monitoring_manager = Manager(usage="Handle core monitoring functions")


@monitoring_manager.option('--port', help='Port to listen on', default=8080)
def run_monitoring_server(port):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from psutil import process_iter
    import re
    from json import dumps

    PROCESS_NAME = re.compile('python')
    GUNICORN_NAME = re.compile('gunicorn')
    CMD_NAME = re.compile('sief.main:bootstrap_app')

    class MonitoringWrapper(BaseHTTPRequestHandler):

        # Handler for the GET requests
        def do_GET(self):
            if self.path != '/monitoring/api':
                self.send_error(404)
                return

            def forge_answer_api(status, pid):
                details = {'name': "Test process API ",
                           'label': "Check API process",
                           'status': 'OK',
                           'reason': 'API is running. PID : %s' % pid
                           }
                if pid:
                    details.update({'reason': 'API is running. PID : %s' % pid})
                else:
                    details.update({'reason': 'API is not running'})

                return dumps({'globalStatus': status,
                              'details': [details, ]}).encode()

            if self.path == '/monitoring/api':
                # Check process and get /moi with provided credentials
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                for proc in map(lambda x: x.as_dict(['cmdline', 'pid']), process_iter()):
                    cmdline = proc.get('cmdline', [])
                    pid = proc.get('pid')
                    if (len(cmdline) and
                            PROCESS_NAME.search(cmdline[0]) and
                            GUNICORN_NAME.search(cmdline[1]) and
                            CMD_NAME.search(cmdline[2])):
                        self.wfile.write(forge_answer_api('OK', pid))
                        return
                self.wfile.write(forge_answer_api('ERROR', None))

    try:
        server = HTTPServer(('', int(port)), MonitoringWrapper)
        server.serve_forever()
    except KeyboardInterrupt:
        server.socket.close()

if __name__ == "__main__":
    monitoring_manager.run()
