def compute_metrics(predicted, gold):

    tp = 0
    fp = 0
    fn = 0

    for key in gold.keys():

        gold_set = set(gold[key])
        pred_set = set(predicted.get(key, []))

        tp += len(gold_set & pred_set)
        fp += len(pred_set - gold_set)
        fn += len(gold_set - pred_set)

    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0

    if precision + recall == 0:
        f1 = 0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1
    }
