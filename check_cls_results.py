"""Read all completed classification validation reports."""
import json, os, sys
sys.path.insert(0, "python")

endpoints = [
    "bee_acute_oral_ld50",
    "bee_acute_contact_ld50", 
    "fish_acute_lc50",
    "algae_growth_ec50",
    "bird_acute_oral_ld50"
]

print(f"{'Endpoint':<25} {'BA':>6} {'AUC':>6} {'F1':>6} {'ECE':>6} {'Cov':>6} {'SetSz':>6} {'Train':>6} {'Test':>5}")
print("-" * 100)

for ep in endpoints:
    rpt = f"data/checkpoints/{ep}/v1.0_cls/validation_report.json"
    if os.path.exists(rpt):
        d = json.load(open(rpt))
        o = d["overall"]
        ba = o["balanced_accuracy"]
        auc = o.get("auc_roc") or 0.0
        f1 = o["f1"]
        ece = o["ece"]
        cov = d["conformal_coverage"]
        ss = d["mean_set_size"]
        tr = d["train_samples"]
        te = d["test_samples"]
        print(f"{ep:<25} {ba:>6.3f} {auc:>6.3f} {f1:>6.3f} {ece:>6.3f} {cov:>6.3f} {ss:>6.2f} {tr:>6} {te:>5}")
    else:
        print(f"{ep:<25} -- not trained yet --")
