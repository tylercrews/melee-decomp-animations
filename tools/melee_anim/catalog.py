"""Join verified actions to every real selectable costume and paired member.

The output is a job inventory, not a claim that all renderers/runtime features
are implemented. Zelda and Sheik are separate records. Filenames are not used
to deduplicate costume jobs, and shared motion sources retain actor identity.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


# Display names in CharacterKind order, verified in src/melee/ft/forward.h.
CHARACTERS = (
    ("captain-falcon", "Captain Falcon"), ("donkey-kong", "Donkey Kong"),
    ("fox", "Fox"), ("game-and-watch", "Mr. Game & Watch"),
    ("kirby", "Kirby"), ("bowser", "Bowser"), ("link", "Link"),
    ("luigi", "Luigi"), ("mario", "Mario"), ("marth", "Marth"),
    ("mewtwo", "Mewtwo"), ("ness", "Ness"), ("peach", "Peach"),
    ("pikachu", "Pikachu"), ("ice-climbers", "Ice Climbers"),
    ("jigglypuff", "Jigglypuff"), ("samus", "Samus"), ("yoshi", "Yoshi"),
    ("zelda", "Zelda"), ("sheik", "Sheik"), ("falco", "Falco"),
    ("young-link", "Young Link"), ("dr-mario", "Dr. Mario"),
    ("roy", "Roy"), ("pichu", "Pichu"), ("ganondorf", "Ganondorf"),
)

# External CharacterKind 26..31; keep the selectable roster above unchanged.
EXTRA_CHARACTERS = (("master-hand", "Master Hand"), ("male-wireframe", "Male Wireframe"),
                    ("female-wireframe", "Female Wireframe"), ("giga-bowser", "Giga Bowser"),
                    ("crazy-hand", "Crazy Hand"), ("sandbag", "Sandbag"))
ALL_CHARACTERS = CHARACTERS + EXTRA_CHARACTERS


def build_catalog(models, motions):
    costumes = models["costume_catalog"]
    results = {t["fighter_kind"]: t for t in motions["results"]}
    taunts = {t["fighter_kind"]: t for t in motions["taunts"]}
    entries = []
    job_count = 0
    for primary in costumes["fighters"]:
        if primary["paired_member"]:
            continue
        ckind = primary["character_kind"]
        slug, name = CHARACTERS[ckind]
        companions = [f for f in costumes["fighters"]
                      if f["character_kind"] == ckind and f["paired_member"]]
        actions = []
        for action, animation_id in (("results-clap", 9), ("victory1", 0),
                                     ("victory2", 2), ("victory3", 5)):
            sections = [("source", animation_id)]
            if action.startswith("victory"):
                sections.append(("wait", animation_id + 1))
            for section, aid in sections:
                actors = []
                for fighter in [primary, *companions]:
                    result = results[fighter["fighter_kind"]]
                    clip = result["motions"][aid]
                    if not clip["size"]:
                        raise ValueError(f"{name} {action}/{section}: missing results motion")
                    actors.append({"fighter_kind": fighter["fighter_kind"],
                                   "paired_member": fighter["paired_member"],
                                   "animation_id": aid, "clip": clip,
                                   "archive": result["results_archive"],
                                   "container_public": result["motion_file_symbol"],
                                   "container_offset": result["motion_file_data_offset"]})
                actions.append({"action": action, "section": section,
                                "actors": actors, "automatic_game_transition_verified": False})
        for facing in ("right", "left"):
            actors = []
            for fighter in [primary, *companions]:
                table = taunts[fighter["fighter_kind"]]
                chosen = table["standard_facing"][facing]
                clip = next(c for c in table["clips"]
                            if c["animation_id"] == chosen["animation_id"]
                            and c["source_fighter_kind"] == chosen["source_fighter_kind"])
                actors.append({"fighter_kind": fighter["fighter_kind"],
                               "paired_member": fighter["paired_member"],
                               **chosen, "clip": clip,
                               "runtime_notes": table.get("runtime_notes", [])})
            actions.append({"action": "taunt", "facing": facing, "actors": actors})
        specials = taunts[primary["fighter_kind"]]["special_sequences"]
        for special in specials:
            actions.append({"action": "stage-taunt", **special,
                            "runtime_capture_required_for_scene_behavior": True})
        jobs = []
        for costume in primary["costumes"]:
            members = [{"fighter_kind": primary["fighter_kind"], **costume}]
            for companion in companions:
                match = next(c for c in companion["costumes"] if c["costume_id"] == costume["costume_id"])
                members.append({"fighter_kind": companion["fighter_kind"], **match})
            for action_index, action in enumerate(actions):
                jobs.append({"job_id": f"{slug}/costume-{costume['costume_id']:02d}/"
                                       f"{action['action']}/{action.get('section', action.get('facing', 'source'))}",
                             "costume_id": costume["costume_id"], "model_members": members,
                             "action_index": action_index,
                             "render_status": "pilot available" if slug == "mario" else "catalog verified; renderer pending"})
        job_count += len(jobs)
        entries.append({"character_kind": ckind, "character": name, "slug": slug,
                        "costume_count": primary["costume_count"], "actions": actions, "jobs": jobs})
    assert len(entries) == 26
    assert len({job["job_id"] for e in entries for job in e["jobs"]}) == job_count
    return {"schema": "melee_anim.action_catalog.v1",
            "evidence": "verified DOL mappings, extracted clip tables, costume model roots",
            "selectable_forms": len(entries), "selectable_costumes": sum(e["costume_count"] for e in entries),
            "job_count_including_wait_sections_and_facing": job_count,
            "stage_taunts": "Fox/Falco optional Corneria/Venom radio sequences; not ordinary taunts",
            "characters": entries}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, default=Path("build/melee_anim/models.json"))
    parser.add_argument("--motions", type=Path, default=Path("build/melee_anim/motions.json"))
    parser.add_argument("--output", type=Path, default=Path("build/melee_anim/action_catalog.json"))
    args = parser.parse_args()
    report = build_catalog(json.loads(args.models.read_text()), json.loads(args.motions.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(f"Catalog: {report['selectable_forms']} forms, {report['selectable_costumes']} costumes, "
          f"{report['job_count_including_wait_sections_and_facing']} action/costume jobs. {args.output}")


if __name__ == "__main__":
    main()
