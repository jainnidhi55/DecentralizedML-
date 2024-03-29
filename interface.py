"""

To run this file, add a folder called "data" within the same home directory.
Within data add and decompress all of the MNIST files from http://yann.lecun.com/exdb/mnist/

"""


print("importing libraries")

from email import message
import torch
import torch.optim as optim
import torch.nn as nn
import torch.nn.functional as F
from mnist import MNIST
import torch.multiprocessing as multiprocessing
from torch.multiprocessing import Process
import numpy as np
import math

import sys

# np.random.seed(0)

print("downloading mnist")
mndata = MNIST('data/')
IMAGES_TRAIN, LABELS_TRAIN = mndata.load_training()
IMAGES_TEST, LABELS_TEST = mndata.load_testing()
IMAGES_TRAIN = np.asarray(IMAGES_TRAIN).reshape((-1, 1, 28, 28))
IMAGES_TEST = np.asarray(IMAGES_TEST).reshape((-1, 1, 28, 28))

#shuffle 
shuffled_ids = [i for i in range(len(IMAGES_TRAIN))]
np.random.shuffle(shuffled_ids)
IMAGES_TRAIN = np.asarray([IMAGES_TRAIN[i] for i in shuffled_ids])
LABELS_TRAIN = np.asarray([LABELS_TRAIN[i] for i in shuffled_ids])

class CNN(nn.Module):
    def __init__(self):
        super(CNN, self).__init__()
        self.conv1 = nn.Conv2d(1, 6, 5)
        self.pool = nn.MaxPool2d(2, 2)
        self.conv2 = nn.Conv2d(6, 16, 5)
        self.fc1 = nn.Linear(256, 120)
        self.fc2 = nn.Linear(120, 84)
        self.fc3 = nn.Linear(84, 10)

    def forward(self, x):

        # x = self.pool(F.relu(self.conv1(x)))
        x = F.relu(x)
        x = self.conv1(x)
        x = F.relu(x)
        x = self.pool(x)

        x = self.pool(F.relu(self.conv2(x)))
        x = torch.flatten(x, 1) # flatten all dimensions except batch
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.fc3(x)
        return x

# cindy
class Client():
  def __init__(self, uid, replica_group_id, queue, bsz=32, epochs=20, indices=[0, 50], byzantine=False):
    
    self.uid = uid
    self.replica_group_id = replica_group_id
    self.queue = queue
    self.indices = indices

    self.byzantine = byzantine
    
    # MODEL
    self.model = CNN() 

    # TRAINING HYPERPARAMETERS
    self.bsz = bsz
    self.num_epochs = epochs
    # SGD inputs
    self.random_seed = 0
    self.lr = 0.01
    self.momentum = 0
    self.weight_decay = 0
    self.dampening = 0
    self.nesterov = False
    # self.maximize = False
    self.optimizer = optim.SGD(self.model.parameters(), lr = self.lr, momentum = self.momentum, weight_decay = self.weight_decay, dampening = self.dampening, nesterov = self.nesterov)



    # DATA
    self.train_partititon = IMAGES_TRAIN[indices[0]:indices[1]]
    self.label_partition = LABELS_TRAIN[indices[0]:indices[1]]
  
  def copy():
    return None

  # train local round
  def train(self, round_num):
    
    # torch.manual_seed(self.random_seed)
    if (round_num != 0):
      with torch.no_grad():  
        updated_parameters = None
        while (not self.queue.empty()):
          updated_parameters = self.queue.get().content
        if updated_parameters is None:
          print("ERROR: client ", self.uid, " recieved no parameters")
        self.model.load_state_dict(updated_parameters)
    
    # print("train accuracy before loading model", self.uid, get_accuracy(self.model.state_dict(), self.train_partititon, self.label_partition, bsz=self.bsz))


    # sgd algo
    losses = []
    for _ in range(self.num_epochs):
      
      epoch_loss = 0.0

      for i in range(int(math.ceil(len(self.train_partititon)/self.bsz))):
        data = torch.tensor(self.train_partititon[i * self.bsz: min((i+1) * self.bsz, len(self.train_partititon))]).float()
        target = torch.tensor(self.label_partition[i * self.bsz: min((i+1) * self.bsz, len(self.train_partititon))]).float()
        
        
        self.optimizer.zero_grad()
        output = self.model(data).float()
        loss_fn = nn.CrossEntropyLoss()
        loss = loss_fn(output.float(), target.type(torch.LongTensor))
        epoch_loss += loss.item()
        loss.backward()
        self.optimizer.step()
        losses.append(epoch_loss)


    if (self.byzantine):
      # print("randomizing weights")
      #return random weights
      with torch.no_grad():
        model_dict = {} # self.model.state_dict()
        for k in self.model.state_dict().keys():
          random_factor = (np.random.rand(*self.model.state_dict()[k].shape) * 2) - 1

          # random_factor = (np.random.rand() * 2) - 1
          model_dict[k] = self.model.state_dict()[k] * random_factor
        
        
        # print("train accuracy of byzantine", self.uid, get_accuracy(model_dict, self.train_partititon, self.label_partition, bsz=self.bsz))
        self.send_message(Message(content=model_dict, round_num=round_num, sender=self.uid, receiver=-1))
    else:
      # print("train accuracy after round of training", self.uid, get_accuracy(self.model.state_dict(), self.train_partititon, self.label_partition, bsz=self.bsz))
      # print("train loss after round of training", self.uid, losses[-1])
      self.send_message(Message(content=self.model.state_dict(), round_num=round_num, sender=self.uid, receiver=-1))

  
  #send message to server
  def send_message(self, msg):
    # print("sending message from client ", self.uid)
    self.queue.put(msg)


#threshold range is 0.3 - 1
class Server:
  def __init__(self, threshold = 1):
    self.client_id_to_metadata_dict = {} 
    #client_id_to_metadata_dict[client_uid] = (client object, replica_group_id)

    self.replica_group_id_to_client_uids = {}
    #replica_group_id_to_client_uids[replica_group_id] = (primary client uid, [client uids corresponding to this replica_group])

    self.latest_client_uid = 1025 #non priviliged ports are > 1023
    self.latest_replica_group_id = 0

    self.benign_p = (1 - threshold)
    self.byzantine_p = (1 - threshold) + 0.3
    self.bytes_sent_over_network = 0

  #replica_id is specified if this new client is spawned to be a replica of group replica_id. Otherwise, None
  #returns new client uid
  def spawn_new_client(self, make_replica = False, replica_group_id = None, replica_client_uid = None, data_ind = None, byzantine = False):
    self.latest_client_uid += 1
    if make_replica:
      #assign new client the exact copy of original client 
      new_replica_client = Client(self.latest_client_uid,replica_group_id, multiprocessing.Queue(), indices=data_ind)
      self.client_id_to_metadata_dict[self.latest_client_uid] = (new_replica_client, replica_group_id)

      #add new client to replica data
      self.replica_group_id_to_client_uids[replica_group_id][1].append(self.latest_client_uid)
    else:
      self.latest_replica_group_id += 1
      new_client_q = multiprocessing.Queue()
      new_client = Client(self.latest_client_uid, self.latest_replica_group_id, new_client_q, indices=data_ind, byzantine=byzantine)
      self.client_id_to_metadata_dict[self.latest_client_uid] = (new_client, self.latest_replica_group_id) 
      self.replica_group_id_to_client_uids[self.latest_replica_group_id] = (self.latest_client_uid, [])

    return self.client_id_to_metadata_dict[self.latest_client_uid][0]


  #write code to have the weights from clients collected in organized fashion
  #messages = [Message]
  def aggregate(self, messages, weights): #aggregate local training rounds (Averaging) 
    assert(len(messages) > 0)
    valid_messages = []
    good_client_ids = [] #index in primary list in run trainig
    for i in range(len(messages)):
      if messages[i] != None:
        valid_messages.append(messages[i])
        good_client_ids.append(messages[i].send_id)


    if len(valid_messages) == 0:
      return (None, None)

    weight_sum = 0
    average_model = dict()
    for i in range(len(valid_messages)):
      weight_sum += weights[i]
      for k, v in valid_messages[i].content.items():
        if not (k in average_model):
          average_model[k] = weights[i] * v
        else:
          average_model[k] += weights[i] * v
    for k in average_model:
      average_model[k] = average_model[k] / weight_sum
    return (average_model, good_client_ids)


  def change_primary(self, group_id):
    #replica_group_id_to_client_uids[replica_group_id] = (primary client uid, [client uids corresponding to this replica_group])
    (old_primary_id, _) = self.replica_group_id_to_client_uids[group_id]
    new_primary_id = self.replica_group_id_to_client_uids[group_id][1][0]
    new_replicas = self.replica_group_id_to_client_uids[group_id][1][1:]
    new_replicas.append(old_primary_id)
    self.replica_group_id_to_client_uids[group_id] = (new_primary_id, new_replicas)

    # print("old primary id: ", old_primary_id, "new primary id: ", new_primary_id)


  def send_message(self, client, message):
    # for (client, _) in self.client_id_to_metadata_dict.values():
    # print("server sending message to client ", client.uid)
    self.bytes_sent_over_network += sys.getsizeof(message)
    client.queue.put(message)
  
  def receive_message(self, client): #waits for the next recieved message, times out after a point
    msg = client.queue.get()
    self.bytes_sent_over_network += sys.getsizeof(msg)
    # print("server recieved msg  from ", client.uid)
    p = self.benign_p
    if client.byzantine:
      p = self.byzantine_p
    random_num = np.random.rand()
    if random_num < p:
      # print("bad client alert: ")
      return None
    return msg
  
  #input: all_state_dicts, averages (1 state dict that has avg of all weights)
  #output: list of deviations - 1 list of deviations per client 
  def find_deviation(self, all_state_dicts, averages):
    all_deviations = []

    client_ids = []
    for (client_id, model) in all_state_dicts:
      model_deviations = []
      for k, param in model.items():
        raw_param_deviation = abs(averages[k] - param)
        std_param_deviation = torch.sum(torch.mul(raw_param_deviation, raw_param_deviation)/averages[k])
        model_deviations.append(std_param_deviation.item())
        
      all_deviations.append(model_deviations)
      client_ids.append(client_id)

    return (client_ids, np.asarray(all_deviations))

  #input: list of list of devations (clients * num_params)
  #output: most probable byzantine clients
  def deviations_to_byzantine(self, client_deviations, round_num, total_rounds, byz_stdv_min = 0.5, byz_stdv_max=0.9):

    (ids, deviations) = client_deviations #id: num clients, deviations: num clients X num params
    num_clients = len(deviations)
    threshold = 0.3
    threshold_top_deviations = int(num_clients * threshold) #identify top *threshold* deviations

    num_params = 10
    byz_client_idxs_per_param = np.asarray([0 for i in range(num_params)])
    for param_i in range(num_params):
      #get top problematic clients of current param, accordingly modify byz_client_idxs_per_param
      curr_param_deviations = deviations[:, param_i]
      curr_param_byz_client_idx = (-curr_param_deviations).argsort()[:threshold_top_deviations]

      byz_client_idxs_per_param[curr_param_byz_client_idx] += 1
    

    min_threshold = int(num_params * byz_stdv_min)
    max_threshold = int(num_params * byz_stdv_max)
    threshold_problem_params = ((max_threshold - min_threshold) * (1 - round_num/total_rounds)) + min_threshold
    
    # threshold_problem_params = 5
    byz_client_idxs = np.where(byz_client_idxs_per_param > threshold_problem_params)[0]
    return np.asarray(ids)[byz_client_idxs]
  

def get_accuracy(model_parameters, images, labels, bsz=32):
    with torch.no_grad():
      model = CNN()
      model.load_state_dict(model_parameters)
      
      accuracies = []
      for i in range(int(math.ceil(len(images)/bsz))):
        data = torch.tensor(images[i * bsz: min((i+1) * bsz, len(images))]).float()
        target = torch.tensor(labels[i * bsz: min((i+1) * bsz, len(images))]).float()
        with torch.no_grad():
          output = model(data).float()
          accuracy = torch.sum(torch.argmax(output, dim=1) == target) / (1.0 * len(target))
          accuracies.append(accuracy)

      return(np.mean(np.asarray(accuracies)))


class Message:

  def __init__(self, content, round_num = 0, sender=None, receiver=None):
    self.content = content #numpy array of weights
    self.round_num = round_num
    self.send_id = sender #-1 if server
    self.receive_id = receiver

class RunTraining:

  def __init__(self, num_clients, num_replicas=0, num_rounds=1, num_byzantine = 1, sleep_threshold=1, byz_stdv_min=0.5, byz_stdv_max = 0.9, varying_resource_alloc = False):
    self.s = Server(threshold = sleep_threshold)
    self.clients = []
    self.client_to_process_dict= {}
    self.num_rounds = num_rounds
    self.num_replicas = num_replicas
    self.num_byzantine = num_byzantine

    self.byz_stdv_min = byz_stdv_min
    self.byz_stdv_max = byz_stdv_max

    self.varying_resource_alloc = varying_resource_alloc

    NUM_TRAINING_POINTS = 16000 # #60000
    num_training_per_client = NUM_TRAINING_POINTS // num_clients

    byzantine_client_idxs = np.random.choice(num_clients, size=self.num_byzantine, replace=False)
    byzantine_client_ids = []
    for i in range(num_clients):
      
      curr_client_is_byzantine = (i in byzantine_client_idxs)
      curr_client_idxs = [i * num_training_per_client, (i + 1) * num_training_per_client]
      curr_client = self.s.spawn_new_client(data_ind=curr_client_idxs, byzantine=curr_client_is_byzantine)

      if (curr_client_is_byzantine):
        byzantine_client_ids.append(curr_client.uid)

      self.clients.append(curr_client)
      
      for _ in range(self.num_replicas):
        replica = self.s.spawn_new_client(make_replica = True, replica_group_id = curr_client.replica_group_id, replica_client_uid = curr_client.uid, data_ind = curr_client.indices)
        self.clients.append(replica)
    
    # print("byzantine clients: ", byzantine_client_ids)

  def run_tasks(self, running_tasks):
    for running_task in running_tasks:
          running_task.start()
    for running_task in running_tasks:
        running_task.join()
  
  
  def forward(self):

    self.model_parameters = None #averaged model

    for round_num in range(self.num_rounds): #num global rounds
      print("round num: ", round_num)
      
      #train a round of clients in parallel
      # print("train a round of clients in parallel")
      primaries = []
      for _, v in self.s.replica_group_id_to_client_uids.items():
        (primary_client_uid, _) = v
        client = self.s.client_id_to_metadata_dict[primary_client_uid][0]
        primaries.append(client)
        
      running_tasks = []
      for client in primaries: 
        running_tasks.append(Process(target=client.train, args=(round_num,)))
      self.run_tasks(running_tasks)

      #server receives trained models from each client
      # print("server receives trained models from each client")
      messages = []
      for client in primaries:
        messages.append(self.s.receive_message(client))

      #aggregate models
      # print("aggregate models")
      (new_parameters, non_delayed_client_ids) = self.s.aggregate(messages, [1 for msg in messages])
      delayed_client_ids = []
      for client in primaries:
        if client.uid not in non_delayed_client_ids:
          delayed_client_ids.append(client.uid)
      if new_parameters != None:
        self.model_parameters = new_parameters
      print("delayed client ids: ", delayed_client_ids)

      non_dropped_models = []
      for message in messages:
        if not(message is None): #.send_id not in delayed_client_ids:
          non_dropped_models.append((message.send_id, message.content))

      all_deviations = self.s.find_deviation(non_dropped_models, self.model_parameters)
      outlier_client_uids = list(self.s.deviations_to_byzantine(all_deviations, round_num, self.num_rounds, self.byz_stdv_min, self.byz_stdv_max))
      
      print("outlier client uids: ", outlier_client_uids)


      bad_client_ids = delayed_client_ids + outlier_client_uids
      # print("bad client ids: ", bad_client_ids)
      
      # reaggregate
      # good_models = []
      good_messages = []
      for message in messages:
        if not(message is None) and (message.send_id not in bad_client_ids):
          good_messages.append(message)
      
      if self.varying_resource_alloc:
        param_weights = []
        non_dropped_messages = []
        for message in messages:
          if not(message is None):
            if message.send_id in bad_client_ids:
              param_weights.append(0.1)
            else:
              param_weights.append(1)
            non_dropped_messages.append(message)
        (new_parameters, _) = self.s.aggregate(non_dropped_messages, param_weights)
        if new_parameters != None:
          self.model_parameters = new_parameters

      else:
        param_weights = [1 for msg in messages]
        (new_parameters, _) = self.s.aggregate(good_messages, param_weights)
        if new_parameters != None:
          self.model_parameters = new_parameters

      
      #server sends new model to all clients in parallel
      # print("server sends new model to all clients in parallel")
      running_tasks = []
      for client in self.clients:
        running_tasks.append(Process(target=self.s.send_message, args=(client, Message(content=self.model_parameters, round_num=round_num, sender=-1, receiver=client.uid))))
      self.run_tasks(running_tasks)

      # change primaries ONLY if not doing varying allocation scheme 
      if not(self.varying_resource_alloc):
        # print("all bad client ids: ", bad_client_ids)
        for bad_client_id in bad_client_ids:
          (bad_primary, _) = self.s.client_id_to_metadata_dict[bad_client_id]
          bad_gid = bad_primary.replica_group_id
          # print("changing primary for ", bad_primary.uid)
          self.s.change_primary(bad_gid)


def main():
  runner = RunTraining(num_clients=5, num_replicas=1, num_rounds=5, num_byzantine=3, sleep_threshold=1, byz_stdv_min=0.3, byz_stdv_max = 0.9, varying_resource_alloc = False) #comment
  runner.forward()
  print("final train accuracy: ")
  print(get_accuracy(runner.model_parameters, IMAGES_TRAIN[:16000], LABELS_TRAIN[:16000]))
  print("final test accuracy: ")
  print(get_accuracy(runner.model_parameters, IMAGES_TEST, LABELS_TEST))
  print("final bytes sent over network: ", runner.s.bytes_sent_over_network)

if __name__ == '__main__':
    main()