from typing import Optional

from model import *
from evaluator import PlanScore

def pretty_print_plan(plan: Plan, camp_info: CampInfo, score: Optional[PlanScore] = None):
    if score:
        print(f"Plan penalty: {score.total_penalty()}")
        print(f"Total collisions: {score.collisions()}")
        print(f"Total empty blocks: {score.empty_blocks}")

        for user_id, empty_blocks in score.user_empty_blocks.items():
            if empty_blocks > 0 and camp_info.users[user_id].is_participant():
                print(f"Empty blocks for {camp_info.users[user_id].name} [{user_id}]: {empty_blocks}")

        print()

    for block_id, workshop_ids in plan.items():
        block = camp_info.blocks[block_id]
        print(f"Blok {block_id} ({block.name}, {block.start} to {block.end}):")
        for wid in workshop_ids:
            workshop = camp_info.workshops[wid]
            lecturer_names = ", ".join(camp_info.user_names[lecturer_id] for lecturer_id in workshop.lecturers)
            collisions = score.workshop_collisions.get(wid, 0) if score else 0
            collisions_str = f" | Collisions: {collisions}" if score else ""
            print(f"  {workshop.name} ({lecturer_names}) | Participants: {len(workshop.all_participants())} {collisions_str}")

    print()
    for user_id, user in camp_info.users.items():
        empty_blocks = score.user_empty_blocks[user_id]
        if empty_blocks != 0:
            print(f"{user.name} ({user_id}) has {empty_blocks} extra empty blocks.")

def print_old_format(plan: Plan):
    blocks = []
    for block_id, workshop_ids in sorted(plan.items(), key=lambda x: x[0]):
        blocks.append(workshop_ids)
    print(blocks)