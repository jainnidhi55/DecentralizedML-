# -*- coding: utf-8 -*-
"""interface.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1m3AsFRknW0punAzrQfpVwqlmy_E1ftEn
"""
import socket

# cindy
class client:
  # add fields

  def train(): #train local round
    # sgd algo
    pass
  
  def recieve_training_info(): #receive info from server: data, training hyperparameters, etc.
    pass
  
  def send_message(): #send message to server
    #execute the random delay
    pass

class Server: #NIDHI2
  def __init__(self):
    self.client_id_to_metadata_dict = {} 
    #client_id_to_metadata_dict[client_uid] = (client object, replica_group_index)

    self.replica_group_id_to_client_uids = {}
    #replica_id_to_client_copy[replica_group_id] = (primary client uid, [client uids corresponding to this replica_group])

    self.latest_client_uid = 1025 #non priviliged ports are > 1023
    self.latest_replica_group_id = 0

    self.s = socket.socket() 
    host = "127.0.0.1"
    port = 1024
    self.s.bind((host, port))
    self.s.listen()

  #replica_id is specified if this new client is spawned to be a replica of group replica_id. Otherwise, None
  #returns new client uid
  def spawn_new_client(self, make_replica = False, replica_group_id = None, replica_client_uid = None):
    self.latest_client_uid += 1
    self.client_id_to_metadata_dict[self.latest_client_uid] = (Client(), replica_group_id) #TODO instantiate client 

    if make_replica:
      if self.client_id_to_metadata_dict[replica_client_uid][1] is None: #this will be the first replica of this client type
        #assign original client the new replica group 
        self.latest_replica_group_id += 1
        self.client_id_to_metadata_dict[replica_client_uid][1] = self.latest_replica_group_id

        #assign new client the exact copy of original client 
        self.client_id_to_metadata_dict[self.latest_client_uid] = (self.client_id_to_metadata_dict[replica_client_uid][0].copy(), self.latest_replica_group_id) #TODO client .copy()

        #update replica knowledge
        self.replica_group_id_to_client_uids[self.latest_replica_group_id] = (replica_client_uid, [self.latest_client_uid])
      else: #replicas already exist

        #assign new client the exact copy of original client 
        self.client_id_to_metadata_dict[self.latest_client_uid] = (self.client_id_to_metadata_dict[replica_client_uid][0].copy(), self.latest_replica_group_id) #TODO client .copy()

        #add new client to replica data
        self.replica_group_id_to_client_uids[replica_group_id][1].append(self.latest_client_uid)
    else:
      self.client_id_to_metadata_dict[self.latest_client_uid] = (Client(), None) #TODO 
        
    return self.latest_client_uid

  def aggregate(self, messages): #aggregate local training rounds (Averaging) #TODO, specify input of messages
    msg_sum = None
    for message_curr in messages:
      if msg_sum is None:
        msg_sum = message_curr
      else:
        msg_sum += message_curr
    return msg_sum / len(messages)

  def send_message(self, message, receivers):
    for i in range(len(receivers)):
      c, addr = self.s
      self.s.sendto(message, (addr[0], addr[1])) #TODO

class message:

  # fields 
  # random delay
  #Neha
  pass

class run_training:
  #Neha
  def forward():
    #hi
    pass
