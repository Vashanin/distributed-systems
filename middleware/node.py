import json
import asyncio
import copy
import pprint

import websockets
from websockets.exceptions import ConnectionClosed
from sshtunnel import SSHTunnelForwarder
import configs


class LockedException(Exception):
    def __init__(self):
        pass


class Node(object):
    storage = "storage.json"

    def __init__(self, host):
        self.host = host
        self.current_node  = list(filter(lambda v: v['host'] == host, configs.nodes))
        self.another_nodes = list(filter(lambda v: v['host'] != host, configs.nodes))

        self.locks = {}

    @staticmethod
    def read(var: str = None):
        with open(Node.storage) as fl:
            if var is None:
                return json.load(fl)
            else:
                return json.load(fl)[var]

    @staticmethod
    def update(var: str, value: float):
        data = Node.read()
        data.update({var: value})

        with open(Node.storage, "w") as fl:
            json.dump(data, fl)

    async def commit(self, msg: dict):
        responses = []

        for var in set([v['var'] for v in msg['msg']]):
            responses = await self.notifier(
                msg={"node": self.host, "var": var, "action": "lock"},
                wait_response=True)
            success_set = set([v['success'] for v in responses])
            if success_set != {True} and len(responses) > 0:
                raise LockedException()

        for item in msg['msg']:
            response = copy.deepcopy(item)
            if item['action'] == "read":
                variables = Node.read()
                if item['var'] in variables:
                    response.update({"result": Node.read(item['var'])})
                else:
                    response.update({"result": None})

            elif item['action'] == 'update':
                value = float(eval(item['value'], Node.read()))

                Node.update(item['var'], value)
                await self.notifier({
                    "node": self.host,
                    "var": item['var'],
                    "action": "node_update",
                    "value": value})
                response.update({"result": "ok"})

            responses.append(response)

        await asyncio.sleep(5.0)

        return responses

    async def listener(self, ws, path):
        _ = path

        while True:
            try:
                msg: dict = json.loads(await ws.recv())
                print(f"Receive msg: \t{pprint.pformat(msg)}")

                if msg['action'] == "request":
                    while True:
                        requested_variables = set([v['var'] for v in msg['msg']])
                        locked_variables = set([w for w, v in self.locks.items() if v is True])

                        try:
                            if len(requested_variables & locked_variables) == 0:
                                for item in msg['msg']:
                                    self.locks[item['var']] = True
                                await ws.send(json.dumps(await self.commit(msg=msg)))
                            else:
                                raise LockedException()
                        except LockedException:
                            # Locked
                            print(f"Locked.\n"
                                  f"\tRequested variables: {requested_variables}\n"
                                  f"\tLocked variables: {locked_variables}")
                            await asyncio.sleep(configs.timeout)
                        else:
                            break
                        finally:
                            for var in set([v['var'] for v in msg['msg']]):
                                await self.notifier({"node": self.host, "var": var, "action": "release"})
                                self.locks[var] = False

                if msg['action'] == "lock":
                    response = msg.copy()

                    if msg['var'] not in self.locks or not self.locks[msg['var']]:
                        self.locks[msg['var']] = True
                        response.update({"success": True})
                    else:
                        response.update({"success": False})

                    await ws.send(json.dumps(response))

                if msg['action'] == "release":
                    self.locks[msg['var']] = False

                if msg['action'] == "node_update":
                    Node.update(msg['var'], float(msg['value']))

            except ConnectionClosed:
                break

            except Exception as e:
                print(str(e))

    @staticmethod
    async def notify_node(msg: dict, node: dict, wait_response: bool):
        ssh_tunnel = SSHTunnelForwarder(
            node['host'],
            ssh_username=node['username'],
            ssh_password=node['password'],
            remote_bind_address=("localhost", node['port']))
        ssh_tunnel.start()
        port = ssh_tunnel.local_bind_port

        response = None

        try:
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                await ws.send(json.dumps(msg))
                if wait_response:
                    response = json.loads(await ws.recv())
        finally:
            ssh_tunnel.stop()

        return response

    async def notifier(self, msg: dict, wait_response: bool = False):
        responses = []
        for node in self.another_nodes:
            try:
                response = await asyncio.wait_for(
                    self.notify_node(msg=msg, node=node, wait_response=wait_response),
                    timeout=5.0)
                responses.append(response)
            except Exception:
                print(f"Node {node} dedicated to be fallen.")
        return responses
