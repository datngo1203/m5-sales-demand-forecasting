"""V3 fixed candidates and validation-only selection; no test-based tuning."""
import numpy as np
import forecast_v2 as v2

CANDIDATES = ("weekday_mean4", "blend", "rf_calibrated", "random_forest")


def estimate_k(actual, rf):
    """actual: folds/items/h; rf: folds/seeds/items/h. Validation only."""
    total = float(np.sum(actual))
    result = []
    for s in range(rf.shape[1]):
        predicted = float(np.sum(rf[:, s]))
        if predicted == 0 and total > 0:
            raise ValueError("Cannot calibrate zero forecasts against positive actual")
        result.append(total / predicted if predicted else 1.)
    return result


def candidates(rf, baseline4, ks):
    # These axes work for both validation [fold,seed,item,h] and test [seed,item,h].
    seed_axis = rf.ndim - 3
    shape = [1] * rf.ndim
    shape[seed_axis] = len(ks)
    return {"random_forest": rf, "weekday_mean4": baseline4,
            "blend": .5*rf + .5*baseline4,
            "rf_calibrated": rf*np.asarray(ks).reshape(shape)}


def validation(data, ks=None):
    actual, rf = data["actual"], data["random_forest"]
    ks = estimate_k(actual, rf) if ks is None else ks
    forecasts = candidates(rf, data["weekday_mean4"], ks)
    forecasts["seasonal_naive"] = data["seasonal_naive"]
    origin_rows, summaries = [], {}
    for model, pred in forecasts.items():
        for fold in range(13):
            for s, seed in enumerate(v2.SEEDS):
                origin_rows.append({"fold":fold,"group":fold%4,"seed":seed,"model":model,
                    **v2.metrics(actual[fold],pred[fold,s],data["known"][fold],data["seasonal_naive"][fold,s])})
        seed_metrics=[]
        for s in range(3):
            score=v2.v1.scores(actual,pred[:,s])
            scale=np.maximum(data["known"].mean(axis=2),1.)
            sn=float(np.sum(data["seasonal_naive"][:,s])-np.sum(actual))
            score.update(B_SN=sn,delta_bias=score["bias_units"]-sn,
                normalized_rmse=float(np.sqrt(np.mean(((pred[:,s]-actual)/scale[:,:,None])**2))))
            seed_metrics.append(score)
        median, groups=v2.group_score(origin_rows,model)
        summaries[model]={"score":median,"groups":groups,
            "metrics":{k:float(np.mean([m[k] for m in seed_metrics])) if seed_metrics[0][k] is not None else None
                       for k in seed_metrics[0]},"seed_metrics":seed_metrics}
    return ks, forecasts, origin_rows, summaries


def select(summaries):
    """Exactly four development sets; no test inputs accepted."""
    if len(summaries)!=4:
        raise ValueError("Require CA_1/CA_2 x recent/legacy")
    rf_bias=float(np.mean([abs(s["random_forest"]["metrics"]["bias_pct"]) for s in summaries]))
    candidates_info={}
    for model in CANDIDATES:
        ratios=[]
        for s in summaries:
            ref, value=s["random_forest"]["score"],s[model]["score"]
            ratios.append(value/ref if ref else (1. if value==0 else float("inf")))
        bias=float(np.mean([abs(s[model]["metrics"]["bias_pct"]) for s in summaries]))
        candidates_info[model]={"score":float(np.mean(ratios)),"mean_abs_bias_pct":bias,
                                "eligible":bool(bias<=rf_bias+1e-12)}
    eligible=[m for m in CANDIDATES if candidates_info[m]["eligible"]]
    best=min(candidates_info[m]["score"] for m in eligible)
    choice=next(m for m in CANDIDATES if m in eligible and candidates_info[m]["score"]<=best+1e-12)
    return {"choice":choice,"rf_mean_abs_bias_pct":rf_bias,"candidates":candidates_info}


def integration_gate(rows, choice, stores):
    decisions={}
    for store in stores:
        passed=True
        details={}
        for panel in ("recent","legacy"):
            rf=next(r for r in rows if r["store"]==store and r["panel"]==panel and r["model"]=="random_forest")
            chosen=next(r for r in rows if r["store"]==store and r["panel"]==panel and r["model"]==choice)
            ok=chosen["mae"]<=rf["mae"]+1e-12 and abs(chosen["bias_pct"])<=abs(rf["bias_pct"])+1e-12
            details[panel]=bool(ok)
            passed=passed and ok
        decisions[store]={"passed":bool(passed),"panels":details}
    count=sum(x["passed"] for x in decisions.values())
    return {"stores":decisions,"passed_stores":count,"required":2,"integrate":count>=2}
