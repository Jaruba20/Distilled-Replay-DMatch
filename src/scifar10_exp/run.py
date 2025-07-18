import copy
import random

import torch
import higher
import wandb

import contflame.data.datasets as datasets
from contflame.data.utils import MultiLoader, Buffer
from torch import nn
import numpy as np
from torch import autograd
from torch.utils.data import DataLoader, IterableDataset

import time



import model    # If this import is generating problems, import sys and add the project path.

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"\n=== Using device: {device} ===")
print(f"CUDA initialized: {torch.cuda.is_available()}")
print(f"CUDA device name: {torch.cuda.get_device_name(0)}\n")

# CUDA memory optimization
torch.backends.cudnn.benchmark = True


w = 0
def print_images(data, trgs, mean, std):
    global w

    for img, trg in zip(data, trgs):
        label = trg.item()

        std = [std[0] for _ in range(img.size(0))] if len(std) == 1 else std
        mean = [mean[0] for _ in range(img.size(0))] if len(mean) == 1 else mean

        img = img.detach().clone().cpu().numpy()

        for i in range(img.shape[0]):
            img[i] = img[i] * std[i] + mean[i]

        img = img * 255
        img = np.transpose(img, (1, 2, 0))
        img = np.squeeze(img)
        img = img.astype(np.uint8)

        wandb.log({f'img{w}_{label}':[wandb.Image(img, caption=f"{label}")]})

        w += 1

def initialize_weights(module):
    if isinstance(module, nn.Conv2d) or isinstance(module, nn.Linear):
        nn.init.xavier_uniform_(module.weight)
        module.bias.data.fill_(0.0)

class Train:

    def __init__(self, optimizer, criterion, train_loader, config):
        self.optimizer = optimizer
        self.criterion = criterion
        self.config = config
        self.train_loader = train_loader
        self.iter = enumerate(train_loader)

    def __call__(self, model):
        model.train()

        run_config = self.config['run_config']

        correct = 0
        loss_sum = 0
        tot = 0

        try:
            step, (data, targets) = next(self.iter)
        except StopIteration:
            self.iter = enumerate(self.train_loader)
            step, (data, targets) = next(self.iter)

        data = data.to(run_config['device'])
        targets = targets.to(run_config['device'])
        self.optimizer.zero_grad()

        outputs = model(data)
        loss = self.criterion(outputs, targets)
        loss.backward()

        self.optimizer.step()

        _, preds = torch.max(outputs, dim=1)

        loss_sum += loss.item() * data.size(0)
        correct += preds.eq(targets).sum().item()
        tot += data.size(0)

        accuracy = correct / tot
        loss = loss_sum / tot

        return loss, accuracy

def test(model, criterion, test_loader, config):
    model.eval()

    correct = 0
    loss_sum = 0
    tot = 0

    for step, (data, targets) in enumerate(test_loader):
        data = data.to(config['device'])
        targets = targets.to(config['device'])

        with torch.no_grad():
            outputs = model(data)
            loss = criterion(outputs, targets)

        _, preds = torch.max(outputs, dim=1)

        loss_sum += loss.item() * data.size(0)
        correct += preds.eq(targets).sum().item()
        tot += data.size(0)

    accuracy = correct / tot
    loss = loss_sum / tot

    return loss, accuracy


def run(config):

    run_config = config['run_config']
    model_config = config['model_config']
    param_config = config['param_config']
    data_config = config['data_config']
    log_config = config['log_config']

    if log_config['wandb']:
        wandb.init(project="smnist", name=log_config['wandb_name'])
        wandb.config.update(config)

    # Reproducibility
    seed = run_config['seed']
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)

    # Loss
    criterion = nn.CrossEntropyLoss()

    # Model
    net = getattr(model, model_config['arch']).Model(model_config)
    net.to(device)
    print(f"Model device: {next(net.parameters()).device}")
    net.apply(initialize_weights)

    # Data
    Dataset = getattr(datasets, data_config['dataset'])

    # Training
    memories = []
    validloaders = []
    s = 0

    for task_id, task in enumerate(run_config['tasks'], 0):
        validset = Dataset(dset='test', valid=data_config['valid'], transform=data_config['test_transform'], classes=task)
        validloaders.append(DataLoader(validset, batch_size=param_config['batch_size'], shuffle=False, pin_memory=True, num_workers=data_config['num_workers']))
        trainset = Dataset(dset='train', valid=data_config['valid'], transform=data_config['train_transform'], classes=task)

        # Add pin_memory=True to ALL DataLoaders
        bufferloader = MultiLoader([trainset] + memories, batch_size=param_config['batch_size'], 
                                pin_memory=True)

        optimizer = torch.optim.SGD(net.parameters(), lr=param_config['model_lr'], )
        train = Train(optimizer, criterion, bufferloader, config)

        d_net = copy.deepcopy(net)
        d_trainloader = DataLoader(trainset, batch_size=param_config['distill_batch_size'], shuffle=True, pin_memory=True, num_workers=data_config['num_workers'])
        d_validloader = DataLoader(validset, batch_size=param_config['distill_batch_size'], shuffle=False, pin_memory=True, num_workers=data_config['num_workers'])

        if param_config['step'] == 'epoch':
            steps = len(bufferloader) * param_config['no_steps']
        elif param_config['step'] == 'minibatch':
            steps = param_config['no_steps']
        else:
            raise ValueError

        for step in range(steps):

            buffer_loss, buffer_accuracy = train(net)

            if (int(steps * 0.05) <= 0 or step % int(steps * 0.05) == int(steps * 0.05) - 1 or step == 0):
                valid_m = {'Test accuracy avg': 0}
                for i, vl in enumerate(validloaders):
                    test_loss, test_accuracy = test(net, criterion, vl, run_config)
                    valid_m = {**valid_m, **{f'Test loss {i}': test_loss,
                               f'Test accuracy {i}': test_accuracy,}}
                    valid_m['Test accuracy avg'] += (test_accuracy / len(validloaders))

                train_m = {f'Buffer loss': buffer_loss,
                           f'Buffer accuracy': buffer_accuracy,
                           f'Step': s}
                s += 1
                if log_config['print']:
                    print({**valid_m, **train_m})
                if log_config['wandb']:
                    wandb.log({**valid_m, **train_m})

        if task_id == len(run_config['tasks']) - 1:
            break

        if param_config['buffer_size'] != 0:
            buffer = None
            for t in task:
                ds = Dataset(dset='train', valid=data_config['valid'], transform=data_config['test_transform'], classes=[t])
                buffer = Buffer(ds, param_config['buffer_size']) if buffer is None else buffer + Buffer(ds, param_config['buffer_size'])

            if log_config['wandb']:
                mean, std = data_config['test_transform'].transforms[-1].mean, data_config['test_transform'].transforms[-1].std
                x, y = next(iter(DataLoader(buffer, batch_size=len(buffer), shuffle=False)))
                print_images(x[:1], y[:-1], mean, std)
                print_images(x[1:], y[-1:], mean, std)

            # Added Distribution Matching option
            if run_config['distillation_method'] == 'DM': 
                start_time = time.time()
                buffer, _ = distill_dm(d_net, buffer, config, criterion, d_trainloader)
                end_time = time.time()
            else:
                start_time = time.time()
                buffer, _ = distill(d_net, buffer, config, criterion, d_trainloader, d_validloader, task_id)
                end_time = time.time()

            print(f"*******************Time in {task_id}: {end_time-start_time}")
            


            if log_config['wandb']:
                mean, std = data_config['test_transform'].transforms[-1].mean, data_config['test_transform'].transforms[-1].std
                x, y = next(iter(DataLoader(buffer, batch_size=len(buffer), shuffle=False)))
                print_images(x[:1], y[:1], mean, std)
                print_images(x[-1:], y[-1:], mean, std)

            memories.append(buffer)

def distill_dm(model, buffer, config, criterion, train_loader):
    model = copy.deepcopy(model).to(config['run_config']['device'])
    run_config = config['run_config']
    param_config = config['param_config']
    #log_config = config['log_config']
    device = run_config['device']

    model.train() # Training mode activated

    # batch_size = len of buffer so all data is loaded at once.
    buff_imgs, buff_trgs = next(iter(DataLoader(buffer, batch_size=len(buffer))))
    buff_imgs, buff_trgs = buff_imgs.to(device), buff_trgs.to(device)
    buff_imgs = buff_imgs.contiguous().requires_grad_(True)

    buff_opt = torch.optim.SGD([buff_imgs], lr=param_config['meta_lr'])

    # Generate 'n_inits' different initialized versions of the model's weights
    init_loader = DataLoader(
        ModelInitDataset(model, param_config['n_inits']),
        batch_size=1,
        collate_fn=lambda x: x
    )

    for i in range(param_config['outer_steps']):
        for (real_data, real_labels) in train_loader:
            real_data = real_data.to(device)
            real_labels = real_labels.to(device)

            total_grad_diff = 0
            
            for init_state in init_loader:
                # Create new model instance for each initialization
                current_model = copy.deepcopy(model).to(device)
                current_model.load_state_dict(init_state[0])
                current_model.train()

                # Real data gradients
                real_output = current_model(real_data)
                real_loss = criterion(real_output, real_labels)
                real_grads = torch.autograd.grad(
                    real_loss, 
                    current_model.parameters(), 
                    create_graph=True, 
                    retain_graph=True
                )

                # Synthetic data gradients
                syn_output = current_model(buff_imgs)
                syn_loss = criterion(syn_output, buff_trgs)
                syn_grads = torch.autograd.grad(
                    syn_loss, 
                    current_model.parameters(), 
                    create_graph=True, 
                    retain_graph=True
                )

                # Calculate gradient matching loss
                layer_losses = [
                    torch.norm(rg - sg, p=2) 
                    for rg, sg in zip(real_grads, syn_grads)
                ]
                total_grad_diff += sum(layer_losses)

            # Average and backpropagate
            total_grad_diff /= len(init_loader)
            buff_opt.zero_grad()
            total_grad_diff.backward()
            buff_opt.step()

    # Convert buffer back to dataset
    aux = []
    buff_imgs, buff_trgs = buff_imgs.detach().cpu(), buff_trgs.detach().cpu()
    for i in range(buff_imgs.size(0)):
        aux.append([buff_imgs[i], buff_trgs[i]])
    return Buffer(aux, len(aux)), []

def distill(model, buffer, config, criterion, train_loader, valid_loader, id):
    model = copy.deepcopy(model).to(config['run_config']['device'])

    run_config = config['run_config']
    param_config = config['param_config']
    log_config = config['log_config']

    model.train()
    eval_trainloader = copy.deepcopy(train_loader)

    buff_imgs, buff_trgs = next(iter(DataLoader(buffer, batch_size=len(buffer))))
    #buff_imgs, buff_trgs = buff_imgs.to(run_config['device']), buff_trgs.to(run_config['device'])
    buff_imgs = buff_imgs.to(device)
    buff_trgs = buff_trgs.to(device)

    #buff_imgs.requires_grad = True
    buff_imgs = buff_imgs.contiguous().requires_grad_(True)

    init_valid = DataLoader(ModelInitDataset(model, 10), batch_size=1, collate_fn=lambda x: x)
    init_loader = DataLoader(ModelInitDataset(model, -1), batch_size=1, collate_fn=lambda x: x)
    init_iter = iter(init_loader)

    buff_opt = torch.optim.SGD([buff_imgs], lr=param_config['meta_lr'],)

    lr_list = []
    lr_opts = []
    for _ in range(param_config['inner_steps']):
        lr = np.log(np.exp([param_config['model_lr']]) - 1)  # Inverse of softplus (so that the starting learning rate is actually the specified one)
        lr = torch.tensor(lr, requires_grad=True, device=run_config['device'])
        lr_list.append(lr)
        lr_opts.append(torch.optim.SGD([lr], param_config['lr_lr'],))

    for i in range(param_config['outer_steps']):
        for step, (ds_imgs, ds_trgs) in enumerate(train_loader):
            try: init_batch = next(init_iter)
            except StopIteration: init_iter = iter(init_loader); init_batch = next(init_iter)

            ds_imgs = ds_imgs.to(run_config['device'])
            ds_trgs = ds_trgs.to(run_config['device'])

            acc_loss = None
            epoch_loss = [None for _ in range(param_config['inner_steps'])]

            for r, sigma in enumerate(init_batch):
                model.load_state_dict(sigma)
                model_opt = torch.optim.SGD(model.parameters(), lr=1, )
                with higher.innerloop_ctx(model, model_opt) as (fmodel, diffopt):
                    for j in range(param_config['inner_steps']):
                        # Update the model
                        buff_out = fmodel(buff_imgs)
                        buff_loss = criterion(buff_out, buff_trgs)
                        buff_loss = buff_loss * torch.log(1 + torch.exp(lr_list[j]))
                        diffopt.step(buff_loss)

                        ds_out = fmodel(ds_imgs)
                        ds_loss = criterion(ds_out, ds_trgs)

                        epoch_loss[j] = epoch_loss[j] + ds_loss if epoch_loss[j] is not None else ds_loss
                        acc_loss = acc_loss + ds_loss if acc_loss is not None else ds_loss

                        # Metrics (20 samples of loss and accuracy at the last inner step)
                        if (((step + i * len(train_loader)) % int(round(len(train_loader) * param_config['outer_steps'] * 0.05)) == \
                                int(round(len(train_loader) * param_config['outer_steps'] * 0.05)) - 1) or (step + i * len(train_loader)) == 0) \
                                and j == param_config['inner_steps'] - 1 and r == 0:

                            lrs = [np.log(np.exp(lr.item()) + 1) for lr in lr_list]
                            lrs_log = {f'Learning rate {i} - {id}': lr for (i, lr) in enumerate(lrs)}
                            train_loss, train_accuracy = test_distill(init_valid, lrs, [buff_imgs, buff_trgs], model, criterion, eval_trainloader, run_config)
                            test_loss, test_accuracy = test_distill(init_valid, lrs, [buff_imgs, buff_trgs], model, criterion, valid_loader, run_config)
                            metrics = {f'Distill train loss {id}': train_loss, f'Distill train accuracy {id}': train_accuracy,
                                       f'Distill test loss {id}': test_loss, f'Distill test accuracy {id}': test_accuracy,
                                       f'Distill step {id}': step + i * len(train_loader)}

                            if log_config['wandb']:
                                wandb.log({**metrics, **lrs_log})

                            if log_config['print']:
                                print(metrics)

            # Update the lrs
            for j in range(param_config['inner_steps']):
                lr_opts[j].zero_grad()
                grad, = autograd.grad(epoch_loss[j], lr_list[j], retain_graph=True)
                lr_list[j].grad = grad
                lr_opts[j].step()

            buff_opt.zero_grad()
            acc_loss.backward()
            buff_opt.step()

    aux = []
    buff_imgs, buff_trgs = buff_imgs.detach().cpu(), buff_trgs.detach().cpu()
    for i in range(buff_imgs.size(0)):
        aux.append([buff_imgs[i], buff_trgs[i]])
    lr_list = [np.log(1 + np.exp(lr.item())) for lr in lr_list]

    return Buffer(aux, len(aux), ), lr_list


def test_distill(init_valid, lrs, buffer, model, criterion, eval_trainloader, run_config):
    buff_imgs, buff_trgs = buffer

    avg_loss = avg_accuracy = 0

    for init_batch in init_valid:
        for init in init_batch:
            model.load_state_dict(init)

            for lr in lrs:
                opt = torch.optim.SGD(model.parameters(), lr=lr, )
                pred = model(buff_imgs)
                loss = criterion(pred, buff_trgs)

                opt.zero_grad()
                loss.backward()
                opt.step()

            test_loss, test_accuracy = test(model, criterion, eval_trainloader, run_config)
            avg_loss += (test_loss / len(init_valid))
            avg_accuracy += (test_accuracy / len(init_valid))

    return avg_loss, avg_accuracy


class ModelInitDataset(IterableDataset):

    def __init__(self, target, len):
        self.target = copy.deepcopy(target)
        self.len = len
        self.inits = []
        self.i = 0

    def __iter__(self):
        self.i = 0
        return self

    def __next__(self):
        if self.i >= self.len and self.len >= 0:
            raise StopIteration

        if len(self.inits) - 1 >= self.i:
            res = self.inits[self.i]
        else:
            res = copy.deepcopy(self.target.apply(initialize_weights).state_dict())
            if self.len >= 0:
                self.inits.append(res)

        self.i += 1
        return res

    def __len__(self):
        return self.len
