#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle, Christian
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request, redirect, jsonify
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

#Taken from Hindle Websocket Example, referenced in readme
class Client:
    def __init__(self):
        self.queue = queue.Queue()

    def put(self, v):
        self.queue.put_nowait(v)

    def get(self):
        return self.queue.get()

class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()
        
    def add_set_listener(self, listener):
        self.listeners.append( listener )

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners( entity )

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners( entity )

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())
    
    def world(self):
        return self.space

myWorld = World()  

# Initialize a blank client list (as per Websocket example)
clients = list()      

# Create definition for the listener and have it update all the client
# with json using json.dumps
def set_listener( entity, data ):
    packet = json.dumps({entity: data})
    for c in clients:
       c.put(packet)

# Set the myworld listener to the set listener above
myWorld.add_set_listener( set_listener )
        
@app.route('/')
def hello():
    '''Return something coherent here.. perhaps redirect to /static/index.html '''
    return redirect("static/index.html")

def read_ws(ws,client):
    '''A greenlet function that reads from the websocket and updates the world'''
    # Try to read from the websocket, structure taken from Hindle Websocket example
    try:
        while True:
            data = ws.receive()
            if (data is not None):
                # load the multiple entities from the json data sent from index.html
                entities = json.loads(data)
                # for the corresponding entity and data ex {y: 'some coord'}
                # update myWorld with said entities
                for entity, data in entities.iteritems():
                    # setting the myWorld entities
                    myWorld.set(entity, data)
                    # call update listeners after the entity has been added
                    myWorld.update_listeners(entity)
            else:
                break
    except:
        '''Done'''
    return None

@sockets.route('/subscribe')
def subscribe_socket(ws):

    # Using Hindles websocket sample
    client = Client()
    # Add the client to the client list
    clients.append(client)
    g = gevent.spawn( read_ws, ws, client )    

    # Give the new client the current world
    ws.send(json.dumps(myWorld.world()))

    # Setting up and blocking the websocket as per Hindles Websocket example
    try:
        while True:
            # block here
            msg = client.get()
            ws.send(msg)
    except Exception as e:# WebSocketError as e:
        print "WS Error %s" % e
    finally:
        clients.remove(client)
        gevent.kill(g)
    return None

def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data != ''):
        return json.loads(request.data)
    else:
        return json.loads(request.form.keys()[0])

@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    '''update the entities via this interface'''
    req_data = flask_post_json()
    for key in req_data:
        myWorld.update(entity,key,req_data[key])
    return jsonify(myWorld.get(entity)), 200

@app.route("/world", methods=['POST','GET'])    
def world():
    '''you should probably return the world here'''
    return jsonify(myWorld.world()), 200

@app.route("/entity/<entity>")    
def get_entity(entity):
    '''This is the GET version of the entity interface, return a representation of the entity'''
    return jsonify(myWorld.get(entity)), 200


@app.route("/clear", methods=['POST','GET'])
def clear():
    myWorld.clear()
    return jsonify({"cleared":1}), 200



if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
