import logging

import websockets
from itertools import cycle
import re
import configs
import json

import sshtunnel
from sshtunnel import SSHTunnelForwarder


class Client(object):
    def __init__(self, host):
        self.current_node = list(filter(lambda v: v['host'] == host, configs.nodes))[0]
        self.another_nodes = list(filter(lambda v: v['host'] != host, configs.nodes))

    async def request(self, transaction):
        nodes = cycle([self.current_node] + self.another_nodes)

        while True:
            node = nodes.__next__()
            ssh_tunnel = None

            try:
                logger = logging.Logger("dist-systems-logger", level=logging.CRITICAL)
                sshtunnel.create_logger(logger=logger, loglevel='CRITICAL')
                ssh_tunnel = SSHTunnelForwarder(
                    node['host'],
                    ssh_username=node['username'],
                    ssh_password=node['password'],
                    remote_bind_address=("127.0.0.1", node['port']),
                    mute_exceptions=True,
                    logger=logger)
                ssh_tunnel.start()

                url = f"ws://127.0.0.1:{ssh_tunnel.local_bind_port}"

                async with websockets.connect(url) as ws:
                    await ws.send(json.dumps(transaction))
                    response = json.loads(await ws.recv())
                    print("|| Received:")
                    for el in response:
                        if el.get('action') == 'read':
                            print("DONE", el.get('action'), el.get('var'), ": ", el.get('result'))
                        elif el.get('action') == 'update':
                            print("DONE", el.get('action'), el.get('var'))
                break
            except Exception:
                continue
            finally:
                if ssh_tunnel is not None:
                    ssh_tunnel.close()

    async def listen(self):
        transaction = []

        while True:
            input_msg = input()
            if not re.match(r"[\w.\s]*", input_msg):
                "Invalid input. Try again"
            else:
                if input_msg == 'end':
                    break
                else:
                    try:
                        request = input_msg.split()
                        if request[0] == 'update':
                            msg = {'action': 'update', 'var': request[1], 'value': request[2]}
                        elif request[0] == 'read':
                            msg = {'action': 'read', 'var': request[1], 'value': None}
                        else:
                            print("Unknown operation")
                            continue
                    except IndexError:
                        continue
                    else:
                        transaction.append(msg)
        dict_to_send = {"action": "request", "msg": transaction}
        print("|| Processing your request... wait a moment...")

        await self.request(dict_to_send)

        return transaction

    async def start(self):
        print("|| Type the operation you would like to perform like this: \n"
              "|| 'update a 1' or 'update b b+1' or 'read a'. \n"
              "|| Note that only update and read operations are accepted. \n"
              "|| To complete the transaction type 'end'")
        while True:
            await self.listen()
            while True:
                cont = input("|| One more transaction? y/n: ")
                if cont == "y" or cont == "n":
                    break
                else:
                    print("|| Incorrect input")
                    continue
            if cont == "y":
                print("|| Ok, go on typing: ")
                continue
            elif cont == "n":
                break
