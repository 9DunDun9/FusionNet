import os

import torch
from nets.hrnet_training import (CE_Loss, Dice_loss, Focal_Loss,
                                     weights_init)
from tqdm import tqdm

from utils.utils import get_lr
from utils.utils_metrics import f_score


def fit_one_epoch(model_train, model, loss_history, eval_callback, optimizer, epoch, epoch_step, epoch_step_val, gen,
                  gen_val, Epoch, cuda, cls_weights, num_classes, save_period, save_dir):
    total_loss = 0
    total_f_score = 0
    val_loss = 0
    val_f_score = 0
    print('Start Train')
    pbar = tqdm(total=epoch_step, desc=f'Epoch {epoch + 1}/{Epoch}', postfix=dict, mininterval=0.3)
    model_train.train()
    for iteration, batch in enumerate(gen):
        if iteration >= epoch_step:
            break
        vi_imgs, ir_imgs, pngs, labels = batch
        with torch.no_grad():
            weights = torch.from_numpy(cls_weights)
            if cuda:
                vi_imgs = vi_imgs.cuda(0)
                ir_imgs = ir_imgs.cuda(0)
                pngs = pngs.cuda(0)
                labels = labels.cuda(0)
                weights = weights.cuda(0)

        optimizer.zero_grad()
        outputs = model_train(vi_imgs, ir_imgs)
        loss = CE_Loss(outputs, pngs, weights, num_classes=num_classes)
        main_dice = Dice_loss(outputs, labels)
        loss = loss + main_dice

        with torch.no_grad():
            _f_score = f_score(outputs, labels)

        loss.backward()
        optimizer.step()
        total_loss += loss.item()
        total_f_score += _f_score.item()
        pbar.set_postfix(**{'total_loss': total_loss / (iteration + 1),
                                'f_score': total_f_score / (iteration + 1),
                                'lr': get_lr(optimizer)})
        pbar.update(1)

    pbar.close()
    print('Finish Train')
    print('Start Validation')
    pbar = tqdm(total=epoch_step_val, desc=f'Epoch {epoch + 1}/{Epoch}', postfix=dict, mininterval=0.3)

    model_train.eval()
    for iteration, batch in enumerate(gen_val):
        if iteration >= epoch_step_val:
            break
        vi_imgs, ir_imgs, pngs, labels = batch
        with torch.no_grad():
            weights = torch.from_numpy(cls_weights)
            if cuda:
                vi_imgs = vi_imgs.cuda(0)
                ir_imgs = ir_imgs.cuda(0)
                pngs = pngs.cuda(0)
                labels = labels.cuda(0)
                weights = weights.cuda(0)
            outputs = model_train(vi_imgs, ir_imgs)
            loss = CE_Loss(outputs, pngs, weights, num_classes=num_classes)
            main_dice = Dice_loss(outputs, labels)
            loss = loss + main_dice
            _f_score = f_score(outputs, labels)
            val_loss += loss.item()
            val_f_score += _f_score.item()
        pbar.set_postfix(**{'val_loss': val_loss / (iteration + 1),
                                'f_score': val_f_score / (iteration + 1),
                                'lr': get_lr(optimizer)})
        pbar.update(1)

    pbar.close()
    print('Finish Validation')
    loss_history.append_loss(epoch + 1, total_loss / epoch_step, val_loss / epoch_step_val)
    eval_callback.on_epoch_end(epoch + 1, model_train)
    print('Epoch:' + str(epoch + 1) + '/' + str(Epoch))
    print('Total Loss: %.3f || Val Loss: %.3f ' % (total_loss / epoch_step, val_loss / epoch_step_val))
    if (epoch + 1) % save_period == 0 or epoch + 1 == Epoch:
            torch.save(model.state_dict(), os.path.join(save_dir, 'ep%03d-loss%.3f-val_loss%.3f.pth' % (
            (epoch + 1), total_loss / epoch_step, val_loss / epoch_step_val)))

    if len(loss_history.val_loss) <= 1 or (val_loss / epoch_step_val) <= min(loss_history.val_loss):
            print('Save best model to best_epoch_weights.pth')
            torch.save(model.state_dict(), os.path.join(save_dir, "best_epoch_weights.pth"))

    torch.save(model.state_dict(), os.path.join(save_dir, "last_epoch_weights.pth"))

