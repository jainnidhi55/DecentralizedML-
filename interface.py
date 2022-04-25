# -*- coding: utf-8 -*-
"""interface.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1m3AsFRknW0punAzrQfpVwqlmy_E1ftEn
"""
import socket

import torch
import torch.optim as optim
import torch.nn as nn
import torch.nn.functional as F
from multiprocessing import Process


class CNN(nn.Module): #random CNN found from online
    def __init__(self):
        # Cindy: not sure if Net is missing, plz check
        super(Net, self).__init__()
        self.conv1 = nn.Conv2d(3, 6, 5)
        self.pool = nn.MaxPool2d(2, 2)
        self.conv2 = nn.Conv2d(6, 16, 5)
        self.fc1 = nn.Linear(16 * 5 * 5, 120)
        self.fc2 = nn.Linear(120, 84)
        self.fc3 = nn.Linear(84, 10)

    def forward(self, x):
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = torch.flatten(x, 1) # flatten all dimensions except batch
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.fc3(x)
        return x

# cindy
class Client():
  def __init___(self, bsz, epochs, indices, host, port): #todo: fix initialization (get data, initialize model). port #?
    # MODEL
    self.model = CNN() 

    # TRAINING HYPERPARAMETERS
    self.batch_size = bsz
    self.num_epochs = epochs
    # SGD inputs
    self.random_seed = 0
    self.params = self.model.parameters() 
    self.lr = 0.1
    self.momentum = 0
    self.weight_decay = 0
    self.dampening = 0
    self.nesterov = False
    self.maximize = False

    # DATA
    # dataset
    self.partititon = dataset[indices[0]:indices[1]]
    self.train_set = torch.utils.data.DataLoader(partition, batch_size=bsz, shuffle=True)
    self.test_set = None

    #CONNECT TO SERVER
    self.host = host
    self.port = port
    self.client_socket = socket.socket() # todo: close after done
    self.client_socket.connect((host, port))

  # train local round 
  # added model bc need inplace modification for multiprocessing - Neha
  def train(self):
    # sgd algo
    torch.manual_seed(self.random_seed)
    optimizer = optim.SGD(self.params, lr = self.lr, momentum = self.momentum, weight_decay = self.weight_decay, dampening = self.dampening, nesterov = self.nesterov, maximize = self.maximize)
    losses = []
    for epoch in range(self.num_epochs):
      epoch_loss = 0.0
      for data, target in self.train_set:
        optimizer.zero_grad()
        output = self.model(data)
        loss = nn.MSELoss(output, target)
        epoch_loss += loss.item()
        loss.backward()
        optimizer.step()
        losses.append(epoch_loss)

  #receive info from server: data, training hyperparameters, etc.
  def recieve_training_info(self):
    data = self.client_socket.recv(1024).decode()
  
  #send message to server
  def send_message(self, msg):
    #execute the random delay
    self.client_socket.send(msg)

  #recieve aggregated model from server
  def receive_message(self):
    msg = self.client_socket.recv(1024) #1024 = bufsize
    # TODO: update gradients?

class Server: #todo: send indices of data to client
  def __init__(self):
    self.client_id_to_metadata_dict = {} 
    #client_id_to_metadata_dict[client_uid] = (client object, replica_group_id)

    self.replica_group_id_to_client_uids = {}
    #replica_id_to_client_copy[replica_group_id] = (primary client uid, [client uids corresponding to this replica_group])

    self.latest_client_uid = 1025 #non priviliged ports are > 1023
    self.latest_replica_group_id = 0

    self.s = socket.socket()  #todo: s.close() when done
    host = "127.0.0.1"
    port = 1024
    self.s.bind((host, port))
    self.s.listen()

    listening_tasks = []

  #replica_id is specified if this new client is spawned to be a replica of group replica_id. Otherwise, None
  #returns new client uid
  def spawn_new_client(self, make_replica = False, replica_group_id = None, replica_client_uid = None, data_if_not_replica = None): #TODO 
    self.latest_client_uid += 1
    self.client_id_to_metadata_dict[self.latest_client_uid] = (Client(), replica_group_id) #TODO instantiate client 

    if make_replica:
      #assign new client the exact copy of original client 
      self.client_id_to_metadata_dict[self.latest_client_uid] = (self.client_id_to_metadata_dict[replica_client_uid][0].copy(), replica_group_id) #TODO client .copy()

      #add new client to replica data
      self.replica_group_id_to_client_uids[replica_group_id][1].append(self.latest_client_uid)
    else:
      self.latest_replica_group_id += 1
      self.client_id_to_metadata_dict[self.latest_client_uid] = (Client(data_if_not_replica), self.latest_replica_group_id) #TODO 
        
    
    conn, _ = self.s.accept() #?? idk
    task = Process(target=self.recieve_message, args=(conn, ))
    self.listening_tasks.append(task) # todo: to join later
    task.start()

    return self.latest_client_uid

  #write code to have the weights from clients collected in organized fashion
  def aggregate(self, messages, weights): #aggregate local training rounds (Averaging) 
    msg_sum = None
    for message_curr_i in range(len(messages)):
      message_curr = messages[message_curr_i]
      if msg_sum is None:
        msg_sum = message_curr.content
      else:
        msg_sum += weights[message_curr_i] * message_curr.content
    return msg_sum / len(messages)

  #server sends 1
  def send_message(self, message, receivers):
    for i in range(len(receivers)):
      c, addr = self.s
      self.s.sendto(message, (addr[0], addr[1])) #TODO
  
  def recieve_message(self, conn): #waits for the next recieved message, times out after a point
    while True:
        data = conn.recv(2048)
    # pass
  



# Neha
class message:

  def __init__(self, content, sender, reciever, delay = False):
    self.content = content #numpy array of weights
    self.round_number = 0
    self.sender = sender #source ID
    self.reciever = reciever #dest ID
    self.delay = delay #if there is a delay, we can trigger it when sending message

class run_training: #TODO: make it work end to end. create a new server. blah blah blah 

  def forward(self, num_rounds, clients, server):

    model = None #averaged model

    for _ in range(num_rounds): #num global rounds

      # train clients in parallel
      running_tasks = []
      for i in range(len(clients)):
        running_tasks.append(Process(clients[i].train()))

      for running_task in running_tasks:
          running_task.start()
      for running_task in running_tasks: #do some straggler handling here
          running_task.join()
      
      #average models here
      server.aggregate()

      return model
