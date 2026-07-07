from abc import ABC, abstractmethod

from model import *

class Condition:
    @abstractmethod
    def check(self, plan: Plan) -> bool:
        pass

class EmptyBlockCondition(Condition):
    '''
    There should be no blocks with zero workshops.
    '''
    def check(self, plan: Plan):
        return all(
            len(workshop_ids) > 0 for workshop_ids in plan.values()
        )

class LecturerAttendanceCondition(Condition):
    '''
    All lecturers must be present for their workshop.
    '''
    def __init__(self, camp_info: CampInfo):
        self.camp_info = camp_info

    def check(self, plan: Plan) -> bool:
        return all(self.lecturers_present_during_workshops(block_id, workshop_ids) for block_id, workshop_ids in plan.items())
        
    def lecturers_present_during_workshops(self, block_id, workshop_ids): 
        return all(
            self.lecturers_present_during_block(block_id, workshop_id)
            for workshop_id in workshop_ids
        )

    def lecturers_present_during_block(self, block_id: BlockId, workshop_id: WorkshopId) -> bool:
        workshop = self.camp_info.workshops[workshop_id]
        return all(self.camp_info.user_present_during_block(lecturer_id, block_id) for lecturer_id in workshop.lecturers)


class LecturerCollisionCondition(Condition):
    '''
    Lecturers cannot have more than one workshop in the same block.
    '''
    def __init__(self, camp_info: CampInfo):
        self.camp_info = camp_info

    def check(self, plan: Plan) -> bool:
        return all(self.lecturers_have_no_collisions(workshop_ids) for workshop_ids in plan.values())

    def lecturers_have_no_collisions(self, workshop_ids: List[WorkshopId]):
        lecturers_with_workshops = set()
        for workshop_id in workshop_ids:
            workshop = self.camp_info.workshops[workshop_id]
            for lecturer_id in workshop.lecturers:
                if lecturer_id in lecturers_with_workshops:
                    return False
                else:
                    lecturers_with_workshops.add(lecturer_id)
        return True

class WorkshopDependencyCondition(Condition):
    '''
    If one workshop depends on another they should be during different dates.
    '''
    def __init__(self):
        pass

class Validator:
    '''
    Validator checks plan against hard constraints that cannot be violated:
    - there are no empty blocks
    - lecturers have at most one workshop in each block
    - lecturers are present during their workshop
    '''
    def __init__(self, camp_info: CampInfo):
        self.conditions = [
            EmptyBlockCondition(),
            LecturerAttendanceCondition(camp_info),
            LecturerCollisionCondition(camp_info)
        ]

    def is_plan_valid(self, plan: Plan) -> bool:
        return all(condition.check(plan) for condition in self.conditions)



