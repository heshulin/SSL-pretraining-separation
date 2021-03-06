import torch
from torch import nn
from asteroid.losses import PITLossWrapper, pairwise_neg_sisdr
from asteroid import ConvTasNet


class MultiTaskLossWrapper(PITLossWrapper):
    """ n_src separation + 1_src enhancement
    """
    def __init__(self, loss_func, pit_from="pw_mtx", perm_reduce=None):
        super().__init__(loss_func, pit_from=pit_from, perm_reduce=perm_reduce)

    def forward(self, est_targets, targets, **kwargs):
        n_src = targets.shape[1]
        if n_src == 1:
            est_targets = est_targets[:, -1].reshape(est_targets.size(0), 1, est_targets.size(2))
            return super().forward(est_targets, targets, **kwargs)
        else:
            assert est_targets.shape[1] == n_src + 1
            est_targets = est_targets[:, :-1]
            return super().forward(est_targets, targets, **kwargs)


class MultiTaskBatchSampler(torch.utils.data.BatchSampler):

    def __init__(self, sampler, batch_size, drop_last, cum_thresholds):
        super().__init__(sampler, batch_size, drop_last)
        self.thresholds = cum_thresholds
        self.thres_ranges = list(zip(self.thresholds, self.thresholds[1:]))

    def __iter__(self):
        batches = [[] for _ in self.thres_ranges]
        for idx in self.sampler:
            for range_idx, (st, ed) in enumerate(self.thres_ranges):
                if st <= idx < ed:
                    batches[range_idx].append(idx)
                    if len(batches[range_idx]) == self.batch_size:
                        yield batches[range_idx]
                        batches[range_idx] = []
        for range_idx in range(len(self.thres_ranges)):
            if len(batches[range_idx]) > 0 and not self.drop_last:
                yield batches[range_idx]


def MultiTaskDataLoader(data_sources, shuffle, batch_size, drop_last, generator=None, **kwargs):
    dataset = torch.utils.data.ConcatDataset(data_sources)
    cum_thresholds = [0]
    for data_source in data_sources:
        cum_thresholds.append(cum_thresholds[-1] + len(data_source))
    if shuffle:
        sampler = torch.utils.data.RandomSampler(dataset, generator=generator)
    else:
        sampler = torch.utils.data.SequentialSampler(dataset)
    batch_sampler = MultiTaskBatchSampler(sampler, batch_size=batch_size, drop_last=drop_last, cum_thresholds=cum_thresholds)
    return torch.utils.data.DataLoader(dataset, batch_sampler=batch_sampler, **kwargs)
