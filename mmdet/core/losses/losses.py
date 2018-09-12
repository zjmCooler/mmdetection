# TODO merge naive and weighted loss to one function.
import torch
import torch.nn.functional as F

from ..bbox_ops import bbox_transform_inv, bbox_overlaps


def weighted_nll_loss(pred, label, weight, ave_factor=None):
    if ave_factor is None:
        ave_factor = max(torch.sum(weight > 0).float().item(), 1.)
    raw = F.nll_loss(pred, label, size_average=False, reduce=False)
    return torch.sum(raw * weight)[None] / ave_factor


def weighted_cross_entropy(pred, label, weight, ave_factor=None):
    if ave_factor is None:
        ave_factor = max(torch.sum(weight > 0).float().item(), 1.)
    raw = F.cross_entropy(pred, label, size_average=False, reduce=False)
    return torch.sum(raw * weight)[None] / ave_factor


def weighted_binary_cross_entropy(pred, label, weight, ave_factor=None):
    if ave_factor is None:
        ave_factor = max(torch.sum(weight > 0).float().item(), 1.)
    return F.binary_cross_entropy_with_logits(
        pred, label.float(), weight.float(),
        size_average=False)[None] / ave_factor


def sigmoid_focal_loss(pred,
                       target,
                       weight,
                       gamma=2.0,
                       alpha=0.25,
                       size_average=True):
    pred_sigmoid = pred.sigmoid()
    pt = (1 - pred_sigmoid) * target + pred_sigmoid * (1 - target)
    weight = (alpha * target + (1 - alpha) * (1 - target)) * weight
    weight = weight * pt.pow(gamma)
    return F.binary_cross_entropy_with_logits(
        pred, target, weight, size_average=size_average)


def weighted_sigmoid_focal_loss(pred,
                                target,
                                weight,
                                gamma=2.0,
                                alpha=0.25,
                                ave_factor=None,
                                num_classes=80):
    if ave_factor is None:
        ave_factor = torch.sum(weight > 0).float().item() / num_classes + 1e-6
    return sigmoid_focal_loss(
        pred, target, weight, gamma=gamma, alpha=alpha,
        size_average=False)[None] / ave_factor


def mask_cross_entropy(pred, target, label):
    num_rois = pred.size()[0]
    inds = torch.arange(0, num_rois, dtype=torch.long, device=pred.device)
    pred_slice = pred[inds, label].squeeze(1)
    return F.binary_cross_entropy_with_logits(
        pred_slice, target, size_average=True)[None]


def weighted_mask_cross_entropy(pred, target, weight, label):
    num_rois = pred.size()[0]
    num_samples = torch.sum(weight > 0).float().item() + 1e-6
    assert num_samples >= 1
    inds = torch.arange(0, num_rois).long().cuda()
    pred_slice = pred[inds, label].squeeze(1)
    return F.binary_cross_entropy_with_logits(
        pred_slice, target, weight, size_average=False)[None] / num_samples


def smooth_l1_loss(pred, target, beta=1.0, size_average=True, reduce=True):
    assert beta > 0
    assert pred.size() == target.size() and target.numel() > 0
    diff = torch.abs(pred - target)
    loss = torch.where(diff < beta, 0.5 * diff * diff / beta,
                       diff - 0.5 * beta)
    if size_average:
        loss /= pred.numel()
    if reduce:
        loss = loss.sum()
    return loss


def weighted_smoothl1(pred, target, weight, beta=1.0, ave_factor=None):
    if ave_factor is None:
        ave_factor = torch.sum(weight > 0).float().item() / 4 + 1e-6
    loss = smooth_l1_loss(pred, target, beta, size_average=False, reduce=False)
    return torch.sum(loss * weight)[None] / ave_factor


def accuracy(pred, target, topk=1):
    if isinstance(topk, int):
        topk = (topk, )
        return_single = True

    maxk = max(topk)
    _, pred_label = pred.topk(maxk, 1, True, True)
    pred_label = pred_label.t()
    correct = pred_label.eq(target.view(1, -1).expand_as(pred_label))

    res = []
    for k in topk:
        correct_k = correct[:k].view(-1).float().sum(0, keepdim=True)
        res.append(correct_k.mul_(100.0 / pred.size(0)))
    return res[0] if return_single else res