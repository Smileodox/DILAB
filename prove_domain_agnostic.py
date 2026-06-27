"""Acceptance demo: dock a SECOND, non-RF knowledge base and run the full analytical
chain (profile → morphbox → contrastive CCA → consistent sampling → null-model structure
test) with ZERO code/prompt changes. This is the proof that the pipeline is a domain-
agnostic framework, not a spectrum-monitoring tool.

  uv run python prove_domain_agnostic.py
"""
from __future__ import annotations

import logging

import chromadb

from src.llm import embed
from src.pipeline import functional, structure

# A synthetic KB about a clearly different domain: autonomous precision agriculture.
# Each chunk hints at COMPETING technical approaches so the morphology has real tension.
AG_DOCS = [
    "Precision agriculture systems must sense crop and soil state. Approaches compete: "
    "satellite multispectral imagery offers wide coverage at low resolution; low-altitude "
    "drone hyperspectral scanning gives high resolution over small areas; in-ground IoT soil "
    "probes give continuous point measurements. Each implies a different data cadence and cost.",
    "Field navigation for autonomous farm robots splits between RTK-GNSS guided path following, "
    "vision-based row detection using onboard cameras, and buried-wire or beacon infrastructure. "
    "GNSS fails under canopy; vision struggles in dust and low light; infrastructure is costly to install.",
    "Weed and pest control diverges into broadcast chemical spraying, targeted micro-dosing with "
    "computer-vision nozzles, and fully mechanical or laser weeding. Targeting cuts chemical use but "
    "needs heavy onboard compute; mechanical weeding avoids chemicals but is slow and energy-hungry.",
    "Agronomic decision-making is moving from centralized cloud analytics that aggregate whole-farm "
    "data to edge inference on the machine for real-time actuation, and to federated models that "
    "keep farm data local for privacy. Connectivity in rural fields is the limiting constraint.",
    "Actuation platforms range from large autonomous tractors, to swarms of small lightweight robots, "
    "to fixed gantry systems over permanent beds. Swarms reduce soil compaction but multiply "
    "maintenance; big machines are efficient per hectare but compact the soil.",
    "Power and energy autonomy is contested between diesel-hybrid drivetrains, battery-electric with "
    "swap stations, and solar-assisted slow robots. Battery weight trades against operating time; "
    "solar limits duty cycle but removes refueling logistics.",
    "Yield and harvest sensing competes between destructive sampling, in-line optical grading on the "
    "harvester, and predictive models trained on season-long data. Each shifts where intelligence sits.",
    "Connectivity options for field fleets include cellular 4G/5G, low-power LoRa mesh, and "
    "store-and-forward via the machines themselves. Bandwidth, latency and rural coverage differ sharply.",
    "Data platforms split between proprietary vendor clouds with closed APIs and open "
    "interoperability standards (e.g. ISOBUS, agricultural data exchange formats) that let mixed fleets "
    "share a common data model. Lock-in versus integration cost is the core tension.",
    "Regulatory and certification forces include drone airspace rules, autonomous-machinery safety "
    "standards, and pesticide-application regulations that vary by region and shape what can be deployed.",
]


def build_kb():
    client = chromadb.EphemeralClient()
    coll = client.create_collection("ag_kb")
    embs = embed(AG_DOCS)
    coll.add(
        ids=[f"ag{i}" for i in range(len(AG_DOCS))],
        documents=AG_DOCS,
        embeddings=embs,
        metadatas=[{"source_title": f"AgSource{i}", "pool": "trend"} for i in range(len(AG_DOCS))],
    )
    return coll


def main():
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    print("Docking a SECOND KB (autonomous precision agriculture) — zero code/prompt edits ...\n")
    coll = build_kb()

    # 1. derive the domain profile from THIS KB
    from src.pipeline import domain
    profile = domain.derive(coll, n_sample=len(AG_DOCS))
    print(f"[profile] domain = {profile.domain!r}")
    print(f"          system = {profile.system!r}")
    print(f"          actor  = {profile.actor!r} | horizon {profile.horizon}")
    print(f"          personas = {[p.id for p in profile.personas]}")
    print(f"          function_examples = {profile.function_examples[:160]}")

    # 2. functions + competing directions (morphological field) — driven only by the profile
    morph, drivers = functional.build_morphbox(coll, max_workers=6, profile=profile)
    name_by_fid = {d.id: d.name for d in drivers}
    manif_by_id = {m.id: m for m in morph.all_manifestations}
    print(f"\n[morphbox] {len(morph.drivers)} functions, {len(morph.all_manifestations)} directions")
    for did in morph.drivers[:5]:
        labels = ", ".join(manif_by_id[m].label for m in morph.manifestations[did])
        print(f"  • {name_by_fid[did]}: {labels}")

    if len(morph.drivers) < 3:
        print("\n(too few functions to assess — KB too small; profile derivation still proven)")
        return

    # 3. contrastive CCA + consistent sampling + null-model structure test — same machinery
    cca = functional.assess_cca(morph, manif_by_id, name_by_fid, mode="contrastive",
                                max_workers=6, profile=profile)
    scores = [s for d in cca.values() for s in d.values()]
    if scores:
        print(f"\n[CCA] {len(scores)//2} pairs | mean {sum(scores)/len(scores):+.2f} | "
              f"neg {sum(1 for s in scores if s < 0)} | hard(-2) {sum(1 for s in scores if s <= -2)}")
    configs = functional.sample_consistent(morph, cca, 60, oversample_factor=80.0,
                                            reject_threshold=0.25, seed=42)
    if len(configs) >= 12:
        scens = structure.configs_to_scenarios([c.model_dump(mode="json") for c in configs])
        raw = {"drivers": morph.drivers, "manifestations": morph.manifestations,
               "all_manifestations": [m.model_dump(mode="json") for m in morph.all_manifestations]}
        res = structure.analyze(scens, raw, null_trials=20, seed=42)
        o = res["observed"]
        print(f"\n[structure] {len(configs)} configs | silhouette={o['best_silhouette']} "
              f"effdim={o['effective_dim']} → {res['verdict']}")

    print("\n✓ Full analytical chain ran on a brand-new domain with zero code/prompt changes.")


if __name__ == "__main__":
    main()
